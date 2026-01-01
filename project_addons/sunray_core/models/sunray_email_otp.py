# -*- coding: utf-8 -*-
import hashlib
import logging
import secrets

from odoo import models, fields, api
from datetime import timedelta


_logger = logging.getLogger(__name__)


class SunrayEmailOtp(models.Model):
    _name = 'sunray.email.otp'
    _description = 'Email One-Time Password'
    _rec_name = 'email'
    _order = 'create_date desc'

    # Request identification
    otp_request_id = fields.Char(
        string='OTP Request ID',
        required=True,
        index=True,
        help='Unique identifier for this OTP request (UUID format)'
    )

    # OTP code (hashed, never stored in plain text)
    otp_hash = fields.Char(
        string='OTP Hash (SHA-256)',
        required=True,
        help='SHA-256 hash of the OTP code'
    )

    # Browser binding token (hashed, for anti-phishing)
    browser_token_hash = fields.Char(
        string='Browser Token Hash (SHA-256)',
        required=True,
        help='SHA-256 hash of browser binding token to prevent phishing'
    )

    # User identification
    email = fields.Char(
        string='Email Address',
        required=True,
        index=True,
        help='Email address where OTP was sent (normalized to lowercase)'
    )

    user_id = fields.Many2one(
        'sunray.user',
        string='User',
        ondelete='cascade',
        help='User associated with this OTP request (null if email not found)'
    )

    # Host binding
    host_id = fields.Many2one(
        'sunray.host',
        required=True,
        ondelete='cascade',
        string='Protected Host',
        help='The host this OTP is valid for'
    )

    # Request metadata
    client_ip = fields.Char(
        string='Client IP',
        help='IP address of the client that requested the OTP'
    )

    user_agent = fields.Text(
        string='User Agent',
        help='User agent of the client that requested the OTP'
    )

    # Lifecycle
    expires_at = fields.Datetime(
        string='Expiration',
        required=True,
        help='OTP expiration timestamp'
    )

    attempts = fields.Integer(
        string='Validation Attempts',
        default=0,
        help='Number of failed validation attempts'
    )

    consumed = fields.Boolean(
        string='Consumed',
        default=False,
        help='Whether OTP has been successfully used'
    )

    consumed_at = fields.Datetime(
        string='Consumed At',
        help='When the OTP was successfully consumed'
    )

    # -------------------------------------------------------------------------
    # OTP Generation Methods
    # -------------------------------------------------------------------------

    @api.model
    def _generate_otp_code(self):
        """Generate an 8-character alphanumeric OTP code in AAAA-BBBB format.

        Character set: 23456789ABCDEFGHJKMNPQRSTUVWXYZ (excludes 0, O, I, L, 1)
        Entropy: 32^8 = ~40 bits

        Returns:
            str: Formatted OTP code like 'A2B3-C4D5'
        """
        chars = '23456789ABCDEFGHJKMNPQRSTUVWXYZ'
        code_chars = [secrets.choice(chars) for _ in range(8)]
        # Format: AAAA-BBBB
        return f"{''.join(code_chars[:4])}-{''.join(code_chars[4:])}"

    @api.model
    def _generate_browser_token(self):
        """Generate a browser binding token for anti-phishing protection.

        Format: srbt_ prefix + 32 hex characters (16 random bytes)
        Entropy: 128 bits

        Returns:
            str: Browser token like 'srbt_7f3a9c2e1d4b8f6a0123456789abcdef'
        """
        random_bytes = secrets.token_hex(16)
        return f"srbt_{random_bytes}"

    @api.model
    def _normalize_code_for_hashing(self, code_value):
        """Normalize OTP code for consistent hashing.

        Removes dashes and spaces, converts to uppercase.

        Args:
            code_value: Raw OTP code from input

        Returns:
            str: Normalized code ready for hashing
        """
        return code_value.replace('-', '').replace(' ', '').upper()

    @api.model
    def _hash_value(self, value):
        """Hash a value using SHA-256.

        Args:
            value: String value to hash

        Returns:
            str: SHA-256 hash prefixed with 'sha256:'
        """
        hash_obj = hashlib.sha256(value.encode('utf-8'))
        return f"sha256:{hash_obj.hexdigest()}"

    # -------------------------------------------------------------------------
    # OTP Creation
    # -------------------------------------------------------------------------

    @api.model
    def create_email_otp(self, email, host_id, browser_token_hash, client_ip=None, user_agent=None, validity_seconds=300):
        """Create an email OTP request.

        This method is timing-safe: it returns the same structure whether or not
        the email exists, to prevent email enumeration attacks.

        Args:
            email: Email address (will be normalized to lowercase)
            host_id: ID of the protected host
            browser_token_hash: SHA-256 hash of browser token (generated by worker)
            client_ip: Client IP address
            user_agent: Client user agent string
            validity_seconds: OTP validity duration in seconds (default: 300 = 5 min)

        Returns:
            dict: {
                'otp_request_id': str,
                'expires_at': datetime,
                'resend_available_at': datetime,
                'user_exists': bool,  # Internal only, not exposed to client
                'otp_obj': record or None  # Internal only
            }
        """
        # Normalize email
        email_normalized = email.strip().lower()

        # Generate OTP request ID
        otp_request_id = f"otp_req_{secrets.token_hex(16)}"

        # Generate OTP code (browser token is generated by worker, hash provided)
        otp_code = self._generate_otp_code()

        # Hash OTP code (browser_token_hash already provided by worker)
        otp_hash = self._hash_value(self._normalize_code_for_hashing(otp_code))

        # Calculate expiration
        now = fields.Datetime.now()
        expires_at = now + timedelta(seconds=validity_seconds)
        resend_cooldown_s = 60  # TODO: Get from host config
        resend_available_at = now + timedelta(seconds=resend_cooldown_s)

        # Look up user by email
        host_obj = self.env['sunray.host'].browse(host_id)
        user_obj = self.env['sunray.user'].search([
            ('email', '=ilike', email_normalized),
            ('is_active', '=', True),
            ('host_ids', 'in', [host_id])
        ], limit=1)

        user_exists = bool(user_obj)
        otp_obj = None

        if user_exists:
            # Create OTP record
            otp_obj = self.create({
                'otp_request_id': otp_request_id,
                'otp_hash': otp_hash,
                'browser_token_hash': browser_token_hash,
                'email': email_normalized,
                'user_id': user_obj.id,
                'host_id': host_id,
                'client_ip': client_ip,
                'user_agent': user_agent,
                'expires_at': expires_at,
            })

            # Log OTP request
            self.env['sunray.audit.log'].create_audit_event(
                event_type='auth.email_otp_requested',
                details={
                    'email': email_normalized,
                    'host': host_obj.domain,
                    'otp_request_id': otp_request_id,
                    'validity_seconds': validity_seconds,
                },
                severity='info',
                sunray_user_id=user_obj.id,
                username=user_obj.username,
                ip_address=client_ip,
                user_agent=user_agent
            )

            # Return the plain OTP code for email sending
            result_otp_code = otp_code
        else:
            # User not found - perform equivalent processing for timing safety
            # Create a dummy record that we immediately delete (or just skip)
            # Log internal event
            self.env['sunray.audit.log'].create_audit_event(
                event_type='auth.email_otp_requested_unknown',
                details={
                    'email': email_normalized,
                    'host': host_obj.domain,
                    'otp_request_id': otp_request_id,
                },
                severity='info',
                ip_address=client_ip,
                user_agent=user_agent
            )
            result_otp_code = None

        return {
            'otp_request_id': otp_request_id,
            'expires_at': expires_at,
            'resend_available_at': resend_available_at,
            'user_exists': user_exists,
            'otp_obj': otp_obj,
            'otp_code': result_otp_code,  # Only set if user exists (for email sending)
        }

    # -------------------------------------------------------------------------
    # OTP Validation
    # -------------------------------------------------------------------------

    @api.model
    def validate_email_otp(self, email, otp_code, otp_request_id, browser_token_hash,
                           host_domain, client_ip=None, user_agent=None, max_attempts=5):
        """Validate an email OTP code with browser token binding.

        Args:
            email: Email address used for OTP request
            otp_code: OTP code entered by user
            otp_request_id: OTP request identifier
            browser_token_hash: SHA-256 hash of browser token from cookie (computed by worker)
            host_domain: Domain of the protected host
            client_ip: Client IP address
            user_agent: Client user agent string
            max_attempts: Maximum validation attempts before lockout

        Returns:
            dict: {
                'valid': bool,
                'user_id': int or None,
                'username': str or None,
                'session_duration_s': int or None,
                'error_code': str or None
            }
        """
        result = {
            'valid': False,
            'user_id': None,
            'username': None,
            'session_duration_s': None,
            'error_code': None
        }

        # Normalize inputs (browser_token_hash already computed by worker)
        email_normalized = email.strip().lower()
        otp_code_normalized = self._normalize_code_for_hashing(otp_code)
        otp_hash = self._hash_value(otp_code_normalized)

        # Find host
        host_obj = self.env['sunray.host'].search([('domain', '=', host_domain)], limit=1)
        if not host_obj:
            result['error_code'] = 'host_not_found'
            return result

        # Find OTP record
        otp_obj = self.search([
            ('otp_request_id', '=', otp_request_id),
            ('email', '=', email_normalized),
            ('host_id', '=', host_obj.id)
        ], limit=1)

        if not otp_obj:
            result['error_code'] = 'otp_not_found'
            self._log_validation_failure('auth.email_otp_failed', {
                'email': email_normalized,
                'host': host_domain,
                'reason': 'OTP request not found',
                'otp_request_id': otp_request_id,
            }, client_ip, user_agent)
            return result

        # Check if already consumed
        if otp_obj.consumed:
            result['error_code'] = 'already_consumed'
            self._log_validation_failure('auth.email_otp_failed', {
                'email': email_normalized,
                'host': host_domain,
                'reason': 'OTP already consumed',
                'otp_request_id': otp_request_id,
            }, client_ip, user_agent, otp_obj.user_id)
            return result

        # Check expiration
        if otp_obj.expires_at < fields.Datetime.now():
            result['error_code'] = 'expired'
            self._log_validation_failure('auth.email_otp_expired', {
                'email': email_normalized,
                'host': host_domain,
                'reason': 'OTP expired',
                'otp_request_id': otp_request_id,
                'expired_at': otp_obj.expires_at.isoformat(),
            }, client_ip, user_agent, otp_obj.user_id)
            return result

        # Check attempt count
        if otp_obj.attempts >= max_attempts:
            result['error_code'] = 'max_attempts_exceeded'
            self._log_validation_failure('security.email_otp_lockout', {
                'email': email_normalized,
                'host': host_domain,
                'reason': 'Maximum attempts exceeded',
                'otp_request_id': otp_request_id,
                'attempts': otp_obj.attempts,
            }, client_ip, user_agent, otp_obj.user_id, severity='warning')
            return result

        # Verify browser token (anti-phishing check)
        if otp_obj.browser_token_hash != browser_token_hash:
            otp_obj.attempts += 1
            result['error_code'] = 'browser_token_mismatch'
            self._log_validation_failure('security.email_otp_browser_mismatch', {
                'email': email_normalized,
                'host': host_domain,
                'reason': 'Browser token mismatch - potential phishing attempt',
                'otp_request_id': otp_request_id,
                'attempts': otp_obj.attempts,
            }, client_ip, user_agent, otp_obj.user_id, severity='warning')
            return result

        # Verify OTP code
        if otp_obj.otp_hash != otp_hash:
            otp_obj.attempts += 1
            result['error_code'] = 'invalid_code'
            self._log_validation_failure('auth.email_otp_failed', {
                'email': email_normalized,
                'host': host_domain,
                'reason': 'Invalid OTP code',
                'otp_request_id': otp_request_id,
                'attempts': otp_obj.attempts,
            }, client_ip, user_agent, otp_obj.user_id)
            return result

        # All checks passed - mark as consumed
        otp_obj.write({
            'consumed': True,
            'consumed_at': fields.Datetime.now()
        })

        # Get session duration from host config
        session_duration_s = host_obj.email_login_session_duration_s or host_obj.session_duration_s

        # Log successful validation
        self.env['sunray.audit.log'].create_audit_event(
            event_type='auth.email_otp_validated',
            details={
                'email': email_normalized,
                'host': host_domain,
                'otp_request_id': otp_request_id,
            },
            severity='info',
            sunray_user_id=otp_obj.user_id.id if otp_obj.user_id else None,
            username=otp_obj.user_id.username if otp_obj.user_id else None,
            ip_address=client_ip,
            user_agent=user_agent
        )

        result.update({
            'valid': True,
            'user_id': otp_obj.user_id.id if otp_obj.user_id else None,
            'username': otp_obj.user_id.username if otp_obj.user_id else None,
            'session_duration_s': session_duration_s,
        })

        return result

    def _log_validation_failure(self, event_type, details, client_ip, user_agent,
                                 user_id=None, severity='info'):
        """Helper to log validation failures."""
        self.env['sunray.audit.log'].create_audit_event(
            event_type=event_type,
            details=details,
            severity=severity,
            sunray_user_id=user_id.id if user_id else None,
            username=user_id.username if user_id else None,
            ip_address=client_ip,
            user_agent=user_agent
        )

    # -------------------------------------------------------------------------
    # Cleanup
    # -------------------------------------------------------------------------

    @api.model
    def cleanup_expired(self):
        """Cron job to clean expired and consumed OTPs."""
        # Clean expired OTPs (older than 24 hours)
        cutoff = fields.Datetime.now() - timedelta(hours=24)
        expired_objs = self.search([
            '|',
            ('expires_at', '<', cutoff),
            '&', ('consumed', '=', True), ('consumed_at', '<', cutoff)
        ])

        if expired_objs:
            count = len(expired_objs)
            self.env['sunray.audit.log'].create_audit_event(
                event_type='auth.email_otp_cleanup',
                details={
                    'count': count,
                    'reason': 'Scheduled cleanup of expired/consumed OTPs'
                },
                event_source='system',
                severity='info'
            )
            expired_objs.unlink()
            _logger.info(f"Cleaned up {count} expired/consumed email OTPs")

        return True
