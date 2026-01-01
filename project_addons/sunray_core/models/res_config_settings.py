# -*- coding: utf-8 -*-
from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Setup Token Configuration
    sunray_token_device_name = fields.Char(
        string='Default Device Name',
        default='Device',
        config_parameter='sunray.default_token_device_name',
        help='Default device name used when generating setup tokens. '
             'Examples: "Mobile Phone", "Laptop", "Desktop", "Tablet"'
    )

    sunray_token_valid_hours = fields.Integer(
        string='Default Token Validity (hours)',
        default=48,
        config_parameter='sunray.default_token_valid_hours',
        help='Default validity period for setup tokens in hours. '
             'After this period, unused tokens will expire. '
             'Common values: 24h (1 day), 48h (2 days), 168h (1 week)'
    )

    sunray_token_maximum_use = fields.Integer(
        string='Default Maximum Uses',
        default=1,
        config_parameter='sunray.default_token_maximum_use',
        help='Default maximum number of times a setup token can be used. '
             'Set to 1 for single-use tokens, or higher for reusable tokens. '
             'Use 0 for unlimited uses (not recommended for security).'
    )

    # Email Login Configuration
    sunray_email_otp_template_id = fields.Many2one(
        'mail.template',
        string='Default Email OTP Template',
        config_parameter='sunray.email_otp_template_id',
        domain="[('model_id.model', '=', 'sunray.host')]",
        help='Default email template for sending OTP codes. '
             'Hosts can override this with their own template.'
    )
