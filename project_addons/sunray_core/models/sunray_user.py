# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError
from datetime import timedelta
import requests
import logging

_logger = logging.getLogger(__name__)


class SunrayUser(models.Model):
    _name = 'sunray.user'
    _description = 'Sunray User'
    _rec_name = 'username'
    _order = 'username'
    
    username = fields.Char(
        string='Username', 
        required=True, 
        index=True,
        help='Unique username for authentication'
    )
    email = fields.Char(
        string='Email', 
        required=True,
        help='User email address for notifications'
    )

    is_active = fields.Boolean(
        string='Active', 
        default=True,
        help='Deactivate to temporarily disable user access'
    )
    
    # Relations
    passkey_ids = fields.One2many(
        'sunray.passkey', 
        'user_id', 
        string='Passkeys'
    )
    setup_token_ids = fields.One2many(
        'sunray.setup.token', 
        'user_id', 
        string='Setup Tokens'
    )
    host_ids = fields.Many2many(
        'sunray.host',
        'sunray_user_host_rel',
        'user_id',
        'host_id',
        string='Authorized Hosts'
    )
    session_ids = fields.One2many(
        'sunray.session',
        'user_id',
        string='Sessions'
    )
    
    # Computed fields
    passkey_count = fields.Integer(
        compute='_compute_passkey_count',
        string='Passkey Count',
        store=True
    )
    last_login = fields.Datetime(
        compute='_compute_last_login',
        string='Last Login'
    )
    active_session_count = fields.Integer(
        compute='_compute_active_session_count',
        string='Active Sessions'
    )
    
    # Workers that protect this user's hosts
    worker_ids = fields.Many2many(
        'sunray.worker',
        compute='_compute_worker_ids',
        string='Workers',
        help='Workers that protect hosts this user has access to'
    )
    
    # Version tracking for cache invalidation
    config_version = fields.Datetime(
        string='Configuration Version',
        default=fields.Datetime.now,
        help='Timestamp of last configuration change, used for cache invalidation'
    )
    
    _sql_constraints = [
        ('username_unique', 'UNIQUE(username)', 'Username must be unique!'),
        ('email_unique', 'UNIQUE(email)', 'Email must be unique!')
    ]
    
    @api.depends('passkey_ids')
    def _compute_passkey_count(self):
        for user in self:
            user.passkey_count = len(user.passkey_ids)
    
    @api.depends('session_ids.is_active', 'session_ids.created_at')
    def _compute_last_login(self):
        for user in self:
            active_sessions = user.session_ids.filtered('is_active').sorted('created_at', reverse=True)
            user.last_login = active_sessions[0].created_at if active_sessions else False
    
    @api.depends('session_ids.is_active')
    def _compute_active_session_count(self):
        for user in self:
            user.active_session_count = len(user.session_ids.filtered('is_active'))
    
    @api.depends('host_ids.sunray_worker_id')
    def _compute_worker_ids(self):
        for user in self:
            # Get unique workers from all hosts this user has access to
            workers = user.host_ids.mapped('sunray_worker_id').filtered('id')
            user.worker_ids = workers
    
    def write(self, vals):
        """Override to update config_version on any change"""
        # Don't update version if we're only updating the version itself
        if vals and not (len(vals) == 1 and 'config_version' in vals):
            vals['config_version'] = fields.Datetime.now()
        return super().write(vals)
    
    def generate_setup_token(self):
        """Open wizard to generate a new setup token"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Generate Setup Token',
            'res_model': 'sunray.setup.token.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_user_id': self.id,
            }
        }
    
    def revoke_all_sessions(self):
        """Revoke all active sessions for this user"""
        active_sessions = self.session_ids.filtered('is_active')
        for session in active_sessions:
            session.revoke('User requested revocation of all sessions')
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'title': 'Sessions Revoked',
                'message': f'{len(active_sessions)} session(s) have been revoked.',
                'sticky': False,
            }
        }
    
    def force_cache_refresh(self):
        """Trigger immediate cache refresh for this user on all allowed hosts"""
        for record in self:
            # Get all hosts this user has access to
            host_objs = record.host_ids
            
            if not host_objs:
                raise UserError(f"User {record.username} has no assigned hosts. "
                               "Assign the user to hosts first.")
            
            success_count = 0
            failed_hosts = []
            unbound_hosts = []
            
            for host_obj in host_objs:
                # Check if host is bound to a worker
                if not host_obj.sunray_worker_id:
                    unbound_hosts.append(host_obj.domain)
                    continue
                
                try:
                    # Call worker's cache clear endpoint for this host
                    host_obj._call_worker_cache_clear(
                        scope='user-protectedhost',
                        target={'username': record.username, 'hostname': host_obj.domain},
                        reason=f'Manual user refresh by {self.env.user.name}'
                    )
                    success_count += 1
                except Exception as e:
                    _logger.error(f"Failed to refresh cache for user {record.username} on host {host_obj.domain}: {str(e)}")
                    failed_hosts.append(f'{host_obj.domain}: {str(e)}')
            
            # Log the action
            self.env['sunray.audit.log'].create_audit_event(
                event_type='cache.cleared',
                severity='info',
                details={
                    'scope': 'user-protectedhost',
                    'username': record.username,
                    'hosts_count': success_count,
                    'operation': 'manual_user_cache_refresh',
                    'reason': f'Manual user cache refresh by {self.env.user.name}'
                },
                sunray_user_id=record.id,
                sunray_admin_user_id=self.env.user.id,
                username=record.username
            )
            
            # Handle errors and warnings
            if unbound_hosts and not success_count:
                raise UserError(f"Cannot refresh cache for user {record.username}. "
                               f"All hosts ({', '.join(unbound_hosts)}) are not yet bound to workers. "
                               "Worker binding happens automatically when workers first call the API.")
            elif failed_hosts and not success_count:
                raise UserError(f"Failed to refresh cache for user {record.username} on all hosts: "
                               f"{', '.join(failed_hosts)}")
        
        # Build result message
        message_parts = []
        if success_count:
            message_parts.append(f'Successfully refreshed {success_count} host(s)')
        if unbound_hosts:
            message_parts.append(f'{len(unbound_hosts)} host(s) not bound to workers: {', '.join(unbound_hosts)}')
        if failed_hosts:
            message_parts.append(f'{len(failed_hosts)} host(s) failed: {', '.join(failed_hosts)}')
        
        notification_type = 'success'
        if failed_hosts or unbound_hosts:
            notification_type = 'warning'
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Cache Refresh Results',
                'message': '. '.join(message_parts),
                'type': notification_type,
                'sticky': bool(failed_hosts),  # Stick error messages
            }
        }
    
    def action_revoke_sessions_on_worker(self, worker_id):
        """Revoke all sessions for this user on all hosts protected by a specific worker"""
        self.ensure_one()
        worker_obj = self.env['sunray.worker'].browse(worker_id)
        
        if not worker_obj.exists():
            raise UserError(f"Worker with ID {worker_id} not found")
        
        # Get user's active sessions on hosts protected by this worker
        affected_sessions = self.session_ids.filtered(
            lambda s: s.is_active and s.host_id.sunray_worker_id.id == worker_id
        )
        
        if not affected_sessions:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'No Active Sessions',
                    'message': f'User {self.username} has no active sessions on hosts protected by worker {worker_obj.name}.',
                    'type': 'info',
                }
            }
        
        try:
            # Use the first host to call the worker (all hosts share the same worker)
            first_host = affected_sessions[0].host_id
            first_host._call_worker_cache_clear(
                scope='user-worker',
                target={'username': self.username},
                reason=f'User sessions revoked on worker {worker_obj.name} by {self.env.user.name}'
            )
            
            # Mark local sessions as inactive
            affected_sessions.write({
                'is_active': False,
                'revoked': True,
                'revoked_at': fields.Datetime.now(),
                'revoked_reason': f'Bulk revocation - all sessions on worker {worker_obj.name}'
            })
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Sessions Revoked',
                    'message': f'Revoked {len(affected_sessions)} session(s) for user {self.username} on worker {worker_obj.name}.',
                    'type': 'success',
                }
            }
        except Exception as e:
            _logger.error(f"Failed to revoke sessions for user {self.username} on worker {worker_obj.name}: {str(e)}")
            raise UserError(f"Failed to revoke sessions on worker: {str(e)}")
    
    def action_revoke_sessions_on_host(self, host_id):
        """Revoke all sessions for this user on a specific host"""
        self.ensure_one()
        host_obj = self.env['sunray.host'].browse(host_id)
        
        if not host_obj.exists():
            raise UserError(f"Host with ID {host_id} not found")
        
        # Get user's active sessions on this specific host
        affected_sessions = self.session_ids.filtered(
            lambda s: s.is_active and s.host_id.id == host_id
        )
        
        if not affected_sessions:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'No Active Sessions',
                    'message': f'User {self.username} has no active sessions on host {host_obj.domain}.',
                    'type': 'info',
                }
            }
        
        try:
            # Call worker to clear user sessions on this specific host
            host_obj._call_worker_cache_clear(
                scope='user-protectedhost',
                target={'username': self.username, 'hostname': host_obj.domain},
                reason=f'User sessions revoked on host {host_obj.domain} by {self.env.user.name}'
            )
            
            # Mark local sessions as inactive
            affected_sessions.write({
                'is_active': False,
                'revoked': True,
                'revoked_at': fields.Datetime.now(),
                'revoked_reason': f'Bulk revocation - all sessions on host {host_obj.domain}'
            })
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Sessions Revoked',
                    'message': f'Revoked {len(affected_sessions)} session(s) for user {self.username} on host {host_obj.domain}.',
                    'type': 'success',
                }
            }
        except Exception as e:
            _logger.error(f"Failed to revoke sessions for user {self.username} on host {host_obj.domain}: {str(e)}")
            raise UserError(f"Failed to revoke sessions on host: {str(e)}")
    
    # Removed _call_worker_cache_invalidate method - now uses host's method