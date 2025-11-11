# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError
from datetime import datetime, timedelta
import hashlib
import logging
import cbor2
import base64

try:
    from pycose.keys import CoseKey
    from pycose.exceptions import CoseException
    COSE_AVAILABLE = True
except ImportError:
    COSE_AVAILABLE = False

_logger = logging.getLogger(__name__)


class SunrayPasskey(models.Model):
    _name = 'sunray.passkey'
    _description = 'Sunray Passkey'
    _rec_name = 'name'
    _order = 'create_date desc'
    
    user_id = fields.Many2one(
        'sunray.user', 
        required=True, 
        ondelete='cascade',
        string='User'
    )
    credential_id = fields.Char(
        string='Credential ID', 
        required=True, 
        index=True,
        help='WebAuthn credential identifier'
    )
    public_key = fields.Text(
        string='Public Key', 
        required=True,
        help='WebAuthn public key data as provided by the worker. Server stores but does not validate format.'
    )
    name = fields.Char(
        string='Device Name', 
        required=True,
        help='User-friendly name for this passkey'
    )
    last_used = fields.Datetime(
        string='Last Used',
        help='Last authentication timestamp'
    )
    counter = fields.Integer(
        string='Authentication Counter',
        default=0,
        help='Counter value managed by worker (stored for debugging and audit purposes)'
    )
    
    # WebAuthn rpId binding - CRITICAL for security
    host_domain = fields.Char(
        string='Registered Host Domain',
        required=False,  # Allow blank for existing records to force re-registration
        index=True,
        help='The host domain (rpId) this passkey is bound to per WebAuthn spec. Empty value means passkey needs re-registration to comply with WebAuthn security requirements.'
    )
    
    # Audit fields
    created_ip = fields.Char(
        string='Registration IP',
        help='IP address used during passkey registration'
    )
    created_user_agent = fields.Text(
        string='Registration User Agent',
        help='Browser user agent during registration'
    )
    
    # NEW FIELD: Link to setup token
    setup_token_id = fields.Many2one(
        'sunray.setup.token',
        string='Setup Token',
        help='The setup token used to register this passkey',
        ondelete='set null',
        index=True  # Index for audit queries
    )
    
    _sql_constraints = [
        ('credential_unique', 'UNIQUE(credential_id)', 'Credential ID must be unique!'),
        ('unique_credential_user', 'UNIQUE(credential_id, user_id)', 'Credential ID must be unique per user')
    ]
    
    def _validate_cbor_public_key(self, public_key_b64):
        """
        Validate that the public key is proper CBOR/COSE format.
        
        Args:
            public_key_b64 (str): Base64-encoded public key
            
        Returns:
            tuple: (is_valid, result) where result is CoseKey on success or error message on failure
        """
        try:
            # Decode base64
            try:
                cbor_data = base64.b64decode(public_key_b64)
            except Exception as e:
                return False, f"Invalid base64 encoding: {str(e)}"
            
            # Validate CBOR structure
            try:
                cbor_obj = cbor2.loads(cbor_data)
            except Exception as e:
                return False, f"Invalid CBOR format: {str(e)}"
            
            # Validate COSE key format if library is available
            if COSE_AVAILABLE:
                try:
                    cose_key = CoseKey.from_dict(cbor_obj)
                    return True, cose_key
                except Exception as e:
                    return False, f"Invalid COSE key structure: {str(e)}"
            else:
                # Basic CBOR validation without COSE
                if not isinstance(cbor_obj, dict):
                    return False, "CBOR data must be a dictionary"
                
                # Check for required COSE key fields
                if 1 not in cbor_obj:  # kty (key type)
                    return False, "Missing required COSE key type field (1)"
                
                return True, cbor_obj
                
        except Exception as e:
            return False, f"Unexpected validation error: {str(e)}"
    
    def _normalize_public_key_to_cbor(self, public_key_data):
        """
        Convert any public key format to canonical CBOR.
        Currently assumes input is already in CBOR format.
        
        Args:
            public_key_data (str): Public key data (base64 encoded)
            
        Returns:
            str: Canonical CBOR-encoded public key (base64)
        """
        # For now, we assume the key is already in proper CBOR format
        # Future enhancement could add format detection and conversion
        is_valid, result = self._validate_cbor_public_key(public_key_data)
        if is_valid:
            return public_key_data.strip()
        else:
            raise UserError(f"Cannot normalize public key: {result}")
    
    # CBOR-related error messages
    CBOR_ERROR_MESSAGES = {
        'invalid_base64': 'Public key must be valid base64-encoded data',
        'invalid_cbor': 'Public key must be valid CBOR-encoded data', 
        'invalid_cose': 'Public key must be valid COSE key format',
        'unsupported_algorithm': 'Public key algorithm not supported',
        'missing_required_fields': 'COSE key missing required fields'
    }
    
    
    def revoke(self):
        """Revoke this passkey"""
        self.ensure_one()
        
        # Log the revocation
        self.env['sunray.audit.log'].create_user_event(
            event_type='passkey.revoked',
            details={
                'passkey_name': self.name,
                'credential_id': self.credential_id
            },
            sunray_user_id=self.user_id.id,
            username=self.user_id.username  # Keep for compatibility
        )
        
        # Delete the passkey
        self.unlink()
        
        return True
    
    @api.model
    def register_with_setup_token(self, username, setup_token_hash, credential_id, public_key, host_domain, 
                                  device_name='Passkey', client_ip=None, user_agent=None, worker_id=None):
        """
        Register a new passkey with comprehensive security validation.
        
        This method encapsulates all the business logic for passkey registration,
        making it testable without HTTP context.
        
        Returns:
            dict: {'success': True, 'passkey_id': id} or raises UserError/ValidationError
        """
        _logger.info(f"Starting passkey registration for username: {username}")
        now = fields.Datetime.now()
        
        # Validate required parameters (check for None, not empty strings)
        missing_fields = []
        if username is None:
            missing_fields.append('username')
        if setup_token_hash is None:
            missing_fields.append('setup_token_hash')
        if credential_id is None:
            missing_fields.append('credential_id')
        if host_domain is None:
            missing_fields.append('host_domain')
        
        if missing_fields:
            # AUDIT: Log missing required fields
            self.env['sunray.audit.log'].sudo().create_audit_event(
                event_type='security.passkey.missing_fields',
                details={
                    'username': username,
                    'missing_fields': missing_fields,
                    'provided_fields': [f for f in ['username', 'setup_token_hash', 'credential_id', 'public_key', 'host_domain'] if f not in missing_fields],
                    'host_domain': host_domain or 'not_provided',
                    'worker_id': worker_id
                },
                severity='warning',
                sunray_worker=worker_id,
                ip_address=client_ip,
                username=username
            )
            raise UserError(f'400|Missing required fields: {", ".join(missing_fields)}')
        
        # Special validation for public_key (handle missing, empty, whitespace-only)
        if public_key is None or not str(public_key).strip():
            # AUDIT: Log missing public key
            self.env['sunray.audit.log'].sudo().create_audit_event(
                event_type='security.passkey.missing_public_key',
                details={
                    'username': username,
                    'credential_id': credential_id,
                    'public_key_provided': public_key is not None,
                    'public_key_empty': public_key == '' if public_key is not None else None,
                    'host_domain': host_domain,
                    'worker_id': worker_id,
                    'error': 'WebAuthn public key is required for passkey registration'
                },
                severity='critical',
                sunray_worker=worker_id,
                ip_address=client_ip,
                username=username
            )
            raise UserError('400|Public key is required for passkey registration')
        
        # Phase 1-4: Centralized Setup Token Validation
        _logger.debug("Performing centralized setup token validation")
        validation_result = self.env['sunray.setup.token'].validate_setup_token(
            username=username,
            token_hash=setup_token_hash,
            host_domain=host_domain,
            client_ip=client_ip,
            user_agent=user_agent,
            worker_id=worker_id
        )
        
        if not validation_result['valid']:
            # Convert validation error to UserError for consistency
            error_code = validation_result['error_code']
            error_message = validation_result['error_message']
            # Harmonize error messages with API contract for passkey registration
            if error_code == '403' and error_message == 'IP address not allowed for this token':
                error_message = 'IP not allowed'
            if error_code == '403' and error_message == 'Token not valid for this host domain':
                error_message = 'Token not valid for this host'
            raise UserError(f'{error_code}|{error_message}')
        
        # Extract validated objects from result
        token_obj = validation_result['token_obj']
        user_obj = validation_result['user_obj']
        host_obj = validation_result['host_obj']
        
        # Additional passkey-specific authorization check
        if user_obj not in host_obj.user_ids:
            _logger.warning(f"User {username} not authorized for host {host_domain}")
            # AUDIT: Log unauthorized user for host
            self.env['sunray.audit.log'].sudo().create_audit_event(
                event_type='security.passkey.user_not_authorized',
                details={
                    'username': username,
                    'host_domain': host_domain,
                    'host_user_count': len(host_obj.user_ids),
                    'token_id': token_obj.id,
                    'worker_id': worker_id
                },
                severity='critical',
                sunray_user_id=user_obj.id,
                sunray_worker=worker_id,
                ip_address=client_ip,
                username=username
            )
            raise UserError(f'403|User not authorized for host: {host_domain}')
        
        # Host active status check (not covered by token validation)
        if not host_obj.is_active:
            _logger.warning(f"Blocked attempt to register passkey on inactive host '{host_domain}'.")
            # AUDIT: Log inactive host
            self.env['sunray.audit.log'].sudo().create_audit_event(
                event_type='security.passkey.host_inactive',
                details={
                    'username': username,
                    'requested_host': host_domain,
                    'host_id': host_obj.id,
                    'token_id': token_obj.id,
                    'worker_id': worker_id
                },
                severity='warning',
                sunray_user_id=user_obj.id,
                sunray_worker=worker_id,
                ip_address=client_ip,
                username=username
            )
            raise UserError('400|Host is inactive')
        
        # Phase 5: Credential Validation - CRITICAL for WebAuthn security
        _logger.debug(f"Validating credential for user {username}")
        
        # Validate public_key is provided and not empty
        if not public_key or not public_key.strip():
            # AUDIT: Log missing public key
            self.env['sunray.audit.log'].sudo().create_audit_event(
                event_type='security.passkey.missing_public_key',
                details={
                    'username': username,
                    'host_domain': host_domain,
                    'credential_id': credential_id,
                    'token_id': token_obj.id,
                    'worker_id': worker_id,
                    'error': 'Public key is required for WebAuthn passkey registration'
                },
                severity='critical',
                sunray_user_id=user_obj.id,
                sunray_worker=worker_id,
                ip_address=client_ip,
                username=username
            )
            raise UserError('400|Public key is required for passkey registration')
        
        
        # Phase 6: Duplicate Check
        _logger.debug(f"Checking for duplicate credential: {credential_id}")
        existing_passkey = self.sudo().search([
            ('credential_id', '=', credential_id),
            ('user_id', '=', user_obj.id)
        ])
        
        if existing_passkey:
            _logger.warning(f"Duplicate credential found: {existing_passkey.id}")
            # AUDIT: Log duplicate passkey attempt
            self.env['sunray.audit.log'].sudo().create_audit_event(
                event_type='security.passkey.duplicate_credential',
                details={
                    'username': username,
                    'host_domain': host_domain,
                    'credential_id': credential_id,
                    'existing_passkey_id': existing_passkey.id,
                    'existing_passkey_name': existing_passkey.name,
                    'existing_created_date': existing_passkey.create_date.isoformat(),
                    'token_id': token_obj.id,
                    'worker_id': worker_id
                },
                severity='warning',
                sunray_user_id=user_obj.id,
                sunray_worker=worker_id,
                ip_address=client_ip,
                username=username
            )
            raise UserError('409|Credential already registered')
        
        # Phase 7: Passkey Creation
        _logger.info(f"Creating passkey for user {username} on host {host_domain}")
        try:
            passkey_obj = self.sudo().create({
                'user_id': user_obj.id,
                'credential_id': credential_id,
                'public_key': public_key.strip(),
                'name': device_name,
                'host_domain': host_domain,
                'created_ip': client_ip,
                'created_user_agent': user_agent,
                'setup_token_id': token_obj.id
            })
            _logger.info(f"Passkey created successfully with ID: {passkey_obj.id}")
            
            # Consume the token using the dedicated method
            token_result = token_obj.consume()
            
            # Phase 8: Success Audit
            _logger.info("Recording success audit event")
            self.env['sunray.audit.log'].sudo().create_audit_event(
                event_type='passkey.registered',
                details={
                    'passkey_id': passkey_obj.id,
                    'token_id': token_obj.id,
                    'host_domain': host_domain,
                    'device_name': device_name,
                    'credential_id': credential_id,
                    'token_uses': f"{token_result['current_uses']}/{token_result['max_uses']}",
                    'token_consumed': token_result['consumed'],
                    'worker_id': worker_id
                },
                severity='info',
                sunray_user_id=user_obj.id,
                sunray_worker=worker_id,
                ip_address=client_ip,
                user_agent=user_agent,
                username=username
            )
            
            return {
                'success': True,
                'passkey_id': passkey_obj.id,
                'message': 'Passkey registered successfully'
            }
            
        except Exception as e:
            _logger.error(f"Failed to create passkey: {str(e)}")
            # AUDIT: Log creation failure
            self.env['sunray.audit.log'].sudo().create_audit_event(
                event_type='security.passkey.creation_failed',
                details={
                    'username': username,
                    'error': str(e),
                    'token_id': token_obj.id,
                    'worker_id': worker_id
                },
                severity='error',
                sunray_user_id=user_obj.id,
                sunray_worker=worker_id,
                ip_address=client_ip,
                username=username
            )
            raise

    def init(self):
        """Create database indexes for optimal query performance

        Creates composite index for user+host_domain lookups, which is used by:
        - sunray.protected_host_user_list_report view (passkey_count subselect)
        - Any other queries filtering by user and host domain
        """
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS idx_sunray_passkey_user_host_domain
            ON sunray_passkey(user_id, host_domain)
        """)