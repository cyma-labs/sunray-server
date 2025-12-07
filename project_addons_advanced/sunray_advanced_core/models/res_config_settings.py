# -*- coding: utf-8 -*-
from odoo import models, fields, api


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Setup Token Email Settings
    sunray_setup_token_mail_template_id = fields.Many2one(
        'mail.template',
        string='Default Setup Token Email Template',
        domain=[('model', '=', 'sunray.setup.token')],
        help='Default email template used when sending setup tokens to users',
        config_parameter='sunray.setup_token_mail_template'
    )

    sunray_setup_token_send_email_default = fields.Boolean(
        string='Send Email by Default',
        default=True,
        help='Default value for "Send Email" checkbox in setup token wizards',
        config_parameter='sunray.setup_token_send_email_default'
    )

    # IP Whitelist Settings
    sunray_admin_ip_whitelist = fields.Char(
        string='Admin IP Whitelist',
        help='IP addresses or CIDR ranges allowed to access the Sunray admin interface (comma-separated)\n'
             'Examples: 192.168.1.100, 192.168.1.0/24, 10.0.0.0/8',
        config_parameter='sunray.admin_ip_whitelist'
    )

    # Host Configuration
    sunray_golive_period_duration_days = fields.Integer(
        string='Default Go-Live Period (days)',
        default=30,
        config_parameter='sunray.config_default_golive_period_duration_days',
        help='Default number of days for the go-live period when creating new hosts. '
             'This sets the initial deadline for host activation.'
    )

    @api.model
    def get_values(self):
        """Get configuration values"""
        res = super(ResConfigSettings, self).get_values()

        # Get template from system parameters
        template_xmlid = self.env['ir.config_parameter'].sudo().get_param(
            'sunray.setup_token_mail_template',
            'sunray_core.mail_template_setup_token'
        )

        # Try to resolve the XML ID to a record
        try:
            template = self.env.ref(template_xmlid, raise_if_not_found=False)
            if template:
                res.update(sunray_setup_token_mail_template_id=template.id)
        except ValueError:
            pass

        return res

    def set_values(self):
        """Set configuration values"""
        super(ResConfigSettings, self).set_values()

        # Convert record ID to XML ID format if possible
        if self.sunray_setup_token_mail_template_id:
            # Get the XML ID of the template
            xml_id = self.sunray_setup_token_mail_template_id.get_external_id()
            if xml_id and self.sunray_setup_token_mail_template_id.id in xml_id:
                template_value = xml_id[self.sunray_setup_token_mail_template_id.id]
            else:
                # Fallback to record reference
                template_value = f'mail.template,{self.sunray_setup_token_mail_template_id.id}'

            self.env['ir.config_parameter'].sudo().set_param(
                'sunray.setup_token_mail_template',
                template_value
            )
