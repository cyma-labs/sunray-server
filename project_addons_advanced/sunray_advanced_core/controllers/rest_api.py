# -*- coding: utf-8 -*-
import json
import logging
from datetime import datetime, timedelta

from odoo import http, fields
from odoo.http import request
from odoo.exceptions import ValidationError, UserError
from odoo.addons.sunray_core.controllers.rest_api import SunrayRESTController

_logger = logging.getLogger(__name__)


class AdvancedRestController(SunrayRESTController):
    """
    Extends base REST API with Remote Authentication features.
    This is a PAID feature available only in Sunray Advanced Core.

    New endpoints:
    - POST /sunray-srvr/v1/sessions/remote - Create remote session
    - GET /sunray-srvr/v1/sessions/list/<int:user_id> - List user sessions
    - DELETE /sunray-srvr/v1/sessions/<string:session_id> - Terminate session

    Extended endpoints:
    - GET /sunray-srvr/v1/config - Adds remote_auth object to response
    """

    # ==========================================
    # Remote Session Creation
    # ==========================================

    @http.route('/sunray-srvr/v1/sessions/remote', type='json', auth='none', methods=['POST'], csrf=False)
    def create_remote_session(self, **kwargs):
        """
        Create remote session after Worker has verified WebAuthn credential locally.

        This endpoint is called by the Worker after it has performed local WebAuthn
        verification. The Server trusts the Worker's verification and creates the session.

        Request Body:
        {
            "worker_id": "sunray-worker-01",
            "protected_host_id": 123,  # Maps to host_id internally
            "user_id": 456,
            "session_duration": 3600,  # Optional, uses host default if not provided
            "device_info": {
                "user_agent": "Mozilla/5.0...",
                "ip_address": "192.168.1.50"
            }
        }

        Response:
        {
            "success": true,
            "session_id": "sess_abc123",
            "user_id": 456,
            "expires_at": "2025-10-17T13:00:00Z",
            "session_type": "remote"
        }
        """
        try:
            # 1. Authenticate Worker
            if not self._authenticate_api(request):
                return self._error_response('Unauthorized', 401)

            # 2. Parse and validate request
            worker_id = kwargs.get('worker_id')
            protected_host_id = kwargs.get('protected_host_id')  # API uses protected_host_id
            user_id = kwargs.get('user_id')
            session_duration = kwargs.get('session_duration')
            device_info = kwargs.get('device_info', {})

            # Validate required fields
            if not all([worker_id, protected_host_id, user_id, device_info]):
                return self._error_response('Missing required fields', 400)

            # 3. Setup request context for audit
            self._setup_request_context(worker_id=worker_id)

            # 4. Validate Host (using internal field name host_id)
            host = request.env['sunray.host'].sudo().browse(protected_host_id)
            if not host.exists():
                return self._error_response('Host not found', 404)

            if not host.remote_auth_enabled:
                return self._error_response('Remote authentication not enabled for this host', 501)

            # 5. Validate session duration
            if not host.remote_auth_session_ttl or not host.remote_auth_max_session_ttl:
                _logger.error(f'Missing remote auth TTL config for host {host.domain}')
                return self._error_response('Remote auth TTL not configured for this host', 500)

            default_duration = host.remote_auth_session_ttl
            max_duration = host.remote_auth_max_session_ttl
            requested_duration = session_duration or default_duration

            if requested_duration > max_duration:
                return self._error_response(
                    f'Session duration cannot exceed {max_duration} seconds', 422
                )

            # 6. Get user (Worker has already verified WebAuthn credential locally)
            user = request.env['sunray.user'].sudo().browse(user_id)
            if not user.exists():
                return self._error_response('User not found', 404)

            # 7. Create remote session
            session_id = self._generate_session_id()
            expires_at = datetime.utcnow() + timedelta(seconds=requested_duration)

            # Store session in database (map protected_host_id to host_id)
            session = request.env['sunray.session'].sudo().create({
                'session_id': session_id,
                'user_id': user.id,
                'host_id': protected_host_id,  # Maps protected_host_id → host_id
                'session_type': 'remote',
                'created_via': json.dumps(device_info),
                'created_at': fields.Datetime.now(),
                'expires_at': expires_at,
                'last_activity': fields.Datetime.now()
            })

            # 8. Create audit event
            request.env['sunray.audit.log'].sudo().create_audit_event(
                event_type='remote_auth.session_created',
                details={
                    'session_id': session_id,
                    'worker_id': worker_id,
                    'session_duration': requested_duration,
                    'device_info': device_info,
                    'host_domain': host.domain
                },
                severity='info',
                sunray_user_id=user.id,
                ip_address=device_info.get('ip_address'),
                user_agent=device_info.get('user_agent'),
                request_id=request.env.context.get('request_id'),
                event_source='remote_auth',
                username=user.username
            )

            # 9. Return response (NO JWT generation - Worker handles all JWTs)
            return self._json_response({
                'success': True,
                'session_id': session_id,
                'user_id': user.id,
                'expires_at': expires_at.isoformat() + 'Z',
                'session_type': 'remote'
            })

        except Exception as e:
            _logger.exception('Error creating remote session')
            return self._error_response(str(e), 500)

    # ==========================================
    # Session Listing
    # ==========================================

    @http.route('/sunray-srvr/v1/sessions/list/<int:user_id>', type='json', auth='none', methods=['GET'])
    def list_user_sessions(self, user_id, **kwargs):
        """
        List all active sessions for a user.

        This endpoint is called by the Worker on behalf of the mobile device.
        Mobile devices never connect directly to the Server.

        Path Parameters:
        - user_id: User database ID

        Response:
        [{
            "session_id": "sess_abc123",
            "session_type": "remote",
            "created_at": "2025-10-17T10:00:00Z",
            "expires_at": "2025-10-17T12:00:00Z",
            "last_activity": "2025-10-17T11:30:00Z",
            "device_info": {
                "user_agent": "Chrome/120.0 on Windows",
                "ip_address": "192.168.1.1",
                "platform": "Windows"
            },
            "protected_host": "phost.io"
        }]
        """
        try:
            # 1. Authenticate Worker (only Workers can call this)
            if not self._authenticate_api():
                return self._error_response('Unauthorized - Worker API key required', 401)

            worker_id = request.httprequest.headers.get('X-Worker-ID')
            self._setup_request_context(worker_id=worker_id)

            # 2. Query all active sessions for user
            sessions = request.env['sunray.session'].sudo().search([
                ('user_id', '=', user_id),
                ('expires_at', '>', fields.Datetime.now())
            ], order='created_at desc')

            # 3. Format response
            session_list = []
            for session in sessions:
                device_info = session.get_device_info() if hasattr(session, 'get_device_info') else {}

                # Parse User-Agent to extract browser and OS
                user_agent_parsed = self._parse_user_agent(device_info.get('user_agent', ''))

                session_data = {
                    'session_id': session.session_id,
                    'session_type': getattr(session, 'session_type', 'normal'),
                    'created_at': session.created_at.isoformat() + 'Z' if session.created_at else None,
                    'expires_at': session.expires_at.isoformat() + 'Z' if session.expires_at else None,
                    'last_activity': session.last_activity.isoformat() + 'Z' if session.last_activity else None,
                    'device_info': {
                        'user_agent': user_agent_parsed,
                        'ip_address': device_info.get('ip_address', 'Unknown'),
                        'platform': self._extract_platform(device_info.get('user_agent', ''))
                    },
                    'protected_host': session.host_id.domain if session.host_id else 'Unknown'
                }
                session_list.append(session_data)

            # 4. Audit log the session listing
            if sessions:
                request.env['sunray.audit.log'].sudo().create_audit_event(
                    event_type='remote_auth.session_listed',
                    details={'user_id': user_id, 'session_count': len(sessions)},
                    severity='info',
                    sunray_user_id=user_id,
                    request_id=request.env.context.get('request_id'),
                    event_source='remote_auth'
                )

            return self._json_response(session_list)

        except Exception as e:
            _logger.exception('Error listing user sessions')
            return self._error_response(str(e), 500)

    # ==========================================
    # Session Termination
    # ==========================================

    @http.route('/sunray-srvr/v1/sessions/<string:session_id>', type='json', auth='none', methods=['DELETE'])
    def terminate_session(self, session_id, **kwargs):
        """
        Terminate a specific session.

        This endpoint is called by the Worker on behalf of the user.
        The Worker validates the user's session management JWT and includes X-User-ID.

        Path Parameters:
        - session_id: Session identifier to terminate

        Headers:
        - Authorization: Bearer {ADMIN_API_KEY}
        - X-Worker-ID: Worker identifier
        - X-User-ID: User ID (validated by Worker)

        Response:
        {
            "success": true,
            "message": "Session terminated successfully",
            "session_id": "sess_abc123"
        }
        """
        try:
            # 1. Authenticate Worker
            if not self._authenticate_api():
                return self._error_response('Unauthorized - Worker API key required', 401)

            worker_id = request.httprequest.headers.get('X-Worker-ID')
            user_id = request.httprequest.headers.get('X-User-ID')

            if not user_id:
                return self._error_response('X-User-ID header required', 400)

            self._setup_request_context(worker_id=worker_id)

            # 2. Find session to terminate
            session = request.env['sunray.session'].sudo().search([
                ('session_id', '=', session_id)
            ], limit=1)

            if not session:
                return self._error_response('Session not found', 404)

            # 3. Authorize (Worker validated JWT, we trust X-User-ID)
            if session.user_id.id != int(user_id):
                return self._error_response('Cannot terminate other user\'s sessions', 403)

            # 4. Capture session info before deletion
            session_type = getattr(session, 'session_type', 'normal')
            protected_host = session.host_id.domain if session.host_id else 'Unknown'
            username = session.user_id.username

            # 5. Delete session
            session.unlink()

            # 6. Audit log
            request.env['sunray.audit.log'].sudo().create_audit_event(
                event_type='remote_auth.session_terminated',
                details={
                    'session_id': session_id,
                    'session_type': session_type,
                    'protected_host': protected_host,
                    'terminated_by': 'user'
                },
                severity='info',
                sunray_user_id=int(user_id),
                request_id=request.env.context.get('request_id'),
                event_source='remote_auth',
                username=username
            )

            # 7. Return success
            return self._json_response({
                'success': True,
                'message': 'Session terminated successfully',
                'session_id': session_id
            })

        except Exception as e:
            _logger.exception('Error terminating session')
            return self._error_response(str(e), 500)

    # ==========================================
    # Helper Methods
    # ==========================================

    def _parse_user_agent(self, ua_string):
        """
        Parse User-Agent string to human-readable format.

        Example: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0"
        Returns: "Chrome 120.0 on Windows"
        """
        if not ua_string:
            return 'Unknown Browser'

        # Basic parsing - can be enhanced with ua-parser library if available
        browser = 'Unknown Browser'
        if 'Chrome' in ua_string:
            browser = 'Chrome'
            # Try to extract version
            if 'Chrome/' in ua_string:
                parts = ua_string.split('Chrome/')
                if len(parts) > 1:
                    version = parts[1].split(' ')[0].split('.')[0]
                    browser = f'Chrome {version}'
        elif 'Safari' in ua_string and 'Chrome' not in ua_string:
            browser = 'Safari'
        elif 'Firefox' in ua_string:
            browser = 'Firefox'
            if 'Firefox/' in ua_string:
                parts = ua_string.split('Firefox/')
                if len(parts) > 1:
                    version = parts[1].split(' ')[0].split('.')[0]
                    browser = f'Firefox {version}'

        platform = self._extract_platform(ua_string)
        return f"{browser} on {platform}"

    def _extract_platform(self, ua_string):
        """Extract platform/OS from User-Agent string."""
        if not ua_string:
            return 'Unknown'

        if 'Windows' in ua_string:
            return 'Windows'
        elif 'Mac OS X' in ua_string:
            return 'macOS'
        elif 'iPhone' in ua_string:
            return 'iOS'
        elif 'iPad' in ua_string:
            return 'iPadOS'
        elif 'Android' in ua_string:
            return 'Android'
        elif 'Linux' in ua_string:
            return 'Linux'
        else:
            return 'Unknown'