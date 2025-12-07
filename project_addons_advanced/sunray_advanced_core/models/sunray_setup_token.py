# -*- coding: utf-8 -*-
from odoo import models, api, _


class SetupTokenAdvanced(models.Model):
    _inherit = 'sunray.setup.token'

    def send_token_email(self, token_value):
        """Send setup token email to user

        Args:
            token_value: The plain text token value to include in email

        Returns:
            dict: {'success': bool, 'error': str or None}
        """
        self.ensure_one()

        try:
            template = self._get_mail_template()

            if not template:
                error_msg = "No email template configured. Please configure a default template in Settings."

                # Log error
                self.env['sunray.audit.log'].create_audit_event(
                    event_type='token.email.no_template',
                    details={
                        'username': self.user_id.username,
                        'host': self.host_id.domain,
                        'device_name': self.device_name,
                        'error': error_msg
                    },
                    severity='error',
                    sunray_user_id=self.user_id.id,
                    username=self.user_id.username
                )
                return {'success': False, 'error': error_msg}

            # Verify user has email
            if not self.user_id.email:
                error_msg = f"User {self.user_id.username} has no email address configured."

                # Log error
                self.env['sunray.audit.log'].create_audit_event(
                    event_type='token.email.no_recipient',
                    details={
                        'username': self.user_id.username,
                        'host': self.host_id.domain,
                        'device_name': self.device_name,
                        'error': error_msg
                    },
                    severity='warning',
                    sunray_user_id=self.user_id.id,
                    username=self.user_id.username
                )
                return {'success': False, 'error': error_msg}

            # Send email with token_value in context
            template.with_context(token_value=token_value).send_mail(
                self.id,
                force_send=True,
                raise_exception=True
            )

            # Log success
            self.env['sunray.audit.log'].create_audit_event(
                event_type='token.email.sent',
                details={
                    'username': self.user_id.username,
                    'email': self.user_id.email,
                    'host': self.host_id.domain,
                    'device_name': self.device_name,
                    'template': template.name
                },
                severity='info',
                sunray_user_id=self.user_id.id,
                username=self.user_id.username
            )

            return {'success': True, 'error': None}

        except Exception as e:
            error_msg = f"Failed to send email: {str(e)}"

            self.env['sunray.audit.log'].create_audit_event(
                event_type='token.email.error',
                details={
                    'username': self.user_id.username,
                    'email': self.user_id.email,
                    'host': self.host_id.domain,
                    'device_name': self.device_name,
                    'error': str(e)
                },
                severity='error',
                sunray_user_id=self.user_id.id,
                username=self.user_id.username
            )

            return {'success': False, 'error': error_msg}

    def _get_mail_template(self):
        """Get the mail template from system settings"""
        template_xmlid = self.env['ir.config_parameter'].sudo().get_param(
            'sunray.setup_token_mail_template',
            'sunray_advanced_core.mail_template_setup_token_v2'
        )
        try:
            return self.env.ref(template_xmlid)
        except ValueError:
            # Fallback to default template if configured one doesn't exist
            return self.env.ref('sunray_advanced_core.mail_template_setup_token_v2', raise_if_not_found=False)
