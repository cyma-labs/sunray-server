# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SetupTokenWizard(models.TransientModel):
    _name = 'sunray.setup.token.wizard'
    _description = 'Authorize User Wizard'

    # Authorization mode selection
    authorization_mode = fields.Selection(
        selection=[
            ('passkey', 'Passkey Authentication (Setup Token)'),
            ('email', 'Email Login (No setup required)'),
        ],
        string='Authorization Mode',
        help='Select how this user will authenticate to this host'
    )

    # Computed fields to track available modes (for view visibility)
    passkey_mode_available = fields.Boolean(
        compute='_compute_available_modes',
        string='Passkey Mode Available'
    )
    email_mode_available = fields.Boolean(
        compute='_compute_available_modes',
        string='Email Mode Available'
    )

    # Passkey mode: single user
    user_id = fields.Many2one(
        'sunray.user',
        string='User'
    )
    host_id = fields.Many2one(
        'sunray.host',
        required=True,
        string='Protected Host',
        help='The host this token will grant access to'
    )
    device_name = fields.Char(
        string='Device Name',
        help='Name to identify the device this token is for'
    )
    validity_hours = fields.Integer(
        string='Valid for (hours)',
        help='How long the token remains valid'
    )
    allowed_cidrs = fields.Text(
        string='Allowed CIDRs (one per line)',
        help='Optional: Restrict token to specific IP addresses or CIDR ranges'
    )
    max_uses = fields.Integer(
        string='Maximum Uses',
        help='Number of times this token can be used'
    )
    
    # Passkey mode: display fields
    generated_token = fields.Char(
        string='Generated Token',
        readonly=True
    )
    token_display = fields.Text(
        string='Setup Instructions',
        readonly=True
    )

    # Email mode: multiple users selection
    email_user_ids = fields.Many2many(
        'sunray.user',
        'sunray_authorize_wizard_user_rel',
        'wizard_id',
        'user_id',
        string='Users to Authorize',
        help='Select users to authorize for email login on this host'
    )

    # Email mode: send welcome email flag
    send_welcome_email = fields.Boolean(
        string='Send Welcome Email',
        default=True,
        help='Send an email notification to newly authorized users'
    )

    # Email mode: display fields
    email_authorization_success = fields.Boolean(
        string='Authorization Complete',
        default=False
    )
    email_authorization_result = fields.Text(
        string='Authorization Result',
        readonly=True
    )

    # Error state
    no_login_methods_error = fields.Boolean(
        compute='_compute_no_login_methods_error',
        string='No Login Methods Available'
    )

    @api.depends('host_id')
    def _compute_available_modes(self):
        for record in self:
            if record.host_id:
                record.passkey_mode_available = record.host_id.passkey_enabled
                record.email_mode_available = record.host_id.enable_email_login
            else:
                record.passkey_mode_available = False
                record.email_mode_available = False

    @api.depends('host_id')
    def _compute_no_login_methods_error(self):
        for record in self:
            if record.host_id:
                record.no_login_methods_error = (
                    not record.host_id.passkey_enabled and
                    not record.host_id.enable_email_login
                )
            else:
                record.no_login_methods_error = False

    @api.model
    def default_get(self, fields_list):
        """Load default values from system parameters and set authorization mode"""
        defaults = super().default_get(fields_list)

        # Set default authorization mode based on host config
        if 'authorization_mode' in fields_list:
            host_id = self.env.context.get('default_host_id')
            if host_id:
                host_obj = self.env['sunray.host'].browse(host_id)
                if host_obj.exists():
                    # Default to passkey if enabled, otherwise email
                    if host_obj.passkey_enabled:
                        defaults['authorization_mode'] = 'passkey'
                    elif host_obj.enable_email_login:
                        defaults['authorization_mode'] = 'email'

        # Load defaults from settings
        if 'device_name' in fields_list:
            device_name = self.env['ir.config_parameter'].sudo().get_param(
                'sunray.default_token_device_name',
                'Device'
            )
            defaults['device_name'] = device_name

        if 'validity_hours' in fields_list:
            validity_hours = self.env['ir.config_parameter'].sudo().get_param(
                'sunray.default_token_valid_hours',
                '48'
            )
            defaults['validity_hours'] = int(validity_hours)

        if 'max_uses' in fields_list:
            max_uses = self.env['ir.config_parameter'].sudo().get_param(
                'sunray.default_token_maximum_use',
                '1'
            )
            defaults['max_uses'] = int(max_uses)

        return defaults

    def generate_token(self):
        """Generate and display setup token"""
        self.ensure_one()
        
        # Use centralized token creation method
        token_obj, token_value = self.env['sunray.setup.token'].create_setup_token(
            user_id=self.user_id.id,
            host_id=self.host_id.id,
            device_name=self.device_name,
            validity_hours=self.validity_hours,
            max_uses=self.max_uses,
            allowed_cidrs=self.allowed_cidrs or ''
        )
        
        # Prepare display instructions with improved formatting
        instructions = f"""
✅ Setup Token Generated Successfully!

🔑 TOKEN: {token_value}
👤 Username: {self.user_id.username}
🌐 Host: {self.host_id.domain}
📱 Device: {self.device_name}
⏰ Expires: {token_obj.expires_at}
🔢 Max Uses: {self.max_uses}

📋 INSTRUCTIONS:
1. COPY the token above (it's shown only once!)
2. Visit your protected application at {self.host_id.domain}
3. You'll be redirected to the Sunray setup page
4. Enter this token along with your username
5. Follow the passkey registration process

🔒 SECURITY NOTES:
• Token expires in {self.validity_hours} hours
• Can be used {self.max_uses} time(s)
• Only valid for {self.host_id.domain}
• Format: Groups of 5 characters separated by dashes for easy dictation
"""
        
        if self.allowed_cidrs:
            cidr_list = [cidr.strip() for cidr in self.allowed_cidrs.splitlines() if cidr.strip()]
            if cidr_list:
                instructions += f"• IP restriction: {', '.join(cidr_list)}\n"
        
        # Update wizard for display
        self.generated_token = token_value
        self.token_display = instructions
        
        # We commit now since user may be tempted to use token
        # while it is not commited. This would trigger an API Call 
        # from the worker which will fail and the worker cache 
        # will be set with no token !
        self.env.cr.commit()

        # Return wizard action to show the token
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sunray.setup.token.wizard',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
            'context': self.env.context,
        }

    def action_authorize_email_users(self):
        """Authorize users for email login without setup token"""
        self.ensure_one()

        if not self.email_user_ids:
            raise UserError('Please select at least one user to authorize.')

        host_obj = self.host_id
        authorized_users = []
        already_authorized = []

        for user_obj in self.email_user_ids:
            if user_obj in host_obj.user_ids:
                already_authorized.append(user_obj.username)
            else:
                # Add user to host's authorized users
                host_obj.write({
                    'user_ids': [(4, user_obj.id)]
                })
                authorized_users.append(user_obj)

                # Log audit event
                self.env['sunray.audit.log'].create_admin_event(
                    event_type='host.user_authorized',
                    details={
                        'username': user_obj.username,
                        'email': user_obj.email,
                        'host': host_obj.domain,
                        'authorization_mode': 'email',
                    },
                    sunray_user_id=user_obj.id,
                    username=user_obj.username
                )

        # Send welcome email notifications if enabled
        if authorized_users and self.send_welcome_email:
            self._send_welcome_emails(authorized_users, host_obj)

        # Prepare notification message
        message_parts = []
        if authorized_users:
            usernames = [u.username for u in authorized_users]
            message_parts.append(
                f"Successfully authorized {len(authorized_users)} user(s): {', '.join(usernames)}"
            )
        if already_authorized:
            message_parts.append(f"Already authorized: {', '.join(already_authorized)}")

        # Commit to ensure changes are visible
        self.env.cr.commit()

        # Close wizard and show notification
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Users Authorized',
                'message': '\n'.join(message_parts),
                'type': 'success',
                'sticky': False,
            }
        }

    def _send_welcome_emails(self, authorized_users, host_obj):
        """Send welcome email to newly authorized users"""
        template = self.env.ref(
            'sunray_core.mail_template_user_welcome',
            raise_if_not_found=False
        )
        if not template:
            _logger.info("Welcome email template not found, skipping email notifications")
            return

        for user_obj in authorized_users:
            if user_obj.email:
                try:
                    template.with_context(
                        recipient_email=user_obj.email,
                        recipient_name=user_obj.username,
                    ).send_mail(
                        host_obj.id,
                        email_values={'email_to': user_obj.email},
                        force_send=True
                    )
                    _logger.info(f"Welcome email sent to {user_obj.email} for host {host_obj.domain}")
                except Exception as e:
                    _logger.warning(f"Failed to send welcome email to {user_obj.email}: {e}")