# -*- coding: utf-8 -*-
from odoo import http, fields
from odoo.http import request
from odoo.addons.sunray_core.controllers.rest_api import SunrayRESTController
import logging
import json

_logger = logging.getLogger(__name__)


class UserValidationController(SunrayRESTController):
    """API endpoints for user validation and authentication method discovery

    Inherits from SunrayRESTController to reuse:
    - _authenticate_api(): Worker authentication with auto-registration
    - _json_response(): Standard JSON responses
    - _error_response(): Error responses
    - _setup_request_context(): Audit logging context setup
    """

    @http.route('/sunray-srvr/v1/users/validate',
                type='http', auth='none', methods=['POST'], cors='*', csrf=False)
    def validate_user(self, **kwargs):
        """
        Validate user and return available authentication methods

        This endpoint is used by Workers to:
        - Check if a user exists and is active
        - Determine what authentication methods are available
        - Display appropriate UI

        Request:
        {
            "username": "john@example.com",
            "host": "protected-app.example.com"
        }

        Response:
        {
            "user_exists": true,
            "has_passkey": false,
            "has_valid_token": true,
            "remote_login_allowed": true
        }

        The Worker uses these 4 booleans to determine which UI to display:
        - has_passkey: Show "Sign in with Passkey" button
        - remote_login_allowed: Deployment mode active (allow temporary access)
        - has_valid_token: Show enrollment invitation link
        """
        # Authenticate worker using parent method
        api_key_obj = self._authenticate_api(request)
        if not api_key_obj:
            return self._error_response('Unauthorized', 401)

        # Setup audit context (automatic request_id, event_source, worker_id)
        self._setup_request_context(request)

        # Parse request
        try:
            data = json.loads(request.httprequest.data)
        except (ValueError, TypeError):
            return self._error_response('Invalid JSON', 400)
        host_domain = data.get('host')
        username = data.get('username')

        if not host_domain or not username:
            return self._json_response({
                'error': 'host and username required',
                'user_exists': False
            })

        # Extract IP from request (server-side only, never trust client)
        ip_address = request.httprequest.headers.get('CF-Connecting-IP') or \
                     request.httprequest.environ.get('REMOTE_ADDR') or \
                     'unknown'

        # Find host
        host_obj = request.env['sunray.host'].sudo().search([
            ('domain', '=', host_domain),
            ('is_active', '=', True)
        ], limit=1)

        if not host_obj:
            _logger.warning(f"User validation: host not found: {host_domain}")
            return self._json_response({
                'error': 'Host not found',
                'user_exists': False
            })

        # Find user
        user_obj = request.env['sunray.user'].sudo().search([
            ('username', '=', username),
            ('host_ids', 'in', [host_obj.id]),
            ('is_active', '=', True)
        ], limit=1)

        if not user_obj:
            # Log unknown username attempt (for security monitoring)
            request.env['sunray.audit.log'].sudo().create_audit_event(
                event_type='user.validation.unknown_user',
                severity='info',
                details={
                    'username': username,
                    'host': host_domain,
                    'ip_address': ip_address
                }
            )
            return self._json_response({
                'user_exists': False,
                'has_passkey': False,
                'has_valid_token': False,
                'remote_login_allowed': False
            })

        # Check passkey status - only count passkeys registered for this host
        host_passkeys = user_obj.passkey_ids.filtered(lambda p: p.host_domain == host_domain)
        has_passkey = len(host_passkeys) > 0

        # Check for valid setup token - only for this specific host
        today = fields.Date.today()
        valid_token_obj = request.env['sunray.setup.token'].sudo().search([
            ('user_id', '=', user_obj.id),
            ('host_id', '=', host_obj.id),
            ('consumed', '=', False),
            ('expires_at', '>=', today)
        ], limit=1)
        has_valid_token = bool(valid_token_obj)

        # Check if remote login is allowed (deployment mode or other policies)
        # This checks if the host is in deployment state
        remote_login_allowed = host_obj.state == 'deployment'

        # Audit log the validation
        request.env['sunray.audit.log'].sudo().create_audit_event(
            event_type='user.validation.success',
            severity='info',
            details={
                'username': username,
                'host': host_domain,
                'has_passkey': has_passkey,
                'has_valid_token': has_valid_token,
                'remote_login_allowed': remote_login_allowed,
                'user_id': user_obj.id,
                'ip_address': ip_address
            }
        )

        return self._json_response({
            'user_exists': True,
            'has_passkey': has_passkey,
            'has_valid_token': has_valid_token,
            'remote_login_allowed': remote_login_allowed
        })
