# -*- coding: utf-8 -*-
"""`sunray.host.state` must tell the truth about a host stuck in SCP setup.

Companion to `test_auto_register_scp_selection`: that module covers how a stub
ends up bound to the wrong SCP, this one covers how a stub stuck in setup is
surfaced. Before the `scp_setup` state, `_compute_state` ignored
`scp_setup_in_progress`, so a stub the worker was being answered 202 for showed
as `protected` in the host list. That is what kept the outage invisible.
"""

from odoo.tests import TransactionCase


class TestHostScpSetupState(TransactionCase):
    """`state` must tell the truth about a host stuck in SCP setup.

    Before this, `_compute_state` ignored `scp_setup_in_progress`, so a stub the
    worker was answering 202 for displayed as `protected`. That is what kept the
    outage invisible in the host list.
    """

    def setUp(self):
        super().setUp()
        self.Host = self.env['sunray.host']
        self.worker = self.env['sunray.worker'].create({
            'name': 'scp-setup-state-worker',
            'worker_type': 'fastapi',
        })
        self.host = self.Host.create({
            'domain': 'stub.test.example',
            'backend_url': 'https://stub.test.example/',
            'sunray_worker_id': self.worker.id,
            'is_active': True,
            # Explicit on purpose, do not delete as redundant: `default_get`
            # forces deployment_mode=True on every new host (and fills
            # golive_date from sunray.config_default_golive_period_duration_days),
            # so a host created without it computes 'deployment'. The baseline we
            # want to contrast 'scp_setup' against is 'protected'.
            'deployment_mode': False,
        })

    def test_plain_host_is_protected(self):
        self.assertEqual(self.host.state, 'protected')

    def test_stub_computes_scp_setup(self):
        self.host.scp_setup_in_progress = True

        self.assertEqual(self.host.state, 'scp_setup')

    def test_locked_wins_over_scp_setup(self):
        """STD-26: the state only a human can clear outranks the transient one.

        A stub can carry both flags without any admin action — reactivating an
        archived host does not reset `block_all_traffic`, and nothing in the
        codebase ever writes it back to False. Showing `scp_setup` here would
        hide the reason the host stays dark once setup completes.
        """
        self.host.write({
            'scp_setup_in_progress': True,
            'block_all_traffic': True,
        })

        self.assertEqual(self.host.state, 'locked')

    def test_archived_wins_over_scp_setup(self):
        self.host.write({
            'scp_setup_in_progress': True,
            'is_active': False,
        })

        self.assertEqual(self.host.state, 'archived')

    def test_scp_setup_wins_over_deployment(self):
        """A stub is not in deployment: it is not served at all yet.

        The most representative case of the three, not an edge case: `default_get`
        forces deployment_mode on new hosts, and auto-registered stubs inherit
        `auto_register_deployment_mode` from their worker, so a real stub is far
        more likely to sit here than on the plain `protected` baseline.
        """
        self.host.write({
            'scp_setup_in_progress': True,
            'deployment_mode': True,
        })

        self.assertEqual(self.host.state, 'scp_setup')

    def test_clearing_the_flag_returns_to_protected(self):
        """A successful setup, or the Retry button, brings the host back."""
        self.host.scp_setup_in_progress = True
        self.assertEqual(self.host.state, 'scp_setup')

        self.host.scp_setup_in_progress = False

        self.assertEqual(self.host.state, 'protected')
