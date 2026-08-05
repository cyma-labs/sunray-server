# -*- coding: utf-8 -*-
from odoo import fields, models


class SunrayUserSCP(models.Model):
    """Extend sunray.user with SCP (Sunray Configuration Proxy) account ownership.

    The SCP may only manage the lifecycle of accounts it created itself. An account
    that already existed when the SCP first returned it — or that was created manually
    through the admin UI, the CLI or a setup token — stays under the administrator's
    sole responsibility and is never removed from a host nor deactivated by SCP sync.
    """

    _inherit = 'sunray.user'

    added_by_scp = fields.Boolean(
        string='Created by SCP',
        default=False,
        readonly=True,
        copy=False,
        index=True,
        help='Fact, not a setting: this account was created by an SCP synchronization. '
             'Only such accounts may be removed from a host or deactivated by the SCP. '
             'An account created manually (wizard, CLI, setup token) stays under the '
             "administrator's sole responsibility and is never touched by SCP sync."
    )
