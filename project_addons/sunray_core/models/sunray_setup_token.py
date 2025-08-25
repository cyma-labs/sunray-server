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
    host_id = fields.Many2one(
        'sunray.host',
        required=True,
        ondelete='cascade',
        string='Host',
        help='The host this token is valid for'
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
    allowed_cidrs = fields.Text(
        string='Allowed CIDRs', 
        help='IP addresses or CIDR blocks allowed to use this token (one per line, # for comments)\nExamples: 192.168.1.100 or 192.168.1.100/32 or 192.168.1.0/24'
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
            self.env['sunray.audit.log'].create_audit_event(
                event_type='token.cleanup',
                details={
                    'count': len(expired_objs),
                    'tokens': expired_objs.mapped('id')
                },
                event_source='system'
            )
        
        expired_objs.unlink()
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
    
    @api.model
    def create_setup_token(self, user_id, host_id, device_name, validity_hours=24, max_uses=1, allowed_cidrs=''):
        """
        Create a setup token and auto-authorize user for the host if needed.
        This is the single source of truth for token creation logic.
        
        Args:
            user_id: ID of the user
            host_id: ID of the host
            device_name: Name of the device this token is for
            validity_hours: How long the token is valid (default: 24)
            max_uses: Maximum number of uses (default: 1)
            allowed_cidrs: Text field with allowed CIDRs (one per line)
            
        Returns:
            tuple: (token_obj, plain_token_value)
        """
        import secrets
        import hashlib
        import json
        from datetime import timedelta
        
        # Auto-authorize user for the host if not already
        host_obj = self.env['sunray.host'].browse(host_id)
        user_obj = self.env['sunray.user'].browse(user_id)
        
        if user_obj not in host_obj.user_ids:
            host_obj.write({
                'user_ids': [(4, user_id)]  # Add user to host's authorized users
            })
        
        # Generate secure token
        token_value = secrets.token_urlsafe(32)
        token_hash = f"sha512:{hashlib.sha512(token_value.encode()).hexdigest()}"
        
        # Create token record
        token_obj = self.create({
            'user_id': user_id,
            'host_id': host_id,
            'token_hash': token_hash,
            'device_name': device_name,
            'expires_at': fields.Datetime.now() + timedelta(hours=validity_hours),
            'allowed_cidrs': allowed_cidrs,
            'max_uses': max_uses,
            'current_uses': 0
        })
        
        # Log event
        self.env['sunray.audit.log'].create_admin_event(
            event_type='token.generated',
            details={
                'device_name': device_name,
                'host': host_obj.domain,
                'validity_hours': validity_hours,
                'max_uses': max_uses,
                'target_user': user_obj.username
            },
            sunray_user_id=user_id,  # Also track the target user
            username=user_obj.username  # Keep for compatibility
        )
        
        return token_obj, token_value