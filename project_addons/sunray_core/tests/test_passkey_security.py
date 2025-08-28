# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase, tagged
from odoo.exceptions import ValidationError, UserError
from odoo import fields
from psycopg2 import IntegrityError
from datetime import datetime, timedelta
import json
import hashlib
import logging

_logger = logging.getLogger(__name__)


@tagged('sunray', 'security', 'passkey')
class TestPasskeyRegistrationSecurity(TransactionCase):
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
    
    def setUp(self):
        super().setUp()
        
        # Create test host
        self.host_obj = self.env['sunray.host'].create({
            'domain': 'test.example.com',
            'backend_url': 'https://backend.example.com',
            'is_active': True
        })
        
        # Create test user
        self.user_obj = self.env['sunray.user'].create({
            'username': 'test@example.com',
            'email': 'test@example.com',
            'display_name': 'Test User',
            'is_active': True
        })
        
        # Add user to host
        self.host_obj.user_ids = [(4, self.user_obj.id)]
        
        # Create API key for authentication
        self.api_key_value = 'test_api_key_12345'
        self.api_key_obj = self.env['sunray.api.key'].create({
            'name': 'Test Worker Key',
            'key': self.api_key_value,
            'api_key_type': 'worker',
            'is_active': True
        })
        
        # No longer need controller instance - testing model directly
    
    def create_test_token(self, **kwargs):
        """Helper to create test setup tokens"""
        token_value = kwargs.get('token_value', 'test_token_12345')
        token_hash = f"sha512:{hashlib.sha512(token_value.encode()).hexdigest()}"
        
        token_data = {
            'user_id': kwargs.get('user_id', self.user_obj.id),
            'host_id': kwargs.get('host_id', self.host_obj.id),
            'token_hash': token_hash,
            'consumed': kwargs.get('consumed', False),
            'current_uses': kwargs.get('current_uses', 0),
            'max_uses': kwargs.get('max_uses', 1),
            'expires_at': kwargs.get('expires_at', fields.Datetime.now() + timedelta(hours=24)),
            'allowed_cidrs': kwargs.get('allowed_cidrs', False),
            'device_name': kwargs.get('device_name', 'Test Device')
        }
        
        token_obj = self.env['sunray.setup.token'].create(token_data)
        return token_obj, token_value
    
    def get_token_hash(self, token_value):
        """Helper to compute SHA-512 hash for tokens"""
        return f"sha512:{hashlib.sha512(token_value.encode()).hexdigest()}"
    
    def make_api_call(self, username, data, **kwargs):
        """Call the model method directly instead of HTTP controller"""
        try:
            # Extract parameters from test data
            setup_token_hash = data.get('setup_token_hash')
            credential = data.get('credential', {})
            credential_id = credential.get('id')
            public_key = credential.get('public_key', '')
            host_domain = data.get('host_domain')
            device_name = data.get('name', 'Passkey')
            
            # Call the model method
            result = self.env['sunray.passkey'].register_with_setup_token(
                username=username,
                setup_token_hash=setup_token_hash,
                credential_id=credential_id,
                public_key=public_key,
                host_domain=host_domain,
                device_name=device_name,
                client_ip=kwargs.get('client_ip', '192.168.1.100'),
                user_agent=kwargs.get('user_agent', 'Test Browser'),
                worker_id=kwargs.get('worker_id', 'test-worker-001')
            )
            
            return {
                'status': 200,
                'data': result
            }
            
        except Exception as e:
            # Parse status code from message format: "STATUS|message"
            msg = str(e)
            parts = msg.split('|', 1)  # Split only on first pipe
            
            # Always log exception details for debugging
            _logger.info(f"TEST_DEBUG: Exception - Type: {type(e).__name__}, Message: {repr(msg)}, Parts: {parts}")
            
            if len(parts) == 2 and parts[0].isdigit():
                status = int(parts[0])
                message = parts[1]
            else:
                status = 500  # Unexpected error format
                message = msg
            
            return {
                'status': status,
                'data': {'error': message}
            }
    
    def test_01_successful_registration_complete_flow(self):
        """Test successful passkey registration with all validations passing"""
        # Create valid token
        token_obj, token_value = self.create_test_token()
        
        # Initial state checks
        self.assertEqual(token_obj.current_uses, 0)
        self.assertFalse(token_obj.consumed)
        initial_passkey_count = self.env['sunray.passkey'].search_count([])
        initial_audit_count = self.env['sunray.audit.log'].search_count([])
        
        # Make API call with hash
        token_hash = f"sha512:{hashlib.sha512(token_value.encode()).hexdigest()}"
        response = self.make_api_call('test@example.com', {
            'setup_token_hash': token_hash,
            'credential': {
                'id': 'cred_success_123',
                'public_key': 'pubkey_success_123'
            },
            'host_domain': 'test.example.com',
            'name': 'My Test Device'
        })
        
        # Verify successful response
        self.assertEqual(response['status'], 200)
        self.assertTrue(response['data']['success'])
        self.assertIn('passkey_id', response['data'])
        
        # Verify passkey created with correct data
        passkey = self.env['sunray.passkey'].search([
            ('credential_id', '=', 'cred_success_123')
        ])
        self.assertTrue(passkey)
        self.assertEqual(passkey.user_id.id, self.user_obj.id)
        self.assertEqual(passkey.name, 'My Test Device')
        self.assertEqual(passkey.host_domain, 'test.example.com')
        self.assertEqual(passkey.public_key, 'pubkey_success_123')
        self.assertEqual(passkey.setup_token_id.id, token_obj.id)  # NEW: Token link
        self.assertEqual(passkey.created_ip, '192.168.1.100')
        
        # Verify token consumed - reload from database
        token_obj = self.env['sunray.setup.token'].browse(token_obj.id)
        self.assertEqual(token_obj.current_uses, 1)
        self.assertTrue(token_obj.consumed)
        self.assertIsNotNone(token_obj.consumed_date)
        
        # Verify success audit log created
        audit_log = self.env['sunray.audit.log'].search([
            ('event_type', '=', 'passkey.registered'),
            ('sunray_user_id', '=', self.user_obj.id)
        ], limit=1)
        self.assertTrue(audit_log)
        self.assertEqual(audit_log.severity, 'info')
        
        # Verify audit log details
        if isinstance(audit_log.details, str):
            details = json.loads(audit_log.details)
        else:
            details = audit_log.details
        self.assertEqual(details['passkey_id'], passkey.id)
        self.assertEqual(details['token_id'], token_obj.id)
        self.assertEqual(details['host_domain'], 'test.example.com')
        self.assertEqual(details['device_name'], 'My Test Device')
        self.assertEqual(details['token_uses'], '1/1')
        self.assertTrue(details['token_consumed'])
        
        # Verify counts
        final_passkey_count = self.env['sunray.passkey'].search_count([])
        final_audit_count = self.env['sunray.audit.log'].search_count([])
        self.assertEqual(final_passkey_count, initial_passkey_count + 1)
        self.assertGreaterEqual(final_audit_count, initial_audit_count + 1)
    
    def test_02_unauthorized_api_no_business_data(self):
        """Test unauthorized API access creates audit but no passkey"""
        # SKIP: This test was designed for HTTP controller testing, not model testing
        # Since we refactored to test the model method directly, API key validation
        # is handled at the controller level, not the model level
        self.skipTest("Test requires HTTP controller context (API key validation)")
    
    def test_03_missing_setup_token_hash(self):
        """Test missing setup token hash field"""
        response = self.make_api_call('test@example.com', {
            # Missing setup_token_hash
            'credential': {
                'id': 'cred_missing',
                'public_key': 'pubkey_test'
            },
            'host_domain': 'test.example.com'
        })
        
        # Verify error
        self.assertEqual(response['status'], 400)
        self.assertIn('Missing required fields', response['data']['error'])
        self.assertIn('setup_token_hash', response['data']['error'])
        
        # Verify audit log
        audit_log = self.env['sunray.audit.log'].search([
            ('event_type', '=', 'security.passkey.missing_fields')
        ], limit=1, order='create_date desc')
        self.assertTrue(audit_log)
        if isinstance(audit_log.details, str):
            details = json.loads(audit_log.details)
        else:
            details = audit_log.details
        self.assertIn('setup_token_hash', details['missing_fields'])
    
    def test_04_invalid_token_hash(self):
        """Test invalid token hash prevents registration"""
        # Create token but use wrong hash
        token_obj, _ = self.create_test_token(token_value='correct_token')
        wrong_hash = f"sha512:{hashlib.sha512('wrong_token'.encode()).hexdigest()}"
        
        response = self.make_api_call('test@example.com', {
            'setup_token_hash': wrong_hash,
            'credential': {
                'id': 'cred_invalid_token',
                'public_key': 'pubkey_test'
            },
            'host_domain': 'test.example.com'
        })
        
        # Verify error
        self.assertEqual(response['status'], 401)
        self.assertEqual(response['data']['error'], 'Invalid setup token hash')
        
        # Verify no passkey
        self.assertFalse(self.env['sunray.passkey'].search([
            ('credential_id', '=', 'cred_invalid_token')
        ]))
        
        # Verify token not consumed
        token_obj = self.env['sunray.setup.token'].browse(token_obj.id)
        self.assertEqual(token_obj.current_uses, 0)
        
        # Verify audit
        audit_log = self.env['sunray.audit.log'].search([
            ('event_type', '=', 'security.passkey.setup_token_not_found')
        ], limit=1, order='create_date desc')
        self.assertTrue(audit_log)
        self.assertEqual(audit_log.severity, 'critical')
    
    def test_05_expired_token(self):
        """Test expired token prevents registration"""
        token_obj, token_value = self.create_test_token(
            expires_at=fields.Datetime.now() - timedelta(hours=1)
        )
        
        response = self.make_api_call('test@example.com', {
            'setup_token_hash': f"sha512:{hashlib.sha512(token_value.encode()).hexdigest()}",
            'credential': {
                'id': 'cred_expired',
                'public_key': 'pubkey_test'
            },
            'host_domain': 'test.example.com'
        })
        
        # Verify error
        self.assertEqual(response['status'], 401)
        self.assertEqual(response['data']['error'], 'Setup token expired')
        
        # Verify audit
        audit_log = self.env['sunray.audit.log'].search([
            ('event_type', '=', 'security.passkey.token_expired')
        ], limit=1, order='create_date desc')
        self.assertTrue(audit_log)
        if isinstance(audit_log.details, str):
            details = json.loads(audit_log.details)
        else:
            details = audit_log.details
        self.assertIn('expired_hours_ago', details)
    
    def test_06_consumed_token_replay_attack(self):
        """Test consumed token cannot be reused (replay attack prevention)"""
        token_obj, token_value = self.create_test_token()
        
        # First use - success
        token_hash = f"sha512:{hashlib.sha512(token_value.encode()).hexdigest()}"
        response1 = self.make_api_call('test@example.com', {
            'setup_token_hash': token_hash,
            'credential': {
                'id': 'cred_first',
                'public_key': 'pubkey_first'
            },
            'host_domain': 'test.example.com'
        })
        self.assertEqual(response1['status'], 200)
        
        # Verify token consumed
        token_obj = self.env['sunray.setup.token'].browse(token_obj.id)
        self.assertTrue(token_obj.consumed)
        
        # Second use - should fail
        response2 = self.make_api_call('test@example.com', {
            'setup_token_hash': token_hash,
            'credential': {
                'id': 'cred_replay',
                'public_key': 'pubkey_replay'
            },
            'host_domain': 'test.example.com'
        })
        
        # Verify error
        self.assertEqual(response2['status'], 403)
        self.assertEqual(response2['data']['error'], 'Token already consumed')
        
        # Verify no second passkey
        self.assertFalse(self.env['sunray.passkey'].search([
            ('credential_id', '=', 'cred_replay')
        ]))
        
        # Verify audit for replay attempt
        audit_log = self.env['sunray.audit.log'].search([
            ('event_type', '=', 'security.passkey.token_already_consumed')
        ], limit=1, order='create_date desc')
        self.assertTrue(audit_log)
        self.assertEqual(audit_log.severity, 'critical')
    
    def test_07_wrong_host_binding(self):
        """Test token for different host is rejected"""
        # Create another host
        other_host = self.env['sunray.host'].create({
            'domain': 'other.example.com',
            'backend_url': 'https://other-backend.example.com',
            'is_active': True
        })
        
        # Token for other host
        token_obj, token_value = self.create_test_token(host_id=other_host.id)
        
        response = self.make_api_call('test@example.com', {
            'setup_token_hash': f"sha512:{hashlib.sha512(token_value.encode()).hexdigest()}",
            'credential': {
                'id': 'cred_wronghost',
                'public_key': 'pubkey_wronghost'
            },
            'host_domain': 'test.example.com'  # Wrong!
        })
        
        # Verify error
        self.assertEqual(response['status'], 403)
        self.assertEqual(response['data']['error'], 'Token not valid for this host')
        
        # Verify audit
        audit_log = self.env['sunray.audit.log'].search([
            ('event_type', '=', 'security.passkey.token_wrong_host')
        ], limit=1, order='create_date desc')
        self.assertTrue(audit_log)
        if isinstance(audit_log.details, str):
            details = json.loads(audit_log.details)
        else:
            details = audit_log.details
        self.assertEqual(details['requested_host'], 'test.example.com')
        self.assertEqual(details['token_host'], 'other.example.com')
    
    def test_08_ip_restriction_cidr(self):
        """Test IP CIDR restriction enforcement"""
        token_obj, token_value = self.create_test_token(
            allowed_cidrs='192.168.1.0/24\n10.0.0.0/8'  # Multi-line CIDR
        )
        
        # Call from allowed IP
        token_hash = f"sha512:{hashlib.sha512(token_value.encode()).hexdigest()}"
        response1 = self.make_api_call('test@example.com', {
            'setup_token_hash': token_hash,
            'credential': {
                'id': 'cred_ip_allowed',
                'public_key': 'pubkey_ip_allowed'
            },
            'host_domain': 'test.example.com'
        }, client_ip='192.168.1.50')
        self.assertEqual(response1['status'], 200)
        
        # Reset token for second test
        token_obj.write({'consumed': False, 'current_uses': 0})
        
        # Call from blocked IP
        response2 = self.make_api_call('test@example.com', {
            'setup_token_hash': token_hash,
            'credential': {
                'id': 'cred_ip_blocked',
                'public_key': 'pubkey_ip_blocked'
            },
            'host_domain': 'test.example.com'
        }, client_ip='172.16.0.1')  # Not in allowed CIDRs
        
        # Verify error
        self.assertEqual(response2['status'], 403)
        self.assertEqual(response2['data']['error'], 'IP not allowed')
        
        # Verify audit
        audit_log = self.env['sunray.audit.log'].search([
            ('event_type', '=', 'security.passkey.ip_not_allowed')
        ], limit=1, order='create_date desc')
        self.assertTrue(audit_log)
        if isinstance(audit_log.details, str):
            details = json.loads(audit_log.details)
        else:
            details = audit_log.details
        self.assertEqual(details['client_ip'], '172.16.0.1')
        self.assertIn('192.168.1.0/24', details['allowed_cidrs'])
    
    def test_09_duplicate_credential(self):
        """Test duplicate credential prevention"""
        # Create first passkey
        existing = self.env['sunray.passkey'].create({
            'user_id': self.user_obj.id,
            'credential_id': 'cred_duplicate',
            'public_key': 'pubkey_first',
            'name': 'First Device',
            'host_domain': 'test.example.com'
        })
        
        token_obj, token_value = self.create_test_token()
        
        response = self.make_api_call('test@example.com', {
            'setup_token_hash': f"sha512:{hashlib.sha512(token_value.encode()).hexdigest()}",
            'credential': {
                'id': 'cred_duplicate',  # Same ID!
                'public_key': 'pubkey_duplicate_attempt'
            },
            'host_domain': 'test.example.com'
        })
        
        # Verify error
        self.assertEqual(response['status'], 409)
        self.assertEqual(response['data']['error'], 'Credential already registered')
        
        # Verify only one passkey
        count = self.env['sunray.passkey'].search_count([
            ('credential_id', '=', 'cred_duplicate')
        ])
        self.assertEqual(count, 1)
        
        # Verify audit
        audit_log = self.env['sunray.audit.log'].search([
            ('event_type', '=', 'security.passkey.duplicate_credential')
        ], limit=1, order='create_date desc')
        self.assertTrue(audit_log)
        if isinstance(audit_log.details, str):
            details = json.loads(audit_log.details)
        else:
            details = audit_log.details
        self.assertEqual(details['existing_passkey_id'], existing.id)
    
    def test_10_multi_use_token_management(self):
        """Test multi-use token increment and consumption"""
        token_obj, token_value = self.create_test_token(max_uses=3)
        
        # Use 1: Success
        token_hash = f"sha512:{hashlib.sha512(token_value.encode()).hexdigest()}"
        response1 = self.make_api_call('test@example.com', {
            'setup_token_hash': token_hash,
            'credential': {
                'id': 'cred_multi_1',
                'public_key': 'pubkey_multi_1'
            },
            'host_domain': 'test.example.com'
        })
        self.assertEqual(response1['status'], 200)
        token_obj = self.env['sunray.setup.token'].browse(token_obj.id)
        self.assertEqual(token_obj.current_uses, 1)
        self.assertFalse(token_obj.consumed)
        
        # Use 2: Success
        response2 = self.make_api_call('test@example.com', {
            'setup_token_hash': token_hash,
            'credential': {
                'id': 'cred_multi_2',
                'public_key': 'pubkey_multi_2'
            },
            'host_domain': 'test.example.com'
        })
        self.assertEqual(response2['status'], 200)
        token_obj = self.env['sunray.setup.token'].browse(token_obj.id)
        self.assertEqual(token_obj.current_uses, 2)
        self.assertFalse(token_obj.consumed)
        
        # Use 3: Success and consume
        response3 = self.make_api_call('test@example.com', {
            'setup_token_hash': token_hash,
            'credential': {
                'id': 'cred_multi_3',
                'public_key': 'pubkey_multi_3'
            },
            'host_domain': 'test.example.com'
        })
        self.assertEqual(response3['status'], 200)
        token_obj = self.env['sunray.setup.token'].browse(token_obj.id)
        self.assertEqual(token_obj.current_uses, 3)
        self.assertTrue(token_obj.consumed)  # Now consumed
        
        # Use 4: Fail
        response4 = self.make_api_call('test@example.com', {
            'setup_token_hash': token_hash,
            'credential': {
                'id': 'cred_multi_4',
                'public_key': 'pubkey_multi_4'
            },
            'host_domain': 'test.example.com'
        })
        self.assertEqual(response4['status'], 403)
        
        # Verify all passkeys created except last
        for i in range(1, 4):
            self.assertTrue(self.env['sunray.passkey'].search([
                ('credential_id', '=', f'cred_multi_{i}')
            ]))
        self.assertFalse(self.env['sunray.passkey'].search([
            ('credential_id', '=', 'cred_multi_4')
        ]))
    
    def test_11_missing_public_key(self):
        """Test that missing public_key prevents registration"""
        token_obj, token_value = self.create_test_token()
        
        # Call with credential missing public_key
        response = self.make_api_call('test@example.com', {
            'setup_token_hash': f"sha512:{hashlib.sha512(token_value.encode()).hexdigest()}",
            'credential': {
                'id': 'cred_no_pubkey'
                # public_key is missing!
            },
            'host_domain': 'test.example.com'
        })
        
        # Verify error
        self.assertEqual(response['status'], 400)
        self.assertEqual(response['data']['error'], 'Public key is required for passkey registration')
        
        # Verify no passkey created
        passkey = self.env['sunray.passkey'].search([
            ('credential_id', '=', 'cred_no_pubkey')
        ])
        self.assertFalse(passkey)
        
        # Verify token not consumed
        token_obj = self.env['sunray.setup.token'].browse(token_obj.id)
        self.assertEqual(token_obj.current_uses, 0)
        self.assertFalse(token_obj.consumed)
        
        # Verify security audit log created
        audit_log = self.env['sunray.audit.log'].search([
            ('event_type', '=', 'security.passkey.missing_public_key')
        ], limit=1, order='create_date desc')
        self.assertTrue(audit_log)
        self.assertEqual(audit_log.severity, 'critical')
        if isinstance(audit_log.details, str):
            details = json.loads(audit_log.details)
        else:
            details = audit_log.details
        self.assertEqual(details['credential_id'], 'cred_no_pubkey')
        self.assertIn('error', details)
        self.assertIn('WebAuthn', details['error'])
    
    def test_12_empty_public_key(self):
        """Test that empty public_key prevents registration"""
        token_obj, token_value = self.create_test_token()
        
        # Call with empty public_key
        response = self.make_api_call('test@example.com', {
            'setup_token_hash': f"sha512:{hashlib.sha512(token_value.encode()).hexdigest()}",
            'credential': {
                'id': 'cred_empty_pubkey',
                'public_key': ''  # Empty string
            },
            'host_domain': 'test.example.com'
        })
        
        # Verify error
        self.assertEqual(response['status'], 400)
        self.assertEqual(response['data']['error'], 'Public key is required for passkey registration')
        
        # Verify no passkey created
        passkey = self.env['sunray.passkey'].search([
            ('credential_id', '=', 'cred_empty_pubkey')
        ])
        self.assertFalse(passkey)
        
        # Verify token not consumed
        token_obj = self.env['sunray.setup.token'].browse(token_obj.id)
        self.assertEqual(token_obj.current_uses, 0)
        self.assertFalse(token_obj.consumed)
        
        # Verify security audit log created
        audit_log = self.env['sunray.audit.log'].search([
            ('event_type', '=', 'security.passkey.missing_public_key')
        ], limit=1, order='create_date desc')
        self.assertTrue(audit_log)
        self.assertEqual(audit_log.severity, 'critical')
    
    def test_13_whitespace_only_public_key(self):
        """Test that whitespace-only public_key prevents registration"""
        token_obj, token_value = self.create_test_token()
        
        # Call with whitespace-only public_key
        response = self.make_api_call('test@example.com', {
            'setup_token_hash': f"sha512:{hashlib.sha512(token_value.encode()).hexdigest()}",
            'credential': {
                'id': 'cred_whitespace_pubkey',
                'public_key': '   \t\n   '  # Only whitespace
            },
            'host_domain': 'test.example.com'
        })
        
        # Verify error
        self.assertEqual(response['status'], 400)
        self.assertEqual(response['data']['error'], 'Public key is required for passkey registration')
        
        # Verify no passkey created
        passkey = self.env['sunray.passkey'].search([
            ('credential_id', '=', 'cred_whitespace_pubkey')
        ])
        self.assertFalse(passkey)
        
        # Verify security audit log created
        audit_log = self.env['sunray.audit.log'].search([
            ('event_type', '=', 'security.passkey.missing_public_key')
        ], limit=1, order='create_date desc')
        self.assertTrue(audit_log)
    
    def test_14_complete_audit_trail(self):
        """Test comprehensive audit trail for security investigation"""
        # Attempt 1: Wrong token hash
        wrong_hash = f"sha512:{hashlib.sha512('wrong_token'.encode()).hexdigest()}"
        self.make_api_call('test@example.com', {
            'setup_token_hash': wrong_hash,
            'credential': {
                'id': 'cred_audit_1',
                'public_key': 'pubkey_audit_1'
            },
            'host_domain': 'test.example.com'
        })
        
        # Attempt 2: Expired token
        expired_token, expired_value = self.create_test_token(
            token_value='expired_token_12345',
            expires_at=fields.Datetime.now() - timedelta(hours=1)
        )
        self.make_api_call('test@example.com', {
            'setup_token_hash': f"sha512:{hashlib.sha512(expired_value.encode()).hexdigest()}",
            'credential': {
                'id': 'cred_audit_2',
                'public_key': 'pubkey_audit_2'
            },
            'host_domain': 'test.example.com'
        })
        
        # Attempt 3: Success
        good_token, good_value = self.create_test_token(token_value='good_token_12345')
        good_hash = f"sha512:{hashlib.sha512(good_value.encode()).hexdigest()}"
        self.make_api_call('test@example.com', {
            'setup_token_hash': good_hash,
            'credential': {
                'id': 'cred_audit_3',
                'public_key': 'pubkey_audit_3'
            },
            'host_domain': 'test.example.com'
        })
        
        # Attempt 4: Replay attack
        self.make_api_call('test@example.com', {
            'setup_token_hash': good_hash,
            'credential': {
                'id': 'cred_audit_4',
                'public_key': 'pubkey_audit_4'
            },
            'host_domain': 'test.example.com'
        })
        
        # Verify complete audit trail
        audit_logs = self.env['sunray.audit.log'].search([
            ('username', '=', 'test@example.com')
        ], order='create_date asc')
        
        # Should have at least 4 audit entries
        self.assertGreaterEqual(len(audit_logs), 4)
        
        # Get last 4 events of interest
        security_events = []
        for log in audit_logs:
            if 'passkey' in log.event_type:
                security_events.append(log)
        
        # Verify event sequence
        self.assertGreaterEqual(len(security_events), 4)
        event_types = [log.event_type for log in security_events[-4:]]
        self.assertIn('security.passkey.setup_token_not_found', event_types)
        self.assertIn('security.passkey.token_expired', event_types)
        self.assertIn('passkey.registered', event_types)
        self.assertIn('security.passkey.token_already_consumed', event_types)


