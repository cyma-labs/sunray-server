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
        string='Allowed CIDR Blocks', 
        help='CIDR blocks that bypass all authentication (one per line, # for comments)'
    )
    
    # URL-based public exceptions  
    public_url_patterns = fields.Text(
        string='Public URL Patterns', 
        help='URL patterns that allow unrestricted public access (one per line, # for comments)'
    )
    
    # URL-based token exceptions
    token_url_patterns = fields.Text(
        string='Token-Protected URL Patterns', 
        help='URL patterns that accept token authentication (one per line, # for comments)'
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
        string='Allowed IP Addresses', 
        help='Additional IP restrictions for this host (one per line, # for comments)'
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
    
    def get_allowed_cidrs(self, format='json'):
        """Parse allowed CIDR blocks from line-separated format
        
        Args:
            format: Output format ('json' returns list, future: 'txt', 'yaml')
            
        Returns:
            Parsed data in requested format
        """
        if format == 'json':
            return self._parse_line_separated_field(self.allowed_cidrs)
        elif format == 'txt':
            # Future: return clean text without comments
            raise NotImplementedError(f"Format '{format}' not yet implemented")
        elif format == 'yaml':
            # Future: return YAML formatted data
            raise NotImplementedError(f"Format '{format}' not yet implemented")
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    def get_public_url_patterns(self, format='json'):
        """Parse public URL patterns from line-separated format
        
        Args:
            format: Output format ('json' returns list, future: 'txt', 'yaml')
            
        Returns:
            Parsed data in requested format
        """  
        if format == 'json':
            return self._parse_line_separated_field(self.public_url_patterns)
        elif format == 'txt':
            # Future: return clean text without comments
            raise NotImplementedError(f"Format '{format}' not yet implemented")
        elif format == 'yaml':
            # Future: return YAML formatted data
            raise NotImplementedError(f"Format '{format}' not yet implemented")
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    def get_token_url_patterns(self, format='json'):
        """Parse token URL patterns from line-separated format
        
        Args:
            format: Output format ('json' returns list, future: 'txt', 'yaml')
            
        Returns:
            Parsed data in requested format
        """
        if format == 'json':
            return self._parse_line_separated_field(self.token_url_patterns)
        elif format == 'txt':
            # Future: return clean text without comments
            raise NotImplementedError(f"Format '{format}' not yet implemented")
        elif format == 'yaml':
            # Future: return YAML formatted data
            raise NotImplementedError(f"Format '{format}' not yet implemented")
        else:
            raise ValueError(f"Unsupported format: {format}")
    
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
                for cidr_str in self.get_allowed_cidrs():
                    if client in ipaddress.ip_network(cidr_str, strict=False):
                        return 'cidr_allowed'
            except (ValueError, ipaddress.AddressValueError):
                # Invalid IP format, continue with other checks
                pass
        
        # 2. Check public URL exceptions
        for pattern in self.get_public_url_patterns():
            if re.match(pattern, url_path):
                return 'public'
        
        # 3. Check token URL exceptions  
        for pattern in self.get_token_url_patterns():
            if re.match(pattern, url_path):
                return 'token'
        
        # 4. Default: Require passkey authentication
        return 'passkey'