# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from datetime import datetime, timedelta
import json
from unittest.mock import Mock, patch
from odoo.addons.sunray_core.controllers.rest_api import SunrayRESTController


class TestPasskeyCounter(TransactionCase):
    """Test passkey counter storage functionality - server acts as storage layer only"""
    
    def setUp(self):
        super().setUp()
        
        # Create test user
        self.user_obj = self.env['sunray.user'].create({
            'username': 'counter_test_user',
            'email': 'counter@test.com',
            'is_active': True
        })
        
        # Create test host
        self.host_obj = self.env['sunray.host'].create({
            'domain': 'counter.test.com',
            'backend_url': 'http://backend.counter.test.com',
            'is_active': True,
            'session_duration_s': 3600
        })
        
        # Link user to host
        self.host_obj.user_ids = [(4, self.user_obj.id)]
        
        # Create test passkey
        self.passkey_obj = self.env['sunray.passkey'].create({
            'user_id': self.user_obj.id,
            'credential_id': 'test_counter_cred_123',
            'public_key': 'test_public_key_counter',
            'name': 'Counter Test Device',
            'host_domain': 'counter.test.com',
            'counter': 10  # Starting counter value
        })
        
        # Create API key for session creation tests
        self.api_key_obj = self.env['sunray.api.key'].create({
            'name': 'Counter Test API Key',
            'scopes': 'config:read,session:write',
            'is_active': True
        })
    
    def test_01_session_creation_with_counter_success(self):
        """Test successful session creation with counter storage"""
        original_counter = self.passkey_obj.counter
        new_counter = original_counter + 3
        
        # Create session with counter storage
        session_data = {
            'session_id': 'test_session_counter_success',
            'username': self.user_obj.username,
            'host_domain': self.host_obj.domain,
            'expires_at': '2024-01-01T20:00:00Z',
            'credential_id': self.passkey_obj.credential_id,
            'counter': new_counter,
            'created_ip': '192.168.1.100',
            'user_agent': 'Test Browser Counter',
            'csrf_token': 'test_csrf_counter'
        }
        
        # Simulate API request
        from odoo.http import request
        from unittest.mock import Mock
        
        mock_request = Mock()
        mock_request.httprequest.data = json.dumps(session_data).encode()
        mock_request.env = self.env
        
        # Create controller instance and call method
        controller = SunrayRESTController()
        
        # Mock authentication 
        original_auth = controller._authenticate_api
        controller._authenticate_api = lambda r: self.api_key_obj
        
        # Mock request context setup
        controller._setup_request_context = lambda r: {'worker_id': 'test_worker'}
        
        try:
            # Call session creation
            with self.env.registry.cursor() as cr:
                env = self.env(cr=cr)
                controller_env = SunrayRESTController()
                controller_env._authenticate_api = lambda r: self.api_key_obj
                controller_env._setup_request_context = lambda r: {'worker_id': 'test_worker'}
                
                with patch('odoo.addons.sunray_core.controllers.rest_api.request', mock_request):
                    response = controller_env.create_session()
                
                # Verify response structure
                if hasattr(response, 'data'):
                    response_data = json.loads(response.data.decode())
                    self.assertTrue(response_data['success'])
                    self.assertEqual(response_data['session_id'], session_data['session_id'])
                
                # Verify passkey counter was stored
                self.passkey_obj.invalidate_recordset()
                self.assertEqual(self.passkey_obj.counter, new_counter)
                
                # Verify session was created with passkey link
                session_obj = env['sunray.session'].search([
                    ('session_id', '=', session_data['session_id'])
                ])
                self.assertTrue(session_obj)
                self.assertEqual(session_obj.passkey_id.id, self.passkey_obj.id)
                self.assertEqual(session_obj.credential_id, self.passkey_obj.credential_id)
                
        finally:
            # Restore original authentication method
            controller._authenticate_api = original_auth
    
    def test_02_session_creation_stores_any_counter(self):
        """Test session creation stores any counter value (worker manages validation)"""
        current_counter = self.passkey_obj.counter
        any_counter = current_counter - 1  # Any counter value should be stored
        
        # Session creation with any counter should succeed (worker manages validation)
        session_data = {
            'session_id': 'test_session_any_counter',
            'username': self.user_obj.username,
            'host_domain': self.host_obj.domain,
            'expires_at': '2024-01-01T20:00:00Z',
            'credential_id': self.passkey_obj.credential_id,
            'counter': any_counter,
            'created_ip': '192.168.1.101',
            'user_agent': 'Test Browser Any Counter'
        }
        
        from odoo.http import request
        from unittest.mock import Mock
        
        mock_request = Mock()
        mock_request.httprequest.data = json.dumps(session_data).encode()
        mock_request.env = self.env
        
        controller = SunrayRESTController()
        controller._authenticate_api = lambda r: self.api_key_obj
        controller._setup_request_context = lambda r: {'worker_id': 'test_worker'}
        
        # Call session creation - should succeed (server only stores)
        with patch('odoo.addons.sunray_core.controllers.rest_api.request', mock_request):
            response = controller.create_session()
        
        # Verify success response (server stores any counter value)
        response_data = json.loads(response.data.decode())
        self.assertTrue(response_data.get('success'))
        
        # Verify session was created
        session_obj = self.env['sunray.session'].search([
            ('session_id', '=', session_data['session_id'])
        ])
        self.assertTrue(session_obj)
        
        # Verify counter was stored (any value accepted)
        self.passkey_obj.invalidate_recordset()
        self.assertEqual(self.passkey_obj.counter, any_counter)
        
        # Verify audit log shows storage (not validation failure)
        audit_logs = self.env['sunray.audit.log'].search([
            ('event_type', '=', 'session.created'),
            ('sunray_user_id', '=', self.user_obj.id)
        ])
        self.assertTrue(audit_logs)
        details = json.loads(audit_logs[-1].details)
        self.assertEqual(details['counter_stored'], any_counter)
    
    def test_03_session_creation_requires_counter(self):
        """Test session creation requires counter (for debugging and audit purposes)"""
        original_counter = self.passkey_obj.counter
        
        # Create session without counter field - should fail
        session_data = {
            'session_id': 'test_session_no_counter',
            'username': self.user_obj.username,
            'host_domain': self.host_obj.domain,
            'expires_at': '2024-01-01T20:00:00Z',
            'credential_id': self.passkey_obj.credential_id,
            'created_ip': '192.168.1.102',
            'user_agent': 'Test Browser No Counter'
        }
        
        from odoo.http import request
        from unittest.mock import Mock
        
        mock_request = Mock()
        mock_request.httprequest.data = json.dumps(session_data).encode()
        mock_request.env = self.env
        
        controller = SunrayRESTController()
        controller._authenticate_api = lambda r: self.api_key_obj
        controller._setup_request_context = lambda r: {'worker_id': 'test_worker'}
        
        # Call session creation - should fail
        with patch('odoo.addons.sunray_core.controllers.rest_api.request', mock_request):
            response = controller.create_session()
        
        # Should fail due to missing counter
        if hasattr(response, 'status_code'):
            self.assertEqual(response.status_code, 400)
        elif hasattr(response, 'data'):
            response_data = json.loads(response.data.decode())
            self.assertFalse(response_data.get('success', True))
        
        # Verify counter was NOT updated
        self.passkey_obj.invalidate_recordset()
        self.assertEqual(self.passkey_obj.counter, original_counter)
        
        # Verify session was NOT created
        session_obj = self.env['sunray.session'].search([
            ('session_id', '=', session_data['session_id'])
        ])
        self.assertFalse(session_obj)
    
    def test_04_session_creation_no_credential_id(self):
        """Test session creation without credential_id (should succeed, counter not stored)"""
        original_counter = self.passkey_obj.counter
        
        # Create session without credential_id
        session_data = {
            'session_id': 'test_session_no_credential',
            'username': self.user_obj.username,
            'host_domain': self.host_obj.domain,
            'expires_at': '2024-01-01T20:00:00Z',
            'counter': 999,  # Counter provided but no credential_id
            'created_ip': '192.168.1.103'
        }
        
        from odoo.http import request
        from unittest.mock import Mock
        
        mock_request = Mock()
        mock_request.httprequest.data = json.dumps(session_data).encode()
        mock_request.env = self.env
        
        controller = SunrayRESTController()
        controller._authenticate_api = lambda r: self.api_key_obj
        controller._setup_request_context = lambda r: {'worker_id': 'test_worker'}
        
        # Call session creation
        with patch('odoo.addons.sunray_core.controllers.rest_api.request', mock_request):
            response = controller.create_session()
        
        # Should succeed (counter ignored without credential_id)
        if hasattr(response, 'data'):
            response_data = json.loads(response.data.decode())
            self.assertTrue(response_data['success'])
        
        # Verify counter was NOT updated (no credential_id)
        self.passkey_obj.invalidate_recordset()
        self.assertEqual(self.passkey_obj.counter, original_counter)
    
    def test_05_session_creation_requires_expires_at(self):
        """Test session creation requires expires_at field (worker provides expiration)"""
        
        # Create session without expires_at field - should fail
        session_data = {
            'session_id': 'test_session_no_expires',
            'username': self.user_obj.username,
            'host_domain': self.host_obj.domain,
            'credential_id': self.passkey_obj.credential_id,
            'counter': 50,
            'created_ip': '192.168.1.104',
            'user_agent': 'Test Browser No Expires'
        }
        
        from odoo.http import request
        from unittest.mock import Mock
        
        mock_request = Mock()
        mock_request.httprequest.data = json.dumps(session_data).encode()
        mock_request.env = self.env
        
        controller = SunrayRESTController()
        controller._authenticate_api = lambda r: self.api_key_obj
        controller._setup_request_context = lambda r: {'worker_id': 'test_worker'}
        
        # Call session creation - should fail
        with patch('odoo.addons.sunray_core.controllers.rest_api.request', mock_request):
            response = controller.create_session()
        
        # Should fail due to missing expires_at
        if hasattr(response, 'status_code'):
            self.assertEqual(response.status_code, 400)
        elif hasattr(response, 'data'):
            response_data = json.loads(response.data.decode())
            self.assertFalse(response_data.get('success', True))
        
        # Verify session was NOT created
        session_obj = self.env['sunray.session'].search([
            ('session_id', '=', session_data['session_id'])
        ])
        self.assertFalse(session_obj)
    
    def test_06_session_creation_invalid_expires_at_format(self):
        """Test session creation with invalid expires_at format"""
        
        # Create session with invalid expires_at format - should fail
        session_data = {
            'session_id': 'test_session_invalid_expires',
            'username': self.user_obj.username,
            'host_domain': self.host_obj.domain,
            'expires_at': 'invalid-datetime-format',
            'credential_id': self.passkey_obj.credential_id,
            'counter': 50,
            'created_ip': '192.168.1.105',
            'user_agent': 'Test Browser Invalid Expires'
        }
        
        from odoo.http import request
        from unittest.mock import Mock
        
        mock_request = Mock()
        mock_request.httprequest.data = json.dumps(session_data).encode()
        mock_request.env = self.env
        
        controller = SunrayRESTController()
        controller._authenticate_api = lambda r: self.api_key_obj
        controller._setup_request_context = lambda r: {'worker_id': 'test_worker'}
        
        # Call session creation - should fail
        with patch('odoo.addons.sunray_core.controllers.rest_api.request', mock_request):
            response = controller.create_session()
        
        # Should fail due to invalid expires_at format
        if hasattr(response, 'status_code'):
            self.assertEqual(response.status_code, 400)
        elif hasattr(response, 'data'):
            response_data = json.loads(response.data.decode())
            self.assertFalse(response_data.get('success', True))
        
        # Verify session was NOT created
        session_obj = self.env['sunray.session'].search([
            ('session_id', '=', session_data['session_id'])
        ])
        self.assertFalse(session_obj)

    def test_07_counter_direct_assignment(self):
        """Test that counter can be directly assigned any value (storage-only)"""
        original_counter = self.passkey_obj.counter
        
        # Test various counter values
        test_counters = [0, 5, 100, 999, original_counter - 10, original_counter + 50]
        
        for test_counter in test_counters:
            # Direct assignment should always work (no validation)
            self.passkey_obj.counter = test_counter
            self.passkey_obj.invalidate_recordset()
            self.assertEqual(self.passkey_obj.counter, test_counter)
            
            # Test last_used can also be updated directly
            from odoo import fields
            now = fields.Datetime.now()
            self.passkey_obj.last_used = now
            self.passkey_obj.invalidate_recordset()
            self.assertEqual(self.passkey_obj.last_used, now)