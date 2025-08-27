# -*- coding: utf-8 -*-
"""Test cache invalidation functionality"""

from odoo.tests import TransactionCase
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
import time
import json


class TestCacheInvalidation(TransactionCase):
    """Test cache invalidation and version tracking"""
    
    def setUp(self):
        super().setUp()
        self.User = self.env['sunray.user']
        self.Host = self.env['sunray.host']
        self.ApiKey = self.env['sunray.api.key']
        self.Worker = self.env['sunray.worker']
        
        # Create test API key
        self.api_key = self.ApiKey.create([{
            'name': 'test_worker_key',
            'is_active': True,
            'scopes': 'config:read'
        }])
        
        # Create test worker
        self.worker = self.Worker.create({
            'name': 'Test Worker',
            'worker_type': 'cloudflare',
            'worker_url': 'https://test-worker.example.com',
            'api_key_id': self.api_key.id,
            'is_active': True
        })
        
        # Create test host
        self.host = self.Host.create({
            'domain': 'test.example.com',
            'sunray_worker_id': self.worker.id,
            'backend_url': 'http://backend.example.com',
            'is_active': True
        })
        
        # Create test user
        self.user = self.User.create({
            'username': 'testuser',
            'email': 'test@example.com',
            'is_active': True,
            'host_ids': [(4, self.host.id)]
        })
    
    def test_version_field_initialization(self):
        """Test that config_version is initialized on creation"""
        # Check host version
        self.assertIsNotNone(self.host.config_version)
        self.assertIsInstance(self.host.config_version, datetime)
        
        # Check user version
        self.assertIsNotNone(self.user.config_version)
        self.assertIsInstance(self.user.config_version, datetime)
    
    def test_version_update_on_write(self):
        """Test that config_version updates when record is modified"""
        # Store original versions
        host_original_version = self.host.config_version
        user_original_version = self.user.config_version
        
        # Wait to ensure time difference
        time.sleep(1)
        
        # Update host
        self.host.write({'backend_url': 'http://new-backend.example.com'})
        self.assertGreater(self.host.config_version, host_original_version)
        
        # Update user
        self.user.write({'email': 'newemail@example.com'})
        self.assertGreater(self.user.config_version, user_original_version)
    
    def test_version_not_updated_when_only_version_changes(self):
        """Test that updating only config_version doesn't trigger another update"""
        new_version = datetime.now()
        self.host.write({'config_version': new_version})
        
        # Version should be exactly what we set, not auto-updated
        self.assertEqual(self.host.config_version, new_version)
    
    def test_config_endpoint_includes_versions(self):
        """Test that /config endpoint includes version information"""
        # Create API controller
        from odoo.addons.sunray_core.controllers.rest_api import SunrayRESTController
        controller = SunrayRESTController()
        
        # Create properly configured mock request object
        mock_request_obj = MagicMock()
        mock_request_obj.env = self.env
        
        # Configure httprequest mock to return strings instead of MagicMock objects
        mock_httprequest = MagicMock()
        mock_httprequest.headers = {
            'X-Worker-ID': 'test-worker-123',
            'User-Agent': 'Test-Agent/1.0',
            'X-Forwarded-For': '192.168.1.100'
        }
        mock_httprequest.environ = {
            'REMOTE_ADDR': '192.168.1.100',
            'HTTP_HOST': 'test.example.com'
        }
        mock_request_obj.httprequest = mock_httprequest
        
        # Mock authentication to return True and patch request object
        with patch.object(controller, '_authenticate_api', return_value=True), \
             patch('odoo.addons.sunray_core.controllers.rest_api.request', mock_request_obj):
            
            # Call get_config
            response = controller.get_config()
            data = json.loads(response.data)
            
            # Check response structure
            self.assertIn('config_version', data)
            self.assertIn('host_versions', data)
            self.assertIn('user_versions', data)
            
            # Check host version is included
            self.assertIn(self.host.domain, data['host_versions'])
            host_version = datetime.fromisoformat(data['host_versions'][self.host.domain])
            self.assertEqual(host_version, self.host.config_version)
            
            # Check user version is included
            self.assertIn(self.user.username, data['user_versions'])
            user_version = datetime.fromisoformat(data['user_versions'][self.user.username])
            self.assertEqual(user_version, self.user.config_version)
    
    @patch('requests.post')
    def test_force_cache_refresh_host(self, mock_post):
        """Test force_cache_refresh method on host model"""
        # Configure mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'success': True,
            'message': 'Cache invalidation triggered'
        }
        mock_post.return_value = mock_response
        
        # Worker URL is now taken from the host's worker relationship
        
        # Call force_cache_refresh
        result = self.host.force_cache_refresh()
        
        # Verify API call was made
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        
        # Check URL - cache clearing goes through the protected host URL
        self.assertEqual(
            call_args[0][0],
            'https://test.example.com/sunray-wrkr/v1/cache/clear'
        )
        
        # Check headers
        headers = call_args[1]['headers']
        self.assertIn('Authorization', headers)
        self.assertEqual(headers['Authorization'], f'Bearer {self.api_key.key}')
        
        # Check payload - new API format with target object
        payload = call_args[1]['json']
        self.assertEqual(payload['scope'], 'host')
        self.assertEqual(payload['target'], {'hostname': 'test.example.com'})
        self.assertIn('Manual refresh', payload['reason'])
        
        # Check audit log was created with new event type
        audit_log = self.env['sunray.audit.log'].search([
            ('event_type', '=', 'cache.cleared'),
            ('details', 'like', 'test.example.com')
        ], limit=1)
        self.assertTrue(audit_log)
        
        # Check notification returned
        self.assertEqual(result['type'], 'ir.actions.client')
        self.assertEqual(result['tag'], 'display_notification')
    
    @patch('odoo.addons.sunray_core.models.sunray_user.SunrayUser.action_revoke_sessions_on_host')
    @patch('odoo.addons.sunray_core.models.sunray_audit_log.SunrayAuditLog.create_audit_event')
    def test_action_revoke_sessions_on_all_hosts_user(self, mock_audit_log, mock_revoke_host):
        """Test action_revoke_sessions_on_all_hosts method on user model"""
        # Configure mock response from action_revoke_sessions_on_host
        mock_revoke_host.return_value = {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Sessions Revoked',
                'message': 'Revoked 2 session(s) for user testuser on host test.example.com.',
                'type': 'success',
            }
        }
        
        # Call action_revoke_sessions_on_all_hosts
        result = self.user.action_revoke_sessions_on_all_hosts()
        
        # Verify the underlying method was called once (for one host)
        mock_revoke_host.assert_called_once_with(self.host.id)
        
        # Check the consolidated result
        self.assertEqual(result['type'], 'ir.actions.client')
        self.assertEqual(result['tag'], 'display_notification')
        self.assertEqual(result['params']['title'], 'Bulk Session Revocation Results')
        self.assertIn('Total sessions revoked: 2', result['params']['message'])
        self.assertIn('Successfully revoked sessions on 1 host(s)', result['params']['message'])
        
        # Verify audit log creation was called
        mock_audit_log.assert_called_once()
        audit_call = mock_audit_log.call_args
        self.assertEqual(audit_call[1]['event_type'], 'sessions.bulk_revoked')
        self.assertEqual(audit_call[1]['severity'], 'info')
        self.assertEqual(audit_call[1]['details']['operation'], 'revoke_sessions_all_hosts')
        self.assertEqual(audit_call[1]['sunray_user_id'], self.user.id)
    
    @patch('requests.post')
    def test_force_cache_refresh_error_handling(self, mock_post):
        """Test error handling in force_cache_refresh"""
        # Configure mock to raise exception
        mock_post.side_effect = Exception('Network error')
        
        # Worker URL is now taken from the host's worker relationship
        
        # Call should raise UserError
        from odoo.exceptions import UserError
        with self.assertRaises(UserError) as cm:
            self.host.force_cache_refresh()
        
        self.assertIn('Failed to trigger cache refresh', str(cm.exception))
    
    @patch('requests.post')
    def test_force_cache_refresh_no_api_key(self, mock_post):
        """Test force_cache_refresh when no API key exists"""
        # Make the worker's API key inactive instead of deleting all keys
        self.host.sunray_worker_id.api_key_id.is_active = False
        
        # Worker URL is now taken from the host's worker relationship
        
        # Call should raise UserError
        from odoo.exceptions import UserError
        with self.assertRaises(UserError) as cm:
            self.host.force_cache_refresh()
        
        self.assertIn('No active API key', str(cm.exception))
    
    def test_multiple_hosts_version_tracking(self):
        """Test version tracking with multiple hosts"""
        # Create additional hosts
        host2 = self.Host.create({
            'domain': 'test2.example.com',
            'sunray_worker_id': self.worker.id,
            'backend_url': 'http://backend2.example.com'
        })
        
        host3 = self.Host.create({
            'domain': 'test3.example.com',
            'sunray_worker_id': self.worker.id,
            'backend_url': 'http://backend3.example.com'
        })
        
        # Each should have its own version
        self.assertIsNotNone(host2.config_version)
        self.assertIsNotNone(host3.config_version)
        
        # Update one host
        original_version2 = host2.config_version
        original_version3 = host3.config_version
        time.sleep(1)
        
        host2.write({'is_active': False})
        
        # Only host2 version should change
        self.assertGreater(host2.config_version, original_version2)
        self.assertEqual(host3.config_version, original_version3)
    
    def test_multiple_users_version_tracking(self):
        """Test version tracking with multiple users"""
        # Create additional users
        user2 = self.User.create({
            'username': 'testuser2',
            'email': 'test2@example.com'
        })
        
        user3 = self.User.create({
            'username': 'testuser3',
            'email': 'test3@example.com'
        })
        
        # Update one user
        original_version2 = user2.config_version
        original_version3 = user3.config_version
        time.sleep(1)
        
        user2.write({'display_name': 'Test User 2'})
        
        # Only user2 version should change
        self.assertGreater(user2.config_version, original_version2)
        self.assertEqual(user3.config_version, original_version3)
    
    def test_cascade_version_update_not_triggered(self):
        """Test that related records don't cascade version updates"""
        original_host_version = self.host.config_version
        time.sleep(1)
        
        # Update user (which has relation to host)
        self.user.write({'email': 'another@example.com'})
        
        # Host version should NOT change
        self.assertEqual(self.host.config_version, original_host_version)
    
    @patch('requests.post')
    def test_bulk_cache_refresh(self, mock_post):
        """Test force_cache_refresh on multiple records"""
        # Configure mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'success': True}
        mock_post.return_value = mock_response
        
        # Create additional hosts
        host2 = self.Host.create({
            'domain': 'test2.example.com',
            'sunray_worker_id': self.worker.id,
            'backend_url': 'http://backend2.example.com'
        })
        
        # Worker URL is now taken from the host's worker relationship
        
        # Call on multiple hosts
        hosts = self.host | host2
        result = hosts.force_cache_refresh()
        
        # Should have made 2 API calls
        self.assertEqual(mock_post.call_count, 2)
        
        # Check notification message
        self.assertIn('2 host(s)', result['params']['message'])
    
    def test_version_format_in_api_response(self):
        """Test that versions are properly formatted in API response"""
        from odoo.addons.sunray_core.controllers.rest_api import SunrayRESTController
        controller = SunrayRESTController()
        
        # Create properly configured mock request object
        mock_request_obj = MagicMock()
        mock_request_obj.env = self.env
        
        # Configure httprequest mock to return strings instead of MagicMock objects
        mock_httprequest = MagicMock()
        mock_httprequest.headers = {
            'X-Worker-ID': 'test-worker-123',
            'User-Agent': 'Test-Agent/1.0',
            'X-Forwarded-For': '192.168.1.100'
        }
        mock_httprequest.environ = {
            'REMOTE_ADDR': '192.168.1.100',
            'HTTP_HOST': 'test.example.com'
        }
        mock_request_obj.httprequest = mock_httprequest
        
        # Mock authentication to return True and patch request object
        with patch.object(controller, '_authenticate_api', return_value=True), \
             patch('odoo.addons.sunray_core.controllers.rest_api.request', mock_request_obj):
            
            response = controller.get_config()
            data = json.loads(response.data)
            
            # Version should be ISO format string that can be parsed
            config_version = data['config_version']
            parsed_version = datetime.fromisoformat(config_version)
            self.assertIsInstance(parsed_version, datetime)
            
            # Host versions should be parseable
            for domain, version_str in data['host_versions'].items():
                parsed = datetime.fromisoformat(version_str)
                self.assertIsInstance(parsed, datetime)
            
            # User versions should be parseable
            for username, version_str in data['user_versions'].items():
                parsed = datetime.fromisoformat(version_str)
                self.assertIsInstance(parsed, datetime)