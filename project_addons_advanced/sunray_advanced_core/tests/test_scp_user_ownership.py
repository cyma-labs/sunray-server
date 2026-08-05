# -*- coding: utf-8 -*-
"""SCP account ownership: the SCP may only manage accounts it created itself.

Regression cover for the bug where a manually created account (primary email, holding
the only enrolled passkey) was silently dropped from a protected host — and could even
be globally deactivated — because `scp.user_ids` was used as a proxy for "users owned
by the SCP" when it only means "users the SCP has mentioned".
"""

from unittest.mock import patch

from odoo.tests import TransactionCase


class TestScpUserOwnership(TransactionCase):

    def setUp(self):
        super().setUp()
        self.AuditLog = self.env['sunray.audit.log']
        self.User = self.env['sunray.user']
        self.Host = self.env['sunray.host']
        self.Passkey = self.env['sunray.passkey']
        self.Scp = self.env['sunray.configuration_proxy']

        self.scp = self.Scp.create({
            'name': 'OwnershipSCP',
            'url': 'https://invalid.test.example/inouk-scp/v1/',
            'is_active': True,
        })

        self.host = self.Host.create({
            'domain': 'app.test.example',
            'backend_url': 'https://app.test.example/',
            'scp_id': self.scp.id,
            'scp_sync_enabled': True,
            'scp_hash': 'stale-hash',
        })

        # The human account: created manually, never provisioned by the SCP.
        self.local_user = self.User.create({
            'username': 'Local Human',
            'email': 'human@test.example',
            'is_active': True,
        })

        # A test account the SCP provisioned.
        self.scp_user = self.User.create({
            'username': 'SCP Test Account',
            'email': 'scp+test@test.example',
            'is_active': True,
            'added_by_scp': True,
        })

    # ------------------------------------------------------------------ helpers

    def _scp_payload(self, allowed_users, users=None, host_hash='fresh-hash'):
        """Build a minimal SCP response for self.host."""
        return {
            'protected_hosts': [{
                'fqdn': self.host.domain,
                'hash': host_hash,
                'allowed_users': allowed_users,
                'rules': [],
            }],
            'users': users if users is not None else [
                {'email': u, 'username': u} for u in allowed_users
            ],
        }

    def _sync(self, payload):
        with patch.object(type(self.scp), 'call_scp', return_value=payload):
            self.scp.sync_scp_job()
        self.host.invalidate_recordset(['user_ids'])

    def _authorize(self, *user_objs):
        self.host.user_ids = [(6, 0, [u.id for u in user_objs])]

    def _add_passkey(self, user_obj, host_domain=None):
        return self.Passkey.create({
            'user_id': user_obj.id,
            'credential_id': f'cred-{user_obj.id}',
            'public_key': 'dGVzdC1wdWJsaWMta2V5',
            'name': 'Test Passkey',
            'host_domain': host_domain or self.host.domain,
        })

    # -------------------------------------------------- _find_or_create_user

    def test_find_or_create_preserves_existing(self):
        """A pre-existing account resolved by email must never be claimed by the SCP."""
        resolved = self.scp._find_or_create_user('human@test.example', 'Local Human')

        self.assertEqual(resolved, self.local_user)
        self.assertFalse(
            resolved.added_by_scp,
            'Resolving a pre-existing account must not flag it as SCP-created',
        )

    def test_find_or_create_flags_new(self):
        """An account actually created by the SCP is flagged as such."""
        created = self.scp._find_or_create_user('brand-new@test.example', 'Brand New')

        self.assertNotEqual(created, self.local_user)
        self.assertTrue(created.added_by_scp)

    def test_find_or_create_suffixed_reuse_preserves_flag(self):
        """The username-collision branch also resolves a pre-existing account."""
        existing = self.User.create({
            'username': f'Collide - SCP:{self.scp.id}',
            'email': 'old-address@test.example',
            'is_active': True,
        })
        self.User.create({
            'username': 'Collide',
            'email': 'someone-else@test.example',
            'is_active': True,
        })

        resolved = self.scp._find_or_create_user('new-address@test.example', 'Collide')

        self.assertEqual(resolved, existing)
        self.assertFalse(
            resolved.added_by_scp,
            'Reusing an SCP-suffixed account must not flag it as SCP-created',
        )

    # ------------------------------------------------------------- sync guard

    def test_sync_preserves_local_account(self):
        """THE BUG CASE: a locally-managed account authorized on a host whose
        allowed_users only lists test accounts must survive the sync."""
        self._authorize(self.local_user, self.scp_user)
        self._add_passkey(self.local_user)

        self._sync(self._scp_payload(allowed_users=['scp+test@test.example']))

        self.assertIn(
            self.local_user, self.host.user_ids,
            'Locally-managed account must keep its host authorization',
        )
        self.assertIn(self.scp_user, self.host.user_ids)

    def test_sync_removes_scp_account(self):
        """An SCP-created account dropped from allowed_users is still removed."""
        self._authorize(self.local_user, self.scp_user)

        self._sync(self._scp_payload(allowed_users=[]))

        self.assertNotIn(
            self.scp_user, self.host.user_ids,
            'SCP-created account outside allowed_users must be removed',
        )
        self.assertIn(self.local_user, self.host.user_ids)

    def test_sync_does_not_flag_resolved_local_account(self):
        """Listing a local account in allowed_users must not transfer ownership."""
        self._authorize(self.local_user)

        self._sync(self._scp_payload(allowed_users=['human@test.example']))

        self.local_user.invalidate_recordset(['added_by_scp'])
        self.assertFalse(self.local_user.added_by_scp)
        self.assertIn(self.local_user, self.host.user_ids)

    # ------------------------------------------------------ deactivation guard

    def test_deactivation_skips_local_account(self):
        """Dropping out of every SCP must not deactivate a locally-managed account.

        is_active=False is the widest blast radius of all: /users/validate filters on
        it, so the account would lose access on EVERY host at once.
        """
        self.scp.user_ids = [(6, 0, [self.local_user.id, self.scp_user.id])]
        self._authorize(self.local_user, self.scp_user)

        self._sync(self._scp_payload(allowed_users=[], users=[]))

        self.local_user.invalidate_recordset(['is_active'])
        self.scp_user.invalidate_recordset(['is_active'])
        self.assertTrue(
            self.local_user.is_active,
            'Locally-managed account must never be deactivated by SCP sync',
        )
        self.assertFalse(
            self.scp_user.is_active,
            'SCP-created account removed from the SCP is still deactivated',
        )

    # --------------------------------------------------------- revocation audit

    def test_revocation_with_passkey_audited(self):
        """Revoking a user who holds a passkey on that host emits a warning event."""
        self._authorize(self.scp_user)
        self._add_passkey(self.scp_user)

        before = self.AuditLog.search_count([
            ('event_type', '=', 'security.scp.authorization_revoked_with_passkey')
        ])

        self._sync(self._scp_payload(allowed_users=[]))

        events = self.AuditLog.search(
            [('event_type', '=', 'security.scp.authorization_revoked_with_passkey')],
            order='id desc',
        )
        self.assertEqual(len(events) - before, 1)

        details = events[0].get_details_dict()
        self.assertEqual(events[0].severity, 'warning')
        self.assertEqual(details['host'], self.host.domain)
        self.assertEqual(details['email'], 'scp+test@test.example')
        self.assertEqual(details['passkey_count'], 1)
        self.assertTrue(
            details['added_by_scp'],
            'added_by_scp in the payload is the regression canary: a False here means '
            'a guard let a locally-managed account be revoked',
        )

    def test_no_audit_without_passkey_on_that_host(self):
        """A revocation with no passkey on this host stays out of the audit log."""
        self._authorize(self.scp_user)
        self._add_passkey(self.scp_user, host_domain='other.test.example')

        before = self.AuditLog.search_count([
            ('event_type', '=', 'security.scp.authorization_revoked_with_passkey')
        ])

        self._sync(self._scp_payload(allowed_users=[]))

        after = self.AuditLog.search_count([
            ('event_type', '=', 'security.scp.authorization_revoked_with_passkey')
        ])
        self.assertEqual(after, before, 'Passkey on another host must not raise an event')
