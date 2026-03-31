# -*- coding: utf-8 -*-
from odoo import fields, models


class SunrayAccessRuleSCP(models.Model):
    """Extend sunray.access.rule with SCP-managed rules tracking."""

    _inherit = 'sunray.access.rule'

    scp_id = fields.Many2one(
        'sunray.configuration_proxy',
        string='SCP Source',
        ondelete='set null',
        help='SCP that created this rule. Used to identify and replace SCP-managed rules at sync.'
    )

    _sql_constraints = [
        ('scp_name_unique',
         'UNIQUE(scp_id, name)',
         'SCP-managed rules must have unique names per SCP.'),
    ]
