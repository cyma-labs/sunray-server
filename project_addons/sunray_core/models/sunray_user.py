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
                    # Call worker's cache invalidation endpoint for this host
                    host_obj._call_worker_cache_invalidate(
                        scope='user',
                        target=record.username,
                        reason=f'Manual user refresh by {self.env.user.name}'
                    )
                    success_count += 1
                except Exception as e:
                    _logger.error(f"Failed to refresh cache for user {record.username} on host {host_obj.domain}: {str(e)}")
                    failed_hosts.append(f'{host_obj.domain}: {str(e)}')
            
            # Log the action
            self.env['sunray.audit.log'].create_admin_event(
                event_type='cache_invalidation',
                severity='info',
                details=f'Cache refresh triggered for user {record.username} on {success_count} host(s)',
                sunray_user_id=record.id,
                username=record.username,
                admin_user_id=self.env.user.id
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
    
    # Removed _call_worker_cache_invalidate method - now uses host's method