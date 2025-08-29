# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError
from datetime import datetime, timedelta
from odoo import fields
import hashlib
import json


class TestSetupToken(TransactionCase):
    """Test suite for sunray.setup.token model"""

    def setUp(self):
        super().setUp()
        # Create test host
        self.host_obj = self.env['sunray.host'].create({
            'domain': 'test.example.com',
            'backend_url': 'http://localhost:8000'
        })
        
        # Create test user
        self.user_obj = self.env['sunray.user'].create({
            'username': 'testuser',
            'email': 'test@example.com',
            'is_active': True
        })
    
    def test_01_token_creation_and_hashing(self):
        """Test token creation with proper hashing"""
        token_obj, plain_token = self.env['sunray.setup.token'].create_setup_token(
            user_id=self.user_obj.id,
            host_id=self.host_obj.id,
            device_name='Test Device',
            validity_hours=24,
            max_uses=1
        )
        
        # Verify token object was created
        self.assertTrue(token_obj)
        self.assertEqual(token_obj.user_id.id, self.user_obj.id)
        self.assertEqual(token_obj.host_id.id, self.host_obj.id)
        self.assertEqual(token_obj.device_name, 'Test Device')
        self.assertEqual(token_obj.max_uses, 1)
        self.assertEqual(token_obj.current_uses, 0)
        self.assertFalse(token_obj.consumed)
        
        # Verify token hash matches plain token
        expected_hash = f"sha512:{hashlib.sha512(plain_token.encode()).hexdigest()}"
        self.assertEqual(token_obj.token_hash, expected_hash)
        
        # Verify expiration is set correctly
        expected_expiry = fields.Datetime.now() + timedelta(hours=24)
        time_diff = abs((token_obj.expires_at - expected_expiry).total_seconds())
        self.assertLess(time_diff, 60)  # Within 1 minute tolerance
    
    def test_02_consume_single_use_token(self):
        """Test consuming a single-use token marks it as consumed"""
        token_obj, _ = self.env['sunray.setup.token'].create_setup_token(
            user_id=self.user_obj.id,
            host_id=self.host_obj.id,
            device_name='Single Use Device',
            max_uses=1
        )
        
        # Initial state
        self.assertEqual(token_obj.current_uses, 0)
        self.assertFalse(token_obj.consumed)
        self.assertFalse(token_obj.consumed_date)
        
        # Consume token
        result = token_obj.consume()
        
        # Verify consumption result
        self.assertTrue(result['consumed'])
        self.assertEqual(result['current_uses'], 1)
        self.assertEqual(result['max_uses'], 1)
        
        # Verify token state updated
        self.assertEqual(token_obj.current_uses, 1)
        self.assertTrue(token_obj.consumed)
        self.assertTrue(token_obj.consumed_date)
    
    def test_03_consume_multi_use_token(self):
        """Test consuming a multi-use token increments properly"""
        token_obj, _ = self.env['sunray.setup.token'].create_setup_token(
            user_id=self.user_obj.id,
            host_id=self.host_obj.id,
            device_name='Multi Use Device',
            max_uses=3
        )
        
        # First consumption
        result1 = token_obj.consume()
        self.assertFalse(result1['consumed'])
        self.assertEqual(result1['current_uses'], 1)
        self.assertEqual(token_obj.current_uses, 1)
        self.assertFalse(token_obj.consumed)
        
        # Second consumption
        result2 = token_obj.consume()
        self.assertFalse(result2['consumed'])
        self.assertEqual(result2['current_uses'], 2)
        self.assertEqual(token_obj.current_uses, 2)
        self.assertFalse(token_obj.consumed)
        
        # Third consumption (should mark as consumed)
        result3 = token_obj.consume()
        self.assertTrue(result3['consumed'])
        self.assertEqual(result3['current_uses'], 3)
        self.assertEqual(token_obj.current_uses, 3)
        self.assertTrue(token_obj.consumed)
        self.assertTrue(token_obj.consumed_date)
    
    def test_04_allowed_cidrs_parsing(self):
        """Test CIDR parsing with comments and inline comments"""
        token_obj, _ = self.env['sunray.setup.token'].create_setup_token(
            user_id=self.user_obj.id,
            host_id=self.host_obj.id,
            device_name='CIDR Test Device',
            allowed_cidrs="""192.168.1.0/24    # Home network
10.0.0.0/8        # Corporate network
# This is a comment line
172.16.0.0/12     # VPN network
127.0.0.1         # Localhost
"""
        )
        
        expected_cidrs = [
            '192.168.1.0/24',
            '10.0.0.0/8',
            '172.16.0.0/12',
            '127.0.0.1'
        ]
        
        parsed_cidrs = token_obj.get_allowed_cidrs()
        self.assertEqual(parsed_cidrs, expected_cidrs)
    
    def test_05_empty_allowed_cidrs(self):
        """Test that empty CIDR field returns empty list"""
        token_obj, _ = self.env['sunray.setup.token'].create_setup_token(
            user_id=self.user_obj.id,
            host_id=self.host_obj.id,
            device_name='No CIDR Device',
            allowed_cidrs=''
        )
        
        parsed_cidrs = token_obj.get_allowed_cidrs()
        self.assertEqual(parsed_cidrs, [])
    
    def test_06_cidrs_only_comments(self):
        """Test CIDR field with only comments returns empty list"""
        token_obj, _ = self.env['sunray.setup.token'].create_setup_token(
            user_id=self.user_obj.id,
            host_id=self.host_obj.id,
            device_name='Comments Only Device',
            allowed_cidrs="""# This is just a comment
# Another comment
# Third comment
"""
        )
        
        parsed_cidrs = token_obj.get_allowed_cidrs()
        self.assertEqual(parsed_cidrs, [])
    
    def test_07_user_auto_authorization(self):
        """Test that token creation auto-authorizes user for host"""
        # Verify user not initially authorized
        self.assertNotIn(self.user_obj, self.host_obj.user_ids)
        
        # Create token
        token_obj, _ = self.env['sunray.setup.token'].create_setup_token(
            user_id=self.user_obj.id,
            host_id=self.host_obj.id,
            device_name='Auto Auth Test'
        )
        
        # Verify user is now authorized
        self.assertIn(self.user_obj, self.host_obj.user_ids)
    
    def test_08_cleanup_expired_tokens(self):
        """Test cleanup of expired tokens"""
        # Create expired token
        expired_token, _ = self.env['sunray.setup.token'].create_setup_token(
            user_id=self.user_obj.id,
            host_id=self.host_obj.id,
            device_name='Expired Device'
        )
        # Force expiry
        expired_token.expires_at = fields.Datetime.now() - timedelta(hours=1)
        
        # Create valid token
        valid_token, _ = self.env['sunray.setup.token'].create_setup_token(
            user_id=self.user_obj.id,
            host_id=self.host_obj.id,
            device_name='Valid Device'
        )
        
        # Create consumed but expired token (should not be cleaned)
        consumed_token, _ = self.env['sunray.setup.token'].create_setup_token(
            user_id=self.user_obj.id,
            host_id=self.host_obj.id,
            device_name='Consumed Device'
        )
        consumed_token.expires_at = fields.Datetime.now() - timedelta(hours=1)
        consumed_token.consumed = True
        
        initial_count = self.env['sunray.setup.token'].search_count([])
        
        # Run cleanup
        self.env['sunray.setup.token'].cleanup_expired()
        
        final_count = self.env['sunray.setup.token'].search_count([])
        
        # Should remove only the expired unconsumed token
        self.assertEqual(final_count, initial_count - 1)
        
        # Verify specific tokens
        self.assertFalse(expired_token.exists())
        self.assertTrue(valid_token.exists())
        self.assertTrue(consumed_token.exists())
    
    def test_09_concurrent_consumption(self):
        """Test that multiple consume() calls work correctly"""
        token_obj, _ = self.env['sunray.setup.token'].create_setup_token(
            user_id=self.user_obj.id,
            host_id=self.host_obj.id,
            device_name='Concurrent Test',
            max_uses=2
        )
        
        # Simulate concurrent consumption
        result1 = token_obj.consume()
        result2 = token_obj.consume()
        
        # Verify final state
        self.assertEqual(token_obj.current_uses, 2)
        self.assertTrue(token_obj.consumed)
        self.assertTrue(result2['consumed'])
        self.assertEqual(result2['current_uses'], 2)
    
    def test_10_consume_ensures_one(self):
        """Test that consume() method works on single record"""
        token_obj1, _ = self.env['sunray.setup.token'].create_setup_token(
            user_id=self.user_obj.id,
            host_id=self.host_obj.id,
            device_name='Device 1'
        )
        
        token_obj2, _ = self.env['sunray.setup.token'].create_setup_token(
            user_id=self.user_obj.id,
            host_id=self.host_obj.id,
            device_name='Device 2'
        )
        
        # Single record should work
        result = token_obj1.consume()
        self.assertTrue(result)
        
        # Multiple records should fail
        with self.assertRaises(ValueError):
            (token_obj1 | token_obj2).consume()


