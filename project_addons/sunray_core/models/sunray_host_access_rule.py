# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class SunrayHostAccessRule(models.Model):
    """Association model linking hosts to access rule libraries with host-specific configuration"""
    _name = 'sunray.host.access.rule'
    _description = 'Host-Rule Association with Priority'
    _order = 'host_id, priority'

    host_id = fields.Many2one(
        'sunray.host',
        string='Protected Host',
        required=True,
        ondelete='cascade',
        index=True,
        help='The host this rule is applied to'
    )

    rule_id = fields.Many2one(
        'sunray.access.rule',
        string='Access Rule',
        required=True,
        ondelete='restrict',  # Prevent deletion of rules in use
        index=True,
        help='The access rule library to apply'
    )

    priority = fields.Integer(
        string='Priority',
        required=True,
        default=100,
        help='Lower number = higher priority. Rules are evaluated in priority order on this host.'
    )

    is_active = fields.Boolean(
        string='Active on This Host',
        default=True,
        help='Deactivate to temporarily disable this rule on this specific host'
    )

    # Related fields for convenient UI display
    rule_type = fields.Selection(
        related='rule_id.access_type',
        string='Rule Type',
        readonly=True,
        store=False
    )

    rule_name = fields.Char(
        related='rule_id.name',
        string='Rule Name',
        readonly=True,
        store=False
    )

    host_domain = fields.Char(
        related='host_id.domain',
        string='Host Domain',
        readonly=True,
        store=False
    )

    # SQL Constraints
    _sql_constraints = [
        ('host_rule_unique',
         'UNIQUE(host_id, rule_id)',
         'This rule is already applied to this host! Each rule can only be added once per host.'),

        ('priority_positive',
         'CHECK(priority > 0)',
         'Priority must be a positive number!')
    ]

    @api.constrains('priority')
    def _check_priority_range(self):
        """Validate priority is in reasonable range"""
        for record in self:
            if record.priority <= 0:
                raise ValidationError('Priority must be positive!')
            if record.priority > 10000:
                raise ValidationError('Priority must be less than 10000!')

    def name_get(self):
        """Custom display name: [Priority] Rule Name @ Host"""
        result = []
        for record in self:
            name = f"[{record.priority}] {record.rule_id.name} @ {record.host_id.domain}"
            result.append((record.id, name))
        return result

    def action_view_rule(self):
        """Open the rule library form view"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sunray.access.rule',
            'res_id': self.rule_id.id,
            'view_mode': 'form',
            'target': 'current',
            'context': {'create': False}
        }
