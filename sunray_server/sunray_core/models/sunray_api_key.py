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