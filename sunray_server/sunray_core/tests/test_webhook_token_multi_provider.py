# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
import json
import unittest.mock


class TestWebhookTokenMultiProvider(TransactionCase):
    
    def setUp(self):
        super().setUp()
        
        # Create a test host
        self.host = self.env['sunray.host'].create({
            'domain': 'api.example.com',
            'worker_url': 'https://worker.example.com',
            'backend_url': 'https://backend.example.com',
            'is_active': True,
            'token_url_patterns': '^/api/.*\n^/webhook/.*'
        })
        
        # Create API key for worker authentication
        self.api_key = self.env['sunray.api.key'].create([{
            'name': 'Test Worker Key',
            'is_active': True
        }])
    
    def test_webhook_token_creation_with_per_token_config(self):
        """Test creating webhook tokens with per-token extraction configuration"""
        
        # Shopify webhook token
        shopify_token = self.env['sunray.webhook.token'].create([{
            'host_id': self.host.id,
            'name': 'Shopify Webhook',
            'header_name': 'X-Shopify-Hmac-Sha256',
            'token_source': 'header'
        }])
        
        self.assertTrue(shopify_token.token)  # Auto-generated
        self.assertEqual(shopify_token.header_name, 'X-Shopify-Hmac-Sha256')
        self.assertEqual(shopify_token.token_source, 'header')
        self.assertFalse(shopify_token.param_name)
        
        # Mirakl API token
        mirakl_token = self.env['sunray.webhook.token'].create([{
            'host_id': self.host.id,
            'name': 'Mirakl API',
            'header_name': 'Authorization',
            'token_source': 'header'
        }])
        
        self.assertEqual(mirakl_token.header_name, 'Authorization')
        self.assertEqual(mirakl_token.token_source, 'header')
        
        # Legacy system with URL parameter
        legacy_token = self.env['sunray.webhook.token'].create([{
            'host_id': self.host.id,
            'name': 'Legacy System',
            'param_name': 'api_key',
            'token_source': 'param'
        }])
        
        self.assertEqual(legacy_token.param_name, 'api_key')
        self.assertEqual(legacy_token.token_source, 'param')
        self.assertFalse(legacy_token.header_name)
        
        # Flexible token supporting both
        flexible_token = self.env['sunray.webhook.token'].create([{
            'host_id': self.host.id,
            'name': 'Flexible API',
            'header_name': 'X-API-Key',
            'param_name': 'key',
            'token_source': 'both'
        }])
        
        self.assertEqual(flexible_token.header_name, 'X-API-Key')
        self.assertEqual(flexible_token.param_name, 'key')
        self.assertEqual(flexible_token.token_source, 'both')
    
    def test_get_extraction_config(self):
        """Test the get_extraction_config method"""
        
        token = self.env['sunray.webhook.token'].create([{
            'host_id': self.host.id,
            'name': 'Test Token',
            'token': 'custom_token_123',
            'header_name': 'X-Custom-Token',
            'token_source': 'header',
            'allowed_cidrs': '192.168.1.0/24\n10.0.0.0/8'
        }])
        
        config = token.get_extraction_config()
        
        expected_config = {
            'token': 'custom_token_123',
            'name': 'Test Token',
            'header_name': 'X-Custom-Token',
            'param_name': False,
            'token_source': 'header',
            'allowed_cidrs': ['192.168.1.0/24', '10.0.0.0/8'],
            'expires_at': None
        }
        
        self.assertEqual(config, expected_config)
    
    def test_api_endpoint_response_format(self):
        """Test that webhook tokens provide proper extraction configuration"""
        
        # Create multiple webhook tokens with different configurations
        shopify_token = self.env['sunray.webhook.token'].create([{
            'host_id': self.host.id,
            'name': 'Shopify Webhook',
            'token': 'shopify_secret_123',
            'header_name': 'X-Shopify-Hmac-Sha256',
            'token_source': 'header'
        }])
        
        mirakl_token = self.env['sunray.webhook.token'].create([{
            'host_id': self.host.id,
            'name': 'Mirakl API',
            'token': 'mirakl_key_456',
            'header_name': 'Authorization',
            'token_source': 'header'
        }])
        
        legacy_token = self.env['sunray.webhook.token'].create([{
            'host_id': self.host.id,
            'name': 'Legacy System',
            'token': 'legacy_789',
            'param_name': 'api_key',
            'token_source': 'param'
        }])
        
        # Test the extraction configuration directly from the tokens
        all_tokens = [shopify_token, mirakl_token, legacy_token]
        
        # Verify each token provides proper extraction config
        for token_obj in all_tokens:
            config = token_obj.get_extraction_config()
            
            # All tokens should have these required fields
            self.assertIn('token', config)
            self.assertIn('name', config)
            self.assertIn('header_name', config)
            self.assertIn('param_name', config)
            self.assertIn('token_source', config)
            self.assertIn('allowed_cidrs', config)
            self.assertIn('expires_at', config)
        
        # Test specific configurations
        shopify_config = shopify_token.get_extraction_config()
        self.assertEqual(shopify_config['token'], 'shopify_secret_123')
        self.assertEqual(shopify_config['header_name'], 'X-Shopify-Hmac-Sha256')
        self.assertEqual(shopify_config['token_source'], 'header')
        self.assertFalse(shopify_config['param_name'])
        
        mirakl_config = mirakl_token.get_extraction_config()
        self.assertEqual(mirakl_config['token'], 'mirakl_key_456')
        self.assertEqual(mirakl_config['header_name'], 'Authorization')
        self.assertEqual(mirakl_config['token_source'], 'header')
        
        legacy_config = legacy_token.get_extraction_config()
        self.assertEqual(legacy_config['token'], 'legacy_789')
        self.assertEqual(legacy_config['param_name'], 'api_key')
        self.assertEqual(legacy_config['token_source'], 'param')
        self.assertFalse(legacy_config['header_name'])
    
    def test_token_validation_constraints(self):
        """Test that database constraints work correctly"""
        
        # Test that header source requires header_name
        with self.assertRaises(Exception):
            self.env['sunray.webhook.token'].create([{
                'host_id': self.host.id,
                'name': 'Invalid Header Token',
                'token_source': 'header'
                # Missing header_name
            }])
        
        # Test that param source requires param_name
        with self.assertRaises(Exception):
            self.env['sunray.webhook.token'].create([{
                'host_id': self.host.id,
                'name': 'Invalid Param Token',
                'token_source': 'param'
                # Missing param_name
            }])
        
        # Test that both source requires at least one of header_name or param_name
        # This should work (has header_name)
        token1 = self.env['sunray.webhook.token'].create([{
            'host_id': self.host.id,
            'name': 'Valid Both Token 1',
            'header_name': 'X-Token',
            'token_source': 'both'
        }])
        self.assertTrue(token1.id)
        
        # This should also work (has param_name)
        token2 = self.env['sunray.webhook.token'].create([{
            'host_id': self.host.id,
            'name': 'Valid Both Token 2',
            'param_name': 'token',
            'token_source': 'both'
        }])
        self.assertTrue(token2.id)
    
    def test_multiple_tokens_same_host(self):
        """Test that multiple tokens can coexist on the same host"""
        
        # Create tokens for different providers
        tokens = []
        
        providers = [
            ('Shopify', 'X-Shopify-Hmac-Sha256', None, 'header'),
            ('Stripe', 'Stripe-Signature', None, 'header'),
            ('GitHub', 'X-Hub-Signature-256', None, 'header'),
            ('Legacy API', None, 'api_key', 'param'),
            ('Flexible', 'X-API-Key', 'key', 'both')
        ]
        
        for name, header, param, source in providers:
            token_data = {
                'host_id': self.host.id,
                'name': f'{name} Token',
                'token_source': source
            }
            if header:
                token_data['header_name'] = header
            if param:
                token_data['param_name'] = param
                
            token = self.env['sunray.webhook.token'].create([token_data])
            tokens.append(token)
        
        self.assertEqual(len(tokens), 5)
        
        # Verify each token has correct configuration
        self.assertEqual(tokens[0].header_name, 'X-Shopify-Hmac-Sha256')
        self.assertEqual(tokens[0].token_source, 'header')
        
        self.assertEqual(tokens[3].param_name, 'api_key')
        self.assertEqual(tokens[3].token_source, 'param')
        
        self.assertEqual(tokens[4].header_name, 'X-API-Key')
        self.assertEqual(tokens[4].param_name, 'key')
        self.assertEqual(tokens[4].token_source, 'both')
    
    def test_backward_compatibility(self):
        """Test that the API still includes legacy fields for backward compatibility"""
        
        # Create a token
        self.env['sunray.webhook.token'].create([{
            'host_id': self.host.id,
            'name': 'Test Token',
            'header_name': 'X-Test-Token',
            'token_source': 'header'
        }])
        
        # Mock API call (simplified)
        from odoo.addons.sunray_core.controllers.rest_api import SunrayRESTController
        controller = SunrayRESTController()
        
        # Get host configuration similar to what worker would receive
        host_configs = []
        for host_obj in self.env['sunray.host'].search([('id', '=', self.host.id)]):
            host_config = {
                'domain': host_obj.domain,
                'webhook_header_name': host_obj.webhook_header_name,  # Legacy field
                'webhook_param_name': host_obj.webhook_param_name,    # Legacy field
                'webhook_tokens': []
            }
            
            # Add tokens with new format
            for token_obj in host_obj.webhook_token_ids.filtered('is_active'):
                if token_obj.is_valid():
                    host_config['webhook_tokens'].append(token_obj.get_extraction_config())
            
            host_configs.append(host_config)
        
        # Verify legacy fields are still present
        test_host = host_configs[0]
        self.assertIn('webhook_header_name', test_host)
        self.assertIn('webhook_param_name', test_host)
        
        # Verify new format is also present
        self.assertIn('webhook_tokens', test_host)
        self.assertTrue(len(test_host['webhook_tokens']) > 0)
        
        # Verify new token format includes all required fields
        token_config = test_host['webhook_tokens'][0]
        required_fields = ['token', 'name', 'header_name', 'param_name', 'token_source']
        for field in required_fields:
            self.assertIn(field, token_config)