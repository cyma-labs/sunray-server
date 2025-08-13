# -*- coding: utf-8 -*-
from odoo import models, fields, api
import secrets


class SunrayApiKey(models.Model):
    _name = 'sunray.api.key'
    _description = 'API Key for Worker Authentication'
    _rec_name = 'name'
    _order = 'name'
    
    name = fields.Char(
        string='Name', 
        required=True,
        help='Descriptive name for this API key'
    )
    key = fields.Char(
        string='API Key', 
        required=True, 
        index=True,
        help='The API key value'
    )
    is_active = fields.Boolean(
        string='Active', 
        default=True,
        help='Deactivate to disable this API key'
    )
    description = fields.Text(
        string='Description',
        help='Purpose and usage of this API key'
    )
    scopes = fields.Text(
        string='Scopes',
        help='Permission scopes (e.g., config:read,user:write,session:all)',
        default='all'
    )
    
    # Usage tracking
    last_used = fields.Datetime(
        string='Last Used',
        help='Last time this API key was used'
    )
    usage_count = fields.Integer(
        string='Usage Count', 
        default=0,
        help='Number of API calls made with this key'
    )
    
    _sql_constraints = [
        ('key_unique', 'UNIQUE(key)', 'API key must be unique!')
    ]
    
    def create(self, vals_list):
        """Override create to auto-generate key if not provided"""
        for vals in vals_list:
            if 'key' not in vals or not vals['key']:
                vals['key'] = self.generate_key()
        return super().create(vals_list)
    
    @api.model
    def generate_key(self):
        """Generate a secure API key"""
        return secrets.token_urlsafe(32)
    
    def regenerate_key(self):
        """Generate a new API key"""
        self.ensure_one()
        new_key = self.generate_key()
        
        # Log key regeneration
        self.env['sunray.audit.log'].create({
            'event_type': 'api_key.regenerated',
            'details': f'{{"key_name": "{self.name}"}}'
        })
        
        self.key = new_key
        return new_key
    
    def track_usage(self):
        """Update usage statistics"""
        self.write({
            'last_used': fields.Datetime.now(),
            'usage_count': self.usage_count + 1
        })
        return True
    
    def has_scope(self, required_scope):
        """Check if this API key has the required scope"""
        self.ensure_one()
        
        # 'all' scope grants everything
        if self.scopes == 'all':
            return True
        
        # Check if the required scope is in the key's scopes
        key_scopes = set(s.strip() for s in (self.scopes or '').split(','))
        
        # Check exact match
        if required_scope in key_scopes:
            return True
        
        # Check wildcard match (e.g., 'user:*' matches 'user:read')
        resource, action = required_scope.split(':', 1) if ':' in required_scope else (required_scope, '')
        for scope in key_scopes:
            if scope == f"{resource}:all" or scope == f"{resource}:*":
                return True
        
        return False