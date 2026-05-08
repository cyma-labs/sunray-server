# -*- coding: utf-8 -*-
"""Test SCP unreachable mass-lockdown audit event."""

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
