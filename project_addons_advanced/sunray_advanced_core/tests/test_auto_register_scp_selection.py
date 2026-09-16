# -*- coding: utf-8 -*-
"""Which SCP auto-register picks for an unknown host.

Regression cover for the outage where `sox18-synchro-dev-dharma-phidias-msa21`
hung on the worker's "Setup in Progress" page indefinitely. Its worker had a
single SCP in `auto_register_scp_ids`, and that SCP was *disabled* with an empty
`fqdn_regex` (= match all). `find_matching_scp` did not look at `is_active`, so
the dead SCP won, the stub was created against a control plane that did not know
the FQDN, `setup_host_from_scp` failed on HTTP 400, and the controller answered
`202 setup_in_progress` from then on.

Pinned here: a disabled SCP is never selected, never shadows an active one, and
the configuration that makes auto-register impossible is flagged on the worker.
"""

from odoo.tests import TransactionCase

_AUTOREGISTER_LOGGER = (
    'odoo.addons.sunray_advanced_core.models.sunray_worker_autoregister'
)


class TestScpSelection(TransactionCase):
    """`find_matching_scp` must skip SCPs the admin has disabled."""

    def setUp(self):
        super().setUp()
        self.Scp = self.env['sunray.configuration_proxy']
        self.Worker = self.env['sunray.worker']

        self.worker = self.Worker.create({
            'name': 'scp-selection-test-worker',
            'worker_type': 'fastapi',
            'auto_register_enabled': True,
        })

    # ------------------------------------------------------------------ helpers

    def _scp(self, name, is_active=True, fqdn_regex=False):
        return self.Scp.create({
            'name': name,
            'url': f'https://{name}.invalid.test/inouk-scp/v1/',
            'is_active': is_active,
            'fqdn_regex': fqdn_regex,
        })

    # -------------------------------------------------------------------- tests

    def test_inactive_scp_is_never_selected(self):
        """A disabled match-all SCP must not be picked, even when it is alone."""
        self.worker.auto_register_scp_ids = [
            (6, 0, self._scp('dead-scp', is_active=False).ids)
        ]

        self.assertFalse(
            self.worker.find_matching_scp('app.test.example'),
            "a disabled SCP was selected for auto-registration",
        )

    def test_inactive_match_all_does_not_shadow_an_active_scp(self):
        """The incident itself: dead match-all SCP sorted before the live one.

        SCPs are iterated in the comodel's `_order` ('name asc'), so 'aaa-...'
        is evaluated before 'zzz-...'. Before the fix the disabled SCP matched
        (empty fqdn_regex = match all) and was returned, stranding the host on a
        control plane that no longer managed it.
        """
        dead_scp = self._scp('aaa-dead-scp', is_active=False)
        live_scp = self._scp(
            'zzz-live-scp', is_active=True, fqdn_regex=r'.*\.test\.example'
        )
        self.worker.auto_register_scp_ids = [(6, 0, (dead_scp + live_scp).ids)]

        self.assertEqual(
            self.worker.find_matching_scp('app.test.example'),
            live_scp,
            "the disabled SCP shadowed the active one",
        )

    def test_returns_false_not_none(self):
        """STD-13: 'no record' is False, never None."""
        self.worker.auto_register_scp_ids = [(6, 0, [])]

        self.assertIs(self.worker.find_matching_scp('app.test.example'), False)

    def test_active_scp_with_non_matching_regex_is_skipped(self):
        """Being active is not enough: the regex still has to match (fullmatch)."""
        other_scp = self._scp(
            'other-scp', is_active=True, fqdn_regex=r'.*\.other\.example'
        )
        self.worker.auto_register_scp_ids = [(6, 0, other_scp.ids)]

        self.assertFalse(self.worker.find_matching_scp('app.test.example'))

    def test_disabled_scp_that_does_not_match_logs_nothing(self):
        """Only a skip that changes the outcome is worth a WARNING.

        The caller is an auth='none' endpoint the worker polls every 5s. Logging
        every disabled SCP, matching or not, would drown the log for no signal.
        """
        dead_scp = self._scp(
            'dead-elsewhere-scp', is_active=False, fqdn_regex=r'.*\.other\.example'
        )
        self.worker.auto_register_scp_ids = [(6, 0, dead_scp.ids)]

        with self.assertNoLogs(_AUTOREGISTER_LOGGER, level='WARNING'):
            self.worker.find_matching_scp('app.test.example')

    def test_disabled_scp_that_would_have_matched_is_logged(self):
        """The skip that changes the outcome must leave a trace."""
        dead_scp = self._scp('dead-matching-scp', is_active=False)
        self.worker.auto_register_scp_ids = [(6, 0, dead_scp.ids)]

        with self.assertLogs(_AUTOREGISTER_LOGGER, level='WARNING') as captured:
            self.worker.find_matching_scp('app.test.example')

        self.assertIn('dead-matching-scp', captured.output[0])
        self.assertIn('app.test.example', captured.output[0])


