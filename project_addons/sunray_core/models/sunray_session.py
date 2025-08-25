# -*- coding: utf-8 -*-
from odoo import models, fields, api
import json


class SunraySession(models.Model):
    _name = 'sunray.session'
    _description = 'Active Session'
    _order = 'created_at desc'
    _rec_name = 'session_id'
    
    session_id = fields.Char(
        string='Session ID', 
        required=True, 
        index=True,
        help='Unique session identifier (UUID)'
    )
    user_id = fields.Many2one(
        'sunray.user', 
        required=True, 
        ondelete='cascade',
        string='User'
    )
    host_id = fields.Many2one(
        'sunray.host', 
        required=True,
        string='Host'
    )
    
    # Session metadata
    created_at = fields.Datetime(
        default=fields.Datetime.now, 
        required=True,
        string='Created At'
    )
    last_activity = fields.Datetime(
        default=fields.Datetime.now,
        string='Last Activity'
    )
    expires_at = fields.Datetime(
        required=True,
        string='Expires At'
    )
    
    # Security tracking
    created_ip = fields.Char(string='Created IP')
    last_ip = fields.Char(string='Last IP')
    device_fingerprint = fields.Char(
        string='Device Fingerprint',
        help='SHA-256 hash of device characteristics'
    )
    user_agent = fields.Text(string='User Agent')
    
    # Credential used
    passkey_id = fields.Many2one(
        'sunray.passkey',
        string='Passkey Used'
    )
    credential_id = fields.Char(string='Credential ID')
    
    # Session state
    is_active = fields.Boolean(
        string='Active', 
        default=True,
        help='Whether session is currently active'
    )
    revoked = fields.Boolean(
        string='Revoked', 
        default=False,
        help='Whether session was manually revoked'
    )
    revoked_at = fields.Datetime(string='Revoked At')
    revoked_reason = fields.Text(string='Revocation Reason')
    
    # CSRF token (for additional validation)
    csrf_token = fields.Char(
        string='CSRF Token',
        help='CSRF token for this session'
    )
    
    # Advanced features (if enabled)
    totp_verified = fields.Boolean(
        default=False,
        string='TOTP Verified'
    )
    totp_verified_at = fields.Datetime(string='TOTP Verified At')
    risk_score = fields.Float(string='Risk Score')
    
    _sql_constraints = [
        ('session_unique', 'UNIQUE(session_id)', 'Session ID must be unique!')
    ]
    
    @api.model
    def cleanup_expired(self):
        """Cron job to clean expired sessions"""
        expired_objs = self.search([
            ('expires_at', '<', fields.Datetime.now()),
            ('is_active', '=', True)
        ])
        
        # Mark as inactive rather than delete for audit trail
        expired_objs.write({'is_active': False})
        
        # Log cleanup
        if expired_objs:
            self.env['sunray.audit.log'].create_audit_event(
                event_type='session.expired',
                details={
                    'count': len(expired_objs),
                    'sessions': expired_objs.mapped('session_id')
                },
                event_source='system'
            )
        
        return True
    
    def revoke(self, reason='Manual revocation'):
        """Revoke this session"""
        self.write({
            'is_active': False,
            'revoked': True,
            'revoked_at': fields.Datetime.now(),
            'revoked_reason': reason
        })
        
        # Log revocation
        self.env['sunray.audit.log'].create_user_event(
            event_type='session.revoked',
            details={
                'session_id': self.session_id,
                'reason': reason
            },
            sunray_user_id=self.user_id.id,
            username=self.user_id.username  # Keep for compatibility
        )
        
        return True
    
    def update_activity(self, new_ip=None):
        """Update session last activity timestamp and optionally IP"""
        vals = {'last_activity': fields.Datetime.now()}
        if new_ip:
            vals['last_ip'] = new_ip
        self.write(vals)
        return True