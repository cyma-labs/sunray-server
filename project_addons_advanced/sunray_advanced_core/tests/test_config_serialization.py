# -*- coding: utf-8 -*-
"""Config serialization: session-duration naming convention (*_ttl -> *_duration_s).

Two-phase test by design:

- PHASE 1 (transition, current): the serializers emit BOTH the legacy `*_ttl`
  keys AND the canonical `*_duration_s` keys, with equal values.
- PHASE 2 (after cleanup): the legacy `*_ttl` keys are dropped. To switch, make
  the assertions use `_assert_only_new` instead of `_assert_transition` (the
  (legacy, new) pair lists below stay the same).
"""

from odoo.tests import TransactionCase

# (legacy_key, canonical_key) pairs per serialized block.
REMOTE_AUTH_DURATION_KEYS = [
    ('session_ttl', 'session_duration_s'),
    ('max_session_ttl', 'max_session_duration_s'),
    ('session_mgmt_ttl', 'session_mgmt_duration_s'),
]
DEPLOYMENT_DURATION_KEYS = [
    ('session_ttl', 'session_duration_s'),
]


class TestSessionDurationSerialization(TransactionCase):
    """remote_auth / deployment_mode expose canonical *_duration_s keys."""

    def setUp(self):
        super().setUp()
        self.Host = self.env['sunray.host']
        self.host = self.Host.create({
            'domain': 'durations.test.example',
            'backend_url': 'https://durations.test.example/',
            'passkey_enabled': True,
            # remote auth
            'remote_auth_enabled': True,
            'remote_auth_session_ttl': 3600,
            'remote_auth_max_session_ttl': 7200,
            'session_mgmt_enabled': True,
            'session_mgmt_ttl': 120,
            # deployment mode
            'deployment_mode': True,
            'deployment_session_ttl': 5400,
        })

    def _assert_transition(self, block, pairs):
        """PHASE 1: both legacy and canonical keys present, with equal values."""
        for legacy, new in pairs:
            self.assertIn(new, block, f"canonical key '{new}' must be present")
            self.assertIn(legacy, block, f"legacy key '{legacy}' must still be emitted during transition")
            self.assertEqual(
                block[new], block[legacy],
                f"'{new}' must equal deprecated '{legacy}'",
            )

    def _assert_only_new(self, block, pairs):
        """PHASE 2 (after cleanup): only canonical keys remain, legacy dropped."""
        for legacy, new in pairs:
            self.assertIn(new, block, f"canonical key '{new}' must be present")
            self.assertNotIn(legacy, block, f"deprecated key '{legacy}' must be removed")

    def test_remote_auth_config_exposes_duration_keys(self):
        block = self.host.get_remote_auth_config()
        self._assert_transition(block, REMOTE_AUTH_DURATION_KEYS)
        self.assertEqual(block['session_duration_s'], 3600)
        self.assertEqual(block['max_session_duration_s'], 7200)
        self.assertEqual(block['session_mgmt_duration_s'], 120)

    def test_deployment_mode_config_exposes_duration_keys(self):
        block = self.host.get_deployment_mode_config()
        self._assert_transition(block, DEPLOYMENT_DURATION_KEYS)
        self.assertEqual(block['session_duration_s'], 5400)

    def test_config_data_blocks_expose_duration_keys(self):
        """The full /config payload carries the canonical keys too."""
        config = self.host.get_config_data()[0]
        self._assert_transition(config['remote_auth'], REMOTE_AUTH_DURATION_KEYS)
        self._assert_transition(config['deployment_mode'], DEPLOYMENT_DURATION_KEYS)
