# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)


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
        """Override to add email sending for single-user token generation"""
        result = super(AuthorizeUsersWizardEnterprise, self).generate_token()

        if self.send_email and self.generated_token:
            token_obj = self.env['sunray.setup.token'].search([
                ('user_id', '=', self.user_id.id),
                ('device_name', '=', self.device_name)
            ], limit=1, order='create_date DESC')

            if token_obj:
                self._send_token_email(token_obj, self.generated_token)

        return result

    def action_generate_tokens_for_users(self):
        """Override to send emails for multi-user token generation.

        Calls the _do_ helper to get (token_obj, token_value) pairs,
        sends emails while plain-text values are still available,
        then commits and returns the wizard action.
        """
        generated_tokens = self._do_generate_tokens_for_users()

        if self.send_email and generated_tokens:
            self._send_emails_for_generated_tokens(generated_tokens)

        self.env.cr.commit()

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sunray.authorize.users.wizard',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
            'context': self.env.context,
        }

    def action_generate_tokens_for_hosts(self):
        """Override to send emails for multi-host token generation."""
        generated_tokens = self._do_generate_tokens_for_hosts()

        if self.send_email and generated_tokens:
            self._send_emails_for_generated_tokens(generated_tokens)

        self.env.cr.commit()

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sunray.authorize.users.wizard',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
            'context': self.env.context,
        }

    def _send_emails_for_generated_tokens(self, generated_tokens):
        """Send emails for all generated tokens.

        Args:
            generated_tokens: list of (token_obj, token_value) tuples
        """
        emails_sent = 0
        emails_failed = 0
        no_email = []

        for token_obj, token_value in generated_tokens:
            if not token_obj.user_id.email:
                no_email.append(token_obj.user_id.username)
                continue
            result = token_obj.send_token_email(token_value)
            if result['success']:
                emails_sent += 1
            else:
                emails_failed += 1

        # Append email status to result
        email_status_lines = []
        if emails_sent:
            email_status_lines.append(f"Emails sent: {emails_sent}")
        if emails_failed:
            email_status_lines.append(f"Emails failed: {emails_failed}")
        if no_email:
            email_status_lines.append(f"No email address: {', '.join(no_email)}")

        if email_status_lines:
            self.multi_operation_result = (
                self.multi_operation_result + '\n\n' + '\n'.join(email_status_lines)
            )

    def _send_token_email(self, token_obj, token_value):
        """Send setup token email to user - delegates to model method"""
        self.ensure_one()
        result = token_obj.send_token_email(token_value)
        self.email_sent = result['success']
        self.email_error = result['error'] if not result['success'] else False
