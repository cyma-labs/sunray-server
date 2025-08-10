# -*- coding: utf-8 -*-
from odoo import models, fields, api
from datetime import datetime, timedelta
import json


class SunraySetupToken(models.Model):
    _name = 'sunray.setup.token'
    _description = 'Setup Token'
    _rec_name = 'device_name'
    _order = 'create_date desc'
    
    user_id = fields.Many2one(
        'sunray.user', 
        required=True, 
        ondelete='cascade',
        string='User'
    )
    token_hash = fields.Char(
        string='Token Hash (SHA-512)', 
        required=True,
        help='SHA-512 hash of the setup token'
    )
    device_name = fields.Char(
        string='Device Name',
        help='Intended device for this token'
    )
    expires_at = fields.Datetime(
        string='Expiration', 
        required=True,
        help='Token expiration timestamp'
    )
    consumed = fields.Boolean(
        default=False,
        string='Consumed',
        help='Whether token has been used'
    )
    consumed_date = fields.Datetime(
        string='Consumed Date',
        help='When the token was consumed'
    )
    
    # Constraints
    allowed_ips = fields.Text(
        string='Allowed IPs (JSON)', 
        default='[]',
        help='List of IP addresses allowed to use this token'
    )
    max_uses = fields.Integer(
        default=1,
        string='Max Uses',
        help='Maximum number of times this token can be used'
    )
    current_uses = fields.Integer(
        default=0,
        string='Current Uses',
        help='Number of times this token has been used'
    )
    
    # Note: create_uid automatically tracks who generated the token
    
    @api.model
    def cleanup_expired(self):
        """Cron job to clean expired tokens"""
        expired_objs = self.search([
            ('expires_at', '<', fields.Datetime.now()),
            ('consumed', '=', False)
        ])
        
        # Log cleanup
        if expired_objs:
            self.env['sunray.audit.log'].create({
                'event_type': 'token.cleanup',
                'details': json.dumps({
                    'count': len(expired_objs),
                    'tokens': expired_objs.mapped('id')
                })
            })
        
        expired_objs.unlink()
        return True
    
    def get_allowed_ips(self):
        """Parse and return allowed IPs list"""
        try:
            return json.loads(self.allowed_ips or '[]')
        except (json.JSONDecodeError, TypeError):
            return []