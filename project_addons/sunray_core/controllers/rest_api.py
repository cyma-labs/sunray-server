# -*- coding: utf-8 -*-
from odoo import http, fields
from odoo.http import request, Response
import json
import hashlib
from datetime import datetime, timedelta


class SunrayRESTController(http.Controller):
    """REST API endpoints for Cloudflare Worker communication"""
    
    def _setup_request_context(self, req):
        """Setup request context for audit logging
        
        Extracts and stores request correlation data in Odoo context
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
    
    @http.route('/sunray-srvr/v1/config', type='http', auth='none', methods=['GET'], cors='*')
    def get_config(self, **kwargs):
        """Get configuration for Worker"""
        api_key_obj = self._authenticate_api(request)
        if not api_key_obj:
            return self._error_response('Unauthorized', 401)
        
        # Build configuration with version tracking
        config = {
            'version': 4,  # Incremented for Access Rules support
            'generated_at': fields.Datetime.now().isoformat(),
            'config_version': fields.Datetime.now().isoformat(),  # Global config version
            'host_versions': {},  # Per-host versions
            'user_versions': {},  # Recently modified user versions
            'users': {},
            'hosts': []
        }
        
        # Add users and track recently modified versions
        user_objs = request.env['sunray.user'].sudo().search([('is_active', '=', True)])
        
        # Include users modified in the last 5 minutes
        five_minutes_ago = fields.Datetime.now() - timedelta(minutes=5)
        
        for user_obj in user_objs:
            config['users'][user_obj.username] = {
                'email': user_obj.email,
                'display_name': user_obj.display_name or user_obj.username,
                'created_at': user_obj.create_date.isoformat(),
                'passkeys': []
            }
            
            # Track version for recently modified users
            if user_obj.config_version and user_obj.config_version > five_minutes_ago:
                config['user_versions'][user_obj.username] = user_obj.config_version.isoformat()
            
            # Add passkeys
            for passkey in user_obj.passkey_ids:
                config['users'][user_obj.username]['passkeys'].append({
                    'credential_id': passkey.credential_id,
                    'public_key': passkey.public_key,
                    'name': passkey.name,
                    'created_at': passkey.create_date.isoformat(),
                    'backup_eligible': passkey.backup_eligible,
                    'backup_state': passkey.backup_state
                })
        
        # Add hosts with version tracking
        host_objs = request.env['sunray.host'].sudo().search([('is_active', '=', True)])
        for host_obj in host_objs:
            # Track host version
            if host_obj.config_version:
                config['host_versions'][host_obj.domain] = host_obj.config_version.isoformat()
            
            host_config = {
                'domain': host_obj.domain,
                'backend': host_obj.backend_url,
                'authorized_users': host_obj.user_ids.mapped('username'),
                'session_duration_s': host_obj.session_duration_s,
                
                # NEW: Access Rules - unified exceptions tree
                'exceptions_tree': host_obj.get_exceptions_tree(),
                
                # WAF integration
                'bypass_waf_for_authenticated': host_obj.bypass_waf_for_authenticated,
                'waf_bypass_revalidation_s': host_obj.waf_bypass_revalidation_s,
                
                # Worker information (if bound)
                'worker_id': host_obj.sunray_worker_id.id if host_obj.sunray_worker_id else None,
                'worker_name': host_obj.sunray_worker_id.name if host_obj.sunray_worker_id else None,
            }
            
            
            config['hosts'].append(host_config)
        
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
        
        # Build host-specific configuration
        config = {
            'version': 4,  # API version
            'generated_at': fields.Datetime.now().isoformat(),
            'worker_id': worker_obj.id,
            'worker_name': worker_obj.name,
            'host': {
                'domain': host_obj.domain,
                'backend': host_obj.backend_url,
                'authorized_users': host_obj.user_ids.mapped('username'),
                'session_duration_s': host_obj.session_duration_s,
                'exceptions_tree': host_obj.get_exceptions_tree(),
                'bypass_waf_for_authenticated': host_obj.bypass_waf_for_authenticated,
                'waf_bypass_revalidation_s': host_obj.waf_bypass_revalidation_s,
                'config_version': host_obj.config_version.isoformat() if host_obj.config_version else None
            },
            'users': {}
        }
        
        # Add user data for authorized users only
        for user_obj in host_obj.user_ids.filtered(lambda u: u.is_active):
            config['users'][user_obj.username] = {
                'email': user_obj.email,
                'display_name': user_obj.display_name or user_obj.username,
                'created_at': user_obj.create_date.isoformat(),
                'passkeys': []
            }
            
            # Add passkeys
            for passkey in user_obj.passkey_ids:
                config['users'][user_obj.username]['passkeys'].append({
                    'credential_id': passkey.credential_id,
                    'public_key': passkey.public_key,
                    'name': passkey.name,
                    'created_at': passkey.create_date.isoformat(),
                    'backup_eligible': passkey.backup_eligible,
                    'backup_state': passkey.backup_state
                })
        
        # Audit log successful registration
        request.env['sunray.audit.log'].sudo().create_api_event(
            event_type='worker.registration_success',
            api_key_id=api_key_obj.id,
            details={
                'worker_id': worker_obj.id,
                'worker_name': worker_name,
                'host_id': host_obj.id,
                'hostname': hostname,
                'user_count': len(config['users'])
            },
            ip_address=request.httprequest.environ.get('REMOTE_ADDR')
        )
        
        return self._json_response(config)
    
    @http.route('/sunray-srvr/v1/config/<string:hostname>', type='http', auth='none', methods=['GET'], cors='*', csrf=False)
    def get_host_config(self, hostname, **kwargs):
        """Get configuration for a specific host (worker-optimized endpoint)
        
        This endpoint provides host-specific configuration data for workers.
        Unlike the global /config endpoint, this returns only data relevant
        to the specified hostname, improving security and efficiency.
        
        Args:
            hostname: The hostname to get configuration for
            
        Returns:
            Host-specific configuration data with authorized users only
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
        
        # Find the host
        host_obj = request.env['sunray.host'].sudo().search([
            ('domain', '=', hostname),
            ('is_active', '=', True)
        ], limit=1)
        
        if not host_obj:
            return self._error_response(f'Host "{hostname}" not found', 404)
        
        # Security check: Only bound worker can access this host's config
        if not host_obj.sunray_worker_id or host_obj.sunray_worker_id.id != worker_obj.id:
            return self._error_response(
                f'Worker "{worker_name}" not authorized for host "{hostname}"', 
                403
            )
        
        # Build host-specific configuration (same structure as /register endpoint)
        config = {
            'version': 4,  # API version
            'generated_at': fields.Datetime.now().isoformat(),
            'worker_id': worker_obj.id,
            'worker_name': worker_obj.name,
            'host': {
                'domain': host_obj.domain,
                'backend': host_obj.backend_url,
                'authorized_users': host_obj.user_ids.mapped('username'),
                'session_duration_s': host_obj.session_duration_s,
                'exceptions_tree': host_obj.get_exceptions_tree(),
                'bypass_waf_for_authenticated': host_obj.bypass_waf_for_authenticated,
                'waf_bypass_revalidation_s': host_obj.waf_bypass_revalidation_s,
                'config_version': host_obj.config_version.isoformat() if host_obj.config_version else None
            },
            'users': {}
        }
        
        # Add user data for authorized users only
        for user_obj in host_obj.user_ids.filtered(lambda u: u.is_active):
            config['users'][user_obj.username] = {
                'email': user_obj.email,
                'display_name': user_obj.display_name or user_obj.username,
                'created_at': user_obj.create_date.isoformat(),
                'passkeys': []
            }
            
            # Add passkeys
            for passkey in user_obj.passkey_ids:
                config['users'][user_obj.username]['passkeys'].append({
                    'credential_id': passkey.credential_id,
                    'public_key': passkey.public_key,
                    'name': passkey.name,
                    'created_at': passkey.create_date.isoformat(),
                    'backup_eligible': passkey.backup_eligible,
                    'backup_state': passkey.backup_state
                })
        
        # Setup request context and log config fetch
        context_data = self._setup_request_context(request)
        request.env['sunray.audit.log'].sudo().create_worker_event(
            event_type='config.host_fetched',
            details={
                'worker_id': context_data['worker_id'],
                'hostname': hostname,
                'user_count': len(config['users'])
            },
            sunray_worker=context_data['worker_id'],
            ip_address=request.httprequest.environ.get('REMOTE_ADDR')
        )
        
        return self._json_response(config)
    
    @http.route('/sunray-srvr/v1/users/check', type='http', auth='none', methods=['POST'], cors='*', csrf=False)
    def check_user_exists(self, **kwargs):
        """Check if a user exists"""
        api_key_obj = self._authenticate_api(request)
        if not api_key_obj:
            return self._error_response('Unauthorized', 401)
        
        # Get JSON data
        data = json.loads(request.httprequest.data)
        username = data.get('username')
        
        if not username:
            return self._error_response('Username required', 400)
        
        user_obj = request.env['sunray.user'].sudo().search([
            ('username', '=', username),
            ('is_active', '=', True)
        ], limit=1)
        
        return self._json_response({'exists': bool(user_obj)})
    
    @http.route('/sunray-srvr/v1/setup-tokens/validate', type='http', auth='none', methods=['POST'], cors='*', csrf=False)
    def validate_token(self, **kwargs):
        """Validate setup token"""
        api_key_obj = self._authenticate_api(request)
        if not api_key_obj:
            return self._error_response('Unauthorized', 401)
        
        # Get JSON data
        data = json.loads(request.httprequest.data)
        username = data.get('username')
        token_hash = data.get('token_hash')
        client_ip = data.get('client_ip')
        host_domain = data.get('host_domain')  # Domain where token is being used
        
        if not all([username, token_hash, client_ip, host_domain]):
            return self._error_response('Missing required fields', 400)
        
        # Find user and token
        user_obj = request.env['sunray.user'].sudo().search([
            ('username', '=', username),
            ('is_active', '=', True)
        ])
        
        if not user_obj:
            return self._json_response({'valid': False, 'error': 'User not found'})
        
        # Find matching token
        token_obj = request.env['sunray.setup.token'].sudo().search([
            ('user_id', '=', user_obj.id),
            ('token_hash', '=', token_hash),
            ('consumed', '=', False),
            ('expires_at', '>', fields.Datetime.now())
        ])
        
        if not token_obj:
            return self._json_response({'valid': False, 'error': 'Invalid or expired token'})
        
        # Check if token is for the correct host (REQUIRED)
        host_obj = request.env['sunray.host'].sudo().search([
            ('domain', '=', host_domain),
            ('is_active', '=', True)
        ])
        
        if not host_obj:
            return self._json_response({'valid': False, 'error': 'Unknown host'})
        
        if token_obj.host_id.id != host_obj.id:
            return self._json_response({'valid': False, 'error': 'Token not valid for this host'})
        
        # Check constraints using CIDR
        from odoo.addons.sunray_core.utils.cidr import check_cidr_match
        allowed_cidrs = token_obj.get_allowed_cidrs()
        if allowed_cidrs and not any(check_cidr_match(client_ip, cidr) for cidr in allowed_cidrs):
            return self._json_response({'valid': False, 'error': 'IP not allowed'})
        
        # Check usage limit
        if token_obj.current_uses >= token_obj.max_uses:
            return self._json_response({'valid': False, 'error': 'Token usage limit exceeded'})
        
        # Mark as consumed
        token_obj.write({
            'current_uses': token_obj.current_uses + 1,
            'consumed': token_obj.current_uses + 1 >= token_obj.max_uses,
            'consumed_date': fields.Datetime.now()
        })
        
        # Setup request context and log event
        context_data = self._setup_request_context(request)
        request.env['sunray.audit.log'].sudo().create_user_event(
            event_type='token.consumed',
            details={'token_id': token_obj.id},
            sunray_user_id=user_obj.id,
            sunray_worker=context_data['worker_id'],
            ip_address=client_ip,
            username=username  # Keep for compatibility
        )
        
        return self._json_response({
            'valid': True,
            'user': {
                'username': user_obj.username,
                'email': user_obj.email,
                'display_name': user_obj.display_name
            }
        })
    
    @http.route('/sunray-srvr/v1/users/<string:username>/passkeys', type='http', auth='none', methods=['POST'], cors='*', csrf=False)
    def register_passkey(self, username, **kwargs):
        """Register a new passkey"""
        api_key_obj = self._authenticate_api(request)
        if not api_key_obj:
            return self._error_response('Unauthorized', 401)
        
        # Get JSON data
        data = json.loads(request.httprequest.data)
        
        user_obj = request.env['sunray.user'].sudo().search([('username', '=', username)])
        if not user_obj:
            return self._error_response('User not found', 404)
        
        # Create passkey
        passkey_obj = request.env['sunray.passkey'].sudo().create({
            'user_id': user_obj.id,
            'credential_id': data.get('credential_id'),
            'public_key': data.get('public_key'),
            'name': data.get('name'),
            'created_ip': data.get('client_ip'),
            'created_user_agent': data.get('user_agent'),
            'backup_eligible': data.get('backup_eligible', False),
            'backup_state': data.get('backup_state', False)
        })
        
        # Setup request context and log event
        context_data = self._setup_request_context(request)
        request.env['sunray.audit.log'].sudo().create_user_event(
            event_type='passkey.registered',
            details={'passkey_id': passkey_obj.id, 'name': data.get('name')},
            sunray_user_id=user_obj.id,
            sunray_worker=context_data['worker_id'],
            ip_address=data.get('client_ip'),
            user_agent=data.get('user_agent'),
            username=username  # Keep for compatibility
        )
        
        return self._json_response({'success': True, 'passkey_id': passkey_obj.id})
    
    @http.route('/sunray-srvr/v1/auth/verify', type='http', auth='none', methods=['POST'], cors='*', csrf=False)
    def verify_authentication(self, **kwargs):
        """Verify passkey authentication"""
        api_key_obj = self._authenticate_api(request)
        if not api_key_obj:
            return self._error_response('Unauthorized', 401)
        
        # Get JSON data
        data = json.loads(request.httprequest.data)
        username = data.get('username')
        credential = data.get('credential')
        challenge = data.get('challenge')
        host_domain = data.get('host_domain')  # Domain requesting authentication
        
        if not all([username, credential, challenge]):
            return self._error_response('Missing required fields', 400)
        
        # Find user
        user_obj = request.env['sunray.user'].sudo().search([
            ('username', '=', username),
            ('is_active', '=', True)
        ])
        
        if not user_obj:
            return self._error_response('User not found', 404)
        
        # Check if user is authorized for this specific host
        if host_domain:
            host_obj = request.env['sunray.host'].sudo().search([
                ('domain', '=', host_domain),
                ('is_active', '=', True)
            ])
            
            if host_obj and user_obj not in host_obj.user_ids:
                return self._error_response('User not authorized for this host', 403)
        
        # For MVP, we'll do basic verification
        # In production, this should verify the signature using the public key
        credential_id = credential.get('id')
        
        # Find matching passkey
        passkey_obj = request.env['sunray.passkey'].sudo().search([
            ('user_id', '=', user_obj.id),
            ('credential_id', '=', credential_id)
        ])
        
        if not passkey_obj:
            return self._error_response('Invalid credential', 404)
        
        # Update last used timestamp
        passkey_obj.last_used = fields.Datetime.now()
        
        # Setup request context and log successful authentication
        context_data = self._setup_request_context(request)
        request.env['sunray.audit.log'].sudo().create_user_event(
            event_type='auth.success',
            details={'credential_id': credential_id},
            sunray_user_id=user_obj.id,
            sunray_worker=context_data['worker_id'],
            ip_address=data.get('client_ip'),
            username=username  # Keep for compatibility
        )
        
        return self._json_response({
            'success': True,
            'user': {
                'id': user_obj.id,
                'username': user_obj.username,
                'email': user_obj.email,
                'display_name': user_obj.display_name
            }
        })
    
    @http.route('/sunray-srvr/v1/sessions', type='http', auth='none', methods=['POST'], cors='*', csrf=False)
    def create_session(self, **kwargs):
        """Create new session record"""
        api_key_obj = self._authenticate_api(request)
        if not api_key_obj:
            return self._error_response('Unauthorized', 401)
        
        # Get JSON data
        data = json.loads(request.httprequest.data)
        
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
        
        # Calculate expiration using host's session duration
        duration = host_obj.session_duration_s if host_obj else 3600  # Use host setting or server default
        expires_at = fields.Datetime.now() + timedelta(seconds=duration)
        
        # Create session
        session_obj = request.env['sunray.session'].sudo().create({
            'session_id': data.get('session_id'),
            'user_id': user_obj.id,
            'host_id': host_obj.id if host_obj else False,
            'credential_id': data.get('credential_id'),
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
            details={'session_id': data.get('session_id')},
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