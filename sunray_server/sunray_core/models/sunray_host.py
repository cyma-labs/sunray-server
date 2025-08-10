# -*- coding: utf-8 -*-
from odoo import models, fields, api
import json
import ipaddress
import re


class SunrayHost(models.Model):
    _name = 'sunray.host'
    _description = 'Protected Host'
    _rec_name = 'domain'
    _order = 'domain'
    
    domain = fields.Char(
        string='Domain', 
        required=True, 
        index=True,
        help='Domain name to protect (e.g., app.example.com)'
    )
    backend_url = fields.Char(
        string='Backend URL', 
        required=True,
        help='Backend service URL to proxy requests to'
    )
    is_active = fields.Boolean(
        string='Active', 
        default=True,
        help='Deactivate to temporarily disable host protection'
    )
    
    # Security Exceptions (whitelist approach)
    # Default: Everything requires passkey authentication
    
    # CIDR-based exceptions (bypass all authentication)
    allowed_cidrs = fields.Text(
        string='Allowed CIDR Blocks (JSON)', 
        default='[]',
        help='CIDR blocks that bypass all authentication (e.g., office networks)'
    )
    
    # URL-based public exceptions  
    public_url_patterns = fields.Text(
        string='Public URL Patterns (JSON)', 
        default='[]',
        help='URL regex patterns that allow unrestricted public access'
    )
    
    # URL-based token exceptions
    token_url_patterns = fields.Text(
        string='Token-Protected URL Patterns (JSON)', 
        default='[]',
        help='URL regex patterns that accept token authentication instead of passkeys'
    )
    
    # Webhook Authentication
    webhook_token_ids = fields.One2many(
        'sunray.webhook.token', 
        'host_id', 
        string='Webhook Tokens'
    )
    webhook_header_name = fields.Char(
        string='Webhook Header Name', 
        default='X-Sunray-Webhook-Token',
        help='HTTP header name for webhook token'
    )
    webhook_param_name = fields.Char(
        string='Webhook URL Parameter', 
        default='sunray_token',
        help='URL parameter name for webhook token'
    )
    
    # Access control  
    user_ids = fields.Many2many(
        'sunray.user',
        'sunray_user_host_rel',
        'host_id',
        'user_id',
        string='Authorized Users'
    )
    allowed_ips = fields.Text(
        string='Allowed IPs (JSON)', 
        default='[]',
        help='Additional IP restrictions for this host'
    )
    
    # Session overrides
    session_duration_s = fields.Integer(
        string='Session Duration (seconds)',
        help='Session timeout in seconds. Examples:\n'
             '- 1h = 3600\n'
             '- 4h = 14400\n'
             '- 8h = 28800\n'
             '- 24h = 86400'
    )
    
    _sql_constraints = [
        ('domain_unique', 'UNIQUE(domain)', 'Domain must be unique!')
    ]
    
    def _get_allowed_cidrs(self):
        """Parse allowed CIDR blocks from JSON"""
        try:
            return json.loads(self.allowed_cidrs or '[]')
        except (json.JSONDecodeError, TypeError):
            return []
    
    def _get_public_url_patterns(self):
        """Parse public URL patterns from JSON"""  
        try:
            return json.loads(self.public_url_patterns or '[]')
        except (json.JSONDecodeError, TypeError):
            return []
    
    def _get_token_url_patterns(self):
        """Parse token URL patterns from JSON"""
        try:
            return json.loads(self.token_url_patterns or '[]')
        except (json.JSONDecodeError, TypeError):
            return []
    
    def check_access_requirements(self, client_ip, url_path):
        """
        Determine access requirements for a request
        Security-first approach: Everything locked by default
        
        Returns:
        - 'cidr_allowed': IP is in allowed CIDR, bypass all auth
        - 'public': URL matches public pattern, no auth required  
        - 'token': URL matches token pattern, token auth required
        - 'passkey': Default - passkey authentication required
        """
        # 1. Check CIDR exceptions first (highest priority)
        if client_ip:
            try:
                client = ipaddress.ip_address(client_ip)
                for cidr_str in self._get_allowed_cidrs():
                    if client in ipaddress.ip_network(cidr_str, strict=False):
                        return 'cidr_allowed'
            except (ValueError, ipaddress.AddressValueError):
                # Invalid IP format, continue with other checks
                pass
        
        # 2. Check public URL exceptions
        for pattern in self._get_public_url_patterns():
            if re.match(pattern, url_path):
                return 'public'
        
        # 3. Check token URL exceptions  
        for pattern in self._get_token_url_patterns():
            if re.match(pattern, url_path):
                return 'token'
        
        # 4. Default: Require passkey authentication
        return 'passkey'