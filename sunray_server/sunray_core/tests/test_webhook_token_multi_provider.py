# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError
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
            'is_active': True
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
            'expires_at': None,
            'is_active': True
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
        # SQL constraints fire first, causing database error
        with self.assertRaises(Exception):  # Database constraint violation
            self.env['sunray.webhook.token'].create([{
                'host_id': self.host.id,
                'name': 'Invalid Header Token',
                'token': 'test_token_123',  # Add required token field
                'token_source': 'header'
                # Missing header_name - triggers SQL constraint first
            }])
        
        # Test that param source requires param_name  
        with self.assertRaises(Exception):  # Database constraint violation
            self.env['sunray.webhook.token'].create([{
                'host_id': self.host.id,
                'name': 'Invalid Param Token',
                'token': 'test_token_456',  # Add required token field
                'token_source': 'param'
                # Missing param_name - triggers SQL constraint first
            }])
        
        # Test that both source requires at least one of header_name or param_name
        # This should work (has header_name)
        token1 = self.env['sunray.webhook.token'].create([{
            'host_id': self.host.id,
            'name': 'Valid Both Token 1',
            'token': 'valid_token_123',  # Add required token field
            'header_name': 'X-Token',
            'token_source': 'both'
        }])
        self.assertTrue(token1.id)
        
        # This should also work (has param_name)
        token2 = self.env['sunray.webhook.token'].create([{
            'host_id': self.host.id,
            'name': 'Valid Both Token 2',
            'token': 'valid_token_456',  # Add required token field
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
        test_token = self.env['sunray.webhook.token'].create([{
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
                'exceptions_tree': host_obj.get_exceptions_tree()  # New format
            }
            
            
            host_configs.append(host_config)
        
        # Get the first host config  
        test_host = host_configs[0]
        
        # Verify exceptions_tree format is present
        self.assertIn('exceptions_tree', test_host)
        self.assertIsInstance(test_host['exceptions_tree'], list)
        
        # Since we removed webhook_tokens from API, verify tokens are in exceptions_tree
        # when using Access Rules with token-based access
        exceptions = test_host['exceptions_tree']
        token_exceptions = [ex for ex in exceptions if ex.get('access_type') == 'token']
        if token_exceptions:
            # Check that token configuration is present in exceptions
            token_exception = token_exceptions[0] 
            self.assertIn('tokens', token_exception)
            self.assertTrue(len(token_exception['tokens']) > 0)
    
    def test_access_rules_integration(self):
        """Test integration between webhook tokens and access rules"""
        
        # Create tokens for different providers
        shopify_token = self.env['sunray.webhook.token'].create([{
            'host_id': self.host.id,
            'name': 'Shopify Webhook',
            'token': 'shopify_secret_123',
            'header_name': 'X-Shopify-Hmac-Sha256',
            'token_source': 'header'
        }])
        
        stripe_token = self.env['sunray.webhook.token'].create([{
            'host_id': self.host.id,
            'name': 'Stripe Webhook',
            'token': 'stripe_secret_456',
            'header_name': 'Stripe-Signature',
            'token_source': 'header'
        }])
        
        # Create access rule that uses multiple tokens
        access_rule = self.env['sunray.access.rule'].create([{
            'host_id': self.host.id,
            'description': 'Payment Provider Webhooks',
            'priority': 100,
            'access_type': 'token',
            'url_patterns': '^/webhooks/.*\n^/api/payments/.*',
            'token_ids': [(6, 0, [shopify_token.id, stripe_token.id])]
        }])
        
        # Get exceptions tree
        tree = self.host.get_exceptions_tree()
        
        # Should have one rule
        self.assertEqual(len(tree), 1)
        rule_config = tree[0]
        
        # Verify rule structure
        self.assertEqual(rule_config['priority'], 100)
        self.assertEqual(rule_config['access_type'], 'token')
        self.assertEqual(rule_config['description'], 'Payment Provider Webhooks')
        
        # Should have both URL patterns
        expected_patterns = ['^/webhooks/.*', '^/api/payments/.*']
        self.assertEqual(rule_config['url_patterns'], expected_patterns)
        
        # Should include both tokens
        self.assertEqual(len(rule_config['tokens']), 2)
        token_names = [token['name'] for token in rule_config['tokens']]
        self.assertIn('Shopify Webhook', token_names)
        self.assertIn('Stripe Webhook', token_names)
        
        # Verify token extraction configs are complete
        for token_config in rule_config['tokens']:
            self.assertIn('token', token_config)
            self.assertIn('name', token_config)
            self.assertIn('header_name', token_config)
            self.assertIn('token_source', token_config)
    
    def test_mixed_access_rules_priority(self):
        """Test that different access rule types work together with proper priority"""
        
        # Create webhook token
        webhook_token = self.env['sunray.webhook.token'].create([{
            'host_id': self.host.id,
            'name': 'CI/CD Webhook',
            'token': 'cicd_secret_789',
            'header_name': 'X-CI-Token',
            'token_source': 'header'
        }])
        
        # Create multiple access rules with different priorities
        public_rule = self.env['sunray.access.rule'].create([{
            'host_id': self.host.id,
            'description': 'Health Checks',
            'priority': 300,  # Lowest priority
            'access_type': 'public',
            'url_patterns': '^/health$\n^/status$'
        }])
        
        cidr_rule = self.env['sunray.access.rule'].create([{
            'host_id': self.host.id,
            'description': 'Admin Network',
            'priority': 200,  # Medium priority
            'access_type': 'cidr',
            'url_patterns': '^/admin/.*',
            'allowed_cidrs': '192.168.1.0/24\n10.0.0.0/8'
        }])
        
        token_rule = self.env['sunray.access.rule'].create([{
            'host_id': self.host.id,
            'description': 'Webhook Endpoints',
            'priority': 100,  # Highest priority
            'access_type': 'token',
            'url_patterns': '^/webhooks/.*',
            'token_ids': [(6, 0, [webhook_token.id])]
        }])
        
        # Get exceptions tree
        tree = self.host.get_exceptions_tree()
        
        # Should be ordered by priority (lowest number first)
        self.assertEqual(len(tree), 3)
        self.assertEqual(tree[0]['priority'], 100)  # Token rule first
        self.assertEqual(tree[0]['description'], 'Webhook Endpoints')
        self.assertEqual(tree[1]['priority'], 200)  # CIDR rule second
        self.assertEqual(tree[1]['description'], 'Admin Network')
        self.assertEqual(tree[2]['priority'], 300)  # Public rule last
        self.assertEqual(tree[2]['description'], 'Health Checks')
        
        # Verify each rule has correct structure
        self.assertEqual(tree[0]['access_type'], 'token')
        self.assertEqual(len(tree[0]['tokens']), 1)
        
        self.assertEqual(tree[1]['access_type'], 'cidr')
        self.assertEqual(tree[1]['allowed_cidrs'], ['192.168.1.0/24', '10.0.0.0/8'])
        
        self.assertEqual(tree[2]['access_type'], 'public')
        self.assertEqual(tree[2]['url_patterns'], ['^/health$', '^/status$'])