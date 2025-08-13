# -*- coding: utf-8 -*-
from odoo import models, fields, api
from datetime import timedelta


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