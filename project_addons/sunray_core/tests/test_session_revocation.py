# -*- coding: utf-8 -*-
"""Test session revocation functionality"""

from odoo.tests import TransactionCase
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
import json
from odoo.exceptions import UserError


class TestSessionRevocation(TransactionCase):
    """Test session revocation and bulk clearing functionality"""
    
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
        
        # Create test session
        self.session = self.Session.create({
            'session_id': 'test_session_123',
            'user_id': self.user.id,
            'host_id': self.host.id,
            'is_active': True,
            'created_ip': '192.168.1.100',
            'last_ip': '192.168.1.100',
            'expires_at': datetime.now() + timedelta(hours=1)
        })

    @patch('requests.post')
    def test_individual_session_revoke(self, mock_post):
        """Test revoking a single session via UI action"""
        # Configure mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'success': True,
            'cleared': ['user-session']
        }
        mock_post.return_value = mock_response
        
        # Call the session revoke action
        result = self.session.action_revoke_session('Test revocation')
        
        # Verify session was marked as revoked locally
        self.assertFalse(self.session.is_active)
        self.assertTrue(self.session.revoked)
        self.assertEqual(self.session.revoked_reason, 'Test revocation')
        
        # Verify API call was made
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        
        # Check URL
        self.assertEqual(
            call_args[0][0],
            'https://test.example.com/sunray-wrkr/v1/cache/clear'
        )
        
        # Check payload
        payload = call_args[1]['json']
        self.assertEqual(payload['scope'], 'user-session')
        self.assertEqual(payload['target'], {
            'hostname': 'test.example.com',
            'username': 'testuser',
            'sessionId': 'test_session_123'
        })
        self.assertIn('Session revocation: Test revocation', payload['reason'])
        
        # Check return value
        self.assertEqual(result['type'], 'ir.actions.client')
        self.assertIn('revoked successfully', result['params']['message'])

    @patch('requests.post')
    def test_revoke_user_sessions_on_host(self, mock_post):
        """Test revoking all sessions for user on specific host"""
        # Create additional session for same user on same host
        session2 = self.Session.create({
            'session_id': 'test_session_456',
            'user_id': self.user.id,
            'host_id': self.host.id,
            'is_active': True,
            'created_ip': '192.168.1.101',
            'expires_at': datetime.now() + timedelta(hours=1)
        })
        
        # Configure mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'success': True,
            'cleared': ['user-protectedhost']
        }
        mock_post.return_value = mock_response
        
        # Call the user revoke action
        result = self.user.action_revoke_sessions_on_host(self.host.id)
        
        # Verify both sessions were marked as revoked
        self.assertFalse(self.session.is_active)
        self.assertFalse(session2.is_active)
        self.assertTrue(self.session.revoked)
        self.assertTrue(session2.revoked)
        
        # Check payload
        payload = mock_post.call_args[1]['json']
        self.assertEqual(payload['scope'], 'user-protectedhost')
        self.assertEqual(payload['target'], {
            'username': 'testuser',
            'hostname': 'test.example.com'
        })
        
        # Check return value
        self.assertEqual(result['type'], 'ir.actions.client')
        self.assertIn('2 session(s)', result['params']['message'])

    @patch('requests.post')
    def test_revoke_user_sessions_on_worker(self, mock_post):
        """Test revoking all sessions for user across worker"""
        # Create additional host on same worker
        host2 = self.Host.create({
            'domain': 'test2.example.com',
            'sunray_worker_id': self.worker.id,
            'backend_url': 'http://backend2.example.com',
            'is_active': True
        })
        
        # Create session on second host
        session2 = self.Session.create({
            'session_id': 'test_session_789',
            'user_id': self.user.id,
            'host_id': host2.id,
            'is_active': True,
            'created_ip': '192.168.1.102',
            'expires_at': datetime.now() + timedelta(hours=1)
        })
        
        # Configure mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'success': True,
            'cleared': ['user-worker']
        }
        mock_post.return_value = mock_response
        
        # Call the user revoke on worker action
        result = self.user.action_revoke_sessions_on_worker(self.worker.id)
        
        # Verify both sessions were marked as revoked
        self.assertFalse(self.session.is_active)
        self.assertFalse(session2.is_active)
        
        # Check payload
        payload = mock_post.call_args[1]['json']
        self.assertEqual(payload['scope'], 'user-worker')
        self.assertEqual(payload['target'], {'username': 'testuser'})
        
        # Check return value
        self.assertEqual(result['type'], 'ir.actions.client')
        self.assertIn('2 session(s)', result['params']['message'])

    @patch('requests.post')
    def test_clear_all_sessions_on_host(self, mock_post):
        """Test clearing all sessions on specific host (all users)"""
        # Create another user and session on same host
        user2 = self.User.create({
            'username': 'testuser2',
            'email': 'test2@example.com',
            'is_active': True,
            'host_ids': [(4, self.host.id)]
        })
        
        session2 = self.Session.create({
            'session_id': 'test_session_user2',
            'user_id': user2.id,
            'host_id': self.host.id,
            'is_active': True,
            'created_ip': '192.168.1.103',
            'expires_at': datetime.now() + timedelta(hours=1)
        })
        
        # Configure mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'success': True,
            'cleared': ['allusers-protectedhost']
        }
        mock_post.return_value = mock_response
        
        # Call the host clear all sessions action
        result = self.host.action_clear_all_sessions()
        
        # Verify both sessions were marked as revoked
        self.assertFalse(self.session.is_active)
        self.assertFalse(session2.is_active)
        self.assertTrue(self.session.revoked)
        self.assertTrue(session2.revoked)
        
        # Check payload
        payload = mock_post.call_args[1]['json']
        self.assertEqual(payload['scope'], 'allusers-protectedhost')
        self.assertEqual(payload['target'], {'hostname': 'test.example.com'})
        
        # Check return value
        self.assertEqual(result['type'], 'ir.actions.client')
        self.assertIn('2 active session(s)', result['params']['message'])

    @patch('requests.post')
    def test_nuclear_clear_all_sessions_on_worker(self, mock_post):
        """Test nuclear option: clearing all sessions across worker"""
        # Create additional hosts and sessions
        host2 = self.Host.create({
            'domain': 'test2.example.com',
            'sunray_worker_id': self.worker.id,
            'backend_url': 'http://backend2.example.com',
            'is_active': True
        })
        
        user2 = self.User.create({
            'username': 'testuser2',
            'email': 'test2@example.com',
            'is_active': True,
            'host_ids': [(4, host2.id)]
        })
        
        session2 = self.Session.create({
            'session_id': 'test_session_nuclear',
            'user_id': user2.id,
            'host_id': host2.id,
            'is_active': True,
            'created_ip': '192.168.1.104',
            'expires_at': datetime.now() + timedelta(hours=1)
        })
        
        # Configure mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'success': True,
            'cleared': ['allusers-worker']
        }
        mock_post.return_value = mock_response
        
        # Call the worker nuclear clear action
        result = self.worker.action_clear_all_sessions_nuclear()
        
        # Verify all sessions were marked as revoked
        self.assertFalse(self.session.is_active)
        self.assertFalse(session2.is_active)
        self.assertTrue(self.session.revoked)
        self.assertTrue(session2.revoked)
        
        # Check revocation reason contains "NUCLEAR"
        self.assertIn('NUCLEAR', self.session.revoked_reason)
        self.assertIn('NUCLEAR', session2.revoked_reason)
        
        # Check payload
        payload = mock_post.call_args[1]['json']
        self.assertEqual(payload['scope'], 'allusers-worker')
        self.assertEqual(payload['target'], {})  # No target for allusers-worker
        self.assertIn('NUCLEAR', payload['reason'])
        
        # Check return value
        self.assertEqual(result['type'], 'ir.actions.client')
        self.assertIn('NUCLEAR CLEAR COMPLETE', result['params']['title'])
        
        # Check audit log was created with critical severity
        audit_log = self.env['sunray.audit.log'].search([
            ('event_type', '=', 'cache.nuclear_clear'),
            ('severity', '=', 'critical')
        ], limit=1)
        self.assertTrue(audit_log)

    def test_revoke_no_active_sessions(self):
        """Test revoke operations when no active sessions exist"""
        # Make session inactive
        self.session.is_active = False
        
        # Test individual session revoke
        result = self.session.action_revoke_session('Test')
        self.assertEqual(result['params']['type'], 'warning')
        self.assertIn('already inactive', result['params']['message'])
        
        # Test user revoke on host
        result = self.user.action_revoke_sessions_on_host(self.host.id)
        self.assertEqual(result['params']['type'], 'info')
        self.assertIn('no active sessions', result['params']['message'])

    def test_revoke_unbound_host_error(self):
        """Test revoke operations fail when host has no worker"""
        # Remove worker from host
        self.host.sunray_worker_id = False
        
        # Test should raise UserError
        with self.assertRaises(UserError) as cm:
            self.host.action_clear_all_sessions()
        
        self.assertIn('not bound to a worker', str(cm.exception))

    def test_revoke_inactive_api_key_error(self):
        """Test revoke operations fail when worker has inactive API key"""
        # Make API key inactive
        self.api_key.is_active = False
        
        # Test should raise UserError
        with self.assertRaises(UserError) as cm:
            self.host.action_clear_all_sessions()
        
        self.assertIn('No active API key', str(cm.exception))

    @patch('requests.post')
    def test_revoke_network_error_handling(self, mock_post):
        """Test error handling when worker API call fails"""
        # Configure mock to raise exception
        mock_post.side_effect = Exception('Network timeout')
        
        # Test individual session revoke
        result = self.session.action_revoke_session('Test')
        
        # Session should still be revoked locally
        self.assertFalse(self.session.is_active)
        self.assertTrue(self.session.revoked)
        
        # Should return success notification (graceful degradation)
        self.assertEqual(result['type'], 'ir.actions.client')
        
        # Error should be logged in audit log
        audit_log = self.env['sunray.audit.log'].search([
            ('event_type', '=', 'cache.clear_failed'),
            ('severity', '=', 'warning')
        ], limit=1)
        self.assertTrue(audit_log)

    def test_session_revoke_wizard_context(self):
        """Test session revoke wizard context setup"""
        result = self.session.action_open_revoke_wizard()
        
        self.assertEqual(result['type'], 'ir.actions.act_window')
        self.assertEqual(result['res_model'], 'sunray.session.revoke.wizard')
        self.assertEqual(result['view_mode'], 'form')
        self.assertEqual(result['target'], 'new')
        self.assertEqual(result['context']['default_session_id'], self.session.id)

    def test_computed_fields_for_ui(self):
        """Test computed fields used in UI displays"""
        # Test active_session_count on host
        count = self.host.active_session_count
        self.assertEqual(count, 1)
        
        # Test worker_ids computed field on user
        workers = self.user.worker_ids
        self.assertIn(self.worker, workers)
        
        # Create inactive session, should not affect count
        self.Session.create({
            'session_id': 'inactive_session',
            'user_id': self.user.id,
            'host_id': self.host.id,
            'is_active': False,
            'expires_at': datetime.now() + timedelta(hours=1)
        })
        
        # Count should still be 1
        self.assertEqual(self.host.active_session_count, 1)