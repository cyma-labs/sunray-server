# -*- coding: utf-8 -*-
from odoo import models, fields, api
from datetime import timedelta
import json


class SunrayAuditLog(models.Model):
    _name = 'sunray.audit.log'
    _description = 'Audit Log'
    _order = 'timestamp desc'
    _rec_name = 'event_type'
    
    # Using dedicated timestamp field for indexing and ordering performance
    timestamp = fields.Datetime(
        default=fields.Datetime.now, 
        index=True,
        required=True,
        string='Timestamp'
    )
    event_type = fields.Selection([
        ('auth.success', 'Authentication Success'),
        ('auth.failure', 'Authentication Failure'),
        ('token.generated', 'Token Generated'),
        ('token.consumed', 'Token Consumed'),
        ('token.cleanup', 'Token Cleanup'),
        ('passkey.registered', 'Passkey Registered'),
        ('passkey.revoked', 'Passkey Revoked'),
        ('config.fetched', 'Config Fetched'),
        ('session.created', 'Session Created'),
        ('session.revoked', 'Session Revoked'),
        ('session.expired', 'Session Expired'),
        ('webhook.used', 'Webhook Token Used'),
        ('webhook.regenerated', 'Webhook Token Regenerated'),
        ('api_key.regenerated', 'API Key Regenerated'),
        ('cache_invalidation', 'Cache Invalidation'),
        ('security.alert', 'Security Alert'),
        ('SESSION_FINGERPRINT_MISMATCH', 'Session Fingerprint Mismatch'),
        ('SESSION_IP_CHANGED', 'Session IP Changed'),
        ('SESSION_COUNTRY_CHANGED', 'Session Country Changed'),
        ('SESSION_VALIDATION_FAILED', 'Session Validation Failed'),
    ], required=True, string='Event Type')
    
    user_id = fields.Many2one(
        'res.users',
        string='User'
    )
    username = fields.Char(
        string='Username',
        help='Store even if user deleted'
    )  
    ip_address = fields.Char(string='IP Address')
    user_agent = fields.Text(string='User Agent')
    details = fields.Text(
        string='Details',
        help='JSON field for extra data'
    )
    
    # Severity for security events
    severity = fields.Selection([
        ('info', 'Info'),
        ('warning', 'Warning'),
        ('error', 'Error'),
        ('critical', 'Critical')
    ], default='info', string='Severity')
    
    @api.model
    def cleanup_old_logs(self):
        """Keep last 90 days of logs"""
        cutoff = fields.Datetime.now() - timedelta(days=90)
        old_log_objs = self.search([('timestamp', '<', cutoff)])
        
        # Log the cleanup itself
        if old_log_objs:
            self.create({
                'event_type': 'security.alert',
                'severity': 'info',
                'details': json.dumps({
                    'action': 'audit_log_cleanup',
                    'count': len(old_log_objs)
                })
            })
        
        old_log_objs.unlink()
        return True
    
    @api.model
    def create_security_event(self, event_type, details, severity='warning', user_id=None, ip_address=None):
        """Helper method to create security events"""
        return self.create({
            'event_type': event_type,
            'severity': severity,
            'details': json.dumps(details) if isinstance(details, dict) else details,
            'user_id': user_id,
            'ip_address': ip_address,
            'timestamp': fields.Datetime.now()
        })
    
    def get_details_dict(self):
        """Parse details JSON field"""
        self.ensure_one()
        if self.details:
            try:
                return json.loads(self.details)
            except (json.JSONDecodeError, TypeError):
                return {'raw': self.details}
        return {}