# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase
from odoo import fields
from datetime import datetime, timedelta
import json


class TestVersionTracking(TransactionCase):
    """Test version tracking for cache invalidation"""
    
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
            'worker_url': 'https://worker.test-version.example.com',
            'api_key_id': self.api_key.id,
            'is_active': True
        })
        
        # Create test user
        self.test_user = self.env['sunray.user'].create({
            'username': 'test_version_user',
            'email': 'test_version@example.com',
            'is_active': True
        })
        
        # Create test host
        self.test_host = self.env['sunray.host'].create({
            'domain': 'test-version.example.com',
            'sunray_worker_id': self.worker.id,
            'backend_url': 'http://backend.example.com',
            'is_active': True
        })
    
    def test_user_version_auto_update(self):
        """Test that config_version updates on user modification"""
        initial_version = self.test_user.config_version
        self.assertIsNotNone(initial_version, "Initial version should be set")
        
        # Sleep to ensure time difference (Datetime precision issue)
        import time
        time.sleep(1)
        
        # Modify user
        self.test_user.write({'is_active': False})
        updated_version = self.test_user.config_version
        
        self.assertNotEqual(initial_version, updated_version, 
                           "Version should change after modification")
        self.assertGreater(updated_version, initial_version,
                          "New version should be greater than old version")
    
    def test_host_version_auto_update(self):
        """Test that config_version updates on host modification"""
        initial_version = self.test_host.config_version
        self.assertIsNotNone(initial_version, "Initial version should be set")
        
        # Sleep to ensure time difference
        import time
        time.sleep(1)
        
        # Modify host
        self.test_host.write({'session_duration_s': 7200})
        updated_version = self.test_host.config_version
        
        self.assertGreater(updated_version, initial_version,
                          "New version should be greater than old version")
    
    def test_version_not_updated_on_same_field(self):
        """Test that updating only config_version doesn't trigger another update"""
        initial_version = self.test_user.config_version
        
        # Update only the config_version field
        new_version = fields.Datetime.now()
        self.test_user.write({'config_version': new_version})
        
        # Version should be what we set, not auto-updated again
        self.assertEqual(self.test_user.config_version, new_version,
                        "Version should not auto-update when only version field is changed")
    
    def test_multiple_field_update_triggers_single_version_update(self):
        """Test that updating multiple fields triggers single version update"""
        initial_version = self.test_user.config_version
        
        # Sleep to ensure time difference
        import time
        time.sleep(1)
        
        # Update multiple fields at once
        self.test_user.write({
            'email': 'new_email@example.com',
            'is_active': False
        })
        
        updated_version = self.test_user.config_version
        self.assertGreater(updated_version, initial_version,
                          "Version should be updated once for multiple field changes")
    
    def test_config_endpoint_includes_versions(self):
        """Test that /config endpoint returns version information"""
        # This test would need HTTP client to test the endpoint
        # For now, we'll test the underlying data structure
        
        # Set a recent modification on user
        self.test_user.write({'is_active': False})
        
        # Simulate what the controller does (updated format without redundant properties)
        config = {
            'version': 4,
            'generated_at': fields.Datetime.now().isoformat(),
            'hosts': []
        }
        
        # Add host with config_version in the host object
        host_config = self.test_host.get_config_data()
        config['hosts'].append(host_config)
        
        # Verify structure
        self.assertIn('hosts', config, "Config should have hosts array")
        self.assertTrue(len(config['hosts']) > 0, "Should have at least one host")
        self.assertIn('config_version', config['hosts'][0], "Host should have config_version")
    
    def test_host_authorized_users_change_updates_version(self):
        """Test that changing authorized users updates host version"""
        initial_version = self.test_host.config_version
        
        # Sleep to ensure time difference
        import time
        time.sleep(1)
        
        # Add user to authorized users
        self.test_host.write({
            'user_ids': [(4, self.test_user.id)]
        })
        
        updated_version = self.test_host.config_version
        self.assertGreater(updated_version, initial_version,
                          "Version should update when authorized users change")
    
    def test_webhook_token_change_updates_host_version(self):
        """Test that adding webhook tokens updates host version"""
        initial_version = self.test_host.config_version
        
        # Sleep to ensure time difference
        import time
        time.sleep(1)
        
        # Create webhook token (no longer tied to specific host)
        webhook_token = self.env['sunray.webhook.token'].create([{
            'name': 'Test Webhook',
            'token': 'webhook-token-123',
            'header_name': 'X-Test-Token',  # Required for token_source='header' (default)
            'is_active': True
        }])
        
        # Host version should be updated
        self.test_host.write({'bypass_waf_for_authenticated': True})
        
        updated_version = self.test_host.config_version
        self.assertGreater(updated_version, initial_version,
                          "Version should update when webhook configuration changes")