# -*- coding: utf-8 -*-
from odoo import http, fields
from odoo.http import request
import json
import hashlib
from datetime import datetime, timedelta


class SunrayAPIController(http.Controller):
    """API endpoints for Cloudflare Worker communication"""
    
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
    
    def _add_cors_headers(self, response):
        """Add CORS headers for Worker requests"""
        # Allow the configured Worker URL
        response.headers['Access-Control-Allow-Origin'] = 'https://wrkr-sunray18-main-dev-cmorisse.msa2.lair.ovh'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Authorization, Content-Type, X-Worker-ID'
        response.headers['Access-Control-Max-Age'] = '3600'
        return response
    
    @http.route('/sunray-srvr/v1/config', type='json', auth='none', methods=['GET', 'POST'], cors='*')
    def get_config(self, **kwargs):
        """Get configuration for Worker"""
        if not self._authenticate_api(request):
            return {'error': 'Unauthorized'}, 401
        
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
                'allowed_ips': json.loads(host_obj.allowed_ips or '[]'),
                'session_duration_override': host_obj.session_duration_s,
                
                # Security exceptions (whitelist approach)
                'allowed_cidrs': json.loads(host_obj.allowed_cidrs or '[]'),
                'public_url_patterns': json.loads(host_obj.public_url_patterns or '[]'),
                'token_url_patterns': json.loads(host_obj.token_url_patterns or '[]'),
                
                # Token authentication configuration
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
                        'allowed_ips': json.loads(token_obj.allowed_ips or '[]'),
                        'expires_at': token_obj.expires_at.isoformat() if token_obj.expires_at else None
                    })
            
            config['hosts'].append(host_config)
        
        # Log config fetch
        request.env['sunray.audit.log'].sudo().create({
            'event_type': 'config.fetched',
            'ip_address': request.httprequest.environ.get('REMOTE_ADDR'),
            'details': json.dumps({'worker_id': kwargs.get('worker_id')})
        })
        
        return config
    
    @http.route('/sunray-srvr/v1/users/check', type='json', auth='none', methods=['POST'], cors='*')
    def check_user_exists(self, username, **kwargs):
        """Check if a user exists"""
        if not self._authenticate_api(request):
            return {'error': 'Unauthorized'}, 401
        
        user_obj = request.env['sunray.user'].sudo().search([
            ('username', '=', username),
            ('is_active', '=', True)
        ], limit=1)
        
        return {'exists': bool(user_obj)}
    
    @http.route('/sunray-srvr/v1/setup-tokens/validate', type='json', auth='none', methods=['POST'], cors='*')
    def validate_token(self, username, token_hash, client_ip, **kwargs):
        """Validate setup token"""
        if not self._authenticate_api(request):
            return {'error': 'Unauthorized'}, 401
        
        # Find user and token
        user_obj = request.env['sunray.user'].sudo().search([
            ('username', '=', username),
            ('is_active', '=', True)
        ])
        
        if not user_obj:
            return {'valid': False, 'error': 'User not found'}
        
        # Find matching token
        token_obj = request.env['sunray.setup.token'].sudo().search([
            ('user_id', '=', user_obj.id),
            ('token_hash', '=', token_hash),
            ('consumed', '=', False),
            ('expires_at', '>', fields.Datetime.now())
        ])
        
        if not token_obj:
            return {'valid': False, 'error': 'Invalid or expired token'}
        
        # Check constraints
        allowed_ips = token_obj.get_allowed_ips()
        if allowed_ips and client_ip not in allowed_ips:
            return {'valid': False, 'error': 'IP not allowed'}
        
        # Check usage limit
        if token_obj.current_uses >= token_obj.max_uses:
            return {'valid': False, 'error': 'Token usage limit exceeded'}
        
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
        
        return {'valid': True, 'user': {
            'username': user_obj.username,
            'email': user_obj.email,
            'display_name': user_obj.display_name
        }}
    
    @http.route('/sunray-srvr/v1/users/<string:username>/passkeys', type='json', auth='none', methods=['POST'], cors='*')
    def register_passkey(self, username, credential_id, public_key, name, client_ip, user_agent, **kwargs):
        """Register a new passkey"""
        if not self._authenticate_api(request):
            return {'error': 'Unauthorized'}, 401
        
        user_obj = request.env['sunray.user'].sudo().search([('username', '=', username)])
        if not user_obj:
            return {'error': 'User not found'}, 404
        
        # Create passkey
        passkey_obj = request.env['sunray.passkey'].sudo().create({
            'user_id': user_obj.id,
            'credential_id': credential_id,
            'public_key': public_key,
            'name': name,
            'created_ip': client_ip,
            'created_user_agent': user_agent,
            'backup_eligible': kwargs.get('backup_eligible', False),
            'backup_state': kwargs.get('backup_state', False)
        })
        
        # Log event
        request.env['sunray.audit.log'].sudo().create({
            'event_type': 'passkey.registered',
            'user_id': user_obj.id,
            'username': username,
            'ip_address': client_ip,
            'user_agent': user_agent,
            'details': json.dumps({'passkey_id': passkey_obj.id, 'name': name})
        })
        
        return {'success': True, 'passkey_id': passkey_obj.id}
    
    @http.route('/sunray-srvr/v1/sessions', type='json', auth='none', methods=['POST'], cors='*')
    def create_session(self, session_id, username, credential_id, **kwargs):
        """Create new session record"""
        if not self._authenticate_api(request):
            return {'error': 'Unauthorized'}, 401
        
        user_obj = request.env['sunray.user'].sudo().search([
            ('username', '=', username)
        ])
        
        if not user_obj:
            return {'error': 'User not found'}, 404
        
        # Get host from request
        host_domain = kwargs.get('host_domain')
        host_obj = request.env['sunray.host'].sudo().search([
            ('domain', '=', host_domain)
        ])
        
        # Calculate expiration
        duration = kwargs.get('duration', 28800)  # Default 8 hours
        expires_at = fields.Datetime.now() + timedelta(seconds=duration)
        
        # Create session
        session_obj = request.env['sunray.session'].sudo().create({
            'session_id': session_id,
            'user_id': user_obj.id,
            'host_id': host_obj.id if host_obj else False,
            'credential_id': credential_id,
            'created_ip': kwargs.get('created_ip'),
            'device_fingerprint': kwargs.get('device_fingerprint'),
            'user_agent': kwargs.get('user_agent'),
            'csrf_token': kwargs.get('csrf_token'),
            'expires_at': expires_at
        })
        
        # Log event
        request.env['sunray.audit.log'].sudo().create({
            'event_type': 'session.created',
            'user_id': user_obj.id,
            'username': username,
            'ip_address': kwargs.get('created_ip'),
            'details': json.dumps({'session_id': session_id})
        })
        
        return {'success': True, 'session_id': session_obj.session_id}
    
    @http.route('/sunray-srvr/v1/sessions/<string:session_id>/revoke', type='json', auth='none', methods=['POST'], cors='*')
    def revoke_session(self, session_id, reason='API revocation', **kwargs):
        """Revoke a session"""
        if not self._authenticate_api(request):
            return {'error': 'Unauthorized'}, 401
        
        session_obj = request.env['sunray.session'].sudo().search([
            ('session_id', '=', session_id)
        ])
        
        if not session_obj:
            return {'error': 'Session not found'}, 404
        
        session_obj.revoke(reason)
        return {'success': True}
    
    @http.route('/sunray-srvr/v1/security-events', type='json', auth='none', methods=['POST'], cors='*')
    def log_security_event(self, type, details, **kwargs):
        """Log security event from Worker"""
        if not self._authenticate_api(request):
            return {'error': 'Unauthorized'}, 401
        
        # Create audit log entry
        request.env['sunray.audit.log'].sudo().create({
            'event_type': type,
            'timestamp': fields.Datetime.now(),
            'details': json.dumps(details),
            'ip_address': details.get('ip'),
            'user_agent': details.get('user_agent'),
            'severity': kwargs.get('severity', 'warning')
        })
        
        return {'success': True}
    
    @http.route('/sunray-srvr/v1/webhooks/track-usage', type='json', auth='none', methods=['POST'], cors='*')
    def track_webhook_usage(self, token, client_ip, **kwargs):
        """Track webhook token usage"""
        if not self._authenticate_api(request):
            return {'error': 'Unauthorized'}, 401
        
        token_obj = request.env['sunray.webhook.token'].sudo().search([
            ('token', '=', token)
        ])
        
        if token_obj:
            token_obj.track_usage(client_ip)
        
        return {'success': True}