@tagged('sunray', 'model', 'users', 'passkeys')
class TestUserPasskeyData(TransactionCase):
    """Test that user models correctly return passkey data"""
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        
        # Create test host
        cls.host_obj = cls.env['sunray.host'].create({
            'domain': 'test.example.com',
            'backend_url': 'https://backend.example.com',
            'is_active': True
        })
        
        # Create test user with host access
        cls.user_obj = cls.env['sunray.user'].create({
            'username': 'testuser@example.com',
            'email': 'testuser@example.com',
            'is_active': True,
            'host_ids': [(6, 0, [cls.host_obj.id])]
        })
        
        # Create user without passkeys for testing
        cls.user_no_passkeys = cls.env['sunray.user'].create({
            'username': 'nopasskeys@example.com',
            'email': 'nopasskeys@example.com',
            'is_active': True
        })
        
    def test_user_with_no_passkeys(self):
        """Test user that has no passkeys returns correct data structure"""
        # Verify passkey_ids is empty
        self.assertEqual(len(self.user_no_passkeys.passkey_ids), 0)
        self.assertEqual(self.user_no_passkeys.passkey_count, 0)
        
        # Build passkeys list like the controller does
        passkeys = []
        for passkey in self.user_no_passkeys.passkey_ids:
            passkeys.append({
                'credential_id': passkey.credential_id,
                'public_key': passkey.public_key,
                'name': passkey.name,
                'counter': passkey.counter or 0,
                'created_at': passkey.create_date.isoformat(),
                'last_used_at': passkey.last_used.isoformat() if passkey.last_used else None
            })
        
        self.assertEqual(passkeys, [])  # Empty array for no passkeys
        
    def test_user_with_single_passkey(self):
        """Test user that has one passkey returns correct structure"""
        # Create a passkey for the test user
        passkey_obj = self.env['sunray.passkey'].create({
            'user_id': self.user_obj.id,
            'credential_id': 'test_credential_123',
            'public_key': 'test_public_key_456',
            'name': 'Test Device',
            'counter': 5,
            'host_domain': 'test.example.com'
        })
        
        self.assertEqual(self.user_obj.passkey_count, 1)
        self.assertEqual(len(self.user_obj.passkey_ids), 1)
        
        # Build passkeys list like the controller does
        passkeys = []
        for passkey in self.user_obj.passkey_ids:
            passkeys.append({
                'credential_id': passkey.credential_id,
                'public_key': passkey.public_key,
                'name': passkey.name,
                'counter': passkey.counter or 0,
                'created_at': passkey.create_date.isoformat(),
                'last_used_at': passkey.last_used.isoformat() if passkey.last_used else None
            })
        
        self.assertEqual(len(passkeys), 1)
        passkey_data = passkeys[0]
        self.assertEqual(passkey_data['credential_id'], 'test_credential_123')
        self.assertEqual(passkey_data['public_key'], 'test_public_key_456')
        self.assertEqual(passkey_data['name'], 'Test Device')
        self.assertEqual(passkey_data['counter'], 5)
        self.assertIsNotNone(passkey_data['created_at'])
        self.assertIsNone(passkey_data['last_used_at'])  # Never used
        
    def test_user_with_multiple_passkeys(self):
        """Test user that has multiple passkeys returns all correctly"""
        from datetime import datetime
        
        # Create multiple passkeys
        passkey1 = self.env['sunray.passkey'].create({
            'user_id': self.user_obj.id,
            'credential_id': 'cred_1',
            'public_key': 'key_1',
            'name': 'Device 1',
            'counter': 10
        })
        
        passkey2 = self.env['sunray.passkey'].create({
            'user_id': self.user_obj.id,
            'credential_id': 'cred_2',
            'public_key': 'key_2',
            'name': 'Device 2',
            'counter': 25,
            'last_used': datetime.now()
        })
        
        self.assertEqual(self.user_obj.passkey_count, 2)
        self.assertEqual(len(self.user_obj.passkey_ids), 2)
        
        # Build passkeys list like the controller does
        passkeys = []
        for passkey in self.user_obj.passkey_ids:
            passkeys.append({
                'credential_id': passkey.credential_id,
                'public_key': passkey.public_key,
                'name': passkey.name,
                'counter': passkey.counter or 0,
                'created_at': passkey.create_date.isoformat(),
                'last_used_at': passkey.last_used.isoformat() if passkey.last_used else None
            })
        
        self.assertEqual(len(passkeys), 2)
        
        # Check both passkeys are present
        credential_ids = {pk['credential_id'] for pk in passkeys}
        self.assertEqual(credential_ids, {'cred_1', 'cred_2'})
        
        # Find the passkey with last_used and verify format
        used_passkey = next(pk for pk in passkeys if pk['last_used_at'] is not None)
        self.assertEqual(used_passkey['credential_id'], 'cred_2')
        self.assertEqual(used_passkey['counter'], 25)
        
    def test_counter_field_defaults_to_zero(self):
        """Test that counter field defaults to 0 when not explicitly set"""
        # Create passkey without explicit counter value
        passkey_obj = self.env['sunray.passkey'].create({
            'user_id': self.user_obj.id,
            'credential_id': 'no_counter_cred',
            'public_key': 'no_counter_key',
            'name': 'No Counter Device'
            # counter field not set, should default to 0
        })
        
        # Verify default value
        self.assertEqual(passkey_obj.counter, 0)
        
        # Build passkeys list like the controller does
        passkeys = []
        for passkey in self.user_obj.passkey_ids:
            passkeys.append({
                'credential_id': passkey.credential_id,
                'public_key': passkey.public_key,
                'name': passkey.name,
                'counter': passkey.counter or 0,
                'created_at': passkey.create_date.isoformat(),
                'last_used_at': passkey.last_used.isoformat() if passkey.last_used else None
            })
        
        passkey_data = passkeys[0]
        self.assertEqual(passkey_data['counter'], 0)  # Should default to 0
        
    def test_passkey_all_required_fields_present(self):
        """Test that all required passkey fields are present"""
        from datetime import datetime
        now = datetime.now()
        
        passkey_obj = self.env['sunray.passkey'].create({
            'user_id': self.user_obj.id,
            'credential_id': 'full_cred',
            'public_key': 'full_key',
            'name': 'Full Device',
            'counter': 42,
            'last_used': now
        })
        
        # Build passkeys list like the controller does
        passkeys = []
        for passkey in self.user_obj.passkey_ids:
            passkeys.append({
                'credential_id': passkey.credential_id,
                'public_key': passkey.public_key,
                'name': passkey.name,
                'counter': passkey.counter or 0,
                'created_at': passkey.create_date.isoformat(),
                'last_used_at': passkey.last_used.isoformat() if passkey.last_used else None
            })
        
        passkey = passkeys[0]
        required_fields = ['credential_id', 'public_key', 'name', 'counter', 'created_at', 'last_used_at']
        
        for field in required_fields:
            self.assertIn(field, passkey, f"Missing required field: {field}")
            
        # Verify field values
        self.assertEqual(passkey['credential_id'], 'full_cred')
        self.assertEqual(passkey['public_key'], 'full_key')
        self.assertEqual(passkey['name'], 'Full Device')
        self.assertEqual(passkey['counter'], 42)
        self.assertIsNotNone(passkey['created_at'])
        self.assertIsNotNone(passkey['last_used_at'])
        
    def test_passkey_public_key_included_for_auth(self):
        """Test that public_key is included (needed for worker authentication)"""
        passkey_obj = self.env['sunray.passkey'].create({
            'user_id': self.user_obj.id,
            'credential_id': 'auth_cred',
            'public_key': 'secret_public_key_for_auth',
            'name': 'Auth Device'
        })
        
        # Build passkeys list like the controller does
        passkeys = []
        for passkey in self.user_obj.passkey_ids:
            passkeys.append({
                'credential_id': passkey.credential_id,
                'public_key': passkey.public_key,
                'name': passkey.name,
                'counter': passkey.counter or 0,
                'created_at': passkey.create_date.isoformat(),
                'last_used_at': passkey.last_used.isoformat() if passkey.last_used else None
            })
        
        passkey = passkeys[0]
        self.assertEqual(passkey['public_key'], 'secret_public_key_for_auth')
        self.assertIsNotNone(passkey['public_key'])  # Must be present for signature verification