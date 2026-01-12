# -*- coding: utf-8 -*-
"""Integration tests for user-friendly token format upgrade"""

import json
import re
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError
from datetime import datetime, timedelta
from odoo import fields


class TestTokenUpgradeIntegration(TransactionCase):
    """Integration test suite for the user-friendly token format upgrade
    
    This test suite verifies that the entire token lifecycle works correctly
    with the new user-friendly format while maintaining backward compatibility.
    """

    def setUp(self):
        super().setUp()
        # Create test host
        self.host_obj = self.env['sunray.host'].create({
            'domain': 'integration-test.example.com',
            'backend_url': 'http://localhost:8000',
            'is_active': True
        })
        
        # Create test user
        self.user_obj = self.env['sunray.user'].create({
            'username': 'integrationuser',
            'email': 'integration@example.com',
            'is_active': True
        })
    
    def test_01_end_to_end_token_workflow(self):
        """Test complete workflow: generation → display → validation → consumption"""
        # Phase 1: Token Generation
        token_obj, token_value = self.env['sunray.setup.token'].create_setup_token(
            user_id=self.user_obj.id,
            host_id=self.host_obj.id,
            device_name='Integration Test Device',
            validity_hours=24,
            max_uses=1,
            allowed_cidrs='192.168.1.0/24'
        )
        
        # Verify token format
        self.assertRegex(token_value, r'^[23456789ABCDEFGHJKMNPQRSTUVWXYZ]{5}-[23456789ABCDEFGHJKMNPQRSTUVWXYZ]{5}-[23456789ABCDEFGHJKMNPQRSTUVWXYZ]{5}-[23456789ABCDEFGHJKMNPQRSTUVWXYZ]{5}-[23456789ABCDEFGHJKMNPQRSTUVWXYZ]{5}$')
        self.assertEqual(len(token_value), 29)  # 25 chars + 4 dashes
        
        # Phase 2: Wizard Display Test
        wizard = self.env['sunray.authorize.users.wizard'].create({
            'user_id': self.user_obj.id,
            'host_id': self.host_obj.id,
            'device_name': 'Wizard Test Device',
            'validity_hours': 24,
            'max_uses': 1,
            'allowed_cidrs': '192.168.1.0/24'
        })
        
        # Generate token through wizard
        result = wizard.generate_token()
        
        # Verify wizard response
        self.assertEqual(result['type'], 'ir.actions.act_window')
        self.assertEqual(result['res_model'], 'sunray.authorize.users.wizard')
        self.assertTrue(wizard.generated_token)
        self.assertTrue(wizard.token_display)
        
        # Verify wizard token format
        self.assertRegex(wizard.generated_token, r'^[23456789ABCDEFGHJKMNPQRSTUVWXYZ]{5}-[23456789ABCDEFGHJKMNPQRSTUVWXYZ]{5}-[23456789ABCDEFGHJKMNPQRSTUVWXYZ]{5}-[23456789ABCDEFGHJKMNPQRSTUVWXYZ]{5}-[23456789ABCDEFGHJKMNPQRSTUVWXYZ]{5}$')
        
        # Verify display instructions contain expected elements
        self.assertIn('TOKEN:', wizard.token_display)
        self.assertIn(wizard.generated_token, wizard.token_display)
        self.assertIn('integrationuser', wizard.token_display)
        self.assertIn('Groups of 5 characters', wizard.token_display)
        
        # Phase 3: Validation Test (Multiple Input Formats)
        test_variations = [
            token_value,  # Original format
            token_value.lower(),  # Lowercase
            token_value.replace('-', ''),  # No dashes
            f'  {token_value}  ',  # With whitespace
            token_value.replace('-', ' '),  # Spaces instead of dashes
        ]
        
        for variation in test_variations:
            result = self.env['sunray.setup.token'].validate_setup_token(
                username='integrationuser',
                token_hash=variation,
                host_domain='integration-test.example.com',
                client_ip='192.168.1.100',
                user_agent='Integration Test Browser',
                worker_id='test-worker'
            )
            
            self.assertTrue(result['valid'], f"Failed for variation: {variation}")
            self.assertEqual(result['token_obj'], token_obj)
            self.assertEqual(result['user_obj'], self.user_obj)
            self.assertEqual(result['host_obj'], self.host_obj)
        
        # Phase 4: Token Consumption
        consumption_result = token_obj.consume()
        self.assertTrue(consumption_result['consumed'])
        self.assertEqual(consumption_result['current_uses'], 1)
        self.assertEqual(consumption_result['max_uses'], 1)
        
        # Verify token is now consumed and cannot be reused
        validation_result = self.env['sunray.setup.token'].validate_setup_token(
            username='integrationuser',
            token_hash=token_value,
            host_domain='integration-test.example.com',
            client_ip='192.168.1.100'
        )
        
        self.assertFalse(validation_result['valid'])
        self.assertEqual(validation_result['error_code'], '403')
        self.assertEqual(validation_result['error_message'], 'Token already consumed')
    
    def test_02_multi_format_compatibility(self):
        """Test that old and new formats can coexist and validate correctly"""
        # Create tokens using both approaches
        new_token_obj, new_token_value = self.env['sunray.setup.token'].create_setup_token(
            user_id=self.user_obj.id,
            host_id=self.host_obj.id,
            device_name='New Format Device'
        )
        
        # Simulate old format token (manually create with old-style hash)
        import secrets
        import hashlib
        old_token_value = secrets.token_urlsafe(32)  # Old format
        old_token_hash = f"sha512:{hashlib.sha512(old_token_value.encode()).hexdigest()}"
        
        old_token_obj = self.env['sunray.setup.token'].create({
            'user_id': self.user_obj.id,
            'host_id': self.host_obj.id,
            'token_hash': old_token_hash,
            'device_name': 'Old Format Device',
            'expires_at': fields.Datetime.now() + timedelta(hours=24),
            'max_uses': 1,
            'current_uses': 0
        })
        
        # Test validation of new format token
        new_result = self.env['sunray.setup.token'].validate_setup_token(
            username='integrationuser',
            token_hash=new_token_value,  # Raw token
            host_domain='integration-test.example.com'
        )
        self.assertTrue(new_result['valid'])
        
        # Test validation of old format token (pre-hashed)
        old_result = self.env['sunray.setup.token'].validate_setup_token(
            username='integrationuser',
            token_hash=old_token_hash,  # Pre-hashed
            host_domain='integration-test.example.com'
        )
        self.assertTrue(old_result['valid'])
        
        # Test validation of old format token (raw)
        old_raw_result = self.env['sunray.setup.token'].validate_setup_token(
            username='integrationuser',
            token_hash=old_token_value,  # Raw old token
            host_domain='integration-test.example.com'
        )
        self.assertTrue(old_raw_result['valid'])
    
    def test_03_audit_logging_with_new_format(self):
        """Test that audit logging works correctly with new token format"""
        # Clear existing audit logs
        self.env['sunray.audit.log'].search([]).unlink()
        
        # Generate token
        token_obj, token_value = self.env['sunray.setup.token'].create_setup_token(
            user_id=self.user_obj.id,
            host_id=self.host_obj.id,
            device_name='Audit Test Device'
        )
        
        # Verify token generation audit log
        generation_logs = self.env['sunray.audit.log'].search([
            ('event_type', '=', 'token.generated'),
            ('username', '=', 'integrationuser')
        ])
        self.assertEqual(len(generation_logs), 1)
        
        generation_details = json.loads(generation_logs.details) if isinstance(generation_logs.details, str) else generation_logs.details
        self.assertEqual(generation_details['device_name'], 'Audit Test Device')
        self.assertEqual(generation_details['target_user'], 'integrationuser')
        
        # Test validation audit logging
        self.env['sunray.setup.token'].validate_setup_token(
            username='integrationuser',
            token_hash=token_value,
            host_domain='integration-test.example.com',
            client_ip='192.168.1.100',
            user_agent='Audit Test Browser',
            worker_id='audit-test-worker'
        )
        
        # Verify validation audit log
        validation_logs = self.env['sunray.audit.log'].search([
            ('event_type', '=', 'token.validation.success'),
            ('username', '=', 'integrationuser')
        ])
        self.assertEqual(len(validation_logs), 1)
        
        validation_details = json.loads(validation_logs.details) if isinstance(validation_logs.details, str) else validation_logs.details
        self.assertEqual(validation_details['device_name'], 'Audit Test Device')
        self.assertEqual(validation_details['worker_id'], 'audit-test-worker')
        self.assertEqual(validation_details['client_ip'], '192.168.1.100')
    
    def test_04_security_validation(self):
        """Test that security constraints work correctly with new format"""
        # Test IP restriction enforcement
        restricted_token_obj, restricted_token_value = self.env['sunray.setup.token'].create_setup_token(
            user_id=self.user_obj.id,
            host_id=self.host_obj.id,
            device_name='IP Restricted Device',
            allowed_cidrs='10.0.0.0/8'
        )
        
        # Should succeed with allowed IP
        allowed_result = self.env['sunray.setup.token'].validate_setup_token(
            username='integrationuser',
            token_hash=restricted_token_value,
            host_domain='integration-test.example.com',
            client_ip='10.1.1.100'
        )
        self.assertTrue(allowed_result['valid'])
        
        # Should fail with disallowed IP
        blocked_result = self.env['sunray.setup.token'].validate_setup_token(
            username='integrationuser',
            token_hash=restricted_token_value,
            host_domain='integration-test.example.com',
            client_ip='192.168.1.100'
        )
        self.assertFalse(blocked_result['valid'])
        self.assertEqual(blocked_result['error_code'], '403')
        
        # Test token uniqueness
        tokens = []
        for i in range(50):
            _, token_value = self.env['sunray.setup.token'].create_setup_token(
                user_id=self.user_obj.id,
                host_id=self.host_obj.id,
                device_name=f'Unique Test Device {i}'
            )
            tokens.append(token_value)
        
        # All tokens should be unique
        self.assertEqual(len(set(tokens)), 50)
    
    def test_05_error_handling_robustness(self):
        """Test error handling with various invalid inputs"""
        token_obj, token_value = self.env['sunray.setup.token'].create_setup_token(
            user_id=self.user_obj.id,
            host_id=self.host_obj.id,
            device_name='Error Handling Test'
        )
        
        # Test invalid token variations
        invalid_tokens = [
            'INVALID-TOKEN-FORMAT-HERE-XXXXX',  # Invalid chars
            'SHORT-TOK',  # Too short
            'TOO-LONG-TOKEN-WITH-MANY-GROUPS-EXTRA',  # Too long
            '12345-67890-ABCDE-FGHIJ-KLMNO',  # Contains excluded chars
            '',  # Empty
            None  # None
        ]
        
        for invalid_token in invalid_tokens:
            if invalid_token is None:
                continue  # Skip None test for now
            
            result = self.env['sunray.setup.token'].validate_setup_token(
                username='integrationuser',
                token_hash=invalid_token,
                host_domain='integration-test.example.com'
            )
            self.assertFalse(result['valid'], f"Should fail for invalid token: {invalid_token}")
    
    def test_06_performance_validation(self):
        """Test that new format doesn't significantly impact performance"""
        import time
        
        # Generate multiple tokens and measure time
        start_time = time.time()
        
        tokens = []
        for i in range(20):
            _, token_value = self.env['sunray.setup.token'].create_setup_token(
                user_id=self.user_obj.id,
                host_id=self.host_obj.id,
                device_name=f'Perf Test Device {i}'
            )
            tokens.append(token_value)
        
        generation_time = time.time() - start_time
        
        # Should generate 20 tokens in under 5 seconds
        self.assertLess(generation_time, 5.0, "Token generation is too slow")
        
        # Test validation performance
        start_time = time.time()
        
        for token_value in tokens[:10]:  # Test first 10
            result = self.env['sunray.setup.token'].validate_setup_token(
                username='integrationuser',
                token_hash=token_value,
                host_domain='integration-test.example.com'
            )
            self.assertTrue(result['valid'])
        
        validation_time = time.time() - start_time
        
        # Should validate 10 tokens in under 3 seconds
        self.assertLess(validation_time, 3.0, "Token validation is too slow")
    
    def test_07_wizard_integration(self):
        """Test wizard integration with new token format"""
        # Test wizard creation and token generation
        wizard = self.env['sunray.authorize.users.wizard'].create({
            'user_id': self.user_obj.id,
            'host_id': self.host_obj.id,
            'device_name': 'Wizard Integration Test',
            'validity_hours': 48,
            'max_uses': 3,
            'allowed_cidrs': '172.16.0.0/12\n10.0.0.0/8'
        })
        
        # Generate token
        action = wizard.generate_token()
        
        # Verify wizard state
        self.assertTrue(wizard.generated_token)
        self.assertTrue(wizard.token_display)
        self.assertRegex(wizard.generated_token, r'^[23456789ABCDEFGHJKMNPQRSTUVWXYZ]{5}-[23456789ABCDEFGHJKMNPQRSTUVWXYZ]{5}-[23456789ABCDEFGHJKMNPQRSTUVWXYZ]{5}-[23456789ABCDEFGHJKMNPQRSTUVWXYZ]{5}-[23456789ABCDEFGHJKMNPQRSTUVWXYZ]{5}$')
        
        # Verify display content
        self.assertIn('🔑 TOKEN:', wizard.token_display)
        self.assertIn('Groups of 5 characters', wizard.token_display)
        self.assertIn('48 hours', wizard.token_display)
        self.assertIn('Can be used 3 time(s)', wizard.token_display)
        
        # Verify token works in validation
        result = self.env['sunray.setup.token'].validate_setup_token(
            username='integrationuser',
            token_hash=wizard.generated_token,
            host_domain='integration-test.example.com',
            client_ip='172.16.1.100'  # Within allowed CIDR
        )
        self.assertTrue(result['valid'])
        
        # Verify CIDR restrictions work
        blocked_result = self.env['sunray.setup.token'].validate_setup_token(
            username='integrationuser',
            token_hash=wizard.generated_token,
            host_domain='integration-test.example.com',
            client_ip='192.168.1.100'  # Outside allowed CIDRs
        )
        self.assertFalse(blocked_result['valid'])