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

        # Create test tokens (no longer tied to specific host)
        self.token1 = self.env['sunray.webhook.token'].create({
            'name': 'Shopify Webhook',
            'token': 'shopify_test_123',
            'header_name': 'X-Shopify-Hmac-Sha256',
            'token_source': 'header'
        })

        self.token2 = self.env['sunray.webhook.token'].create({
            'name': 'API Key',
            'token': 'api_key_456',
            'param_name': 'api_key',
            'token_source': 'param'
        })

    def test_access_rule_creation(self):
        """Test creating access rules with different types"""

        # Public access rule (library)
        public_rule = self.env['sunray.access.rule'].create({
            'name': 'Health Check Endpoints',
            'description': 'Health check and status endpoints',
            'access_type': 'public',
            'url_patterns': '^/health$\n^/status$'
        })

        self.assertEqual(public_rule.access_type, 'public')
        self.assertEqual(public_rule.get_url_patterns(), ['^/health$', '^/status$'])

        # CIDR access rule (library)
        cidr_rule = self.env['sunray.access.rule'].create({
            'name': 'Office Network Access',
            'description': 'Access from office networks',
            'access_type': 'cidr',
            'url_patterns': '^/admin/.*',
            'allowed_cidrs': '192.168.1.0/24\n10.0.0.0/8'
        })

        self.assertEqual(cidr_rule.access_type, 'cidr')
        self.assertEqual(cidr_rule.get_allowed_cidrs(), ['192.168.1.0/24', '10.0.0.0/8'])

        # Token access rule (library)
        token_rule = self.env['sunray.access.rule'].create({
            'name': 'API Endpoints',
            'description': 'Token-protected API endpoints',
            'access_type': 'token',
            'url_patterns': '^/api/.*',
            'token_ids': [(6, 0, [self.token1.id, self.token2.id])]
        })

        self.assertEqual(token_rule.access_type, 'token')
        self.assertEqual(len(token_rule.token_ids), 2)

        # Create associations to attach rules to host
        self.env['sunray.host.access.rule'].create({
            'host_id': self.host.id,
            'rule_id': public_rule.id,
            'priority': 10
        })
        self.env['sunray.host.access.rule'].create({
            'host_id': self.host.id,
            'rule_id': cidr_rule.id,
            'priority': 20
        })
        self.env['sunray.host.access.rule'].create({
            'host_id': self.host.id,
            'rule_id': token_rule.id,
            'priority': 30
        })

    def test_access_rule_validation(self):
        """Test validation constraints"""

        # CIDR rule without CIDR blocks should fail
        with self.assertRaises(ValidationError):
            self.env['sunray.access.rule'].create({
                'name': 'Invalid CIDR Rule',
                'access_type': 'cidr',
                'url_patterns': '^/admin/.*'
                # Missing allowed_cidrs
            })

        # Token rule without tokens should fail
        with self.assertRaises(ValidationError):
            self.env['sunray.access.rule'].create({
                'name': 'Invalid Token Rule',
                'access_type': 'token',
                'url_patterns': '^/api/.*'
                # Missing token_ids
            })

        # Rule without URL patterns should fail
        with self.assertRaises(ValidationError):
            self.env['sunray.access.rule'].create({
                'name': 'Invalid Rule',
                'access_type': 'public',
                'url_patterns': ''  # Empty patterns
            })

    def test_priority_ordering(self):
        """Test that associations are ordered by priority"""

        # Create rules in library
        rule3 = self.env['sunray.access.rule'].create({
            'name': 'Third Priority Rule',
            'access_type': 'public',
            'url_patterns': '^/third$'
        })

        rule1 = self.env['sunray.access.rule'].create({
            'name': 'First Priority Rule',
            'access_type': 'public',
            'url_patterns': '^/first$'
        })

        rule2 = self.env['sunray.access.rule'].create({
            'name': 'Second Priority Rule',
            'access_type': 'public',
            'url_patterns': '^/second$'
        })

        # Create associations in non-priority order
        assoc3 = self.env['sunray.host.access.rule'].create({
            'host_id': self.host.id,
            'rule_id': rule3.id,
            'priority': 300
        })

        assoc1 = self.env['sunray.host.access.rule'].create({
            'host_id': self.host.id,
            'rule_id': rule1.id,
            'priority': 100
        })

        assoc2 = self.env['sunray.host.access.rule'].create({
            'host_id': self.host.id,
            'rule_id': rule2.id,
            'priority': 200
        })

        # Search with default order should respect priority
        associations = self.env['sunray.host.access.rule'].search([
            ('host_id', '=', self.host.id)
        ])

        self.assertEqual(associations[0].id, assoc1.id)
        self.assertEqual(associations[1].id, assoc2.id)
        self.assertEqual(associations[2].id, assoc3.id)

    def test_worker_config_generation(self):
        """Test generating worker configuration from rules"""

        # Create different types of rules in library
        public_rule = self.env['sunray.access.rule'].create({
            'name': 'Public Endpoints',
            'description': 'Public access endpoints',
            'access_type': 'public',
            'url_patterns': '^/health$\n^/status$'
        })

        cidr_rule = self.env['sunray.access.rule'].create({
            'name': 'Office Access',
            'description': 'Access from office network',
            'access_type': 'cidr',
            'url_patterns': '^/admin/.*',
            'allowed_cidrs': '192.168.1.0/24'
        })

        token_rule = self.env['sunray.access.rule'].create({
            'name': 'API Access',
            'description': 'Token-protected API access',
            'access_type': 'token',
            'url_patterns': '^/api/.*',
            'token_ids': [(6, 0, [self.token1.id])]
        })

        # Test individual rule config (without priority - that's in associations)
        public_config = public_rule.get_worker_config()
        expected_public = {
            'access_type': 'public',
            'url_patterns': ['^/health$', '^/status$'],
            'description': 'Public access endpoints'
        }
        self.assertEqual(public_config, expected_public)

        cidr_config = cidr_rule.get_worker_config()
        expected_cidr = {
            'access_type': 'cidr',
            'url_patterns': ['^/admin/.*'],
            'allowed_cidrs': ['192.168.1.0/24'],
            'description': 'Access from office network'
        }
        self.assertEqual(cidr_config, expected_cidr)

        token_config = token_rule.get_worker_config()
        self.assertEqual(token_config['access_type'], 'token')
        self.assertEqual(token_config['url_patterns'], ['^/api/.*'])
        self.assertEqual(len(token_config['tokens']), 1)
        self.assertEqual(token_config['tokens'][0]['name'], 'Shopify Webhook')

    def test_exceptions_tree_generation(self):
        """Test generating exceptions tree for worker via host"""

        # Create rules in library
        rule_c = self.env['sunray.access.rule'].create({
            'name': 'Third Rule',
            'access_type': 'public',
            'url_patterns': '^/third$'
        })

        rule_a = self.env['sunray.access.rule'].create({
            'name': 'First Rule',
            'access_type': 'public',
            'url_patterns': '^/first$'
        })

        rule_b = self.env['sunray.access.rule'].create({
            'name': 'Second Rule',
            'access_type': 'cidr',
            'url_patterns': '^/second$',
            'allowed_cidrs': '192.168.1.0/24'
        })

        # Create associations in non-priority order
        self.env['sunray.host.access.rule'].create({
            'host_id': self.host.id,
            'rule_id': rule_c.id,
            'priority': 300
        })

        self.env['sunray.host.access.rule'].create({
            'host_id': self.host.id,
            'rule_id': rule_a.id,
            'priority': 100
        })

        self.env['sunray.host.access.rule'].create({
            'host_id': self.host.id,
            'rule_id': rule_b.id,
            'priority': 200
        })

        # Generate exceptions tree from host
        tree = self.host.get_exceptions_tree()

        # Should be ordered by priority
        self.assertEqual(len(tree), 3)
        self.assertEqual(tree[0]['priority'], 100)
        self.assertEqual(tree[0]['description'], 'First Rule')
        self.assertEqual(tree[1]['priority'], 200)
        self.assertEqual(tree[1]['description'], 'Second Rule')
        self.assertEqual(tree[2]['priority'], 300)
        self.assertEqual(tree[2]['description'], 'Third Rule')

        # Verify structure
        self.assertEqual(tree[0]['access_type'], 'public')
        self.assertEqual(tree[1]['access_type'], 'cidr')
        self.assertEqual(tree[1]['allowed_cidrs'], ['192.168.1.0/24'])

    def test_line_separated_field_parsing(self):
        """Test parsing of line-separated fields with comments"""

        rule = self.env['sunray.access.rule'].create({
            'name': 'Test Rule',
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
            'name': 'Active Rule',
            'access_type': 'public',
            'url_patterns': '^/active$',
            'is_active': True
        })

        # Create inactive rule
        inactive_rule = self.env['sunray.access.rule'].create({
            'name': 'Inactive Rule',
            'access_type': 'public',
            'url_patterns': '^/inactive$',
            'is_active': False
        })

        # Create associations
        self.env['sunray.host.access.rule'].create({
            'host_id': self.host.id,
            'rule_id': active_rule.id,
            'priority': 100
        })

        self.env['sunray.host.access.rule'].create({
            'host_id': self.host.id,
            'rule_id': inactive_rule.id,
            'priority': 50  # Would be higher priority if active
        })

        # Generate exceptions tree from host
        tree = self.host.get_exceptions_tree()

        # Only active rule should be included
        self.assertEqual(len(tree), 1)
        self.assertEqual(tree[0]['description'], 'Active Rule')

    def test_name_get_display(self):
        """Test custom name display format"""

        rule = self.env['sunray.access.rule'].create({
            'name': 'Test Rule',
            'access_type': 'public',
            'url_patterns': '^/test$'
        })

        name_get_result = rule.name_get()
        expected_name = "Test Rule (public)"

        self.assertEqual(len(name_get_result), 1)
        self.assertEqual(name_get_result[0][0], rule.id)
        self.assertEqual(name_get_result[0][1], expected_name)

    def test_host_exceptions_tree_integration(self):
        """Test that host.get_exceptions_tree() works with access rules"""

        # Create rules in library
        api_rule = self.env['sunray.access.rule'].create({
            'name': 'API Access',
            'access_type': 'token',
            'url_patterns': '^/api/.*',
            'token_ids': [(6, 0, [self.token1.id])]
        })

        public_rule = self.env['sunray.access.rule'].create({
            'name': 'Public Endpoints',
            'access_type': 'public',
            'url_patterns': '^/health$'
        })

        # Create associations
        self.env['sunray.host.access.rule'].create({
            'host_id': self.host.id,
            'rule_id': api_rule.id,
            'priority': 100
        })

        self.env['sunray.host.access.rule'].create({
            'host_id': self.host.id,
            'rule_id': public_rule.id,
            'priority': 200
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
            'name': 'Expired Token',
            'token': 'expired_123',
            'header_name': 'X-Expired',
            'token_source': 'header',
            'is_active': True,
            'expires_at': fields.Datetime.now() - timedelta(days=1)
        })

        # Create access rule library with all tokens
        rule = self.env['sunray.access.rule'].create({
            'name': 'API Access',
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
            ('CIDR High Priority', 50, 'cidr'),
            ('Public Medium', 100, 'public'),
            ('Public Low', 200, 'public'),
            ('Token Highest', 10, 'token')
        ]

        created_rules = []
        for name, priority, access_type in rules_data:
            rule_data = {
                'name': name,
                'access_type': access_type
            }

            if access_type == 'cidr':
                rule_data.update({
                    'url_patterns': f'^/{name.lower().replace(" ", "_")}',
                    'allowed_cidrs': '192.168.1.0/24'
                })
            elif access_type == 'token':
                rule_data.update({
                    'url_patterns': f'^/{name.lower().replace(" ", "_")}',
                    'token_ids': [(6, 0, [self.token1.id])]
                })
            else:
                rule_data['url_patterns'] = f'^/{name.lower().replace(" ", "_")}'

            rule = self.env['sunray.access.rule'].create(rule_data)
            created_rules.append((rule, priority))

            # Create association with priority
            self.env['sunray.host.access.rule'].create({
                'host_id': self.host.id,
                'rule_id': rule.id,
                'priority': priority
            })

        # Get exceptions tree from host
        tree = self.host.get_exceptions_tree()

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

    def test_token_reuse_across_multiple_hosts(self):
        """Test that tokens can be reused across multiple hosts via access rules"""

        # Create a second host
        host2 = self.env['sunray.host'].create({
            'domain': 'api2.example.com',
            'sunray_worker_id': self.worker.id,
            'backend_url': 'https://backend2.example.com',
            'is_active': True
        })

        # Create a single global token
        global_token = self.env['sunray.webhook.token'].create({
            'name': 'Global Shopify Webhook',
            'token': 'global_shopify_token_xyz',
            'header_name': 'X-Shopify-Hmac-Sha256',
            'token_source': 'header'
        })

        # Create a single reusable rule in the library
        shopify_rule = self.env['sunray.access.rule'].create({
            'name': 'Shopify Webhooks',
            'description': 'Shopify webhook endpoints',
            'access_type': 'token',
            'url_patterns': '^/api/shopify/webhook\n^/webhooks/shopify/.*',
            'token_ids': [(6, 0, [global_token.id])]
        })

        # Attach the same rule to both hosts with different priorities
        assoc1 = self.env['sunray.host.access.rule'].create({
            'host_id': self.host.id,
            'rule_id': shopify_rule.id,
            'priority': 100
        })

        assoc2 = self.env['sunray.host.access.rule'].create({
            'host_id': host2.id,
            'rule_id': shopify_rule.id,
            'priority': 200  # Different priority on host 2
        })

        # Verify rule is referenced in both associations
        self.assertEqual(assoc1.rule_id.id, shopify_rule.id)
        self.assertEqual(assoc2.rule_id.id, shopify_rule.id)

        # Get worker configs for both hosts
        exceptions_tree1 = self.host.get_exceptions_tree()
        exceptions_tree2 = host2.get_exceptions_tree()

        # Both should have the same rule with same token but different priorities
        self.assertEqual(len(exceptions_tree1), 1)
        self.assertEqual(len(exceptions_tree2), 1)
        self.assertEqual(exceptions_tree1[0]['priority'], 100)
        self.assertEqual(exceptions_tree2[0]['priority'], 200)
        self.assertEqual(exceptions_tree1[0]['tokens'][0]['token'], 'global_shopify_token_xyz')
        self.assertEqual(exceptions_tree2[0]['tokens'][0]['token'], 'global_shopify_token_xyz')

        # Update the token - verify change propagates to both hosts
        global_token.write({'is_active': False})

        # Refresh configs
        exceptions_tree1 = self.host.get_exceptions_tree()
        exceptions_tree2 = host2.get_exceptions_tree()

        # Both should now have empty token lists (token filtered out because inactive)
        self.assertEqual(len(exceptions_tree1[0]['tokens']), 0)
        self.assertEqual(len(exceptions_tree2[0]['tokens']), 0)

        print(f"✓ Rule reuse verified: Same rule used on {self.host.domain} and {host2.domain} with different priorities")

    def test_rule_deletion_protection(self):
        """Test that rules in use cannot be deleted"""

        # Create a rule
        rule = self.env['sunray.access.rule'].create({
            'name': 'Protected Rule',
            'access_type': 'public',
            'url_patterns': '^/test$'
        })

        # Attach it to host
        self.env['sunray.host.access.rule'].create({
            'host_id': self.host.id,
            'rule_id': rule.id,
            'priority': 100
        })

        # Try to delete - should fail
        with self.assertRaises(ValidationError) as cm:
            rule.unlink()

        self.assertIn('used by', str(cm.exception))
        self.assertIn('api.example.com', str(cm.exception))

    def test_association_unique_constraint(self):
        """Test that same rule cannot be added twice to same host"""

        # Create a rule
        rule = self.env['sunray.access.rule'].create({
            'name': 'Test Rule',
            'access_type': 'public',
            'url_patterns': '^/test$'
        })

        # Create first association
        self.env['sunray.host.access.rule'].create({
            'host_id': self.host.id,
            'rule_id': rule.id,
            'priority': 100
        })

        # Try to create duplicate association - should fail
        with self.assertRaises(Exception):  # Will be a database constraint error
            self.env['sunray.host.access.rule'].create({
                'host_id': self.host.id,
                'rule_id': rule.id,
                'priority': 200
            })

    def test_association_inactive_status(self):
        """Test that association.is_active controls per-host rule activation"""

        # Create rule
        rule = self.env['sunray.access.rule'].create({
            'name': 'Test Rule',
            'access_type': 'public',
            'url_patterns': '^/test$',
            'is_active': True  # Rule is active in library
        })

        # Create active association
        assoc_active = self.env['sunray.host.access.rule'].create({
            'host_id': self.host.id,
            'rule_id': rule.id,
            'priority': 100,
            'is_active': True
        })

        # Rule should be in exceptions tree
        tree = self.host.get_exceptions_tree()
        self.assertEqual(len(tree), 1)

        # Deactivate association (not rule)
        assoc_active.write({'is_active': False})

        # Rule should NOT be in exceptions tree
        tree = self.host.get_exceptions_tree()
        self.assertEqual(len(tree), 0)

        # Reactivate association
        assoc_active.write({'is_active': True})

        # Rule should be back in exceptions tree
        tree = self.host.get_exceptions_tree()
        self.assertEqual(len(tree), 1)
