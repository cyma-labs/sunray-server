# -*- coding: utf-8 -*-
"""Worker-wide cache clear scopes say which host carries the call.

Section 6.4 of "Sunray Worker FastAPI : risque d'intrusion et de rebond": the
choice used to be an unexplained host_ids[0].
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from odoo.exceptions import UserError
from odoo.tests import TransactionCase


class TestWorkerCacheClearHost(TransactionCase):
    """Worker-wide scopes say which host carries the call."""

    def setUp(self):
        super().setUp()
        self.api_key_obj = self.env['sunray.api.key'].create({
            'name': 'host_choice_worker_key',
            'is_active': True,
            'scopes': 'config:read',
        })
        self.worker_obj = self.env['sunray.worker'].create({
            'name': 'Host Choice Worker',
            'worker_type': 'fastapi',
            'api_key_id': self.api_key_obj.id,
            'is_active': True,
        })

    def _host(self, domain, is_active=True):
        return self.env['sunray.host'].create({
            'domain': domain,
            'sunray_worker_id': self.worker_obj.id,
            'backend_url': f'http://{domain}',
            'is_active': is_active,
        })

    def _mock_answer(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'success': True, 'cleared': ['1 item cleared']}
        mock_post.return_value = mock_response

    @patch('requests.post')
    def test_worker_scope_picks_first_active_host(self, mock_post):
        self._mock_answer(mock_post)
        self._host('first-inactive.example.com', is_active=False)
        self._host('second-active.example.com')

        self.worker_obj._call_cache_clear(scope='config', target={})

        self.assertEqual(
            mock_post.call_args.args[0],
            'https://second-active.example.com/sunray-wrkr/v1/cache/clear',
        )

    @patch('requests.post')
    def test_worker_scope_falls_back_to_first_bound_host(self, mock_post):
        self._mock_answer(mock_post)
        self._host('only-inactive.example.com', is_active=False)

        self.worker_obj._call_cache_clear(scope='config', target={})

        self.assertEqual(
            mock_post.call_args.args[0],
            'https://only-inactive.example.com/sunray-wrkr/v1/cache/clear',
        )

    @patch('requests.post')
    def test_worker_scope_without_host_raises(self, mock_post):
        with self.assertRaises(UserError) as cm:
            self.worker_obj._call_cache_clear(scope='config', target={})

        self.assertIn('protects no host', str(cm.exception))
        self.assertFalse(mock_post.called)

    @patch('requests.post')
    def test_user_revoke_on_worker_uses_worker_host(self, mock_post):
        self._mock_answer(mock_post)
        self._host('inactive-first.example.com', is_active=False)
        session_host_obj = self._host('session-host.example.com')
        user_obj = self.env['sunray.user'].create({
            'username': 'host-choice-user',
            'email': 'host-choice-user@example.com',
            'is_active': True,
            'host_ids': [(4, session_host_obj.id)],
        })
        self.env['sunray.session'].create({
            'session_id': 'host-choice-session',
            'user_id': user_obj.id,
            'host_id': session_host_obj.id,
            'is_active': True,
            'created_ip': '192.0.2.2',
            'expires_at': datetime.now() + timedelta(hours=1),
        })

        user_obj.action_revoke_sessions_on_worker(self.worker_obj.id)

        payload = mock_post.call_args.kwargs['json']
        self.assertEqual(payload['scope'], 'user-worker')
        self.assertEqual(payload['target'], {'username': 'host-choice-user'})
        self.assertEqual(
            mock_post.call_args.args[0],
            'https://session-host.example.com/sunray-wrkr/v1/cache/clear',
        )
