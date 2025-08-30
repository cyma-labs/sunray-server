# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError
import json


class TestAccessRules(TransactionCase):
    
    def setUp(self):
        super().setUp()
        
        # Create test API key
        self.api_key = self.env['sunray.api.key'].create({
            'name': 'test_worker_key',
            'is_active': True,
            'scopes': 'config:read'
        })
        
        # Create test worker
        self.worker = self.env['sunray.worker'].create({
            'name': 'Test Worker',
            'worker_type': 'cloudflare',
            'worker_url': 'https://worker.example.com',
            'api_key_id': self.api_key.id,
            'is_active': True
        })
        
        # Create a test host
        self.host = self.env['sunray.host'].create({
            'domain': 'api.example.com',
            'sunray_worker_id': self.worker.id,
            'backend_url': 'https://backend.example.com',
            'is_active': True
        })
        
        # Create test tokens
        self.token1 = self.env['sunray.webhook.token'].create({
            'host_id': self.host.id,
            'name': 'Shopify Webhook',
            'token': 'shopify_test_123',
            'header_name': 'X-Shopify-Hmac-Sha256',
            'token_source': 'header'
        })
        
        self.token2 = self.env['sunray.webhook.token'].create({
            'host_id': self.host.id,
            'name': 'API Key',
            'token': 'api_key_456',
            'param_name': 'api_key',
            'token_source': 'param'
        })
    
    def test_access_rule_creation(self):
        """Test creating access rules with different types"""
        
        # Public access rule
        public_rule = self.env['sunray.access.rule'].create({
            'host_id': self.host.id,
            'description': 'Health check endpoints',
            'priority': 10,
            'access_type': 'public',
            'url_patterns': '^/health$\n^/status$'
        })
        
        self.assertEqual(public_rule.access_type, 'public')
        self.assertEqual(public_rule.get_url_patterns(), ['^/health$', '^/status$'])
        
        # CIDR access rule
        cidr_rule = self.env['sunray.access.rule'].create({
            'host_id': self.host.id,
            'description': 'Office network access',
            'priority': 20,
            'access_type': 'cidr',
            'url_patterns': '^/admin/.*',
            'allowed_cidrs': '192.168.1.0/24\n10.0.0.0/8'
        })
        
        self.assertEqual(cidr_rule.access_type, 'cidr')
        self.assertEqual(cidr_rule.get_allowed_cidrs(), ['192.168.1.0/24', '10.0.0.0/8'])
        
        # Token access rule
        token_rule = self.env['sunray.access.rule'].create({
            'host_id': self.host.id,
            'description': 'API endpoints',
            'priority': 30,
            'access_type': 'token',
            'url_patterns': '^/api/.*',
            'token_ids': [(6, 0, [self.token1.id, self.token2.id])]
        })
        
        self.assertEqual(token_rule.access_type, 'token')
        self.assertEqual(len(token_rule.token_ids), 2)
    
    def test_access_rule_validation(self):
        """Test validation constraints"""
        
        # CIDR rule without CIDR blocks should fail
        with self.assertRaises(ValidationError):
            self.env['sunray.access.rule'].create({
                'host_id': self.host.id,
                'description': 'Invalid CIDR rule',
                'access_type': 'cidr',
                'url_patterns': '^/admin/.*'
                # Missing allowed_cidrs
            })
        
        # Token rule without tokens should fail
        with self.assertRaises(ValidationError):
            self.env['sunray.access.rule'].create({
                'host_id': self.host.id,
                'description': 'Invalid token rule',
                'access_type': 'token',
                'url_patterns': '^/api/.*'
                # Missing token_ids
            })
        
        # Rule without URL patterns should fail
        with self.assertRaises(ValidationError):
            self.env['sunray.access.rule'].create({
                'host_id': self.host.id,
                'description': 'Invalid rule',
                'access_type': 'public',
                'url_patterns': ''  # Empty patterns
            })
    
    def test_priority_ordering(self):
        """Test that rules are ordered by priority"""
        
        # Create rules in non-priority order
        rule3 = self.env['sunray.access.rule'].create({
            'host_id': self.host.id,
            'description': 'Third priority',
            'priority': 300,
            'access_type': 'public',
            'url_patterns': '^/third$'
        })
        
        rule1 = self.env['sunray.access.rule'].create({
            'host_id': self.host.id,
            'description': 'First priority',
            'priority': 100,
            'access_type': 'public',
            'url_patterns': '^/first$'
        })
        
        rule2 = self.env['sunray.access.rule'].create({
            'host_id': self.host.id,
            'description': 'Second priority',
            'priority': 200,
            'access_type': 'public',
            'url_patterns': '^/second$'
        })
        
        # Search with default order should respect priority
        rules = self.env['sunray.access.rule'].search([
            ('host_id', '=', self.host.id)
        ])
        
        self.assertEqual(rules[0].id, rule1.id)
        self.assertEqual(rules[1].id, rule2.id)
        self.assertEqual(rules[2].id, rule3.id)
    
    def test_worker_config_generation(self):
        """Test generating worker configuration from rules"""
        
        # Create different types of rules
        public_rule = self.env['sunray.access.rule'].create({
            'host_id': self.host.id,
            'description': 'Public endpoints',
            'priority': 10,
            'access_type': 'public',
            'url_patterns': '^/health$\n^/status$'
        })
        
        cidr_rule = self.env['sunray.access.rule'].create({
            'host_id': self.host.id,
            'description': 'Office access',
            'priority': 20,
            'access_type': 'cidr',
            'url_patterns': '^/admin/.*',
            'allowed_cidrs': '192.168.1.0/24'
        })
        
        token_rule = self.env['sunray.access.rule'].create({
            'host_id': self.host.id,
            'description': 'API access',
            'priority': 30,
            'access_type': 'token',
            'url_patterns': '^/api/.*',
            'token_ids': [(6, 0, [self.token1.id])]
        })
        
        # Test individual rule config
        public_config = public_rule.get_worker_config()
        expected_public = {
            'priority': 10,
            'access_type': 'public',
            'url_patterns': ['^/health$', '^/status$'],
            'description': 'Public endpoints'
        }
        self.assertEqual(public_config, expected_public)
        
        cidr_config = cidr_rule.get_worker_config()
        expected_cidr = {
            'priority': 20,
            'access_type': 'cidr',
            'url_patterns': ['^/admin/.*'],
            'allowed_cidrs': ['192.168.1.0/24'],
            'description': 'Office access'
        }
        self.assertEqual(cidr_config, expected_cidr)
        
        token_config = token_rule.get_worker_config()
        self.assertEqual(token_config['priority'], 30)
        self.assertEqual(token_config['access_type'], 'token')
        self.assertEqual(token_config['url_patterns'], ['^/api/.*'])
        self.assertEqual(len(token_config['tokens']), 1)
        self.assertEqual(token_config['tokens'][0]['name'], 'Shopify Webhook')
    
    def test_exceptions_tree_generation(self):
        """Test generating exceptions tree for worker"""
        
        # Create rules in non-priority order
        rule_c = self.env['sunray.access.rule'].create({
            'host_id': self.host.id,
            'description': 'Third rule',
            'priority': 300,
            'access_type': 'public',
            'url_patterns': '^/third$'
        })
        
        rule_a = self.env['sunray.access.rule'].create({
            'host_id': self.host.id,
            'description': 'First rule',
            'priority': 100,
            'access_type': 'public',
            'url_patterns': '^/first$'
        })
        
        rule_b = self.env['sunray.access.rule'].create({
            'host_id': self.host.id,
            'description': 'Second rule',
            'priority': 200,
            'access_type': 'cidr',
            'url_patterns': '^/second$',
            'allowed_cidrs': '192.168.1.0/24'
        })
        
        # Generate exceptions tree
        tree = self.env['sunray.access.rule'].generate_exceptions_tree(self.host.id)
        
        # Should be ordered by priority
        self.assertEqual(len(tree), 3)
        self.assertEqual(tree[0]['priority'], 100)
        self.assertEqual(tree[0]['description'], 'First rule')
        self.assertEqual(tree[1]['priority'], 200)
        self.assertEqual(tree[1]['description'], 'Second rule')
        self.assertEqual(tree[2]['priority'], 300)
        self.assertEqual(tree[2]['description'], 'Third rule')
        
        # Verify structure
        self.assertEqual(tree[0]['access_type'], 'public')
        self.assertEqual(tree[1]['access_type'], 'cidr')
        self.assertEqual(tree[1]['allowed_cidrs'], ['192.168.1.0/24'])
    
    def test_line_separated_field_parsing(self):
        """Test parsing of line-separated fields with comments"""
        
        rule = self.env['sunray.access.rule'].create({
            'host_id': self.host.id,
            'description': 'Test rule',
            'priority': 100,
            'access_type': 'cidr',
            'url_patterns': '# Comments are ignored\n^/api/.*  # Inline comment\n^/webhook/.*\n\n# Empty lines ignored',
            'allowed_cidrs': '192.168.1.0/24  # Office network\n# 10.0.0.0/8  # Commented out\n172.16.0.0/12'
        })
        
        # Test URL patterns parsing
        patterns = rule.get_url_patterns()
        expected_patterns = ['^/api/.*', '^/webhook/.*']
        self.assertEqual(patterns, expected_patterns)
        
        # Test CIDR parsing
        cidrs = rule.get_allowed_cidrs()
        expected_cidrs = ['192.168.1.0/24', '172.16.0.0/12']
        self.assertEqual(cidrs, expected_cidrs)
    
    def test_inactive_rules_excluded(self):
        """Test that inactive rules are excluded from exceptions tree"""
        
        # Create active rule
        active_rule = self.env['sunray.access.rule'].create({
            'host_id': self.host.id,
            'description': 'Active rule',
            'priority': 100,
            'access_type': 'public',
            'url_patterns': '^/active$',
            'is_active': True
        })
        
        # Create inactive rule
        inactive_rule = self.env['sunray.access.rule'].create({
            'host_id': self.host.id,
            'description': 'Inactive rule',
            'priority': 50,
            'access_type': 'public',
            'url_patterns': '^/inactive$',
            'is_active': False
        })
        
        # Generate exceptions tree
        tree = self.env['sunray.access.rule'].generate_exceptions_tree(self.host.id)
        
        # Only active rule should be included
        self.assertEqual(len(tree), 1)
        self.assertEqual(tree[0]['description'], 'Active rule')
    
    def test_name_get_display(self):
        """Test custom name display format"""
        
        rule = self.env['sunray.access.rule'].create({
            'host_id': self.host.id,
            'description': 'Test rule',
            'priority': 100,
            'access_type': 'public',
            'url_patterns': '^/test$'
        })
        
        name_get_result = rule.name_get()
        expected_name = "[100] Test rule (public)"
        
        self.assertEqual(len(name_get_result), 1)
        self.assertEqual(name_get_result[0][0], rule.id)
        self.assertEqual(name_get_result[0][1], expected_name)
    
    def test_host_exceptions_tree_integration(self):
        """Test that host.get_exceptions_tree() works with access rules"""
        
        # Create access rules for the host
        self.env['sunray.access.rule'].create({
            'host_id': self.host.id,
            'description': 'API access',
            'priority': 100,
            'access_type': 'token',
            'url_patterns': '^/api/.*',
            'token_ids': [(6, 0, [self.token1.id])]
        })
        
        self.env['sunray.access.rule'].create({
            'host_id': self.host.id,
            'description': 'Public endpoints',
            'priority': 200,
            'access_type': 'public',
            'url_patterns': '^/health$'
        })
        
        # Get exceptions tree from host
        tree = self.host.get_exceptions_tree()
        
        self.assertEqual(len(tree), 2)
        self.assertEqual(tree[0]['priority'], 100)
        self.assertEqual(tree[0]['access_type'], 'token')
        self.assertEqual(tree[1]['priority'], 200)
        self.assertEqual(tree[1]['access_type'], 'public')
    
    
    def test_token_filtering_in_worker_config(self):
        """Test that only active and valid tokens are included in worker config"""
        
        # Create inactive token
        inactive_token = self.env['sunray.webhook.token'].create({
            'host_id': self.host.id,
            'name': 'Inactive Token',
            'token': 'inactive_123',
            'header_name': 'X-Inactive',
            'token_source': 'header',
            'is_active': False
        })
        
        # Create expired token
        from odoo import fields
        from datetime import datetime, timedelta
        
        expired_token = self.env['sunray.webhook.token'].create({
            'host_id': self.host.id,
            'name': 'Expired Token',
            'token': 'expired_123',
            'header_name': 'X-Expired',
            'token_source': 'header',
            'is_active': True,
            'expires_at': fields.Datetime.now() - timedelta(days=1)
        })
        
        # Create access rule with all tokens
        rule = self.env['sunray.access.rule'].create({
            'host_id': self.host.id,
            'description': 'API access',
            'priority': 100,
            'access_type': 'token',
            'url_patterns': '^/api/.*',
            'token_ids': [(6, 0, [self.token1.id, inactive_token.id, expired_token.id])]
        })
        
        # Get worker config
        config = rule.get_worker_config()
        
        # Only active and valid token should be included
        self.assertEqual(len(config['tokens']), 1)
        self.assertEqual(config['tokens'][0]['name'], 'Shopify Webhook')




    def test_mixed_rule_priority_ordering(self):
        """Test priority ordering works with different access types"""

        rules_data = [
            ('cidr_high', 50, 'cidr'),
            ('http_medium', 100, 'public'),
            ('public_low', 200, 'public'),
            ('token_highest', 10, 'token')
        ]

        created_rules = []
        for name, priority, access_type in rules_data:
            rule_data = {
                'host_id': self.host.id,
                'description': f'{name} rule',
                'priority': priority,
                'access_type': access_type
            }

            if access_type == 'cidr':
                rule_data.update({
                    'url_patterns': f'^/{name}',
                    'allowed_cidrs': '192.168.1.0/24'
                })
            elif access_type == 'token':
                rule_data.update({
                    'url_patterns': f'^/{name}',
                    'token_ids': [(6, 0, [self.token1.id])]
                })
            else:
                rule_data['url_patterns'] = f'^/{name}'

            created_rules.append(self.env['sunray.access.rule'].create(rule_data))

        # Get exceptions tree
        tree = self.env['sunray.access.rule'].generate_exceptions_tree(self.host.id)

        # Should be ordered by priority
        expected_order = [10, 50, 100, 200]  # token_highest, cidr_high, http_medium, public_low
        actual_order = [rule['priority'] for rule in tree]

        self.assertEqual(actual_order, expected_order)

    # Host WebSocket URL Prefix Tests
    def test_host_websocket_url_prefix_field(self):
        """Test WebSocket URL prefix field on host model"""
        
        # Test empty prefix (default)
        self.assertEqual(self.host.websocket_url_prefix, '')
        
        # Set WebSocket prefix
        self.host.write({'websocket_url_prefix': '/ws/'})
        self.assertEqual(self.host.websocket_url_prefix, '/ws/')
        
        # Test various valid prefixes
        test_prefixes = ['/websocket/', '/wss/', '/socket/', '/api/ws/', '']
        for prefix in test_prefixes:
            self.host.write({'websocket_url_prefix': prefix})
            self.assertEqual(self.host.websocket_url_prefix, prefix)
    
    def test_websocket_url_prefix_in_api_response(self):
        """Test that WebSocket URL prefix is included in API responses"""
        
        # Test empty prefix
        self.assertEqual(self.host.websocket_url_prefix, '')
        
        # Set WebSocket prefix on host
        self.host.write({'websocket_url_prefix': '/ws/'})
        
        # Verify the prefix is set correctly
        self.assertEqual(self.host.websocket_url_prefix, '/ws/')
    
    def test_websocket_url_prefix_performance(self):
        """Test performance comparison between regex and prefix approach"""
        import time
        
        # Setup test URL
        test_url = '/ws/chat/room123'
        
        # Test prefix approach (current)
        prefix = '/ws/'
        start_time = time.perf_counter()
        for _ in range(1000):
            is_websocket = test_url.startswith(prefix) if prefix else False
        prefix_time = time.perf_counter() - start_time
        
        # Test regex approach (old)
        import re
        patterns = ['^/ws/chat/.*', '^/ws/notifications']
        compiled_patterns = [re.compile(p) for p in patterns]
        start_time = time.perf_counter()
        for _ in range(1000):
            is_websocket = any(p.match(test_url) for p in compiled_patterns)
        regex_time = time.perf_counter() - start_time
        
        # Prefix should be significantly faster
        self.assertLess(prefix_time, regex_time)
        
        # Log the performance improvement
        improvement = regex_time / prefix_time if prefix_time > 0 else float('inf')
        print(f"Performance improvement: {improvement:.1f}x faster ({regex_time*1000:.3f}ms vs {prefix_time*1000:.3f}ms for 1000 operations)")


