# -*- coding: utf-8 -*-
"""Test CLI commands for cache clearing"""

from odoo.tests import TransactionCase
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from io import StringIO
import sys


class TestCLICacheCommands(TransactionCase):
    """Test CLI commands for cache clearing functionality"""
    
    def setUp(self):
        super().setUp()
        self.User = self.env['sunray.user']
        self.Host = self.env['sunray.host']
        self.Session = self.env['sunray.session']
        self.ApiKey = self.env['sunray.api.key']
        self.Worker = self.env['sunray.worker']
        
        # Create CLI handler
        from odoo.addons.sunray_core.cli.sunray_cli import SunrayCLIHandler
        self.cli_handler = SunrayCLIHandler()
        
        # Create test infrastructure
        self.api_key = self.ApiKey.create({
            'name': 'test_worker_key',
            'is_active': True,
            'scopes': 'config:read'
        })
        
        self.worker = self.Worker.create({
            'name': 'Test Worker',
            'worker_type': 'cloudflare',
            'worker_url': 'https://test-worker.example.com',
            'api_key_id': self.api_key.id,
            'is_active': True
        })
        
        self.host = self.Host.create({
            'domain': 'test.example.com',
            'sunray_worker_id': self.worker.id,
            'backend_url': 'http://backend.example.com',
            'is_active': True
        })
        
        self.user = self.User.create({
            'username': 'testuser',
            'email': 'test@example.com',
            'is_active': True,
            'host_ids': [(4, self.host.id)]
        })
        
        self.session = self.Session.create({
            'session_id': 'test_session_123',
            'user_id': self.user.id,
            'host_id': self.host.id,
            'is_active': True,
            'created_ip': '192.168.1.100',
            'expires_at': datetime.now() + timedelta(hours=1)
        })

    def _create_mock_args(self, **kwargs):
        """Helper to create mock argument objects"""
        from argparse import Namespace
        return Namespace(**kwargs)

    def _capture_output(self, func, *args, **kwargs):
        """Helper to capture print output from CLI commands"""
        old_stdout = sys.stdout
        sys.stdout = captured_output = StringIO()
        try:
            func(*args, **kwargs)
            return captured_output.getvalue()
        finally:
            sys.stdout = old_stdout

    @patch('requests.post')
    def test_cli_session_revoke_user_host(self, mock_post):
        """Test CLI: srctl session revoke-user-host"""
        # Configure mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'success': True}
        mock_post.return_value = mock_response
        
        # Create mock args
        args = self._create_mock_args(
            command='session',
            action='revoke-user-host',
            username='testuser',
            domain='test.example.com',
            reason='CLI test revocation'
        )
        
        # Capture output
        output = self._capture_output(
            self.cli_handler._handle_session,
            self.env,
            args
        )
        
        # Verify success message
        self.assertIn('Sessions revoked for user testuser on host test.example.com', output)
        
        # Verify API call was made
        self.assertTrue(mock_post.called)

    @patch('requests.post')
    def test_cli_session_revoke_user_worker(self, mock_post):
        """Test CLI: srctl session revoke-user-worker"""
        # Configure mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'success': True}
        mock_post.return_value = mock_response
        
        # Create mock args
        args = self._create_mock_args(
            command='session',
            action='revoke-user-worker',
            username='testuser',
            worker_name='Test Worker',
            reason='CLI worker revocation'
        )
        
        # Capture output
        output = self._capture_output(
            self.cli_handler._handle_session,
            self.env,
            args
        )
        
        # Verify success message
        self.assertIn('Sessions revoked for user testuser on worker Test Worker', output)

    @patch('requests.post')
    def test_cli_session_clear_host(self, mock_post):
        """Test CLI: srctl session clear-host"""
        # Configure mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'success': True}
        mock_post.return_value = mock_response
        
        # Create mock args
        args = self._create_mock_args(
            command='session',
            action='clear-host',
            domain='test.example.com',
            reason='CLI host clear'
        )
        
        # Capture output
        output = self._capture_output(
            self.cli_handler._handle_session,
            self.env,
            args
        )
        
        # Verify success message
        self.assertIn('All sessions cleared on host test.example.com', output)

    @patch('requests.post')
    def test_cli_host_clear_sessions(self, mock_post):
        """Test CLI: srctl host clear-sessions"""
        # Configure mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'success': True}
        mock_post.return_value = mock_response
        
        # Create mock args
        args = self._create_mock_args(
            command='host',
            action='clear-sessions',
            domain='test.example.com',
            reason='CLI host clear sessions'
        )
        
        # Capture output
        output = self._capture_output(
            self.cli_handler._handle_host,
            self.env,
            args
        )
        
        # Verify success message
        self.assertIn("All sessions cleared on host 'test.example.com'", output)

    @patch('requests.post')
    def test_cli_user_revoke_sessions_host(self, mock_post):
        """Test CLI: srctl user revoke-sessions-host"""
        # Configure mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'success': True}
        mock_post.return_value = mock_response
        
        # Create mock args
        args = self._create_mock_args(
            command='user',
            action='revoke-sessions-host',
            username='testuser',
            domain='test.example.com',
            reason='CLI user host revocation'
        )
        
        # Capture output
        output = self._capture_output(
            self.cli_handler._handle_user,
            self.env,
            args
        )
        
        # Verify success message
        self.assertIn("Sessions revoked for user 'testuser' on host 'test.example.com'", output)

    @patch('requests.post')
    def test_cli_user_revoke_sessions_worker(self, mock_post):
        """Test CLI: srctl user revoke-sessions-worker"""
        # Configure mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'success': True}
        mock_post.return_value = mock_response
        
        # Create mock args
        args = self._create_mock_args(
            command='user',
            action='revoke-sessions-worker',
            username='testuser',
            worker_name='Test Worker',
            reason='CLI user worker revocation'
        )
        
        # Capture output
        output = self._capture_output(
            self.cli_handler._handle_user,
            self.env,
            args
        )
        
        # Verify success message
        self.assertIn("Sessions revoked for user 'testuser' on worker 'Test Worker'", output)

    @patch('requests.post')
    def test_cli_worker_force_config_refresh(self, mock_post):
        """Test CLI: srctl worker force-config-refresh"""
        # Configure mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'success': True}
        mock_post.return_value = mock_response
        
        # Create mock args
        args = self._create_mock_args(
            command='worker',
            action='force-config-refresh',
            name='Test Worker',
            reason='CLI config refresh'
        )
        
        # Capture output
        output = self._capture_output(
            self.cli_handler._handle_worker,
            self.env,
            args
        )
        
        # Verify success message
        self.assertIn("Configuration refresh triggered for worker 'Test Worker'", output)

    @patch('requests.post')
    def test_cli_worker_clear_all_sessions(self, mock_post):
        """Test CLI: srctl worker clear-all-sessions --confirm"""
        # Configure mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'success': True}
        mock_post.return_value = mock_response
        
        # Create mock args with confirmation
        args = self._create_mock_args(
            command='worker',
            action='clear-all-sessions',
            name='Test Worker',
            confirm=True,
            reason='CLI nuclear clear'
        )
        
        # Capture output
        output = self._capture_output(
            self.cli_handler._handle_worker,
            self.env,
            args
        )
        
        # Verify nuclear clear message
        self.assertIn("NUCLEAR CLEAR COMPLETE for worker 'Test Worker'", output)

    def test_cli_worker_clear_all_sessions_no_confirm(self):
        """Test CLI: srctl worker clear-all-sessions without --confirm flag"""
        # Create mock args without confirmation
        args = self._create_mock_args(
            command='worker',
            action='clear-all-sessions',
            name='Test Worker',
            confirm=False,
            reason='CLI nuclear clear'
        )
        
        # Capture output
        output = self._capture_output(
            self.cli_handler._handle_worker,
            self.env,
            args
        )
        
        # Should show error message requiring confirmation
        self.assertIn('--confirm flag is required', output)
        self.assertIn('dangerous operation', output)

    def test_cli_session_revoke_user_not_found(self):
        """Test CLI commands with non-existent user"""
        args = self._create_mock_args(
            command='session',
            action='revoke-user-host',
            username='nonexistent',
            domain='test.example.com',
            reason='Test'
        )
        
        # Capture output
        output = self._capture_output(
            self.cli_handler._handle_session,
            self.env,
            args
        )
        
        # Should show user not found message
        self.assertIn("User 'nonexistent' not found", output)

    def test_cli_session_revoke_host_not_found(self):
        """Test CLI commands with non-existent host"""
        args = self._create_mock_args(
            command='session',
            action='revoke-user-host',
            username='testuser',
            domain='nonexistent.example.com',
            reason='Test'
        )
        
        # Capture output
        output = self._capture_output(
            self.cli_handler._handle_session,
            self.env,
            args
        )
        
        # Should show host not found message
        self.assertIn("Host 'nonexistent.example.com' not found", output)

    def test_cli_worker_not_found(self):
        """Test CLI commands with non-existent worker"""
        args = self._create_mock_args(
            command='worker',
            action='force-config-refresh',
            name='Nonexistent Worker',
            reason='Test'
        )
        
        # Capture output
        output = self._capture_output(
            self.cli_handler._handle_worker,
            self.env,
            args
        )
        
        # Should show worker not found message
        self.assertIn("Worker 'Nonexistent Worker' not found", output)

    def test_cli_session_revoke_error_handling(self):
        """Test CLI commands handle errors gracefully"""
        # Create mock args that will cause an error
        args = self._create_mock_args(
            command='session',
            action='revoke-user-host',
            username='testuser',
            domain='test.example.com',
            reason='Test error'
        )
        
        # Mock the user action to raise an exception
        with patch.object(self.user, 'action_revoke_sessions_on_host', side_effect=Exception('Test error')):
            # Capture output
            output = self._capture_output(
                self.cli_handler._handle_session,
                self.env,
                args
            )
            
            # Should show error message
            self.assertIn('Error revoking sessions: Test error', output)

    def test_cli_reason_parameter_handling(self):
        """Test that reason parameters are properly handled"""
        # Test with reason provided
        with patch('requests.post') as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {'success': True}
            mock_post.return_value = mock_response
            
            args = self._create_mock_args(
                command='session',
                action='revoke-user-host',
                username='testuser',
                domain='test.example.com',
                reason='Custom reason for testing'
            )
            
            # Capture output
            output = self._capture_output(
                self.cli_handler._handle_session,
                self.env,
                args
            )
            
            # Should include the reason in output
            self.assertIn('Reason: Custom reason for testing', output)

    def test_cli_reason_parameter_optional(self):
        """Test that reason parameters are optional"""
        # Test without reason provided (should still work)
        with patch('requests.post') as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {'success': True}
            mock_post.return_value = mock_response
            
            args = self._create_mock_args(
                command='session',
                action='revoke-user-host',
                username='testuser',
                domain='test.example.com',
                reason=None  # No reason provided
            )
            
            # Capture output
            output = self._capture_output(
                self.cli_handler._handle_session,
                self.env,
                args
            )
            
            # Should work without reason
            self.assertIn('Sessions revoked', output)

    def test_cli_all_new_session_commands(self):
        """Test all new session-related CLI commands exist and work"""
        session_commands = [
            'revoke-user-host',
            'revoke-user-worker', 
            'clear-host'
        ]
        
        for command in session_commands:
            with self.subTest(command=command):
                with patch('requests.post') as mock_post:
                    mock_response = MagicMock()
                    mock_response.status_code = 200
                    mock_response.json.return_value = {'success': True}
                    mock_post.return_value = mock_response
                    
                    # Create appropriate args for each command
                    if command == 'revoke-user-host':
                        args = self._create_mock_args(
                            command='session',
                            action=command,
                            username='testuser',
                            domain='test.example.com'
                        )
                    elif command == 'revoke-user-worker':
                        args = self._create_mock_args(
                            command='session',
                            action=command,
                            username='testuser',
                            worker_name='Test Worker'
                        )
                    elif command == 'clear-host':
                        args = self._create_mock_args(
                            command='session',
                            action=command,
                            domain='test.example.com'
                        )
                    
                    # Should not raise any exceptions
                    try:
                        self.cli_handler._handle_session(self.env, args)
                    except Exception as e:
                        self.fail(f"CLI command {command} raised exception: {e}")

    def test_cli_all_new_user_commands(self):
        """Test all new user-related CLI commands exist and work"""
        user_commands = [
            'revoke-sessions-host',
            'revoke-sessions-worker'
        ]
        
        for command in user_commands:
            with self.subTest(command=command):
                with patch('requests.post') as mock_post:
                    mock_response = MagicMock()
                    mock_response.status_code = 200
                    mock_response.json.return_value = {'success': True}
                    mock_post.return_value = mock_response
                    
                    # Create appropriate args
                    if command == 'revoke-sessions-host':
                        args = self._create_mock_args(
                            command='user',
                            action=command,
                            username='testuser',
                            domain='test.example.com'
                        )
                    elif command == 'revoke-sessions-worker':
                        args = self._create_mock_args(
                            command='user',
                            action=command,
                            username='testuser',
                            worker_name='Test Worker'
                        )
                    
                    # Should not raise any exceptions
                    try:
                        self.cli_handler._handle_user(self.env, args)
                    except Exception as e:
                        self.fail(f"CLI command {command} raised exception: {e}")

    def test_cli_all_new_worker_commands(self):
        """Test all new worker-related CLI commands exist and work"""
        worker_commands = [
            'force-config-refresh',
            'clear-all-sessions'
        ]
        
        for command in worker_commands:
            with self.subTest(command=command):
                with patch('requests.post') as mock_post:
                    mock_response = MagicMock()
                    mock_response.status_code = 200
                    mock_response.json.return_value = {'success': True}
                    mock_post.return_value = mock_response
                    
                    # Create appropriate args
                    if command == 'force-config-refresh':
                        args = self._create_mock_args(
                            command='worker',
                            action=command,
                            name='Test Worker'
                        )
                    elif command == 'clear-all-sessions':
                        args = self._create_mock_args(
                            command='worker',
                            action=command,
                            name='Test Worker',
                            confirm=True  # Required for nuclear option
                        )
                    
                    # Should not raise any exceptions
                    try:
                        self.cli_handler._handle_worker(self.env, args)
                    except Exception as e:
                        self.fail(f"CLI command {command} raised exception: {e}")

    def test_cli_host_clear_sessions_command(self):
        """Test new host clear-sessions CLI command"""
        with patch('requests.post') as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {'success': True}
            mock_post.return_value = mock_response
            
            args = self._create_mock_args(
                command='host',
                action='clear-sessions',
                domain='test.example.com'
            )
            
            # Should not raise any exceptions
            try:
                self.cli_handler._handle_host(self.env, args)
            except Exception as e:
                self.fail(f"CLI command host clear-sessions raised exception: {e}")

    def test_cli_command_consistency(self):
        """Test that CLI commands are consistent with UI actions"""
        # CLI and UI should call the same underlying methods
        # This ensures consistency between interfaces
        
        with patch.object(self.user, 'action_revoke_sessions_on_host') as mock_method:
            mock_method.return_value = {
                'type': 'ir.actions.client',
                'params': {'message': 'Test'}
            }
            
            args = self._create_mock_args(
                command='session',
                action='revoke-user-host',
                username='testuser',
                domain='test.example.com'
            )
            
            # Call CLI handler
            self.cli_handler._handle_session(self.env, args)
            
            # Should have called the same method as UI
            mock_method.assert_called_once_with(self.host.id)