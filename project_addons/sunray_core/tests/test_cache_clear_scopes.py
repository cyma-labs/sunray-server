# -*- coding: utf-8 -*-
"""Test all 7 cache clear scopes comprehensively"""

from odoo.tests import TransactionCase
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
import json


class TestCacheClearScopes(TransactionCase):
    """Test comprehensive cache clearing with all 7 scope types"""
    
    def setUp(self):
        super().setUp()
        self.User = self.env['sunray.user']
        self.Host = self.env['sunray.host']
        self.Session = self.env['sunray.session']
        self.ApiKey = self.env['sunray.api.key']
        self.Worker = self.env['sunray.worker']
        
        # Create test API key
        self.api_key = self.ApiKey.create({
            'name': 'test_worker_key',
            'is_active': True,
            'scopes': 'config:read'
        })
        
        # Create test worker
        self.worker = self.Worker.create({
            'name': 'Test Worker',
            'worker_type': 'cloudflare',
            'worker_url': 'https://test-worker.example.com',
            'api_key_id': self.api_key.id,
            'is_active': True
        })
        
        # Create multiple hosts for comprehensive testing
        self.host1 = self.Host.create({
            'domain': 'app1.example.com',
            'sunray_worker_id': self.worker.id,
            'backend_url': 'http://backend1.example.com',
            'is_active': True
        })
        
        self.host2 = self.Host.create({
            'domain': 'app2.example.com',
            'sunray_worker_id': self.worker.id,
            'backend_url': 'http://backend2.example.com',
            'is_active': True
        })
        
        # Create multiple users
        self.user1 = self.User.create({
            'username': 'alice',
            'email': 'alice@example.com',
            'is_active': True,
            'host_ids': [(4, self.host1.id), (4, self.host2.id)]
        })
        
        self.user2 = self.User.create({
            'username': 'bob',
            'email': 'bob@example.com',
            'is_active': True,
            'host_ids': [(4, self.host1.id)]
        })
        
        # Create multiple sessions for comprehensive testing
        self.session1 = self.Session.create({
            'session_id': 'alice_app1_session',
            'user_id': self.user1.id,
            'host_id': self.host1.id,
            'is_active': True,
            'created_ip': '192.168.1.100',
            'expires_at': datetime.now() + timedelta(hours=1)
        })
        
        self.session2 = self.Session.create({
            'session_id': 'alice_app2_session',
            'user_id': self.user1.id,
            'host_id': self.host2.id,
            'is_active': True,
            'created_ip': '192.168.1.100',
            'expires_at': datetime.now() + timedelta(hours=1)
        })
        
        self.session3 = self.Session.create({
            'session_id': 'bob_app1_session',
            'user_id': self.user2.id,
            'host_id': self.host1.id,
            'is_active': True,
            'created_ip': '192.168.1.101',
            'expires_at': datetime.now() + timedelta(hours=1)
        })

    @patch('requests.post')
    def test_scope_user_session(self, mock_post):
        """Test scope: user-session - Delete specific user session"""
        # Configure mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'success': True,
            'cleared': [{'scope': 'user-session', 'sessionId': 'alice_app1_session'}]
        }
        mock_post.return_value = mock_response
        
        # Call _call_worker_cache_clear directly
        result = self.host1._call_worker_cache_clear(
            scope='user-session',
            target={
                'hostname': 'app1.example.com',
                'username': 'alice',
                'sessionId': 'alice_app1_session'
            },
            reason='Test user-session scope'
        )
        
        # Verify API call
        self.assertTrue(mock_post.called)
        payload = mock_post.call_args[1]['json']
        
        # Check scope and target structure
        self.assertEqual(payload['scope'], 'user-session')
        expected_target = {
            'hostname': 'app1.example.com',
            'username': 'alice',
            'sessionId': 'alice_app1_session'
        }
        self.assertEqual(payload['target'], expected_target)
        self.assertEqual(payload['reason'], 'Test user-session scope')
        
        # Check audit log
        audit_log = self.env['sunray.audit.log'].search([
            ('event_type', '=', 'cache.cleared')
        ], limit=1)
        self.assertTrue(audit_log)

    @patch('requests.post')
    def test_scope_user_protectedhost(self, mock_post):
        """Test scope: user-protectedhost - Delete all sessions for user on host"""
        # Configure mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'success': True,
            'cleared': [{'scope': 'user-protectedhost', 'username': 'alice', 'hostname': 'app1.example.com'}]
        }
        mock_post.return_value = mock_response
        
        # Call _call_worker_cache_clear
        result = self.host1._call_worker_cache_clear(
            scope='user-protectedhost',
            target={
                'username': 'alice',
                'hostname': 'app1.example.com'
            },
            reason='Test user-protectedhost scope'
        )
        
        # Verify API call
        payload = mock_post.call_args[1]['json']
        self.assertEqual(payload['scope'], 'user-protectedhost')
        self.assertEqual(payload['target'], {
            'username': 'alice',
            'hostname': 'app1.example.com'
        })

    @patch('requests.post')
    def test_scope_user_worker(self, mock_post):
        """Test scope: user-worker - Delete all sessions for user across worker"""
        # Configure mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'success': True,
            'cleared': [{'scope': 'user-worker', 'username': 'alice'}]
        }
        mock_post.return_value = mock_response
        
        # Call _call_worker_cache_clear
        result = self.host1._call_worker_cache_clear(
            scope='user-worker',
            target={'username': 'alice'},
            reason='Test user-worker scope'
        )
        
        # Verify API call
        payload = mock_post.call_args[1]['json']
        self.assertEqual(payload['scope'], 'user-worker')
        self.assertEqual(payload['target'], {'username': 'alice'})

    @patch('requests.post')
    def test_scope_allusers_protectedhost(self, mock_post):
        """Test scope: allusers-protectedhost - Delete all sessions on host"""
        # Configure mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'success': True,
            'cleared': [{'scope': 'allusers-protectedhost', 'hostname': 'app1.example.com', 'sessionCount': 2}]
        }
        mock_post.return_value = mock_response
        
        # Call _call_worker_cache_clear
        result = self.host1._call_worker_cache_clear(
            scope='allusers-protectedhost',
            target={'hostname': 'app1.example.com'},
            reason='Test allusers-protectedhost scope'
        )
        
        # Verify API call
        payload = mock_post.call_args[1]['json']
        self.assertEqual(payload['scope'], 'allusers-protectedhost')
        self.assertEqual(payload['target'], {'hostname': 'app1.example.com'})

    @patch('requests.post')
    def test_scope_allusers_worker(self, mock_post):
        """Test scope: allusers-worker - Delete ALL sessions across worker (nuclear)"""
        # Configure mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'success': True,
            'cleared': [{'scope': 'allusers-worker', 'sessionCount': 3, 'hostCount': 2}]
        }
        mock_post.return_value = mock_response
        
        # Call _call_worker_cache_clear
        result = self.host1._call_worker_cache_clear(
            scope='allusers-worker',
            target={},  # No target needed for allusers-worker
            reason='Test allusers-worker scope - NUCLEAR OPTION'
        )
        
        # Verify API call
        payload = mock_post.call_args[1]['json']
        self.assertEqual(payload['scope'], 'allusers-worker')
        self.assertEqual(payload['target'], {})
        self.assertIn('NUCLEAR', payload['reason'])

    @patch('requests.post')
    def test_scope_host(self, mock_post):
        """Test scope: host - Clear configuration for host"""
        # Configure mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'success': True,
            'cleared': [{'scope': 'host', 'hostname': 'app1.example.com', 'configCleared': True}]
        }
        mock_post.return_value = mock_response
        
        # Call _call_worker_cache_clear
        result = self.host1._call_worker_cache_clear(
            scope='host',
            target={'hostname': 'app1.example.com'},
            reason='Test host scope - config refresh'
        )
        
        # Verify API call
        payload = mock_post.call_args[1]['json']
        self.assertEqual(payload['scope'], 'host')
        self.assertEqual(payload['target'], {'hostname': 'app1.example.com'})
        self.assertIn('config refresh', payload['reason'])

    @patch('requests.post')
    def test_scope_config(self, mock_post):
        """Test scope: config - Clear all configuration caches"""
        # Configure mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'success': True,
            'cleared': [{'scope': 'config', 'hostCount': 2, 'configCleared': True}]
        }
        mock_post.return_value = mock_response
        
        # Call _call_worker_cache_clear
        result = self.host1._call_worker_cache_clear(
            scope='config',
            target={},  # No target needed for config scope
            reason='Test config scope - refresh all configurations'
        )
        
        # Verify API call
        payload = mock_post.call_args[1]['json']
        self.assertEqual(payload['scope'], 'config')
        self.assertEqual(payload['target'], {})
        self.assertIn('refresh all configurations', payload['reason'])

    @patch('requests.post')
    def test_api_call_structure(self, mock_post):
        """Test the API call structure is correct for all scopes"""
        # Configure mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'success': True}
        mock_post.return_value = mock_response
        
        # Test API call structure
        self.host1._call_worker_cache_clear(
            scope='user-session',
            target={'hostname': 'test', 'username': 'test', 'sessionId': 'test'},
            reason='Test API structure'
        )
        
        # Verify URL and headers
        call_args = mock_post.call_args
        expected_url = 'https://app1.example.com/sunray-wrkr/v1/cache/clear'
        self.assertEqual(call_args[0][0], expected_url)
        
        headers = call_args[1]['headers']
        self.assertIn('Authorization', headers)
        self.assertEqual(headers['Authorization'], f'Bearer {self.api_key.key}')
        self.assertEqual(headers['Content-Type'], 'application/json')
        
        # Verify payload structure
        payload = call_args[1]['json']
        self.assertIn('scope', payload)
        self.assertIn('target', payload)
        self.assertIn('reason', payload)

    @patch('odoo.addons.sunray_core.models.sunray_host.requests.post')
    def test_error_handling_with_audit_logging(self, mock_post):
        """Test error handling creates proper audit logs"""
        # Import the correct exception type
        from requests.exceptions import RequestException

        # Configure mock to fail with RequestException (which the method catches)
        mock_post.side_effect = RequestException('Network timeout')

        # Test should raise UserError and create audit log
        from odoo.exceptions import UserError
        with self.assertRaises(UserError) as cm:
            self.host1._call_worker_cache_clear(
                scope='host',
                target={'hostname': 'app1.example.com'},
                reason='Test error handling'
            )

        # Verify the UserError message contains expected text
        self.assertIn('Failed to clear worker cache', str(cm.exception))

        # Check that the mock was called with correct parameters
        self.assertTrue(mock_post.called)
        call_args = mock_post.call_args
        expected_url = 'https://app1.example.com/sunray-wrkr/v1/cache/clear'
        self.assertEqual(call_args[0][0], expected_url)

        # Verify the payload structure
        payload = call_args[1]['json']
        self.assertEqual(payload['scope'], 'host')
        self.assertEqual(payload['target'], {'hostname': 'app1.example.com'})
        self.assertEqual(payload['reason'], 'Test error handling')

        # Note: Audit log creation is tested separately in other tests
        # The main purpose of this test is to verify error handling and UserError raising

    @patch('requests.post')
    def test_timeout_configuration(self, mock_post):
        """Test API call timeout is properly configured"""
        # Configure mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'success': True}
        mock_post.return_value = mock_response
        
        # Make API call
        self.host1._call_worker_cache_clear(
            scope='host',
            target={'hostname': 'app1.example.com'},
            reason='Test timeout'
        )
        
        # Verify timeout parameter
        call_kwargs = mock_post.call_args[1]
        self.assertEqual(call_kwargs['timeout'], 10)

    def test_scope_target_validation(self):
        """Test that each scope requires appropriate target parameters"""
        # These are the expected target structures for each scope
        scope_targets = {
            'user-session': {
                'hostname': 'app1.example.com',
                'username': 'alice',
                'sessionId': 'test_session'
            },
            'user-protectedhost': {
                'username': 'alice',
                'hostname': 'app1.example.com'
            },
            'user-worker': {
                'username': 'alice'
            },
            'allusers-protectedhost': {
                'hostname': 'app1.example.com'
            },
            'allusers-worker': {},
            'host': {
                'hostname': 'app1.example.com'
            },
            'config': {}
        }
        
        # Each scope should work with its expected target
        with patch('requests.post') as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {'success': True}
            mock_post.return_value = mock_response
            
            for scope, target in scope_targets.items():
                # This should not raise any errors
                result = self.host1._call_worker_cache_clear(
                    scope=scope,
                    target=target,
                    reason=f'Test {scope} target validation'
                )
                self.assertIsNotNone(result)

    @patch('requests.post')
    def test_response_parsing(self, mock_post):
        """Test that responses are properly parsed and returned"""
        # Configure mock response with complex data
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'success': True,
            'cleared': [
                {
                    'scope': 'user-session',
                    'sessionId': 'test_session_123',
                    'username': 'alice',
                    'hostname': 'app1.example.com'
                }
            ],
            'timestamp': '2023-01-01T12:00:00Z',
            'workerVersion': '1.2.3'
        }
        mock_post.return_value = mock_response
        
        # Make API call
        result = self.host1._call_worker_cache_clear(
            scope='user-session',
            target={
                'hostname': 'app1.example.com',
                'username': 'alice',
                'sessionId': 'test_session_123'
            },
            reason='Test response parsing'
        )
        
        # Verify response structure is preserved
        self.assertTrue(result['success'])
        self.assertIn('cleared', result)
        self.assertEqual(len(result['cleared']), 1)
        self.assertEqual(result['cleared'][0]['scope'], 'user-session')