class TestWorkerAutoRegisterStatus(TransactionCase):
    """The standing admin signal for a worker that cannot register anything.

    Skipping disabled SCPs is right, but it turns a loud failure (the host hangs
    on the worker's setup page) into a silent one (404, worker serves a 503,
    nothing points at the worker). These two fields are what keep it visible, in
    the worker list as much as on the form.
    """

    def setUp(self):
        super().setUp()
        self.Scp = self.env['sunray.configuration_proxy']
        self.worker = self.env['sunray.worker'].create({
            'name': 'autoregister-status-worker',
            'worker_type': 'fastapi',
            'auto_register_enabled': True,
        })

    def _scp(self, name, is_active=True):
        return self.Scp.create({
            'name': name,
            'url': f'https://{name}.invalid.test/inouk-scp/v1/',
            'is_active': is_active,
        })

    def test_no_scp_linked_is_broken(self):
        """Auto-register on with nothing linked can never register a host."""
        self.worker.auto_register_scp_ids = [(6, 0, [])]

        self.assertTrue(self.worker.auto_register_no_active_scp)
        self.assertEqual(self.worker.auto_register_status, 'On — no SCP linked')

    def test_all_linked_scps_disabled_is_broken(self):
        """The configuration behind the outage: linked, but all disabled."""
        dead_scp = self._scp('all-dead-scp', is_active=False)
        self.worker.auto_register_scp_ids = [(6, 0, dead_scp.ids)]

        self.assertTrue(self.worker.auto_register_no_active_scp)
        self.assertEqual(
            self.worker.auto_register_status, 'On — all 1 SCP(s) disabled'
        )

    def test_one_active_scp_is_healthy(self):
        """A single active SCP is enough, whatever else is linked."""
        dead_scp = self._scp('mixed-dead-scp', is_active=False)
        live_scp = self._scp('mixed-live-scp', is_active=True)
        self.worker.auto_register_scp_ids = [(6, 0, (dead_scp + live_scp).ids)]

        self.assertFalse(self.worker.auto_register_no_active_scp)
        self.assertEqual(self.worker.auto_register_status, 'mixed-live-scp')

    def test_status_names_every_active_scp(self):
        """The list column says which control plane a worker registers against."""
        first_scp = self._scp('aaa-live-scp')
        second_scp = self._scp('bbb-live-scp')
        self.worker.auto_register_scp_ids = [(6, 0, (first_scp + second_scp).ids)]

        self.assertFalse(self.worker.auto_register_no_active_scp)
        self.assertEqual(
            self.worker.auto_register_status, 'aaa-live-scp, bbb-live-scp'
        )

    def test_auto_register_off_is_not_broken(self):
        """No auto-registration, no problem to report — even with a dead SCP."""
        self.worker.auto_register_enabled = False
        self.worker.auto_register_scp_ids = [
            (6, 0, self._scp('off-dead-scp', is_active=False).ids)
        ]

        self.assertFalse(self.worker.auto_register_no_active_scp)
        self.assertEqual(self.worker.auto_register_status, 'Off')
