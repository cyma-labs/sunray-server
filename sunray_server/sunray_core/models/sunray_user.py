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
        """Trigger immediate cache refresh for this user via Worker API"""
        for record in self:
            try:
                # Call worker's cache invalidation endpoint
                self._call_worker_cache_invalidate(
                    scope='user',
                    target=record.username,
                    reason=f'Manual refresh by {self.env.user.name}'
                )
                
                # Log the action
                self.env['sunray.audit.log'].create({
                    'event_type': 'cache_invalidation',
                    'severity': 'info',
                    'user_id': record.id,
                    'username': record.username,
                    'details': f'Cache refresh triggered for user {record.username}'
                })
            except Exception as e:
                _logger.error(f"Failed to trigger cache refresh for user {record.username}: {str(e)}")
                raise UserError(f"Failed to trigger cache refresh: {str(e)}")
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Cache Refresh Triggered',
                'message': f'Worker caches will refresh for {len(self)} user(s) within 60 seconds',
                'type': 'warning',
            }
        }
    
    def _call_worker_cache_invalidate(self, scope, target=None, reason=''):
        """Call Worker API to trigger cache invalidation"""
        # Get configuration
        ICP = self.env['ir.config_parameter'].sudo()
        worker_url = ICP.get_param('sunray.worker_url')
        
        if not worker_url:
            # Try to get from environment or use a default
            worker_url = 'https://sunray-worker.oursbleu.workers.dev'
            _logger.warning(f"sunray.worker_url not configured, using default: {worker_url}")
        
        # Get API key
        api_key_obj = self.env['sunray.api.key'].sudo().search([
            ('is_active', '=', True)
        ], limit=1)
        
        if not api_key_obj:
            raise UserError('No active API key found for Worker communication')
        
        # Call the worker's invalidation endpoint
        url = f"{worker_url}/sunray-wrkr/v1/cache/invalidate"
        headers = {
            'Authorization': f'Bearer {api_key_obj.key}',
            'Content-Type': 'application/json'
        }
        payload = {
            'scope': scope,
            'target': target,
            'reason': reason
        }
        
        _logger.info(f"Calling Worker cache invalidation: {url} with scope={scope}, target={target}")
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=5)
            response.raise_for_status()
            result = response.json()
            _logger.info(f"Worker cache invalidation successful: {result}")
            return result
        except requests.exceptions.RequestException as e:
            _logger.error(f"Worker cache invalidation failed: {str(e)}")
            raise UserError(f"Failed to trigger cache refresh: {str(e)}")