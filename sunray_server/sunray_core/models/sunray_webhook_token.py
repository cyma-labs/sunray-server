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
        string='Allowed IPs', 
        help='IP addresses allowed to use this token (one per line, # for comments)'
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
            allowed_ips = self.get_allowed_ips()
            if allowed_ips and client_ip not in allowed_ips:
                return False
        
        return True
    
    def _parse_line_separated_field(self, field_value):
        """Parse line-separated field with comment support
        
        Format:
        - One value per line
        - Lines starting with # are ignored (comments)
        - # can be used for inline comments
        
        Args:
            field_value: The raw field value to parse
            
        Returns:
            list: Array of parsed values
        """
        if not field_value:
            return []
        
        result = []
        for line in field_value.split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            # Remove inline comments
            if '#' in line:
                line = line.split('#')[0].strip()
            if line:
                result.append(line)
        return result
    
    def get_allowed_ips(self, format='json'):
        """Parse allowed IP addresses from line-separated format
        
        Args:
            format: Output format ('json' returns list, future: 'txt', 'yaml')
            
        Returns:
            Parsed data in requested format
        """
        if format == 'json':
            return self._parse_line_separated_field(self.allowed_ips)
        elif format == 'txt':
            # Future: return clean text without comments
            raise NotImplementedError(f"Format '{format}' not yet implemented")
        elif format == 'yaml':
            # Future: return YAML formatted data
            raise NotImplementedError(f"Format '{format}' not yet implemented")
        else:
            raise ValueError(f"Unsupported format: {format}")
    
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