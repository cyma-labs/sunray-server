# -*- coding: utf-8 -*-
from odoo import http, fields
from odoo.http import request, Response
import json
import hashlib
from datetime import datetime, timedelta


class SunrayRESTController(http.Controller):
    """REST API endpoints for Cloudflare Worker communication"""
    
    def _authenticate_api(self, req):
        """Authenticate API request using Bearer token"""
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
            api_key_obj.track_usage()
            return True
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
        if self._authenticate_api(request):
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
        if not self._authenticate_api(request):
            return self._error_response('Unauthorized', 401)
        
        # Build configuration
        config = {
            'version': 3,
            'generated_at': fields.Datetime.now().isoformat(),
            'users': {},
            'hosts': []
        }
        
        # Add users
        user_objs = request.env['sunray.user'].sudo().search([('is_active', '=', True)])
        for user_obj in user_objs:
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
        
        # Add hosts
        host_objs = request.env['sunray.host'].sudo().search([('is_active', '=', True)])
        for host_obj in host_objs:
            host_config = {
                'domain': host_obj.domain,
                'backend': host_obj.backend_url,
                'authorized_users': host_obj.user_ids.mapped('username'),
                'allowed_ips': host_obj.get_allowed_ips(),
                'session_duration_override': host_obj.session_duration_s,
                
                # Security exceptions
                'allowed_cidrs': host_obj.get_allowed_cidrs(),
                'public_url_patterns': host_obj.get_public_url_patterns(),
                'token_url_patterns': host_obj.get_token_url_patterns(),
                
                # Token authentication
                'webhook_header_name': host_obj.webhook_header_name,
                'webhook_param_name': host_obj.webhook_param_name,
                'webhook_tokens': []
            }
            
            # Add active webhook tokens
            for token_obj in host_obj.webhook_token_ids.filtered('is_active'):
                if token_obj.is_valid():
                    host_config['webhook_tokens'].append({
                        'token': token_obj.token,
                        'name': token_obj.name,
                        'allowed_ips': token_obj.get_allowed_ips(),
                        'expires_at': token_obj.expires_at.isoformat() if token_obj.expires_at else None
                    })
            
            config['hosts'].append(host_config)
        
        # Log config fetch
        request.env['sunray.audit.log'].sudo().create({
            'event_type': 'config.fetched',
            'ip_address': request.httprequest.environ.get('REMOTE_ADDR'),
            'details': json.dumps({'worker_id': request.httprequest.headers.get('X-Worker-ID')})
        })
        
        return self._json_response(config)
    
    @http.route('/sunray-srvr/v1/users/check', type='http', auth='none', methods=['POST'], cors='*', csrf=False)
    def check_user_exists(self, **kwargs):
        """Check if a user exists"""
        if not self._authenticate_api(request):
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
        if not self._authenticate_api(request):
            return self._error_response('Unauthorized', 401)
        
        # Get JSON data
        data = json.loads(request.httprequest.data)
        username = data.get('username')
        token_hash = data.get('token_hash')
        client_ip = data.get('client_ip')
        
        if not all([username, token_hash, client_ip]):
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
        
        # Check constraints
        allowed_ips = token_obj.get_allowed_ips()
        if allowed_ips and client_ip not in allowed_ips:
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
        
        # Log event
        request.env['sunray.audit.log'].sudo().create({
            'event_type': 'token.consumed',
            'user_id': user_obj.id,
            'username': username,
            'ip_address': client_ip,
            'details': json.dumps({'token_id': token_obj.id})
        })
        
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
        if not self._authenticate_api(request):
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
        
        # Log event
        request.env['sunray.audit.log'].sudo().create({
            'event_type': 'passkey.registered',
            'user_id': user_obj.id,
            'username': username,
            'ip_address': data.get('client_ip'),
            'user_agent': data.get('user_agent'),
            'details': json.dumps({'passkey_id': passkey_obj.id, 'name': data.get('name')})
        })
        
        return self._json_response({'success': True, 'passkey_id': passkey_obj.id})
    
    @http.route('/sunray-srvr/v1/auth/verify', type='http', auth='none', methods=['POST'], cors='*', csrf=False)
    def verify_authentication(self, **kwargs):
        """Verify passkey authentication"""
        if not self._authenticate_api(request):
            return self._error_response('Unauthorized', 401)
        
        # Get JSON data
        data = json.loads(request.httprequest.data)
        username = data.get('username')
        credential = data.get('credential')
        challenge = data.get('challenge')
        
        if not all([username, credential, challenge]):
            return self._error_response('Missing required fields', 400)
        
        # Find user
        user_obj = request.env['sunray.user'].sudo().search([
            ('username', '=', username),
            ('is_active', '=', True)
        ])
        
        if not user_obj:
            return self._error_response('User not found', 404)
        
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
        
        # Log successful authentication
        request.env['sunray.audit.log'].sudo().create({
            'event_type': 'auth.success',
            'user_id': user_obj.id,
            'username': username,
            'ip_address': data.get('client_ip'),
            'details': json.dumps({'credential_id': credential_id})
        })
        
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
        if not self._authenticate_api(request):
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
        
        # Calculate expiration
        duration = data.get('duration', 28800)  # Default 8 hours
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
        
        # Log event
        request.env['sunray.audit.log'].sudo().create({
            'event_type': 'session.created',
            'user_id': user_obj.id,
            'username': data.get('username'),
            'ip_address': data.get('created_ip'),
            'details': json.dumps({'session_id': data.get('session_id')})
        })
        
        return self._json_response({'success': True, 'session_id': session_obj.session_id})
    
    @http.route('/sunray-srvr/v1/sessions/<string:session_id>/revoke', type='http', auth='none', methods=['POST'], cors='*', csrf=False)
    def revoke_session(self, session_id, **kwargs):
        """Revoke a session"""
        if not self._authenticate_api(request):
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
    
    @http.route('/sunray-srvr/v1/security-events', type='http', auth='none', methods=['POST'], cors='*', csrf=False)
    def log_security_event(self, **kwargs):
        """Log security event from Worker"""
        if not self._authenticate_api(request):
            return self._error_response('Unauthorized', 401)
        
        # Get JSON data
        data = json.loads(request.httprequest.data)
        
        # Create audit log entry
        request.env['sunray.audit.log'].sudo().create({
            'event_type': data.get('type'),
            'timestamp': fields.Datetime.now(),
            'details': json.dumps(data.get('details', {})),
            'ip_address': data.get('details', {}).get('ip'),
            'user_agent': data.get('details', {}).get('user_agent'),
            'severity': data.get('severity', 'warning')
        })
        
        return self._json_response({'success': True})
    
    @http.route('/sunray-srvr/v1/webhooks/track-usage', type='http', auth='none', methods=['POST'], cors='*', csrf=False)
    def track_webhook_usage(self, **kwargs):
        """Track webhook token usage"""
        if not self._authenticate_api(request):
            return self._error_response('Unauthorized', 401)
        
        # Get JSON data
        data = json.loads(request.httprequest.data)
        
        token_obj = request.env['sunray.webhook.token'].sudo().search([
            ('token', '=', data.get('token'))
        ])
        
        if token_obj:
            token_obj.track_usage(data.get('client_ip'))
        
        return self._json_response({'success': True})