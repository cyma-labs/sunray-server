# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError
import json
import secrets
import string


class SunrayWebhookToken(models.Model):
    _name = 'sunray.webhook.token'
    _description = 'API and Webhook Authentication Token'
    _rec_name = 'name'
    _order = 'name'

    name = fields.Char(
        string='Token Name',
        required=True,
        help='Descriptive name for this token (e.g., "Shopify Webhook", "Payment API", "CI/CD Pipeline"). '
             'Tokens are reusable across multiple hosts via Access Rules.'
    )
    token = fields.Char(
        string='Token Value', 
        required=True, 
        index=True,
        help='The actual token value for API and webhook authentication'
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

    # UI display helper field
    show_full_token = fields.Boolean(
        string='Show Full Token',
        default=False,
        store=False,
        help='Toggle to show/hide full token value in form view',
        inverse='_inverse_show_full_token'
    )
    def _inverse_show_full_token(self):
        for record in self:
            pass
            #record.show_full_token = record.show_full_token

    # Optional restrictions
    allowed_cidrs = fields.Text(
        string='Allowed CIDRs', 
        help='IP addresses or CIDR blocks allowed to use this token (one per line, # for comments)\nExamples: 192.168.1.100 or 192.168.1.100/32 or 192.168.1.0/24'
    )
    expires_at = fields.Datetime(
        string='Expiration Date',
        help='Token expiration date (empty = never expires)'
    )
    
    # Token extraction configuration
    header_name = fields.Char(
        string='Header Name',
        help='HTTP header name for API/webhook token extraction (e.g., X-Shopify-Hmac-Sha256, Authorization, X-API-Key)'
    )
    param_name = fields.Char(
        string='Parameter Name',
        help='URL parameter name for API/webhook token extraction (e.g., api_key, token, key)'
    )
    token_source = fields.Selection([
        ('header', 'HTTP Header Only'),
        ('param', 'URL Parameter Only'),
        ('both', 'Both (Header First)')
    ], string='Token Source', default='header',
       help='Where to extract the API/webhook token from')
    
    _sql_constraints = [
        ('token_unique', 'UNIQUE(token)', 'Token must be unique!'),
        ('source_config_check', 
         "CHECK((token_source = 'header' AND header_name IS NOT NULL) OR "
         "(token_source = 'param' AND param_name IS NOT NULL) OR "
         "(token_source = 'both' AND (header_name IS NOT NULL OR param_name IS NOT NULL)))",
         'Header name required for header source, parameter name required for param source!')
    ]
    
    @api.constrains('token_source', 'header_name', 'param_name')
    def _check_token_source_configuration(self):
        """Validate token source configuration"""
        for record in self:
            if record.token_source == 'header' and not record.header_name:
                raise ValidationError('Header name is required when token source is "header"')
            elif record.token_source == 'param' and not record.param_name:
                raise ValidationError('Parameter name is required when token source is "param"')
            elif record.token_source == 'both' and not record.header_name and not record.param_name:
                raise ValidationError('At least one of header name or parameter name is required when token source is "both"')
    
    @api.model_create_multi
    def create(self, vals_list):
        """Override create to auto-generate token if not provided"""
        for vals in vals_list:
            if 'token' not in vals or not vals['token']:
                vals['token'] = self.generate_token()
        return super().create(vals_list)
    
    #def write(self, vals):
    #    result = super().write(vals)
    #    return result

    def generate_token(self):
        """Generate a secure random token"""
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(32))
    
    def regenerate_token(self):
        """Generate a new token value"""
        self.ensure_one()
        new_token = self.generate_token()

        # Log token regeneration
        self.env['sunray.audit.log'].create_admin_event(
            event_type='webhook.regenerated',
            details={
                'token_name': self.name,
                'token_id': self.id
            }
        )

        self.token = new_token
        return new_token
    
    def is_valid(self, client_ip=None):
        """Check if token is valid and authorized"""
        if not self.is_active:
            return False
        
        # Check expiration
        if self.expires_at and self.expires_at < fields.Datetime.now():
            return False
        
        # Check IP restrictions using CIDR
        if client_ip and self.allowed_cidrs:
            from odoo.addons.sunray_core.utils.cidr import check_cidr_match
            allowed_cidrs = self.get_allowed_cidrs()
            if allowed_cidrs and not any(check_cidr_match(client_ip, cidr) for cidr in allowed_cidrs):
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
    
    def get_allowed_cidrs(self, format='json'):
        """Parse allowed CIDRs from line-separated format
        
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
    
    def track_usage(self, client_ip=None, host_domain=None):
        """Update usage statistics

        Args:
            client_ip: IP address of the client using the token
            host_domain: Domain of the host where token was used (optional, for audit context)
        """
        self.write({
            'last_used': fields.Datetime.now(),
            'usage_count': self.usage_count + 1
        })

        # Log usage
        details = {
            'token_name': self.name,
            'token_id': self.id
        }
        if host_domain:
            details['host'] = host_domain

        self.env['sunray.audit.log'].create_audit_event(
            event_type='webhook.used',
            details=details,
            ip_address=client_ip,
            event_source='api'
        )

        return True
    
    def get_extraction_config(self):
        """Get API/webhook token extraction configuration for worker"""
        self.ensure_one()
        return {
            'token': self.token,
            'name': self.name,
            'header_name': self.header_name,
            'param_name': self.param_name,
            'token_source': self.token_source,
            'allowed_cidrs': self.get_allowed_cidrs(),
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'is_active': self.is_active
        }

    def btn_refresh(self):
        """Refresh button action - reload the form"""
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    def action_view_usage_logs(self):
        """View audit logs for this token's usage"""
        self.ensure_one()
        return {
            'name': f'Usage Logs: {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'sunray.audit.log',
            'view_mode': 'list,form',
            'domain': [
                ('event_type', '=', 'webhook.used'),
                ('details', 'ilike', f'"token_name": "{self.name}"')
            ],
            'context': {'search_default_group_by_date': 1}
        }