from odoo import api, fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        values['action_id'] = self.env.ref('sunray_dashboard.sunray_dashboard_act_window').id
        return values