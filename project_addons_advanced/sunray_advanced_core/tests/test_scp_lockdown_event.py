# -*- coding: utf-8 -*-
"""Test SCP sync: lockdown audit event, username collision, transaction recovery."""

from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.tests import TransactionCase


class TestScpUnreachableLockdownEvent(TransactionCase):
    """Verify that exceeding sunray.auto_register_scp_cache_duration_s
    while the SCP is unreachable emits a single critical audit event
    and locks all managed hosts."""

    def setUp(self):
        super().setUp()
        self.AuditLog = self.env['sunray.audit.log']
        self.Host = self.env['sunray.host']
        self.Scp = self.env['sunray.configuration_proxy']

        self.env['ir.config_parameter'].sudo().set_param(
            'sunray.auto_register_scp_cache_duration_s', '60'
        )

        self.scp = self.Scp.create({
            'name': 'TestSCP',
            'url': 'https://invalid.test.example/inouk-scp/v1/',
            'is_active': True,
        })

        self.host_a = self.Host.create({
            'domain': 'a.test.example',
            'backend_url': 'https://a.test.example/',
            'scp_id': self.scp.id,
            'scp_sync_enabled': True,
        })
        self.host_b = self.Host.create({
            'domain': 'b.test.example',
            'backend_url': 'https://b.test.example/',
            'scp_id': self.scp.id,
            'scp_sync_enabled': True,
        })

    def _trigger_failed_sync(self):
        with patch.object(
            type(self.scp),
            'call_scp',
            side_effect=RuntimeError('simulated SCP unreachable'),
        ):
            self.scp.sync_scp_job()

    def test_lockdown_event_emitted_when_threshold_exceeded(self):
        """SCP failing past threshold → 1 audit event + hosts locked."""
        self.scp.last_sync_ts = fields.Datetime.now() - timedelta(seconds=300)

        events_before = self.AuditLog.search_count([
            ('event_type', '=', 'scp.unreachable_lockdown')
        ])

        self._trigger_failed_sync()

        events = self.AuditLog.search([
            ('event_type', '=', 'scp.unreachable_lockdown')
        ], order='id desc')
        self.assertEqual(
            len(events) - events_before, 1,
            'Exactly one scp.unreachable_lockdown event must be emitted'
        )

        event = events[0]
        self.assertEqual(event.severity, 'critical')
        self.assertEqual(event.event_source, 'system')

        details = event.get_details_dict()
        self.assertEqual(details['scp_name'], 'TestSCP')
        self.assertEqual(details['scp_id'], self.scp.id)
        self.assertEqual(details['threshold_s'], 60)
        self.assertGreater(details['time_unreachable_s'], 60)
        self.assertEqual(details['locked_host_count'], 2)
        self.assertIn(self.host_a.id, details['locked_host_ids'])
        self.assertIn(self.host_b.id, details['locked_host_ids'])
        self.assertIn(
            "Failed to reach SCP 'TestSCP'",
            details['message'],
        )
        self.assertIn(
            'sunray.auto_register_scp_cache_duration_s = 60',
            details['message'],
        )

        self.host_a.invalidate_recordset(['block_all_traffic'])
        self.host_b.invalidate_recordset(['block_all_traffic'])
        self.assertTrue(self.host_a.block_all_traffic)
        self.assertTrue(self.host_b.block_all_traffic)

    def test_no_event_when_under_threshold(self):
        """SCP failing under threshold → no event, hosts intact."""
        self.scp.last_sync_ts = fields.Datetime.now() - timedelta(seconds=10)

        events_before = self.AuditLog.search_count([
            ('event_type', '=', 'scp.unreachable_lockdown')
        ])

        self._trigger_failed_sync()

        events_after = self.AuditLog.search_count([
            ('event_type', '=', 'scp.unreachable_lockdown')
        ])
        self.assertEqual(events_after, events_before)

        self.host_a.invalidate_recordset(['block_all_traffic'])
        self.host_b.invalidate_recordset(['block_all_traffic'])
        self.assertFalse(self.host_a.block_all_traffic)
        self.assertFalse(self.host_b.block_all_traffic)

    def test_find_or_create_user_reuses_suffixed_username(self):
        """Bug 1: If suffixed username already exists, reuse it instead of crash."""
        User = self.env['sunray.user']

        # Create a user that "owns" the base username
        User.create({
            'username': 'John DOE',
            'email': 'john.original@example.com',
            'is_active': True,
        })

        # First call: email not found, username taken → creates suffixed
        user1 = self.scp._find_or_create_user('john.scp@example.com', 'John DOE')
        self.assertEqual(user1.username, f'John DOE - SCP:{self.scp.id}')
        self.assertEqual(user1.email, 'john.scp@example.com')

        # Second call: email CHANGED in SCP but same username
        # This used to crash with UniqueViolation
        user2 = self.scp._find_or_create_user('john.new@example.com', 'John DOE')
        self.assertEqual(user2.id, user1.id, 'Should reuse the existing SCP user')
        self.assertEqual(user2.email, 'john.new@example.com', 'Email should be updated')

    def test_lockdown_works_after_real_db_error(self):
        """Bug 2: Lockdown must work after a REAL PG transaction failure.

        Triggers a genuine UniqueViolation via SQL so the cursor enters
        InFailedSqlTransaction state. The savepoint must rollback so the
        except handler can run subsequent SQL (audit event, lockdown).
        """
        self.scp.last_sync_ts = fields.Datetime.now() - timedelta(seconds=300)

        # Pre-create a user we will collide with
        existing = self.env['sunray.user'].create({
            'username': 'collide-me',
            'email': 'collide@test.example',
        })

        def trigger_real_pg_error(*args, **kwargs):
            # Direct SQL INSERT bypassing the ORM — guaranteed to put PG
            # into InFailedSqlTransaction. The ORM .create() would also work
            # but ORM convertSql/flush behavior could mask the failed-tx state.
            self.env.cr.execute(
                "INSERT INTO sunray_user (username, email, is_active, "
                "create_uid, create_date, write_uid, write_date) "
                "VALUES (%s, %s, true, 1, NOW(), 1, NOW())",
                (existing.username, 'other@test.example'),
            )
            return {'protected_hosts': [], 'users': []}

        with patch.object(type(self.scp), 'call_scp', side_effect=trigger_real_pg_error):
            self.scp.sync_scp_job()

        # Verify the cursor is back in a usable state by running a SELECT
        self.env.cr.execute("SELECT 1")
        self.assertEqual(self.env.cr.fetchone()[0], 1, 'Cursor must be usable')

        # Lockdown must have happened despite the failed-tx state
        events = self.AuditLog.search([
            ('event_type', '=', 'scp.unreachable_lockdown')
        ], order='id desc', limit=1)
        self.assertTrue(
            events,
            'Lockdown event must be created even after PG transaction failure'
        )

        self.host_a.invalidate_recordset(['block_all_traffic'])
        self.host_b.invalidate_recordset(['block_all_traffic'])
        self.assertTrue(self.host_a.block_all_traffic)
        self.assertTrue(self.host_b.block_all_traffic)

        # last_error must also have been written successfully
        self.scp.invalidate_recordset(['last_error'])
        self.assertTrue(self.scp.last_error)

    def test_last_error_saved_after_sync_failure(self):
        """Bug 2 bonus: last_error field is written after sync failure."""
        self.scp.last_sync_ts = fields.Datetime.now() - timedelta(seconds=10)

        self._trigger_failed_sync()

        self.scp.invalidate_recordset(['last_error'])
        self.assertIn('simulated SCP unreachable', self.scp.last_error or '')
