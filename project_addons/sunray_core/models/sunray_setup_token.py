# -*- coding: utf-8 -*-
import hashlib
import ipaddress
import json
import logging
import secrets

from odoo import models, fields, api
from datetime import datetime, timedelta


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
        string='Protected Host',
        help='The host this token is valid for'
    )
    token_hash = fields.Char(
        string='Token Hash (SHA-512)', 
        required=True,
        help='SHA-512 hash of the setup token'
    )
    device_name = fields.Char(
        string='Token Name',
        help='Intended name for this token'
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
    
    # UI display helper field
    show_full_token = fields.Boolean(
        string='Show Full Token',
        default=False,
        store=False,
        help='Toggle to show/hide full token hash in form view',
        inverse='_inverse_show_full_token'
    )
    def _inverse_show_full_token(self):
        for record in self:
            pass
            #record.show_full_token = record.show_full_token
    
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
    def _generate_readable_token(self):
        """Generate a user-friendly token that can be easily dictated and typed.
        
        Format: XXXXX-XXXXX-XXXXX-XXXXX-XXXXX (25 characters, 5 groups of 5)
        Character set: 23456789ABCDEFGHJKMNPQRSTUVWXYZ (32 chars, excludes 0,O,I,L,1)
        Entropy: 32^25 = ~125 bits (cryptographically secure)
        
        Returns:
            str: Formatted token like 'A2B3C-4D5E6-F7G8H-9J2K3-M4N5P'
        """
        # Character set excluding ambiguous chars (0, O, I, L, 1)
        chars = '23456789ABCDEFGHJKMNPQRSTUVWXYZ'
        
        # Generate 25 random characters
        token_chars = [secrets.choice(chars) for _ in range(25)]
        
        # Format with dashes: XXXXX-XXXXX-XXXXX-XXXXX-XXXXX
        formatted_token = '-'.join([
            ''.join(token_chars[0:5]),
            ''.join(token_chars[5:10]),
            ''.join(token_chars[10:15]),
            ''.join(token_chars[15:20]),
            ''.join(token_chars[20:25])
        ])
        
        return formatted_token
    
    @api.model
    def _normalize_token_for_hashing(self, token_value):
        """Normalize token for hashing by removing dashes and converting to uppercase.
        
        This supports both old format (urlsafe) and new format (readable) tokens.
        
        Args:
            token_value: Raw token value from input
            
        Returns:
            str: Normalized token ready for hashing
        """
        # Remove dashes and spaces, convert to uppercase
        normalized = token_value.replace('-', '').replace(' ', '').upper()
        return normalized
    
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
        
        # Generate secure user-friendly token
        token_value = self._generate_readable_token()
        # Normalize for consistent hashing (handles both old and new formats)
        normalized_token = self._normalize_token_for_hashing(token_value)
        token_hash = f"sha512:{hashlib.sha512(normalized_token.encode()).hexdigest()}"
        
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
    
    def consume(self):
        """
        Consume this token by incrementing usage count and marking as consumed if max uses reached.
        
        This method encapsulates all token consumption logic and should be called after
        successful passkey registration.
        
        Returns:
            dict: {'consumed': bool, 'current_uses': int, 'max_uses': int}
        """
        self.ensure_one()
        import logging
        _logger = logging.getLogger(__name__)
        
        _logger.info(f"Consuming token {self.id}, current uses: {self.current_uses}")
        new_uses = self.current_uses + 1
        token_consumed = new_uses >= self.max_uses
        
        self.write({
            'current_uses': new_uses,
            'consumed': token_consumed,
            'consumed_date': fields.Datetime.now() if token_consumed else False
        })
        
        _logger.info(f"Token updated: uses={new_uses}/{self.max_uses}, consumed={token_consumed}")
        
        return {
            'consumed': token_consumed,
            'current_uses': new_uses,
            'max_uses': self.max_uses
        }
    
    @api.model
    def validate_setup_token(self, username, token_hash, host_domain, client_ip=None, user_agent=None, worker_id=None):
        """
        Validate a setup token with comprehensive security checks.
        
        This is the centralized validation method that performs all setup token validation
        logic. It's used by both the REST API endpoint and passkey registration.
        
        Args:
            username: Username associated with the token
            token_hash: Either SHA-512 hash (prefixed with "sha512:") OR raw token value
            host_domain: Domain the token is being used for
            client_ip: Client IP address for CIDR validation (optional)
            user_agent: Client user agent string (optional)
            worker_id: Worker identifier making the request (optional)
            
        Returns:
            dict: Validation result containing:
                - valid: boolean indicating if token is valid
                - token_obj: token object if valid (None if invalid)
                - user_obj: user object if valid (None if invalid)  
                - host_obj: host object if valid (None if invalid)
                - error_code: HTTP-style error code if invalid
                - error_message: human-readable error message if invalid
        """
        _logger = logging.getLogger(__name__)
        
        _logger.debug(f"Validating setup token for username: {username}, host: {host_domain}")
        now = fields.Datetime.now()
        
        # Handle both raw tokens and pre-hashed tokens for backward compatibility
        if token_hash and not token_hash.startswith('sha512:'):
            # This is a raw token value, normalize and hash it
            normalized_token = self._normalize_token_for_hashing(token_hash)
            token_hash = f"sha512:{hashlib.sha512(normalized_token.encode()).hexdigest()}"
            _logger.debug("Converted raw token to hash for validation")
        
        # Initialize result structure
        result = {
            'valid': False,
            'token_obj': None,
            'user_obj': None,
            'host_obj': None,
            'error_code': None,
            'error_message': None
        }
        
        try:
            # Phase 1: User Validation
            _logger.debug("Validating user existence and status")
            user_obj = self.env['sunray.user'].sudo().search([('username', '=', username)], limit=1)
            if not user_obj:
                _logger.warning(f"User not found: {username}")
                # AUDIT: Log user not found
                self.env['sunray.audit.log'].sudo().create_audit_event(
                    event_type='token.validation.user_not_found',
                    details={
                        'username': username,
                        'host_domain': host_domain,
                        'worker_id': worker_id
                    },
                    severity='warning',
                    sunray_worker=worker_id,
                    ip_address=client_ip,
                    user_agent=user_agent,
                    username=username
                )
                result.update({
                    'error_code': '404',
                    'error_message': 'User not found'
                })
                return result
            
            if not user_obj.is_active:
                _logger.warning(f"Inactive user attempted token validation: {username}")
                # AUDIT: Log inactive user attempt
                self.env['sunray.audit.log'].sudo().create_audit_event(
                    event_type='token.validation.user_inactive',
                    details={
                        'username': username,
                        'user_id': user_obj.id,
                        'host_domain': host_domain,
                        'worker_id': worker_id
                    },
                    severity='warning',
                    sunray_user_id=user_obj.id,
                    sunray_worker=worker_id,
                    ip_address=client_ip,
                    user_agent=user_agent,
                    username=username
                )
                result.update({
                    'error_code': '403',
                    'error_message': 'User is inactive'
                })
                return result
            
            # Phase 2: Setup Token Hash Validation
            _logger.debug(f"Validating setup token hash for user {username}")
            
            token_obj = self.env['sunray.setup.token'].sudo().search([
                ('token_hash', '=', token_hash),
                ('user_id', '=', user_obj.id)
            ], limit=1)
            
            if not token_obj:
                _logger.warning(f"Invalid setup token hash for user {username}")
                # AUDIT: Log invalid token hash
                self.env['sunray.audit.log'].sudo().create_audit_event(
                    event_type='token.validation.token_not_found',
                    details={
                        'username': username,
                        'user_id': user_obj.id,
                        'host_domain': host_domain,
                        'worker_id': worker_id
                    },
                    severity='critical',
                    sunray_user_id=user_obj.id,
                    sunray_worker=worker_id,
                    ip_address=client_ip,
                    user_agent=user_agent,
                    username=username
                )
                result.update({
                    'error_code': '401',
                    'error_message': 'Invalid setup token hash'
                })
                return result
            
            # Check token expiry
            if token_obj.expires_at < now:
                hours_ago = (now - token_obj.expires_at).total_seconds() / 3600
                _logger.warning(f"Expired token used for {username}, expired {hours_ago:.1f} hours ago")
                # AUDIT: Log expired token
                self.env['sunray.audit.log'].sudo().create_audit_event(
                    event_type='token.validation.expired',
                    details={
                        'username': username,
                        'token_id': token_obj.id,
                        'expired_hours_ago': round(hours_ago, 1),
                        'expired_at': token_obj.expires_at.isoformat(),
                        'host_domain': host_domain,
                        'worker_id': worker_id
                    },
                    severity='warning',
                    sunray_user_id=user_obj.id,
                    sunray_worker=worker_id,
                    ip_address=client_ip,
                    user_agent=user_agent,
                    username=username
                )
                result.update({
                    'error_code': '401',
                    'error_message': 'Setup token expired'
                })
                return result
            
            # Check if token is already consumed
            if token_obj.consumed:
                _logger.warning(f"Consumed token reuse attempted for {username}")
                # AUDIT: Log consumed token reuse
                self.env['sunray.audit.log'].sudo().create_audit_event(
                    event_type='token.validation.consumed',
                    details={
                        'username': username,
                        'token_id': token_obj.id,
                        'consumed_date': token_obj.consumed_date.isoformat() if token_obj.consumed_date else None,
                        'current_uses': token_obj.current_uses,
                        'max_uses': token_obj.max_uses,
                        'host_domain': host_domain,
                        'worker_id': worker_id
                    },
                    severity='critical',
                    sunray_user_id=user_obj.id,
                    sunray_worker=worker_id,
                    ip_address=client_ip,
                    user_agent=user_agent,
                    username=username
                )
                result.update({
                    'error_code': '403',
                    'error_message': 'Token already consumed'
                })
                return result
            
            # Check token usage limit
            if token_obj.current_uses >= token_obj.max_uses:
                _logger.warning(f"Token usage limit exceeded for {username}: {token_obj.current_uses}/{token_obj.max_uses}")
                # AUDIT: Log token usage limit exceeded
                self.env['sunray.audit.log'].sudo().create_audit_event(
                    event_type='token.validation.usage_exceeded',
                    details={
                        'username': username,
                        'token_id': token_obj.id,
                        'current_uses': token_obj.current_uses,
                        'max_uses': token_obj.max_uses,
                        'host_domain': host_domain,
                        'worker_id': worker_id
                    },
                    severity='critical',
                    sunray_user_id=user_obj.id,
                    sunray_worker=worker_id,
                    ip_address=client_ip,
                    user_agent=user_agent,
                    username=username
                )
                result.update({
                    'error_code': '403',
                    'error_message': 'Token usage limit exceeded'
                })
                return result
            
            # Phase 3: Host Domain Validation
            _logger.debug(f"Validating host domain: {host_domain}")
            host_obj = self.env['sunray.host'].sudo().search([('domain', '=', host_domain)], limit=1)
            
            if not host_obj:
                _logger.warning(f"Unknown host domain: {host_domain}")
                # AUDIT: Log unknown host
                self.env['sunray.audit.log'].sudo().create_audit_event(
                    event_type='token.validation.unknown_host',
                    details={
                        'username': username,
                        'token_id': token_obj.id,
                        'host_domain': host_domain,
                        'worker_id': worker_id
                    },
                    severity='critical',
                    sunray_user_id=user_obj.id,
                    sunray_worker=worker_id,
                    ip_address=client_ip,
                    user_agent=user_agent,
                    username=username
                )
                result.update({
                    'error_code': '404',
                    'error_message': 'Unknown host domain'
                })
                return result
            
            # Verify token is for the correct host
            if token_obj.host_id.id != host_obj.id:
                _logger.warning(f"Token host mismatch: token for {token_obj.host_id.domain}, requested for {host_domain}")
                # AUDIT: Log host mismatch
                self.env['sunray.audit.log'].sudo().create_audit_event(
                    event_type='token.validation.host_mismatch',
                    details={
                        'username': username,
                        'token_id': token_obj.id,
                        'token_host': token_obj.host_id.domain,
                        'requested_host': host_domain,
                        'worker_id': worker_id
                    },
                    severity='critical',
                    sunray_user_id=user_obj.id,
                    sunray_worker=worker_id,
                    ip_address=client_ip,
                    user_agent=user_agent,
                    username=username
                )
                result.update({
                    'error_code': '403',
                    'error_message': 'Token not valid for this host domain'
                })
                return result
            
            # Phase 4: CIDR IP Address Validation (if configured and client_ip provided)
            if client_ip and token_obj.allowed_cidrs:
                allowed_cidrs = token_obj.get_allowed_cidrs()
                if allowed_cidrs:
                    ip_allowed = False
                    try:
                        client_ip_obj = ipaddress.ip_address(client_ip)
                        for cidr in allowed_cidrs:
                            try:
                                if '/' in cidr:
                                    # CIDR notation
                                    network = ipaddress.ip_network(cidr, strict=False)
                                    if client_ip_obj in network:
                                        ip_allowed = True
                                        break
                                else:
                                    # Single IP
                                    if client_ip_obj == ipaddress.ip_address(cidr):
                                        ip_allowed = True
                                        break
                            except ValueError:
                                _logger.warning(f"Invalid CIDR in token {token_obj.id}: {cidr}")
                                continue
                    except ValueError:
                        _logger.warning(f"Invalid client IP address: {client_ip}")
                        # AUDIT: Log invalid IP
                        self.env['sunray.audit.log'].sudo().create_audit_event(
                            event_type='token.validation.invalid_ip',
                            details={
                                'username': username,
                                'token_id': token_obj.id,
                                'client_ip': client_ip,
                                'host_domain': host_domain,
                                'worker_id': worker_id
                            },
                            severity='warning',
                            sunray_user_id=user_obj.id,
                            sunray_worker=worker_id,
                            ip_address=client_ip,
                            user_agent=user_agent,
                            username=username
                        )
                        result.update({
                            'error_code': '400',
                            'error_message': 'Invalid client IP address'
                        })
                        return result
                    
                    if not ip_allowed:
                        _logger.warning(f"IP address {client_ip} not allowed for token {token_obj.id}")
                        # AUDIT: Log IP restriction
                        self.env['sunray.audit.log'].sudo().create_audit_event(
                            event_type='token.validation.ip_restricted',
                            details={
                                'username': username,
                                'token_id': token_obj.id,
                                'client_ip': client_ip,
                                'allowed_cidrs': allowed_cidrs,
                                'host_domain': host_domain,
                                'worker_id': worker_id
                            },
                            severity='critical',
                            sunray_user_id=user_obj.id,
                            sunray_worker=worker_id,
                            ip_address=client_ip,
                            user_agent=user_agent,
                            username=username
                        )
                        result.update({
                            'error_code': '403',
                            'error_message': 'IP address not allowed for this token'
                        })
                        return result
            
            # All validation checks passed
            _logger.info(f"Setup token validation successful for {username} on {host_domain}")
            
            # AUDIT: Log successful validation
            self.env['sunray.audit.log'].sudo().create_audit_event(
                event_type='token.validation.success',
                details={
                    'username': username,
                    'token_id': token_obj.id,
                    'host_domain': host_domain,
                    'client_ip': client_ip,
                    'worker_id': worker_id,
                    'device_name': token_obj.device_name,
                    'uses_remaining': token_obj.max_uses - token_obj.current_uses
                },
                severity='info',
                sunray_user_id=user_obj.id,
                sunray_worker=worker_id,
                ip_address=client_ip,
                user_agent=user_agent,
                username=username
            )
            
            result.update({
                'valid': True,
                'token_obj': token_obj,
                'user_obj': user_obj,
                'host_obj': host_obj
            })
            return result
            
        except Exception as e:
            _logger.error(f"Unexpected error during token validation: {str(e)}")
            # AUDIT: Log validation error
            self.env['sunray.audit.log'].sudo().create_audit_event(
                event_type='token.validation.error',
                details={
                    'username': username,
                    'host_domain': host_domain,
                    'error': str(e),
                    'worker_id': worker_id
                },
                severity='error',
                sunray_worker=worker_id,
                ip_address=client_ip,
                user_agent=user_agent,
                username=username
            )
            result.update({
                'error_code': '500',
                'error_message': 'Internal validation error'
            })
            return result

    def init(self):
        """Create database indexes for optimal query performance

        Creates composite index for user+host lookups, which is used by:
        - sunray.protected_host_user_list_report view (setup_token_count subselect)
        - Any other queries filtering by user and host
        """
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS idx_sunray_setup_token_user_host
            ON sunray_setup_token(user_id, host_id)
        """)