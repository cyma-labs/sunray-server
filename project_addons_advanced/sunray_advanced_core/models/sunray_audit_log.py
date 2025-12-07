# -*- coding: utf-8 -*-
from odoo import models, fields


class SunrayAuditLogAdvanced(models.Model):
    _inherit = 'sunray.audit.log'

    event_type = fields.Selection(
        selection_add=[
            # Token Email Events
            ('token.email.sent', 'Token Email Sent'),
            ('token.email.no_template', 'Token Email No Template'),
            ('token.email.no_recipient', 'Token Email No Recipient'),
            ('token.email.error', 'Token Email Error'),
            # User Validation Events
            ('user.validation.success', 'User Validation Success'),
            ('user.validation.unknown_user', 'User Validation Unknown User'),
            # Host Lifecycle Events
            ('host.golive_transition', 'Host Go-Live Transition'),
            ('remote_auth.qr_page_displayed', 'Remote Auth QR Code page displayed'),
            ('remote_auth.challenge_created', 'Remote Auth Challenge created'),
            ('remote_auth.challenge_expired', 'Remote Auth Challenge expired'),
            ('remote_auth.verification_failed', 'Remote Auth Verification failed'),
            ('remote_auth.verification_success', 'Remote Auth Verification success'),
            ('remote_auth.mobile_auth_initiated', 'Remote Auth Mobile Auth initiated'),
            ('remote_auth.manual_code_entered', 'Remote Auth Manual Code Entered'),
        ],
        ondelete={
            'token.email.sent': 'cascade',
            'token.email.no_template': 'cascade',
            'token.email.no_recipient': 'cascade',
            'token.email.error': 'cascade',
            'user.validation.success': 'cascade',
            'user.validation.unknown_user': 'cascade',
            'host.golive_transition': 'cascade',
            'remote_auth.qr_page_displayed': 'cascade',
            'remote_auth.challenge_created': 'cascade',
            'remote_auth.challenge_expired': 'cascade',
            'remote_auth.verification_failed': 'cascade',
            'remote_auth.verification_success': 'cascade',
            'remote_auth.mobile_auth_initiated': 'cascade',
            'remote_auth.manual_code_entered': 'cascade',
        }
    )
