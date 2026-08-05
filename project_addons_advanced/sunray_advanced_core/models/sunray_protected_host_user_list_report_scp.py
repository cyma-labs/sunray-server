# -*- coding: utf-8 -*-
from odoo import fields, models


class ProtectedHostUserListReportSCP(models.Model):
    """Surface SCP account ownership in the per-host authorized users report.

    Declared as a related field rather than a column of the SQL view: the view
    lives in sunray_core, which must not reference an advanced-only column on
    sunray_user. Non-stored, so it is displayable but not sortable/searchable —
    acceptable for a read-only informational column.
    """

    _inherit = 'sunray.protected_host_user_list_report'

    added_by_scp = fields.Boolean(
        related='user_id.added_by_scp',
        string='Created by SCP',
        readonly=True,
    )
