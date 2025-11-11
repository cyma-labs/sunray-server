# -*- coding: utf-8 -*-

from odoo import http, fields
from odoo.http import request, Response
from odoo.exceptions import UserError, ValidationError
from psycopg2 import IntegrityError
import hashlib
import json
import logging
import cbor2
import base64

from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)


class SunrayRESTController(http.Controller):
    """REST API endpoints for Cloudflare Worker communication"""
    
    def _setup_request_context(self, req):
        """Setup request context for audit logging with implicit context injection
        
        This method extracts request correlation data and IMPLICITLY injects it into 
        the Odoo environment context. This allows all subsequent audit log entries 
        within the same request to automatically inherit correlation fields without 
        explicit passing.
        
        Context fields injected:
        - sunray_request_id: Unique request identifier for correlation
        - sunray_event_source: Source of the event (api/ui/worker/cli/system)  
        - sunray_worker_id: Worker identifier if present in headers
        
        The audit log's create() method override automatically uses these context 
        values if the fields are not explicitly provided, enabling transparent 
        request correlation across all audit events.
        
        Args:
            req: The HTTP request object
            
        Returns:
            dict: Contains request_id, event_source, and worker_id for explicit use
                  Note: Even though returned, these values are already in context
        
        Example:
            context_data = self._setup_request_context(request)
            # After this call, any audit event created will automatically have:
            # - request_id from context (if not explicitly passed)
            # - event_source from context (if not explicitly passed)
            
            # This audit event automatically gets request_id and event_source:
            request.env['sunray.audit.log'].sudo().create_audit_event(
                event_type='some.event',
                details={'key': 'value'}
                # request_id and event_source are pulled from context automatically
            )
        """
        # Get or create request ID
        audit_model = request.env['sunray.audit.log'].sudo()
        request_id = audit_model._get_or_create_request_id(req)
        
        # Detect event source
        event_source = audit_model._detect_source_from_request(req)
        
        # Extract worker ID
        worker_id = req.httprequest.headers.get('X-Worker-ID')
        
        # Update context with correlation data
        context_updates = {
            'sunray_request_id': request_id,
            'sunray_event_source': event_source,
        }
        
        if worker_id:
            context_updates['sunray_worker_id'] = worker_id
            
        request.env.context = dict(request.env.context, **context_updates)
        
        return {
            'request_id': request_id,
            'event_source': event_source,
            'worker_id': worker_id
        }
    
    def _authenticate_api(self, req):
        """Authenticate API request using Bearer token
        
        Returns:
            api_key_obj if authenticated, False otherwise
        """
        auth_header = req.httprequest.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return False
        
        token = auth_header[7:]
        # Validate against sunray.api.key model
        api_key_obj = request.env['sunray.api.key'].sudo().search([
            ('key', '=', token),
            ('is_active', '=', True)
        ])
        
        if api_key_obj:
            # Get worker info from headers
            worker_name = req.httprequest.headers.get('X-Worker-ID')
            worker_version = req.httprequest.headers.get('X-Worker-Version')
            ip_address = req.httprequest.environ.get('REMOTE_ADDR')
            
            # Track usage and auto-register worker if needed
            api_key_obj.track_usage(
                worker_name=worker_name,
                ip_address=ip_address
            )
            return api_key_obj
        return False
    
    def _json_response(self, data, status=200):
        """Return JSON response without JSON-RPC wrapper"""
        return Response(
            json.dumps(data, indent=2, default=str),
            content_type='application/json',
            status=status
        )
    
    def _error_response(self, message, status=400):
        """Return error response"""
        return self._json_response({'error': message}, status)
    
    @http.route('/sunray-srvr/v1/status', type='http', auth='none', methods=['GET'], cors='*')
    def get_status(self, **kwargs):
        """Health check endpoint - no authentication required"""
        # Collect all IP information from headers
        headers = request.httprequest.headers
        ip_info = {
            # Standard IP
            'remote_addr': request.httprequest.environ.get('REMOTE_ADDR'),
            
            # X-Forwarded headers (standard proxy headers)
            'x_forwarded_for': headers.get('X-Forwarded-For'),
            'x_real_ip': headers.get('X-Real-IP'),
            
            # Cloudflare specific headers
            'cf_connecting_ip': headers.get('CF-Connecting-IP'),
            'cf_ipcountry': headers.get('CF-IPCountry'),
            'cf_ray': headers.get('CF-RAY'),
            'cf_visitor': headers.get('CF-Visitor'),
            
            # Cloudflared tunnel headers
            'cf_access_authenticated_user_email': headers.get('CF-Access-Authenticated-User-Email'),
            'cf_access_jwt_assertion': headers.get('CF-Access-JWT-Assertion') and 'present',
            
            # Other useful headers
            'host': headers.get('Host'),
            'user_agent': headers.get('User-Agent'),
            'origin': headers.get('Origin'),
            'referer': headers.get('Referer')
        }
        
        # Clean up None values
        ip_info = {k: v for k, v in ip_info.items() if v is not None}
        
        status_data = {
            'status': 'healthy',
            'service': 'sunray-server',
            'version': '1.0.0',
            'timestamp': fields.Datetime.now().isoformat(),
            'caller_info': ip_info,
            'endpoints': {
                'status': '/sunray-srvr/v1/status',
                'health': '/sunray-srvr/v1/health',
                'config': '/sunray-srvr/v1/config',
                'users': '/sunray-srvr/v1/users/*',
                'sessions': '/sunray-srvr/v1/sessions/*',
                'setup_tokens': '/sunray-srvr/v1/setup-tokens/*',
                'security_events': '/sunray-srvr/v1/security-events',
                'webhooks': '/sunray-srvr/v1/webhooks/*'
            }
        }
        
        return self._json_response(status_data)
    
    @http.route('/sunray-srvr/v1/health', type='http', auth='none', methods=['GET'], cors='*')
    def health_check(self, **kwargs):
        """Detailed health check with optional authentication"""
        health = {
            'status': 'healthy',
            'timestamp': fields.Datetime.now().isoformat()
        }
        
        # Add detailed info if authenticated
        api_key_obj = self._authenticate_api(request)
        if api_key_obj:
            try:
                # Check database connectivity
                request.env['sunray.host'].sudo().search_count([])
                health['database'] = 'connected'
                
                # Count resources
                health['resources'] = {
                    'hosts': request.env['sunray.host'].sudo().search_count([('is_active', '=', True)]),
                    'users': request.env['sunray.user'].sudo().search_count([('is_active', '=', True)]),
                    'active_sessions': request.env['sunray.session'].sudo().search_count([
                        ('is_active', '=', True),
                        ('expires_at', '>', fields.Datetime.now())
                    ]),
                    'api_keys': request.env['sunray.api.key'].sudo().search_count([('is_active', '=', True)])
                }
            except Exception as e:
                health['status'] = 'degraded'
                health['error'] = str(e)
        
        return self._json_response(health)
    
    @http.route('/sunray-srvr/v1/setup-tokens/validate', type='http', auth='none', methods=['POST'], cors='*', csrf=False)
    def validate_setup_token(self, **kwargs):
        """Validate a setup token before WebAuthn registration
        
        This endpoint allows workers to validate setup tokens before initiating
        the WebAuthn registration ceremony, providing early feedback to users.
        
        Required Headers:
        - Authorization: Bearer <api-key>
        - X-Worker-ID: <worker-identifier>
        
        JSON Body:
        - username: User's username
        - token_hash: SHA-512 hash of setup token (prefixed with "sha512:")
        - client_ip: Client's IP address
        - host_domain: Domain being protected
        
        Returns:
        - {"valid": true} if token is valid
        - {"valid": false} if token is invalid
        """
        # Set up request context for audit logging
        context_data = self._setup_request_context(request)
        
        # Authenticate API request
        api_key_obj = self._authenticate_api(request)
        if not api_key_obj:
            return self._error_response('Unauthorized', 401)
        
        # Parse JSON body
        try:
            data = json.loads(request.httprequest.get_data())
        except (ValueError, TypeError):
            return self._error_response('Invalid JSON in request body', 400)
        
        # Extract required parameters
        username = data.get('username')
        token_hash = data.get('token_hash')
        client_ip = data.get('client_ip')
        host_domain = data.get('host_domain')
        
        # Get optional parameters from headers and body
        worker_id = context_data['worker_id']
        user_agent = request.httprequest.headers.get('User-Agent', '')
        
        # Validate required fields
        missing_fields = []
        if not username:
            missing_fields.append('username')
        if not token_hash:
            missing_fields.append('token_hash')
        if not client_ip:
            missing_fields.append('client_ip')
        if not host_domain:
            missing_fields.append('host_domain')
        
        if missing_fields:
            return self._error_response(f'Missing required fields: {", ".join(missing_fields)}', 400)
        
        # Call centralized validation method
        try:
            validation_result = request.env['sunray.setup.token'].validate_setup_token(
                username=username,
                token_hash=token_hash,
                host_domain=host_domain,
                client_ip=client_ip,
                user_agent=user_agent,
                worker_id=worker_id
            )
            
            # Return simple validation result
            return self._json_response({
                'valid': validation_result['valid']
            })
            
        except Exception as e:
            # Log unexpected errors
            _logger.error(f"Unexpected error in setup token validation: {str(e)}")
            
            # Create audit event for system error
            request.env['sunray.audit.log'].sudo().create_audit_event(
                event_type='token.validation.system_error',
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
            
            # Return generic error (don't expose internal details)
            return self._json_response({'valid': False})
    
    @http.route('/sunray-srvr/v1/config', type='http', auth='none', methods=['GET'], cors='*')
    def get_config(self, **kwargs):
        """Get configuration for Worker"""
        api_key_obj = self._authenticate_api(request)
        if not api_key_obj:
            return self._error_response('Unauthorized', 401)
        
        # Build configuration
        config = {
            'version': 4,  # Incremented for Access Rules support
            'generated_at': fields.Datetime.now().isoformat(),
            'hosts': request.env['sunray.host'].sudo().search([]).get_config_data()
        }
        
        # Setup request context and log config fetch
        context_data = self._setup_request_context(request)
        request.env['sunray.audit.log'].sudo().create_worker_event(
            event_type='config.fetched',
            details={'worker_id': context_data['worker_id']},
            sunray_worker=context_data['worker_id'],
            ip_address=request.httprequest.environ.get('REMOTE_ADDR')
        )
        
        return self._json_response(config)
    
    @http.route('/sunray-srvr/v1/config/register', type='http', auth='none', methods=['POST'], cors='*', csrf=False)
    def register_worker(self, **kwargs):
        """Register worker to a specific host and return host-specific configuration
        
        Requires:
        - hostname parameter: The hostname of the protected host
        - X-Worker-ID header: Worker identifier
        - Valid API key
        
        Returns:
        - Host-specific configuration data
        - Error if worker or host not found
        """
        api_key_obj = self._authenticate_api(request)
        if not api_key_obj:
            return self._error_response('Unauthorized', 401)
        
        # Get JSON data
        try:
            data = json.loads(request.httprequest.data) if request.httprequest.data else {}
        except json.JSONDecodeError:
            return self._error_response('Invalid JSON payload', 400)
        
        hostname = data.get('hostname') or request.params.get('hostname')
        if not hostname:
            return self._error_response('hostname parameter required', 400)
        
        # Get worker ID from header
        worker_name = request.httprequest.headers.get('X-Worker-ID')
        if not worker_name:
            return self._error_response('X-Worker-ID header required', 400)
        
        # Find the worker (should exist due to auto-registration in authentication)
        worker_obj = request.env['sunray.worker'].sudo().search([
            ('name', '=', worker_name)
        ], limit=1)
        
        if not worker_obj:
            # Audit log the failed registration attempt
            request.env['sunray.audit.log'].sudo().create_api_event(
                event_type='worker.registration_failed',
                api_key_id=api_key_obj.id,
                details={
                    'worker_name': worker_name,
                    'hostname': hostname,
                    'reason': 'Worker not found (auto-registration failed)'
                },
                ip_address=request.httprequest.environ.get('REMOTE_ADDR')
            )
            return self._error_response(f'Worker "{worker_name}" not found', 404)
        
        # Find the host
        host_obj = request.env['sunray.host'].sudo().search([
            ('domain', '=', hostname)
        ], limit=1)
        
        if not host_obj:
            # Audit log the failed registration attempt
            request.env['sunray.audit.log'].sudo().create_api_event(
                event_type='worker.registration_failed',
                api_key_id=api_key_obj.id,
                details={
                    'worker_id': worker_obj.id,
                    'worker_name': worker_name,
                    'hostname': hostname,
                    'reason': 'Host not found'
                },
                ip_address=request.httprequest.environ.get('REMOTE_ADDR')
            )
            return self._error_response(f'Host "{hostname}" not found', 404)
        
        # Handle worker-host binding with migration support
        if not host_obj.sunray_worker_id:
            # Host has no worker - bind immediately
            host_obj.sunray_worker_id = worker_obj.id
            
            # Audit log the binding
            request.env['sunray.audit.log'].sudo().create_api_event(
                event_type='worker.host_bound',
                api_key_id=api_key_obj.id,
                details={
                    'worker_id': worker_obj.id,
                    'worker_name': worker_name,
                    'host_id': host_obj.id,
                    'hostname': hostname
                },
                ip_address=request.httprequest.environ.get('REMOTE_ADDR')
            )
            
        elif host_obj.sunray_worker_id.id == worker_obj.id:
            # Same worker re-registering (idempotent operation)
            request.env['sunray.audit.log'].sudo().create_api_event(
                event_type='worker.re_registered',
                api_key_id=api_key_obj.id,
                details={
                    'worker_id': worker_obj.id,
                    'worker_name': worker_name,
                    'host_id': host_obj.id,
                    'hostname': hostname
                },
                ip_address=request.httprequest.environ.get('REMOTE_ADDR')
            )
            
        elif host_obj.pending_worker_name == worker_name:
            # Pending worker registering - perform migration
            old_worker = host_obj.sunray_worker_id
            migration_duration = None
            
            # Calculate migration duration if available
            if host_obj.migration_requested_at:
                delta = fields.Datetime.now() - host_obj.migration_requested_at
                migration_duration = str(delta)
            
            # Audit log migration start
            request.env['sunray.audit.log'].sudo().create_api_event(
                event_type='worker.migration_started',
                api_key_id=api_key_obj.id,
                details={
                    'worker_id': worker_obj.id,
                    'worker_name': worker_name,
                    'host_id': host_obj.id,
                    'hostname': hostname,
                    'old_worker_id': old_worker.id,
                    'old_worker_name': old_worker.name,
                    'migration_requested_at': host_obj.migration_requested_at.isoformat() if host_obj.migration_requested_at else None
                },
                ip_address=request.httprequest.environ.get('REMOTE_ADDR')
            )
            
            # Perform the migration
            host_obj.write({
                'sunray_worker_id': worker_obj.id,
                'pending_worker_name': False,
                'migration_requested_at': False,
                'last_migration_ts': fields.Datetime.now()
            })
            
            # Audit log successful migration
            request.env['sunray.audit.log'].sudo().create_api_event(
                event_type='worker.migration_completed',
                api_key_id=api_key_obj.id,
                details={
                    'worker_id': worker_obj.id,
                    'worker_name': worker_name,
                    'host_id': host_obj.id,
                    'hostname': hostname,
                    'old_worker_id': old_worker.id,
                    'old_worker_name': old_worker.name,
                    'migration_duration': migration_duration
                },
                ip_address=request.httprequest.environ.get('REMOTE_ADDR')
            )
            
        else:
            # Unauthorized worker trying to register
            request.env['sunray.audit.log'].sudo().create_api_event(
                event_type='worker.registration_blocked',
                api_key_id=api_key_obj.id,
                details={
                    'worker_id': worker_obj.id,
                    'worker_name': worker_name,
                    'host_id': host_obj.id,
                    'hostname': hostname,
                    'current_worker_id': host_obj.sunray_worker_id.id,
                    'current_worker_name': host_obj.sunray_worker_id.name,
                    'pending_worker': host_obj.pending_worker_name or 'none',
                    'reason': 'Unauthorized worker registration attempt'
                },
                ip_address=request.httprequest.environ.get('REMOTE_ADDR')
            )
            
            # Return detailed error response
            error_details = {
                'error': 'registration_blocked',
                'message': 'Host is bound to another worker',
                'details': {
                    'current_worker': host_obj.sunray_worker_id.name,
                    'pending_worker': host_obj.pending_worker_name or None,
                    'host': hostname,
                    'action_required': 'Contact administrator for migration approval'
                },
                'timestamp': fields.Datetime.now().isoformat()
            }
            return self._json_response(error_details, status=409)
        
        # Build host-specific configuration using centralized method
        host_config_list = host_obj.get_config_data()
        config = {
            'version': 4,  # API version
            'generated_at': fields.Datetime.now().isoformat(),
            'worker_id': worker_obj.id,
            'worker_name': worker_obj.name,
            'host': host_config_list[0] if host_config_list else None  # Includes is_active and all other fields
        }
        
        # Audit log registration to inactive host (if applicable)
        if not host_obj.is_active:
            request.env['sunray.audit.log'].sudo().create_api_event(
                event_type='worker.registered_inactive_host',
                api_key_id=api_key_obj.id,
                details={
                    'worker_id': worker_obj.id,
                    'worker_name': worker_name,
                    'host_id': host_obj.id,
                    'hostname': hostname,
                    'is_active': False
                },
                severity='warning',
                ip_address=request.httprequest.environ.get('REMOTE_ADDR')
            )
        
        # Audit log successful registration
        request.env['sunray.audit.log'].sudo().create_api_event(
            event_type='worker.registration_success',
            api_key_id=api_key_obj.id,
            details={
                'worker_id': worker_obj.id,
                'worker_name': worker_name,
                'host_id': host_obj.id,
                'hostname': hostname
            },
            ip_address=request.httprequest.environ.get('REMOTE_ADDR')
        )
        
        return self._json_response(config)
    
    @http.route('/sunray-srvr/v1/config/<string:hostname>', type='http', auth='none', methods=['GET', 'HEAD'], cors='*', csrf=False)
    def get_host_config(self, hostname, **kwargs):
        """Get configuration for a specific host (worker-optimized endpoint)
        
        This endpoint provides host-specific configuration data for workers.
        Unlike the global /config endpoint, this returns only data relevant
        to the specified hostname, improving security and efficiency.
        
        Supports both GET and HEAD requests:
        - GET: Returns full configuration data
        - HEAD: Returns only X-Config-Version header for cache validation
        
        Args:
            hostname: The hostname to get configuration for
            
        Returns:
            Host-specific configuration data with authorized users only (GET)
            Empty response with X-Config-Version header (HEAD)
        """
        api_key_obj = self._authenticate_api(request)
        if not api_key_obj:
            return self._error_response('Unauthorized', 401)
        
        # Get worker ID from header (required for security)
        worker_name = request.httprequest.headers.get('X-Worker-ID')
        if not worker_name:
            return self._error_response('X-Worker-ID header required', 400)
        
        # Find the worker
        worker_obj = request.env['sunray.worker'].sudo().search([
            ('name', '=', worker_name)
        ], limit=1)
        
        if not worker_obj:
            return self._error_response(f'Worker "{worker_name}" not found', 404)
        
        # Find the host (including inactive hosts)
        host_obj = request.env['sunray.host'].sudo().search([
            ('domain', '=', hostname)
        ], limit=1)
        
        if not host_obj:
            return self._error_response(f'Host "{hostname}" not found', 404)
        
        # Security check: Only bound worker can access this host's config
        if not host_obj.sunray_worker_id or host_obj.sunray_worker_id.id != worker_obj.id:
            return self._error_response(
                f'Worker "{worker_name}" not authorized for host "{hostname}"', 
                403
            )
        
        # Handle HEAD request - return only X-Config-Version header
        if request.httprequest.method == 'HEAD':
            config_version = host_obj.config_version.isoformat() if host_obj.config_version else fields.Datetime.now().isoformat()            
            return Response(
                '',
                status=200,
                headers={'X-Config-Version': config_version}
            )
        
        # Handle GET request - return full configuration
        # Build host-specific configuration using centralized method
        host_config_list = host_obj.get_config_data()
        config = {
            'version': 4,  # API version
            'generated_at': fields.Datetime.now().isoformat(),
            'worker_id': worker_obj.id,
            'worker_name': worker_obj.name,
            'host': host_config_list[0] if host_config_list else None  # Includes is_active and all other fields
        }
        
        # Setup request context and log config fetch
        context_data = self._setup_request_context(request)
        request.env['sunray.audit.log'].sudo().create_worker_event(
            event_type='config.host_fetched',
            details={
                'worker_id': context_data['worker_id'],
                'hostname': hostname
            },
            sunray_worker=context_data['worker_id'],
            ip_address=request.httprequest.environ.get('REMOTE_ADDR')
        )
        
        return self._json_response(config)
    
    @http.route('/sunray-srvr/v1/users/<string:username>', type='http', auth='none', methods=['GET'], cors='*', csrf=False)
    def get_user(self, username, **kwargs):
        """Get user details by username"""
        api_key_obj = self._authenticate_api(request)
        if not api_key_obj:
            return self._error_response('Unauthorized', 401)
        
        if not username:
            return self._error_response('Username required', 400)
        
        user_obj = request.env['sunray.user'].sudo().search([
            ('username', '=', username)
        ], limit=1)
        
        if not user_obj:
            return self._error_response('User not found', 404)
        
        # Get authorized hosts data (include all hosts, even inactive ones)
        authorized_hosts = []
        for host in user_obj.host_ids:
            authorized_hosts.append({
                'domain': host.domain,
                'name': host.domain,
                'is_active': host.is_active  # Include flag for worker decision-making
            })
        
        # Get passkeys data
        passkeys = []
        for passkey in user_obj.passkey_ids:
            passkeys.append({
                'credential_id': passkey.credential_id,
                'public_key': passkey.public_key,
                'public_key_format': 'cbor_cose',
                'name': passkey.name,
                'counter': passkey.counter or 0,
                'created_at': passkey.create_date.isoformat(),
                'last_used_at': passkey.last_used.isoformat() if passkey.last_used else None
            })
        
        # Build response data
        user_data = {
            'username': user_obj.username,
            'email': user_obj.email,
            'display_name': user_obj.email,  # Using email as display name for now
            'is_active': user_obj.is_active,
            'passkey_count': user_obj.passkey_count,
            'active_session_count': user_obj.active_session_count,
            'last_login': user_obj.last_login.isoformat() if user_obj.last_login else None,
            'authorized_hosts': authorized_hosts,
            'passkeys': passkeys,
            'config_version': user_obj.config_version.isoformat() if user_obj.config_version else None
        }
        
        return self._json_response(user_data)
    
    @http.route('/sunray-srvr/v1/users/<string:username>/passkeys', type='http', auth='none', methods=['POST'], cors='*', csrf=False)
    def register_passkey(self, username, **kwargs):
        """Register a new passkey using the model method"""
        
        _logger.info(f"REST API: Starting passkey registration for username: {username}")
        
        # Setup request context
        context_data = self._setup_request_context(request)
        client_ip = request.httprequest.remote_addr
        user_agent = request.httprequest.headers.get('User-Agent', '')
        worker_id = context_data.get('worker_id')

        # API Authentication
        api_key_obj = self._authenticate_api(request)
        if not api_key_obj:
            _logger.warning(f"API authentication failed for username: {username}")
            request.env['sunray.audit.log'].sudo().create_audit_event(
                event_type='security.passkey.unauthorized_api',
                details={
                    'username': username,
                    'ip_address': client_ip,
                    'user_agent': user_agent,
                    'endpoint': f'/users/{username}/passkeys'
                },
                severity='critical',
                ip_address=client_ip,
                user_agent=user_agent
            )
            return self._error_response('Unauthorized', 401)

        # Parse Request
        _logger.debug("Parsing request JSON data")
        try:
            data = json.loads(request.httprequest.data)
            _logger.debug(f"Request data keys: {list(data.keys())}")
        except json.JSONDecodeError as e:
            _logger.error(f"JSON decode error: {str(e)}")
            # AUDIT: Log malformed request
            request.env['sunray.audit.log'].sudo().create_audit_event(
                event_type='security.passkey.invalid_json',
                details={
                    'username': username,
                    'error': str(e),
                    'worker_id': context_data.get('worker_id'),
                    'raw_data_length': len(request.httprequest.data)
                },
                severity='warning',
                sunray_worker=context_data.get('worker_id'),
                ip_address=client_ip
            )
            return self._error_response('Invalid JSON', 400)

        # Field Validation 
        setup_token_hash = data.get('setup_token_hash')
        credential = data.get('credential')
        host_domain = data.get('host_domain')
        device_name = data.get('name', 'Passkey')

        # Check required fields
        missing_fields = []
        if not setup_token_hash:
            missing_fields.append('setup_token_hash')
        if not credential:
            missing_fields.append('credential')
        if not host_domain:
            missing_fields.append('host_domain')

        if missing_fields:
            # AUDIT: Log missing required fields
            request.env['sunray.audit.log'].sudo().create_audit_event(
                event_type='security.passkey.missing_fields',
                details={
                    'username': username,
                    'missing_fields': missing_fields,
                    'provided_fields': list(data.keys()),
                    'host_domain': host_domain or 'not_provided',
                    'worker_id': context_data.get('worker_id')
                },
                severity='warning',
                sunray_worker=context_data.get('worker_id'),
                ip_address=client_ip,
                username=username
            )
            return self._error_response(f'Missing required fields: {", ".join(missing_fields)}', 400)

        # Extract credential details
        credential_id = credential.get('id') or data.get('credential_id')
        public_key = credential.get('public_key', '').strip()
        
        if not credential_id:
            return self._error_response('Credential ID required', 400)
        
        if not public_key:
            return self._error_response('Public key is required for passkey registration', 400)
        
        # Validate CBOR format before processing
        try:
            cbor_data = base64.b64decode(public_key)
            cbor2.loads(cbor_data)
        except Exception as e:
            return self._error_response(f'Invalid CBOR public key format: {str(e)}', 400)

        # ========== Use Model Method for All Business Logic ==========
        try:
            result = request.env['sunray.passkey'].register_with_setup_token(
                username=username,
                setup_token_hash=setup_token_hash,
                credential_id=credential_id,
                public_key=public_key,
                host_domain=host_domain,
                device_name=device_name,
                client_ip=client_ip,
                user_agent=user_agent,
                worker_id=worker_id
            )
            
            # Success response
            return self._json_response({
                'success': True,
                'passkey_id': result['passkey_id'],
                'message': 'Passkey registered successfully'
            })
            
        except (UserError, ValidationError) as e:
            # Parse status code from message format: "STATUS|message"
            msg = str(e)
            parts = msg.split('|', 1)  # Split only on first pipe
            
            if len(parts) == 2 and parts[0].isdigit():
                status = int(parts[0])
                message = parts[1]
            else:
                status = 400  # Default for unparseable format
                message = msg
            
            return self._error_response(message, status)
        except IntegrityError as e:
            # Database constraint violation (e.g., unique constraint)
            _logger.error(f"Integrity error during passkey creation: {str(e)}")
            request.env['sunray.audit.log'].sudo().create_audit_event(
                event_type='security.passkey.integrity_error',
                details={
                    'username': username,
                    'host_domain': host_domain,
                    'error': str(e),
                    'worker_id': worker_id
                },
                severity='critical',
                sunray_worker=worker_id,
                ip_address=client_ip,
                username=username
            )
            return self._error_response('Registration failed', 500)
        except Exception as e:
            # Unexpected error
            _logger.error(f"Unexpected error during passkey registration: {str(e)}")
            request.env['sunray.audit.log'].sudo().create_audit_event(
                event_type='security.passkey.unexpected_error',
                details={
                    'username': username,
                    'host_domain': host_domain,
                    'error': str(e),
                    'worker_id': worker_id
                },
                severity='critical',
                sunray_worker=worker_id,
                ip_address=client_ip,
                username=username
            )
            return self._error_response('Registration failed', 500)
    
    @http.route('/sunray-srvr/v1/sessions', type='http', auth='none', methods=['POST'], cors='*', csrf=False)
    def create_session(self, **kwargs):
        """Create new session record - server acts as storage layer only"""
        api_key_obj = self._authenticate_api(request)
        if not api_key_obj:
            return self._error_response('Unauthorized', 401)
        
        try:
            # Get JSON data
            data = json.loads(request.httprequest.data)
        except json.JSONDecodeError as e:
            return self._error_response('Invalid JSON', 400)
        
        user_obj = request.env['sunray.user'].sudo().search([
            ('username', '=', data.get('username'))
        ])
        
        if not user_obj:
            return self._error_response('User not found', 404)
        
        # Get host from request
        host_domain = data.get('host_domain')
        host_obj = request.env['sunray.host'].sudo().search([
            ('domain', '=', host_domain)
        ])
        # Session creation NOT allowed on inactive hosts (per design decision)
        # Inactive hosts should return 503 at worker level, not create sessions
        if not host_obj or not host_obj.is_active:
            context_data = self._setup_request_context(request)

            if not host_obj:
                reason = "Host not found in database"
                severity = 'error'
            else:
                reason = "Host is inactive/archived (is_active=False) - sessions not allowed"
                severity = 'warning'  # Expected behavior for deactivated hosts

            request.env['sunray.audit.log'].sudo().create_user_event(
                event_type='session.creation_failed',
                severity=severity,
                details={
                    'host_domain': host_domain,
                    'reason': reason,
                },
                sunray_worker=context_data['worker_id'],
                username=data.get('username')
            )
            return self._error_response(f'Host "{host_domain}" not available for sessions', 503)        
        # Get credential_id and counter from request (worker managed)
        credential_id = data.get('credential_id')
        auth_counter = data.get('counter')  # Counter managed by worker, required for debugging
        
        # Validate required fields
        if auth_counter is None:
            return self._error_response('counter is required for debugging and audit purposes', 400)
        
        passkey_obj = None
        if credential_id:
            # Find the passkey for counter storage (no validation)
            passkey_obj = request.env['sunray.passkey'].sudo().search([
                ('credential_id', '=', credential_id),
                ('user_id', '=', user_obj.id)
            ], limit=1)
            
            if passkey_obj:
                # Store counter value without validation - worker manages counter logic
                passkey_obj.counter = auth_counter
                passkey_obj.last_used = fields.Datetime.now()
        
        # Get expiration time from worker (worker calculates based on its config)
        expires_at_str = data.get('expires_at')
        if not expires_at_str:
            return self._error_response('expires_at is required', 400)
        
        try:
            # Parse ISO 8601 datetime using dateutil for proper ISO 8601 support
            from dateutil.parser import isoparse
            expires_at_dt = isoparse(expires_at_str)
            
            # Odoo requires naive datetime (no timezone info)
            if expires_at_dt.tzinfo:
                expires_at = expires_at_dt.replace(tzinfo=None)
            else:
                expires_at = expires_at_dt
                
        except (ValueError, TypeError) as e:
            return self._error_response(f'Invalid expires_at format, expected ISO 8601: {str(e)}', 400)
        
        # Create session with passkey link
        session_obj = request.env['sunray.session'].sudo().create({
            'session_id': data.get('session_id'),
            'user_id': user_obj.id,
            'host_id': host_obj.id if host_obj else False,
            'passkey_id': passkey_obj.id if passkey_obj else False,
            'credential_id': credential_id,
            'created_ip': data.get('created_ip'),
            'device_fingerprint': data.get('device_fingerprint'),
            'user_agent': data.get('user_agent'),
            'csrf_token': data.get('csrf_token'),
            'expires_at': expires_at
        })
        
        # Setup request context and log event
        context_data = self._setup_request_context(request)
        request.env['sunray.audit.log'].sudo().create_user_event(
            event_type='session.created',
            details={
                'session_id': data.get('session_id'),
                'credential_id': credential_id,
                'passkey_id': passkey_obj.id if passkey_obj else None,
                'counter_stored': auth_counter,
                'expires_at': expires_at_str
            },
            sunray_user_id=user_obj.id,
            sunray_worker=context_data['worker_id'],
            ip_address=data.get('created_ip'),
            username=data.get('username')  # Keep for compatibility
        )
        
        return self._json_response({'success': True, 'session_id': session_obj.session_id})
    
    @http.route('/sunray-srvr/v1/sessions/<string:session_id>/revoke', type='http', auth='none', methods=['POST'], cors='*', csrf=False)
    def revoke_session(self, session_id, **kwargs):
        """Revoke a session"""
        api_key_obj = self._authenticate_api(request)
        if not api_key_obj:
            return self._error_response('Unauthorized', 401)
        
        # Get JSON data if any
        try:
            data = json.loads(request.httprequest.data) if request.httprequest.data else {}
        except:
            data = {}
        
        reason = data.get('reason', 'API revocation')
        
        session_obj = request.env['sunray.session'].sudo().search([
            ('session_id', '=', session_id)
        ])
        
        if not session_obj:
            return self._error_response('Session not found', 404)
        
        session_obj.revoke(reason)
        return self._json_response({'success': True})
    
    @http.route('/sunray-srvr/v1/logout', type='http', auth='none', methods=['POST'], cors='*', csrf=False)
    def logout(self, **kwargs):
        """User-initiated logout endpoint"""
        api_key_obj = self._authenticate_api(request)
        if not api_key_obj:
            return self._error_response('Unauthorized', 401)
        
        # Get JSON data
        try:
            data = json.loads(request.httprequest.data) if request.httprequest.data else {}
        except json.JSONDecodeError:
            return self._error_response('Invalid JSON payload', 400)
        
        session_id = data.get('session_id')
        if not session_id:
            return self._error_response('session_id is required', 400)
        
        # Find the session
        session_obj = request.env['sunray.session'].sudo().search([
            ('session_id', '=', session_id)
        ])
        
        if not session_obj:
            return self._error_response('Session not found', 404)
        
        # Revoke the session with logout-specific reason
        session_obj.revoke('User logout')
        
        # Setup request context and log logout event
        context_data = self._setup_request_context(request)
        request.env['sunray.audit.log'].sudo().create_user_event(
            event_type='auth.logout',
            details={'session_id': session_id},
            sunray_user_id=session_obj.user_id.id,
            sunray_worker=context_data['worker_id'],
            ip_address=data.get('ip_address'),
            username=session_obj.user_id.username
        )
        
        return self._json_response({
            'success': True,
            'message': 'User logged out successfully'
        })
    
    
    @http.route('/sunray-srvr/v1/audit', type='http', auth='none', methods=['POST'], cors='*', csrf=False)
    def log_audit_event(self, **kwargs):
        """Log audit events from workers - UNIFIED ENDPOINT"""
        api_key_obj = self._authenticate_api(request)
        if not api_key_obj:
            return self._error_response('Unauthorized', 401)
        
        # Get JSON data
        try:
            data = json.loads(request.httprequest.data) if request.httprequest.data else {}
        except json.JSONDecodeError:
            return self._error_response('Invalid JSON payload', 400)
        
        # Validate required fields
        event_type = data.get('event_type')
        if not event_type:
            return self._error_response('event_type is required', 400)
        
        # Setup request context
        context_data = self._setup_request_context(request)
        
        # Prepare details with extra context
        details = data.get('details', {})
        if isinstance(details, dict):
            if data.get('host'):
                details['host'] = data.get('host')
            details['api_key_id'] = api_key_obj.id
        
        # Create unified audit log entry
        audit_record = request.env['sunray.audit.log'].sudo().create_audit_event(
            event_type=event_type,
            details=details,
            username=data.get('username'),
            ip_address=data.get('ip_address') or request.httprequest.environ.get('REMOTE_ADDR'),
            user_agent=data.get('user_agent'),
            severity=data.get('severity', 'info'),
            sunray_worker=context_data['worker_id'],
            event_source='worker'
        )
        
        return self._json_response({
            'success': True,
            'audit_id': audit_record.id
        })
    
    @http.route('/sunray-srvr/v1/webhooks/track-usage', type='http', auth='none', methods=['POST'], cors='*', csrf=False)
    def track_webhook_usage(self, **kwargs):
        """Track webhook token usage"""
        api_key_obj = self._authenticate_api(request)
        if not api_key_obj:
            return self._error_response('Unauthorized', 401)
        
        # Get JSON data
        data = json.loads(request.httprequest.data)
        
        token_obj = request.env['sunray.webhook.token'].sudo().search([
            ('token', '=', data.get('token'))
        ])
        
        if token_obj:
            token_obj.track_usage(data.get('client_ip'))
        
        return self._json_response({'success': True})