# -*- coding: utf-8 -*-
from odoo import models, fields, api
import json
import secrets
import string


class SunrayWebhookToken(models.Model):
    _name = 'sunray.webhook.token'
    _description = 'Webhook Authentication Token'
    _rec_name = 'name'
    _order = 'name'
    
    host_id = fields.Many2one(
        'sunray.host', 
        required=True, 
        ondelete='cascade',
        string='Host'
    )
    name = fields.Char(
        string='Token Name', 
        required=True,
        help='Descriptive name for this token'
    )
    token = fields.Char(
        string='Token Value', 
        required=True, 
        index=True,
        help='The actual token value'
    )
    is_active = fields.Boolean(
        string='Active', 
        default=True,
        help='Deactivate to temporarily disable token'
    )
    last_used = fields.Datetime(
        string='Last Used',
        help='Last time this token was used'
    )
    usage_count = fields.Integer(
        default=0,
        string='Usage Count',
        help='Number of times this token has been used'
    )
    
    # Optional restrictions
    allowed_ips = fields.Text(
        string='Allowed IPs (JSON)', 
        default='[]',
        help='List of IP addresses allowed to use this token'
    )
    expires_at = fields.Datetime(
        string='Expiration Date',
        help='Token expiration date (empty = never expires)'
    )
    
    _sql_constraints = [
        ('token_unique', 'UNIQUE(token)', 'Token must be unique!')
    ]
    
    def create(self, vals_list):
        """Override create to auto-generate token if not provided"""
        for vals in vals_list:
            if 'token' not in vals or not vals['token']:
                vals['token'] = self.generate_token()
        return super().create(vals_list)
    
    def generate_token(self):
        """Generate a secure random token"""
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(32))
    
    def regenerate_token(self):
        """Generate a new token value"""
        self.ensure_one()
        new_token = self.generate_token()
        
        # Log token regeneration
        self.env['sunray.audit.log'].create({
            'event_type': 'webhook.regenerated',
            'details': json.dumps({
                'token_name': self.name,
                'host': self.host_id.domain
            })
        })
        
        self.token = new_token
        return new_token
    
    def is_valid(self, client_ip=None):
        """Check if token is valid and authorized"""
        if not self.is_active:
            return False
        
        # Check expiration
        if self.expires_at and self.expires_at < fields.Datetime.now():
            return False
        
        # Check IP restrictions
        if client_ip and self.allowed_ips:
            try:
                allowed_ips = json.loads(self.allowed_ips or '[]')
                if allowed_ips and client_ip not in allowed_ips:
                    return False
            except (json.JSONDecodeError, TypeError):
                return False
        
        return True
    
    def track_usage(self, client_ip=None):
        """Update usage statistics"""
        self.write({
            'last_used': fields.Datetime.now(),
            'usage_count': self.usage_count + 1
        })
        
        # Log usage
        self.env['sunray.audit.log'].create({
            'event_type': 'webhook.used',
            'ip_address': client_ip,
            'details': json.dumps({
                'token_name': self.name,
                'host': self.host_id.domain
            })
        })
        
        return True