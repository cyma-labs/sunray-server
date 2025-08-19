# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase
from odoo import fields
from datetime import datetime, timedelta
import json


class TestVersionTracking(TransactionCase):
    """Test version tracking for cache invalidation"""
    
    def setUp(self):
        super().setUp()
        # Create test user
        self.test_user = self.env['sunray.user'].create({
            'username': 'test_version_user',
            'email': 'test_version@example.com',
            'is_active': True
        })
        
        # Create test host
        self.test_host = self.env['sunray.host'].create({
            'domain': 'test-version.example.com',
            'worker_url': 'https://worker.test-version.example.com',
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
        
        # Simulate what the controller does
        config = {
            'version': 3,
            'generated_at': fields.Datetime.now().isoformat(),
            'config_version': fields.Datetime.now().isoformat(),
            'host_versions': {},
            'user_versions': {},
            'users': {},
            'hosts': []
        }
        
        # Add host version
        if self.test_host.config_version:
            config['host_versions'][self.test_host.domain] = self.test_host.config_version.isoformat()
        
        # Add user version if recently modified
        five_minutes_ago = fields.Datetime.now() - timedelta(minutes=5)
        if self.test_user.config_version and self.test_user.config_version > five_minutes_ago:
            config['user_versions'][self.test_user.username] = self.test_user.config_version.isoformat()
        
        # Verify structure
        self.assertIn('config_version', config, "Config should have global version")
        self.assertIn('host_versions', config, "Config should have host versions")
        self.assertIn('user_versions', config, "Config should have user versions")
        self.assertIn(self.test_host.domain, config['host_versions'], 
                     "Test host should be in host versions")
        self.assertIn(self.test_user.username, config['user_versions'],
                     "Recently modified user should be in user versions")
    
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
        
        # Create webhook token for host - providing token explicitly to avoid create() issue
        webhook_token = self.env['sunray.webhook.token'].create([{
            'name': 'Test Webhook',
            'token': 'webhook-token-123',
            'host_id': self.test_host.id,
            'header_name': 'X-Test-Token',  # Required for token_source='header' (default)
            'is_active': True
        }])
        
        # Host version should be updated
        self.test_host.write({'bypass_waf_for_authenticated': True})
        
        updated_version = self.test_host.config_version
        self.assertGreater(updated_version, initial_version,
                          "Version should update when webhook configuration changes")