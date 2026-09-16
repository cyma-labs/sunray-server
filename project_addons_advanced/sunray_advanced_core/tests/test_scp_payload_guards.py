# -*- coding: utf-8 -*-
"""SCP payload trust boundary, and recovery of a stub whose setup job failed.

Regression cover for the outage where a SCP answered HTTP 200 carrying a single
`127.0.0.1` entry (its `web.base.url` had been left on a loopback URL). The sync
took that for the whole host inventory and deactivated all 62 tracked hosts. The
worker then re-registered each one, which created a stub flagged
`scp_setup_in_progress`; the setup job failed against the still-degraded SCP,
left the flag on, and the controller answered `202 setup_in_progress` forever —
the hosts stayed unreachable long after the SCP recovered.

Two properties are pinned here:

- an *invalid* payload is refused, while an *empty* one is honoured — wiping
  every host of a SCP has to remain a legitimate operation;
- a stub the SCP describes is recovered by the periodic sync, so a failed setup
  job can no longer strand a host for good.
"""

from unittest.mock import MagicMock, patch

from odoo.addons.inouk_message_queue.api import IMQError
from odoo.tests import TransactionCase

from .common import assert_raises_keeping_writes


class TestScpPayloadGuards(TransactionCase):

    def setUp(self):
        super().setUp()
        self.Host = self.env['sunray.host']
        self.Scp = self.env['sunray.configuration_proxy']
        self.Worker = self.env['sunray.worker']

        self.scp = self.Scp.create({
            'name': 'GuardSCP',
            'url': 'https://invalid.test.example/inouk-scp/v1/',
            'is_active': True,
        })
        self.worker = self.Worker.create({
            'name': 'guard-test-worker',
            'worker_type': 'fastapi',
        })
        self.host = self.Host.create({
            'domain': 'app.test.example',
            'backend_url': 'https://app.test.example/',
            'scp_id': self.scp.id,
            'scp_sync_enabled': True,
            'is_active': True,
        })

    # ------------------------------------------------------------------ helpers

    def _host_entry(self, fqdn, host_hash='fresh-hash'):
        return {
            'fqdn': fqdn,
            'hash': host_hash,
            'allowed_users': [],
            'rules': [],
        }

    def _payload(self, protected_hosts):
        return {'protected_hosts': protected_hosts, 'users': []}

    def _http_sync(self, payload, raises=None):
        """Run a sync against `payload` through the real `call_scp`.

        Mocking `requests.get` rather than `call_scp` keeps the payload
        validation in the exercised path — that is the whole point here.

        `raises` asserts the sync fails with that exception while preserving
        what its handler wrote; see `assert_raises_keeping_writes`.
        """
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = payload
        response.raise_for_status.return_value = None
        with patch('requests.get', return_value=response):
            if raises:
                assert_raises_keeping_writes(self, raises, self.scp.sync_scp_job)
            else:
                self.scp.sync_scp_job()

    # ------------------------------------------- payload is refused as a whole

    def test_loopback_only_payload_deactivates_nothing(self):
        """The exact outage shape: a 200 carrying only a loopback entry."""
        self._http_sync(self._payload([self._host_entry('127.0.0.1')]), raises=IMQError)

        self.host.invalidate_recordset(['is_active'])
        self.assertTrue(
            self.host.is_active,
            'A payload Sunray cannot act on must never deactivate a host',
        )
        self.assertTrue(self.scp.last_error, 'The failure must be recorded on the SCP')

    # ------------------------------------------- the refusal reaches a human

    def _sync_capturing_notifications(self, payload):
        """Run a refused sync and return the ik_notify_with_link call args."""
        with patch.object(
            type(self.env['res.users']), 'ik_notify_with_link'
        ) as notify_mock:
            self._http_sync(payload, raises=IMQError)
        return notify_mock

    def test_refusal_notifies_the_sunray_admins(self):
        """Nobody watches the IMQ queue; the people who can fix the SCP are told.

        The fault is on the other side of the API, and the job runs as the API
        service account with no session, so the notification has to name the
        administrators explicitly.
        """
        notify_mock = self._sync_capturing_notifications(
            self._payload([self._host_entry('localhost')])
        )

        notify_mock.assert_called_once()
        args, kwargs = notify_mock.call_args
        self.assertEqual(args[0], 'danger')
        self.assertIn('localhost', str(args[2]))
        self.assertIn(self.scp.name, str(args[2]))
        self.assertIn('whole response was ignored', str(args[2]))
        self.assertEqual(kwargs['model'], 'sunray.configuration_proxy')
        self.assertEqual(kwargs['res_id'], self.scp.id)
        self.assertTrue(kwargs['sticky'])

    def test_repeated_identical_failure_notifies_once(self):
        """The sync runs every 5 minutes; a sticky toast per tick is unusable.

        During the September episode this guard fired 82 times in a single day.
        Re-notify only when the error changes. The throttle reads `last_error`,
        which the calling job stores re-wrapped ("Sync failed: ..."), so the
        check has to be a substring test rather than equality.
        """
        payload = self._payload([self._host_entry('localhost')])

        first_mock = self._sync_capturing_notifications(payload)
        second_mock = self._sync_capturing_notifications(payload)

        first_mock.assert_called_once()
        second_mock.assert_not_called()

    def test_a_different_failure_notifies_again(self):
        """A new fault is news, even right after another one."""
        self._sync_capturing_notifications(
            self._payload([self._host_entry('localhost')])
        )

        notify_mock = self._sync_capturing_notifications(
            self._payload([self._host_entry('127.0.0.1')])
        )

        notify_mock.assert_called_once()

    def test_offender_values_are_escaped(self):
        """Offenders come from an external API and land in an admin's browser."""
        notify_mock = self._sync_capturing_notifications(
            self._payload([self._host_entry('<img src=x onerror=alert(1)>')])
        )

        body = str(notify_mock.call_args[0][2])
        self.assertNotIn('<img', body)
        self.assertIn('&lt;img', body)

    def test_unpublishable_fqdns_are_refused(self):
        """Every FQDN shape that cannot designate a reachable host."""
        for fqdn in ('127.0.0.1', '::1', '[::1]', 'localhost', 'bare-label', '', None):
            with self.subTest(fqdn=fqdn):
                self._http_sync(self._payload([self._host_entry(fqdn)]), raises=IMQError)

    def test_one_bad_entry_refuses_the_whole_payload(self):
        """A SCP that publishes an unreachable name is not trusted for the rest."""
        self._http_sync(self._payload([
            self._host_entry(self.host.domain),
            self._host_entry('127.0.0.1'),
        ]), raises=IMQError)

        self.host.invalidate_recordset(['is_active'])
        self.assertTrue(self.host.is_active)

    def test_entry_without_fqdn_is_refused(self):
        """A malformed entry must not reach the `h['fqdn']` indexing in the sync."""
        self._http_sync(self._payload([{'hash': 'x', 'allowed_users': []}]), raises=IMQError)

    # ------------------------------------------------- emptying a SCP is legal

    def test_empty_payload_deactivates_every_host(self):
        """No host left in the SCP is a valid state, not an anomaly."""
        self._http_sync(self._payload([]))

        self.host.invalidate_recordset(['is_active'])
        self.assertFalse(
            self.host.is_active,
            'Removing every host from a SCP must stay a supported operation',
        )

    # ------------------------------------------------------- stub is recovered

    def test_sync_recovers_a_stub_the_scp_describes(self):
        """A failed setup job must not strand a host the SCP knows about."""
        self.host.write({
            'scp_setup_in_progress': True,
            'scp_setup_error': "Host setup failed at step 'scp_call': boom",
        })

        self._http_sync(self._payload([self._host_entry(self.host.domain)]))

        self.host.invalidate_recordset(['scp_setup_in_progress', 'scp_setup_error'])
        self.assertFalse(
            self.host.scp_setup_in_progress,
            'The sync must clear the stub flag once the SCP describes the host',
        )
        self.assertFalse(self.host.scp_setup_error)

    def test_stub_recovered_even_when_hash_is_unchanged(self):
        """Recovery runs before the hash short-circuit, or the stub is skipped forever."""
        self.host.write({
            'scp_setup_in_progress': True,
            'scp_hash': 'same-hash',
        })

        self._http_sync(
            self._payload([self._host_entry(self.host.domain, host_hash='same-hash')])
        )

        self.host.invalidate_recordset(['scp_setup_in_progress'])
        self.assertFalse(self.host.scp_setup_in_progress)

    def test_recovery_is_audited(self):
        """Silently un-sticking a host would hide the incident that caused it."""
        self.host.write({'scp_setup_in_progress': True})

        self._http_sync(self._payload([self._host_entry(self.host.domain)]))

        event = self.env['sunray.audit.log'].search([
            ('event_type', '=', 'auto_register.stub_recovered'),
        ], limit=1)
        self.assertTrue(event, 'Recovering a stub must leave an audit trail')

    # ---------------------------------------------- setup failure is not silent

    def test_setup_failure_records_error_and_fails_the_job(self):
        """`done` on a setup that never completed is what hid the outage."""
        self.host.write({'scp_setup_in_progress': True})
        # The SCP answers, but not about this host — fails at step 'fqdn_match'.
        payload = self._payload([self._host_entry('other.test.example')])

        with patch.object(type(self.scp), 'call_scp', return_value=payload):
            assert_raises_keeping_writes(
                self, IMQError,
                self.scp.setup_host_from_scp, self.host.domain, self.worker.id,
            )

        self.host.invalidate_recordset(['scp_setup_in_progress', 'scp_setup_error'])
        self.assertTrue(
            self.host.scp_setup_in_progress,
            'The stub flag is kept so the admin can retry',
        )
        self.assertIn('fqdn_match', self.host.scp_setup_error or '')

    def test_successful_setup_clears_a_stale_error(self):
        """A recovered host must not keep displaying the failure banner."""
        self.host.write({
            'scp_setup_in_progress': True,
            'scp_setup_error': 'previous failure',
        })
        payload = self._payload([self._host_entry(self.host.domain)])

        with patch.object(type(self.scp), 'call_scp', return_value=payload):
            self.scp.setup_host_from_scp(self.host.domain, self.worker.id)

        self.host.invalidate_recordset(['scp_setup_in_progress', 'scp_setup_error'])
        self.assertFalse(self.host.scp_setup_in_progress)
        self.assertFalse(self.host.scp_setup_error)
