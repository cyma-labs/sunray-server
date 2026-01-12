# -*- coding: utf-8 -*-
from odoo import models, fields, api


class AuthorizeUsersWizardEnterprise(models.TransientModel):
    _inherit = 'sunray.authorize.users.wizard'

    # Email fields
    send_email = fields.Boolean(
        string='Email Setup Token',
        help='Send the setup token to the user by email'
    )
    email_sent = fields.Boolean(
        string='Email Sent',
        readonly=True,
        default=False
    )
    email_error = fields.Text(
        string='Email Error',
        readonly=True
    )

    @api.model
    def default_get(self, fields_list):
        """Set default send_email from system config"""
        res = super(AuthorizeUsersWizardEnterprise, self).default_get(fields_list)
        if 'send_email' in fields_list:
            send_email_default = self.env['ir.config_parameter'].sudo().get_param(
                'sunray.setup_token_send_email_default',
                'True'
            )
            res['send_email'] = send_email_default == 'True'
        return res

    def generate_token(self):
        """Override to add email sending"""
        # Call parent to generate token
        result = super(AuthorizeUsersWizardEnterprise, self).generate_token()

        # Send email if requested
        if self.send_email and self.generated_token:
            # Get the token object
            token_obj = self.env['sunray.setup.token'].search([
                ('user_id', '=', self.user_id.id),
                ('device_name', '=', self.device_name)
            ], limit=1, order='create_date DESC')

            if token_obj:
                self._send_token_email(token_obj, self.generated_token)

        return result

    def _send_token_email(self, token_obj, token_value):
        """Send setup token email to user - delegates to model method

        Args:
            token_obj: The sunray.setup.token record
            token_value: The plain text token value to include in email
        """
        self.ensure_one()

        # Use the model's send_token_email method
        result = token_obj.send_token_email(token_value)

        # Update wizard fields based on result
        self.email_sent = result['success']
        self.email_error = result['error'] if not result['success'] else False
