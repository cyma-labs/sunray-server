# -*- coding: utf-8 -*-

from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError
import base64
import cbor2
import json
from unittest.mock import patch
from datetime import datetime, timedelta


class TestCBORPublicKeys(TransactionCase):
    """Test CBOR/COSE public key validation"""

    def setUp(self):
        super().setUp()
        
        # Create test user
        self.test_user = self.env['sunray.user'].create({
            'username': 'testuser',
            'email': 'testuser@example.com',
            'is_active': True
        })
        
        # Create test host
        self.test_host = self.env['sunray.host'].create({
            'domain': 'test.example.com',
            'backend_url': 'http://localhost:8000',
            'is_active': True,
            'user_ids': [(4, self.test_user.id)]
        })
        
        # Create valid setup token
        self.setup_token = self.env['sunray.setup.token'].create({
            'user_id': self.test_user.id,
            'host_id': self.test_host.id,
            'expires_at': datetime.now() + timedelta(hours=24),
            'max_uses': 1,
            'token_hash': 'test_token_hash'
        })
        
        # Valid COSE key (EC2/ES256)
        self.valid_cose_key = {
            1: 2,    # kty: EC2
            3: -7,   # alg: ES256
            -1: 1,   # crv: P-256
            -2: b'x' * 32,  # x coordinate (32 bytes)
            -3: b'y' * 32   # y coordinate (32 bytes)
        }
        
        # Valid CBOR-encoded, base64-encoded public key
        cbor_data = cbor2.dumps(self.valid_cose_key)
        self.valid_public_key = base64.b64encode(cbor_data).decode('ascii')
        
        # Invalid keys for testing
        self.invalid_base64 = "not_base64!!!"
        self.invalid_cbor = base64.b64encode(b"not cbor data").decode('ascii')
        
        # Invalid COSE structure (missing required fields)
        invalid_cose = {"invalid": "structure"}
        invalid_cbor = cbor2.dumps(invalid_cose)
        self.invalid_cose_key = base64.b64encode(invalid_cbor).decode('ascii')
    
    def test_validate_cbor_public_key_valid(self):
        """Test validation of valid CBOR/COSE public key"""
        passkey_model = self.env['sunray.passkey']
        
        is_valid, result = passkey_model._validate_cbor_public_key(self.valid_public_key)
        
        self.assertTrue(is_valid)
        self.assertIsNotNone(result)
    
    def test_validate_cbor_public_key_invalid_base64(self):
        """Test validation fails for invalid base64"""
        passkey_model = self.env['sunray.passkey']
        
        is_valid, error_msg = passkey_model._validate_cbor_public_key(self.invalid_base64)
        
        self.assertFalse(is_valid)
        self.assertIn("Invalid base64 encoding", error_msg)
    
    def test_validate_cbor_public_key_invalid_cbor(self):
        """Test validation fails for invalid CBOR"""
        passkey_model = self.env['sunray.passkey']
        
        is_valid, error_msg = passkey_model._validate_cbor_public_key(self.invalid_cbor)
        
        self.assertFalse(is_valid)
        self.assertIn("Invalid CBOR format", error_msg)
    
    def test_validate_cbor_public_key_invalid_cose(self):
        """Test validation fails for invalid COSE structure"""
        passkey_model = self.env['sunray.passkey']
        
        is_valid, error_msg = passkey_model._validate_cbor_public_key(self.invalid_cose_key)
        
        self.assertFalse(is_valid)
        # Error message varies based on whether pycose is available
        self.assertTrue(
            "Missing required COSE key type field" in error_msg or
            "Invalid COSE key structure" in error_msg
        )
    
    def test_normalize_public_key_to_cbor_valid(self):
        """Test normalization of valid CBOR key"""
        passkey_model = self.env['sunray.passkey']
        
        normalized = passkey_model._normalize_public_key_to_cbor(self.valid_public_key)
        
        self.assertEqual(normalized, self.valid_public_key)
    
    def test_normalize_public_key_to_cbor_invalid(self):
        """Test normalization fails for invalid key"""
        passkey_model = self.env['sunray.passkey']
        
        with self.assertRaises(UserError) as context:
            passkey_model._normalize_public_key_to_cbor(self.invalid_base64)
        
        self.assertIn("Cannot normalize public key", str(context.exception))
    
    def test_registration_with_valid_cbor_key(self):
        """Test passkey registration with valid CBOR key"""
        result = self.env['sunray.passkey'].register_with_setup_token(
            username='testuser',
            setup_token_hash=self.setup_token.token_hash,
            credential_id='test_credential_123',
            public_key=self.valid_public_key,
            host_domain='test.example.com',
            device_name='Test Device',
            client_ip='127.0.0.1',
            user_agent='Test Browser',
            worker_id='test-worker'
        )
        
        self.assertTrue(result['success'])
        self.assertIn('passkey_id', result)
        
        # Verify passkey was created with CBOR key
        passkey = self.env['sunray.passkey'].browse(result['passkey_id'])
        self.assertEqual(passkey.public_key, self.valid_public_key)
        self.assertEqual(passkey.credential_id, 'test_credential_123')
    
    def test_registration_with_invalid_cbor_key_base64(self):
        """Test passkey registration fails with invalid base64 key"""
        with self.assertRaises(UserError) as context:
            self.env['sunray.passkey'].register_with_setup_token(
                username='testuser',
                setup_token_hash=self.setup_token.token_hash,
                credential_id='test_credential_456',
                public_key=self.invalid_base64,
                host_domain='test.example.com',
                device_name='Test Device',
                client_ip='127.0.0.1',
                user_agent='Test Browser',
                worker_id='test-worker'
            )
        
        error_msg = str(context.exception)
        self.assertIn("400|", error_msg)
        self.assertIn("Invalid WebAuthn public key format", error_msg)
        self.assertIn("Invalid base64 encoding", error_msg)
    
    def test_registration_with_invalid_cbor_key_cbor(self):
        """Test passkey registration fails with invalid CBOR key"""
        with self.assertRaises(UserError) as context:
            self.env['sunray.passkey'].register_with_setup_token(
                username='testuser',
                setup_token_hash=self.setup_token.token_hash,
                credential_id='test_credential_789',
                public_key=self.invalid_cbor,
                host_domain='test.example.com',
                device_name='Test Device',
                client_ip='127.0.0.1',
                user_agent='Test Browser',
                worker_id='test-worker'
            )
        
        error_msg = str(context.exception)
        self.assertIn("400|", error_msg)
        self.assertIn("Invalid WebAuthn public key format", error_msg)
        self.assertIn("Invalid CBOR format", error_msg)
    
    def test_registration_with_invalid_cose_structure(self):
        """Test passkey registration fails with invalid COSE structure"""
        with self.assertRaises(UserError) as context:
            self.env['sunray.passkey'].register_with_setup_token(
                username='testuser',
                setup_token_hash=self.setup_token.token_hash,
                credential_id='test_credential_cose',
                public_key=self.invalid_cose_key,
                host_domain='test.example.com',
                device_name='Test Device',
                client_ip='127.0.0.1',
                user_agent='Test Browser',
                worker_id='test-worker'
            )
        
        error_msg = str(context.exception)
        self.assertIn("400|", error_msg)
        self.assertIn("Invalid WebAuthn public key format", error_msg)
    
    def test_audit_events_on_cbor_validation_success(self):
        """Test audit events are created on successful CBOR validation"""
        initial_count = self.env['sunray.audit.log'].search_count([
            ('event_type', '=', 'passkey.cbor_validation_success')
        ])
        
        self.env['sunray.passkey'].register_with_setup_token(
            username='testuser',
            setup_token_hash=self.setup_token.token_hash,
            credential_id='test_credential_audit',
            public_key=self.valid_public_key,
            host_domain='test.example.com',
            device_name='Test Device',
            client_ip='127.0.0.1',
            user_agent='Test Browser',
            worker_id='test-worker'
        )
        
        final_count = self.env['sunray.audit.log'].search_count([
            ('event_type', '=', 'passkey.cbor_validation_success')
        ])
        
        self.assertEqual(final_count, initial_count + 1)
        
        # Check audit event details
        audit_event = self.env['sunray.audit.log'].search([
            ('event_type', '=', 'passkey.cbor_validation_success'),
            ('username', '=', 'testuser')
        ], limit=1)
        
        self.assertTrue(audit_event)
        self.assertEqual(audit_event.severity, 'info')
        self.assertIn('Valid CBOR/COSE format', audit_event.details)
    
    def test_audit_events_on_cbor_validation_failure(self):
        """Test audit events are created on CBOR validation failure"""
        initial_count = self.env['sunray.audit.log'].search_count([
            ('event_type', '=', 'security.passkey.invalid_cbor_format')
        ])
        
        with self.assertRaises(UserError):
            self.env['sunray.passkey'].register_with_setup_token(
                username='testuser',
                setup_token_hash=self.setup_token.token_hash,
                credential_id='test_credential_fail',
                public_key=self.invalid_base64,
                host_domain='test.example.com',
                device_name='Test Device',
                client_ip='127.0.0.1',
                user_agent='Test Browser',
                worker_id='test-worker'
            )
        
        final_count = self.env['sunray.audit.log'].search_count([
            ('event_type', '=', 'security.passkey.invalid_cbor_format')
        ])
        
        self.assertEqual(final_count, initial_count + 1)
        
        # Check audit event details
        audit_event = self.env['sunray.audit.log'].search([
            ('event_type', '=', 'security.passkey.invalid_cbor_format'),
            ('username', '=', 'testuser')
        ], limit=1)
        
        self.assertTrue(audit_event)
        self.assertEqual(audit_event.severity, 'critical')
        self.assertIn('Invalid base64 encoding', audit_event.details)
    
    def test_different_key_algorithms(self):
        """Test validation of different COSE key algorithms"""
        # Test RSA key (algorithm RS256 = -257)
        rsa_cose_key = {
            1: 3,    # kty: RSA
            3: -257, # alg: RS256
            -1: b'n' * 256,  # modulus (256 bytes for 2048-bit)
            -2: b'\x01\x00\x01'  # exponent (65537)
        }
        
        cbor_data = cbor2.dumps(rsa_cose_key)
        rsa_public_key = base64.b64encode(cbor_data).decode('ascii')
        
        passkey_model = self.env['sunray.passkey']
        is_valid, result = passkey_model._validate_cbor_public_key(rsa_public_key)
        
        self.assertTrue(is_valid)
        self.assertIsNotNone(result)
    