class TestSetupTokenValidation(TransactionCase):
    """Test suite for sunray.setup.token validation method"""
    
    def setUp(self):
        super().setUp()
        # Create test host
        self.host_obj = self.env['sunray.host'].create({
            'domain': 'validation-test.example.com',
            'backend_url': 'http://localhost:8000',
            'is_active': True
        })
        
        # Create test user
        self.user_obj = self.env['sunray.user'].create({
            'username': 'validationuser',
            'email': 'validation@example.com',
            'is_active': True
        })
        
        # Create inactive user for testing
        self.inactive_user_obj = self.env['sunray.user'].create({
            'username': 'inactiveuser',
            'email': 'inactive@example.com',
            'is_active': False
        })
        
        # Create inactive host for testing
        self.inactive_host_obj = self.env['sunray.host'].create({
            'domain': 'inactive-test.example.com',
            'backend_url': 'http://localhost:8001',
            'is_active': False
        })
        
        # Create valid token for testing
        self.valid_token, self.plain_token = self.env['sunray.setup.token'].create_setup_token(
            user_id=self.user_obj.id,
            host_id=self.host_obj.id,
            device_name='Valid Test Device',
            validity_hours=24,
            max_uses=1
        )
    
    def test_01_successful_validation(self):
        """Test successful token validation"""
        result = self.env['sunray.setup.token'].validate_setup_token(
            username='validationuser',
            token_hash=self.valid_token.token_hash,
            host_domain='validation-test.example.com',
            client_ip='192.168.1.100',
            user_agent='Test Browser',
            worker_id='test-worker'
        )
        
        self.assertTrue(result['valid'])
        self.assertEqual(result['token_obj'], self.valid_token)
        self.assertEqual(result['user_obj'], self.user_obj)
        self.assertEqual(result['host_obj'], self.host_obj)
        self.assertIsNone(result['error_code'])
        self.assertIsNone(result['error_message'])
        
        # Verify audit log entry was created
        audit_logs = self.env['sunray.audit.log'].search([
            ('event_type', '=', 'token.validation.success'),
            ('username', '=', 'validationuser')
        ])
        self.assertTrue(audit_logs)
        
    def test_02_user_not_found(self):
        """Test validation with non-existent user"""
        result = self.env['sunray.setup.token'].validate_setup_token(
            username='nonexistentuser',
            token_hash=self.valid_token.token_hash,
            host_domain='validation-test.example.com',
            client_ip='192.168.1.100',
            worker_id='test-worker'
        )
        
        self.assertFalse(result['valid'])
        self.assertEqual(result['error_code'], '404')
        self.assertEqual(result['error_message'], 'User not found')
        self.assertIsNone(result['token_obj'])
        
        # Verify audit log entry
        audit_logs = self.env['sunray.audit.log'].search([
            ('event_type', '=', 'token.validation.user_not_found'),
            ('username', '=', 'nonexistentuser')
        ])
        self.assertTrue(audit_logs)
        
    def test_03_inactive_user(self):
        """Test validation with inactive user"""
        result = self.env['sunray.setup.token'].validate_setup_token(
            username='inactiveuser',
            token_hash=self.valid_token.token_hash,
            host_domain='validation-test.example.com',
            client_ip='192.168.1.100',
            worker_id='test-worker'
        )
        
        self.assertFalse(result['valid'])
        self.assertEqual(result['error_code'], '403')
        self.assertEqual(result['error_message'], 'User is inactive')
        
        # Verify audit log entry
        audit_logs = self.env['sunray.audit.log'].search([
            ('event_type', '=', 'token.validation.user_inactive'),
            ('username', '=', 'inactiveuser')
        ])
        self.assertTrue(audit_logs)
        
    def test_04_invalid_token_hash(self):
        """Test validation with invalid token hash"""
        result = self.env['sunray.setup.token'].validate_setup_token(
            username='validationuser',
            token_hash='sha512:invalid_hash_value',
            host_domain='validation-test.example.com',
            client_ip='192.168.1.100',
            worker_id='test-worker'
        )
        
        self.assertFalse(result['valid'])
        self.assertEqual(result['error_code'], '401')
        self.assertEqual(result['error_message'], 'Invalid setup token hash')
        
        # Verify audit log entry
        audit_logs = self.env['sunray.audit.log'].search([
            ('event_type', '=', 'token.validation.token_not_found'),
            ('username', '=', 'validationuser')
        ])
        self.assertTrue(audit_logs)
        
    def test_05_expired_token(self):
        """Test validation with expired token"""
        # Create expired token
        expired_token, _ = self.env['sunray.setup.token'].create_setup_token(
            user_id=self.user_obj.id,
            host_id=self.host_obj.id,
            device_name='Expired Device',
            validity_hours=1
        )
        # Force expiry
        expired_token.expires_at = fields.Datetime.now() - timedelta(hours=1)
        
        result = self.env['sunray.setup.token'].validate_setup_token(
            username='validationuser',
            token_hash=expired_token.token_hash,
            host_domain='validation-test.example.com',
            client_ip='192.168.1.100',
            worker_id='test-worker'
        )
        
        self.assertFalse(result['valid'])
        self.assertEqual(result['error_code'], '401')
        self.assertEqual(result['error_message'], 'Setup token expired')
        
        # Verify audit log entry
        audit_logs = self.env['sunray.audit.log'].search([
            ('event_type', '=', 'token.validation.expired'),
            ('username', '=', 'validationuser')
        ])
        self.assertTrue(audit_logs)
        
    def test_06_consumed_token(self):
        """Test validation with consumed token"""
        # Consume the token
        self.valid_token.consumed = True
        self.valid_token.consumed_date = fields.Datetime.now()
        
        result = self.env['sunray.setup.token'].validate_setup_token(
            username='validationuser',
            token_hash=self.valid_token.token_hash,
            host_domain='validation-test.example.com',
            client_ip='192.168.1.100',
            worker_id='test-worker'
        )
        
        self.assertFalse(result['valid'])
        self.assertEqual(result['error_code'], '403')
        self.assertEqual(result['error_message'], 'Token already consumed')
        
        # Verify audit log entry
        audit_logs = self.env['sunray.audit.log'].search([
            ('event_type', '=', 'token.validation.consumed'),
            ('username', '=', 'validationuser')
        ])
        self.assertTrue(audit_logs)
        
    def test_07_usage_limit_exceeded(self):
        """Test validation with token at usage limit"""
        # Set token at usage limit
        self.valid_token.current_uses = 1
        self.valid_token.max_uses = 1
        
        result = self.env['sunray.setup.token'].validate_setup_token(
            username='validationuser',
            token_hash=self.valid_token.token_hash,
            host_domain='validation-test.example.com',
            client_ip='192.168.1.100',
            worker_id='test-worker'
        )
        
        self.assertFalse(result['valid'])
        self.assertEqual(result['error_code'], '403')
        self.assertEqual(result['error_message'], 'Token usage limit exceeded')
        
        # Verify audit log entry
        audit_logs = self.env['sunray.audit.log'].search([
            ('event_type', '=', 'token.validation.usage_exceeded'),
            ('username', '=', 'validationuser')
        ])
        self.assertTrue(audit_logs)
        
    def test_08_unknown_host_domain(self):
        """Test validation with unknown host domain"""
        result = self.env['sunray.setup.token'].validate_setup_token(
            username='validationuser',
            token_hash=self.valid_token.token_hash,
            host_domain='unknown.example.com',
            client_ip='192.168.1.100',
            worker_id='test-worker'
        )
        
        self.assertFalse(result['valid'])
        self.assertEqual(result['error_code'], '404')
        self.assertEqual(result['error_message'], 'Unknown host domain')
        
        # Verify audit log entry
        audit_logs = self.env['sunray.audit.log'].search([
            ('event_type', '=', 'token.validation.unknown_host'),
            ('username', '=', 'validationuser')
        ])
        self.assertTrue(audit_logs)
        
    def test_09_host_mismatch(self):
        """Test validation with token for different host"""
        # Create token for different host
        different_host = self.env['sunray.host'].create({
            'domain': 'different.example.com',
            'backend_url': 'http://localhost:8002',
            'is_active': True
        })
        
        different_token, _ = self.env['sunray.setup.token'].create_setup_token(
            user_id=self.user_obj.id,
            host_id=different_host.id,
            device_name='Different Host Device'
        )
        
        result = self.env['sunray.setup.token'].validate_setup_token(
            username='validationuser',
            token_hash=different_token.token_hash,
            host_domain='validation-test.example.com',  # Different host
            client_ip='192.168.1.100',
            worker_id='test-worker'
        )
        
        self.assertFalse(result['valid'])
        self.assertEqual(result['error_code'], '403')
        self.assertEqual(result['error_message'], 'Token not valid for this host domain')
        
        # Verify audit log entry
        audit_logs = self.env['sunray.audit.log'].search([
            ('event_type', '=', 'token.validation.host_mismatch'),
            ('username', '=', 'validationuser')
        ])
        self.assertTrue(audit_logs)
        
    def test_10_ip_restrictions_allowed(self):
        """Test validation with IP restrictions - allowed IP"""
        # Create token with CIDR restrictions
        restricted_token, _ = self.env['sunray.setup.token'].create_setup_token(
            user_id=self.user_obj.id,
            host_id=self.host_obj.id,
            device_name='Restricted Device',
            allowed_cidrs='192.168.1.0/24'
        )
        
        result = self.env['sunray.setup.token'].validate_setup_token(
            username='validationuser',
            token_hash=restricted_token.token_hash,
            host_domain='validation-test.example.com',
            client_ip='192.168.1.100',  # Within allowed CIDR
            worker_id='test-worker'
        )
        
        self.assertTrue(result['valid'])
        
    def test_11_ip_restrictions_blocked(self):
        """Test validation with IP restrictions - blocked IP"""
        # Create token with CIDR restrictions
        restricted_token, _ = self.env['sunray.setup.token'].create_setup_token(
            user_id=self.user_obj.id,
            host_id=self.host_obj.id,
            device_name='Restricted Device',
            allowed_cidrs='192.168.1.0/24'
        )
        
        result = self.env['sunray.setup.token'].validate_setup_token(
            username='validationuser',
            token_hash=restricted_token.token_hash,
            host_domain='validation-test.example.com',
            client_ip='10.0.0.100',  # Outside allowed CIDR
            worker_id='test-worker'
        )
        
        self.assertFalse(result['valid'])
        self.assertEqual(result['error_code'], '403')
        self.assertEqual(result['error_message'], 'IP address not allowed for this token')
        
        # Verify audit log entry
        audit_logs = self.env['sunray.audit.log'].search([
            ('event_type', '=', 'token.validation.ip_restricted'),
            ('username', '=', 'validationuser')
        ])
        self.assertTrue(audit_logs)
        
    def test_12_invalid_ip_address(self):
        """Test validation with invalid IP address"""
        result = self.env['sunray.setup.token'].validate_setup_token(
            username='validationuser',
            token_hash=self.valid_token.token_hash,
            host_domain='validation-test.example.com',
            client_ip='invalid.ip.address',
            worker_id='test-worker'
        )
        
        # Should still succeed if no CIDR restrictions
        self.assertTrue(result['valid'])
        
        # Test with CIDR restrictions and invalid IP
        restricted_token, _ = self.env['sunray.setup.token'].create_setup_token(
            user_id=self.user_obj.id,
            host_id=self.host_obj.id,
            device_name='Invalid IP Test',
            allowed_cidrs='192.168.1.0/24'
        )
        
        result = self.env['sunray.setup.token'].validate_setup_token(
            username='validationuser',
            token_hash=restricted_token.token_hash,
            host_domain='validation-test.example.com',
            client_ip='invalid.ip.address',
            worker_id='test-worker'
        )
        
        self.assertFalse(result['valid'])
        self.assertEqual(result['error_code'], '400')
        self.assertEqual(result['error_message'], 'Invalid client IP address')
        
    def test_13_no_client_ip_with_restrictions(self):
        """Test validation without client IP when token has CIDR restrictions"""
        # Create token with CIDR restrictions
        restricted_token, _ = self.env['sunray.setup.token'].create_setup_token(
            user_id=self.user_obj.id,
            host_id=self.host_obj.id,
            device_name='No IP Test',
            allowed_cidrs='192.168.1.0/24'
        )
        
        # Should pass when no client_ip provided (CIDR check skipped)
        result = self.env['sunray.setup.token'].validate_setup_token(
            username='validationuser',
            token_hash=restricted_token.token_hash,
            host_domain='validation-test.example.com',
            client_ip=None,
            worker_id='test-worker'
        )
        
        self.assertTrue(result['valid'])
        
    def test_14_comprehensive_audit_logging(self):
        """Test that all validation attempts create proper audit logs"""
        # Clear existing audit logs for clean test
        self.env['sunray.audit.log'].search([]).unlink()
        
        # Test successful validation
        self.env['sunray.setup.token'].validate_setup_token(
            username='validationuser',
            token_hash=self.valid_token.token_hash,
            host_domain='validation-test.example.com',
            client_ip='192.168.1.100',
            user_agent='Test Browser',
            worker_id='test-worker'
        )
        
        # Verify audit log details
        audit_log = self.env['sunray.audit.log'].search([
            ('event_type', '=', 'token.validation.success')
        ])
        self.assertEqual(len(audit_log), 1)
        
        details = json.loads(audit_log.details) if isinstance(audit_log.details, str) else audit_log.details
        self.assertEqual(details['username'], 'validationuser')
        self.assertEqual(details['token_id'], self.valid_token.id)
        self.assertEqual(details['host_domain'], 'validation-test.example.com')
        self.assertEqual(details['client_ip'], '192.168.1.100')
        self.assertEqual(details['worker_id'], 'test-worker')
        self.assertEqual(details['device_name'], 'Valid Test Device')
        self.assertIn('uses_remaining', details)