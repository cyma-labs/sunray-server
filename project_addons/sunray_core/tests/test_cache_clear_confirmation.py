# -*- coding: utf-8 -*-
"""A worker cache clear only succeeds when the worker confirms it.

Section 6.4 of "Sunray Worker FastAPI : risque d'intrusion et de rebond": a
worker that ignores /cache/clear still answers 200, and the server used to
record that as a success. On a session scope, a 200 that confirms nothing is
now a failure the admin sees, audited outside the rolled-back transaction.
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from odoo.tests import TransactionCase

from odoo.addons.sunray_core.models.sunray_host import (
    SESSION_CLEAR_SCOPES,
    WorkerCacheClearError,
)


class TestCacheClearConfirmation(TransactionCase):

    def setUp(self):
        super().setUp()
        # Failures are audited through a separate cursor; test mode keeps that
        # cursor inside the test transaction.
        self.registry.enter_test_mode(self.cr)
        self.addCleanup(self.registry.leave_test_mode)

        self.AuditLog = self.env['sunray.audit.log']
        self.api_key_obj = self.env['sunray.api.key'].create({
            'name': 'confirmation_worker_key',
            'is_active': True,
        })
        self.worker_obj = self.env['sunray.worker'].create({
            'name': 'Confirmation Worker',
            'api_key_id': self.api_key_obj.id,
        })
        self.host_obj = self.env['sunray.host'].create({
            'domain': 'confirm.example.com',
            'sunray_worker_id': self.worker_obj.id,
            'backend_url': 'http://backend.example.com',
        })

    def _mock_answer(self, mock_post, body):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = body
        mock_post.return_value = mock_response

    def _audit_objs(self, event_type):
        return self.AuditLog.search([('event_type', '=', event_type)]).filtered(
            lambda log_obj: log_obj.get_details_dict().get('host') == self.host_obj.domain
        )

    def _clear_expecting_failure(self, scope):
        """Call the worker and return the raised error.

        Deliberately not self.assertRaises: Odoo wraps it in a savepoint that
        would roll the audit line back and hide what this test looks at.
        """
        try:
            self.host_obj._call_worker_cache_clear(scope=scope, target={}, reason='test')
        except WorkerCacheClearError as error:
            return error
        self.fail(f"scope {scope}: a 200 confirming nothing was taken for a success")

    @patch('requests.post')
    def test_empty_cleared_on_session_scope_is_failure(self, mock_post):
        for body in ({'success': True, 'cleared': []}, {'success': True}):
            for scope in sorted(SESSION_CLEAR_SCOPES):
                with self.subTest(scope=scope, body=body):
                    self._mock_answer(mock_post, body)
                    before = len(self._audit_objs('cache.clear_failed'))

                    error = self._clear_expecting_failure(scope)

                    self.assertIn('did not confirm', str(error))
                    failed_objs = self._audit_objs('cache.clear_failed')
                    self.assertEqual(len(failed_objs), before + 1)
                    details = failed_objs.sorted('id')[-1].get_details_dict()
                    self.assertEqual(details['failure'], 'worker_confirmed_nothing')
                    self.assertEqual(details['scope'], scope)
                    self.assertEqual(details['response'], body)
        self.assertFalse(self._audit_objs('cache.cleared'))

    @patch('requests.post')
    def test_success_false_is_failure(self, mock_post):
        # The shape an older FastAPI worker returns, or any error it dresses as 200
        self._mock_answer(mock_post, {'success': False, 'cleared': ['nothing done']})

        self._clear_expecting_failure('user-session')

        self.assertFalse(self._audit_objs('cache.cleared'))

    @patch('requests.post')
    def test_non_object_answer_is_failure(self, mock_post):
        self._mock_answer(mock_post, ['session deleted'])

        self._clear_expecting_failure('user-worker')

    @patch('requests.post')
    def test_empty_cleared_on_config_scopes_is_success(self, mock_post):
        # An older FastAPI worker answers config scopes without `cleared` and
        # does clear the config: that is not a revocation left undone.
        for scope in ('host', 'config'):
            with self.subTest(scope=scope):
                self._mock_answer(mock_post, {'success': True, 'message': 'cleared'})

                result = self.host_obj._call_worker_cache_clear(scope=scope, target={})

                self.assertTrue(result['success'])
        self.assertEqual(len(self._audit_objs('cache.cleared')), 2)
        self.assertFalse(self._audit_objs('cache.clear_failed'))

    @patch('requests.post')
    def test_confirmed_session_scope_is_success(self, mock_post):
        self._mock_answer(mock_post, {'success': True, 'cleared': ['session abc deleted']})

        self.host_obj._call_worker_cache_clear(
            scope='user-session',
            target={'hostname': self.host_obj.domain, 'username': 'alice', 'sessionId': 'abc'},
        )

        cleared_objs = self._audit_objs('cache.cleared')
        self.assertEqual(len(cleared_objs), 1)
        self.assertEqual(
            cleared_objs.get_details_dict()['cleared_items'], ['session abc deleted']
        )

    @patch('requests.post')
    def test_failure_audit_written_through_separate_cursor(self, mock_post):
        # Written through self.env, the line would be rolled back with the
        # request as soon as the UserError propagates.
        self._mock_answer(mock_post, {'success': True, 'cleared': []})

        with patch.object(
            type(self.registry), 'cursor', autospec=True,
            side_effect=type(self.registry).cursor,
        ) as cursor_spy:
            self._clear_expecting_failure('allusers-protectedhost')

        self.assertTrue(cursor_spy.called)

    @patch('requests.post')
    def test_request_failure_is_audited_once(self, mock_post):
        from requests.exceptions import ConnectionError as RequestsConnectionError
        mock_post.side_effect = RequestsConnectionError('worker unreachable')

        error = self._clear_expecting_failure('user-session')

        self.assertIn('Failed to clear worker cache', str(error))
        failed_objs = self._audit_objs('cache.clear_failed')
        self.assertEqual(len(failed_objs), 1)
        self.assertEqual(failed_objs.get_details_dict()['failure'], 'request_failed')

    @patch('requests.post')
    def test_session_revoke_does_not_report_success_nor_audit_twice(self, mock_post):
        self._mock_answer(mock_post, {'success': True, 'cleared': []})
        user_obj = self.env['sunray.user'].create({
            'username': 'confirm-user',
            'email': 'confirm-user@example.com',
        })
        session_obj = self.env['sunray.session'].create({
            'session_id': 'confirm-session',
            'user_id': user_obj.id,
            'host_id': self.host_obj.id,
            'is_active': True,
            'expires_at': datetime.now() + timedelta(hours=1),
        })

        with patch.object(type(self.env.user), 'ik_notify') as notify_spy:
            session_obj.action_revoke_session('test')

        self.assertTrue(session_obj.revoked, "the local revocation must stand")
        self.assertEqual(notify_spy.call_args.args[0], 'warning')
        # Audited once, by _call_worker_cache_clear - not again by the caller,
        # whose own line would carry the session_id.
        self.assertEqual(len(self._audit_objs('cache.clear_failed')), 1)
        caller_objs = self.AuditLog.search([('event_type', '=', 'cache.clear_failed')]).filtered(
            lambda log_obj: log_obj.get_details_dict().get('session_id') == 'confirm-session'
        )
        self.assertFalse(caller_objs)
