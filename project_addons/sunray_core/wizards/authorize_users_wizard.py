# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AuthorizeUsersWizard(models.TransientModel):
    _name = 'sunray.authorize.users.wizard'
    _description = 'Authorize User Wizard'

    # Workflow direction (set via default_get from context)
    workflow = fields.Selection(
        selection=[
            ('host_to_users', 'Authorize Users on a Host'),
            ('user_to_hosts', 'Authorize User on Hosts'),
        ],
        string='Workflow',
    )

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

    # Passkey mode: single user (kept for single-user preview)
    user_id = fields.Many2one(
        'sunray.user',
        string='User'
    )
    host_id = fields.Many2one(
        'sunray.host',
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

    # Passkey mode: display fields (single-user preview)
    generated_token = fields.Char(
        string='Generated Token',
        readonly=True
    )
    token_display = fields.Text(
        string='Setup Instructions',
        readonly=True
    )

    # Passkey mode: multi-user selection (Host-to-Users)
    passkey_user_ids = fields.Many2many(
        'sunray.user',
        'sunray_authorize_wizard_passkey_user_rel',
        'wizard_id',
        'user_id',
        string='Users',
        help='Select users to generate passkey setup tokens for'
    )
    passkey_user_count = fields.Integer(
        compute='_compute_passkey_user_count',
        string='Passkey User Count'
    )

    # Email mode: multiple users selection (Host-to-Users)
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

    # Multi-hosts for User-to-Hosts workflow
    host_ids = fields.Many2many(
        'sunray.host',
        'sunray_authorize_wizard_host_rel',
        'wizard_id',
        'host_id',
        string='Protected Hosts',
        help='Select hosts to authorize this user on'
    )

    # Multi-operation results (multi-user passkey or User-to-Hosts passkey)
    multi_operation_result = fields.Text(
        string='Operation Results',
        readonly=True
    )
    multi_operation_success = fields.Boolean(
        string='Operation Complete',
        default=False
    )

    # Error state
    no_login_methods_error = fields.Boolean(
        compute='_compute_no_login_methods_error',
        string='No Login Methods Available'
    )

    @api.depends('passkey_user_ids')
    def _compute_passkey_user_count(self):
        for record in self:
            record.passkey_user_count = len(record.passkey_user_ids)

    @api.depends('host_id', 'host_ids')
    def _compute_available_modes(self):
        for record in self:
            if record.host_id:
                # Host-to-Users: single host determines modes
                record.passkey_mode_available = record.host_id.passkey_enabled
                record.email_mode_available = record.host_id.enable_email_login
            elif record.host_ids:
                # User-to-Hosts: mode available if ANY selected host supports it
                record.passkey_mode_available = any(h.passkey_enabled for h in record.host_ids)
                record.email_mode_available = any(h.enable_email_login for h in record.host_ids)
            else:
                record.passkey_mode_available = False
                record.email_mode_available = False

    @api.depends('host_id', 'host_ids')
    def _compute_no_login_methods_error(self):
        for record in self:
            if record.host_id:
                record.no_login_methods_error = (
                    not record.host_id.passkey_enabled and
                    not record.host_id.enable_email_login
                )
            elif record.host_ids:
                # Error if NONE of the selected hosts have any login method
                record.no_login_methods_error = all(
                    not h.passkey_enabled and not h.enable_email_login
                    for h in record.host_ids
                )
            else:
                record.no_login_methods_error = False

    @api.model
    def default_get(self, fields_list):
        """Load default values from system parameters and set authorization mode"""
        defaults = super().default_get(fields_list)

        # Determine workflow from context
        host_id = self.env.context.get('default_host_id')
        user_id = self.env.context.get('default_user_id')

        if 'workflow' in fields_list:
            defaults['workflow'] = 'host_to_users' if host_id else 'user_to_hosts'

        # Set default authorization mode based on host config
        if 'authorization_mode' in fields_list:
            if host_id:
                host_obj = self.env['sunray.host'].browse(host_id)
                if host_obj.exists():
                    if host_obj.passkey_enabled:
                        defaults['authorization_mode'] = 'passkey'
                    elif host_obj.enable_email_login:
                        defaults['authorization_mode'] = 'email'
            elif user_id:
                # User-to-Hosts: default to email (most common multi-host use case)
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

    # ==========================================
    # Host-to-Users: Passkey (single user)
    # ==========================================

    def generate_token(self):
        """Generate and display setup token for a single user"""
        self.ensure_one()

        # In Host-to-Users workflow, user comes from passkey_user_ids
        if self.passkey_user_ids and not self.user_id:
            self.user_id = self.passkey_user_ids[0]

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
            'res_model': 'sunray.authorize.users.wizard',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
            'context': self.env.context,
        }

    # ==========================================
    # Host-to-Users: Passkey (multi-user)
    # ==========================================

    def _do_generate_tokens_for_users(self):
        """Generate setup tokens for multiple users on a single host.

        Returns:
            list of (token_obj, token_value) tuples for generated tokens.
            Also sets multi_operation_result and multi_operation_success.
        """
        self.ensure_one()

        if not self.passkey_user_ids:
            raise UserError('Please select at least one user.')

        if not self.host_id:
            raise UserError('Please select a host.')

        generated_tokens = []
        results = []
        skipped = []
        for user_obj in self.passkey_user_ids:
            if not self.host_id.passkey_enabled:
                skipped.append(f"{user_obj.username} — host does not support passkey")
                continue

            token_obj, token_value = self.env['sunray.setup.token'].create_setup_token(
                user_id=user_obj.id,
                host_id=self.host_id.id,
                device_name=self.device_name,
                validity_hours=self.validity_hours,
                max_uses=self.max_uses,
                allowed_cidrs=self.allowed_cidrs or ''
            )
            generated_tokens.append((token_obj, token_value))
            results.append(f"{user_obj.username} | {token_value}")

        # Build summary
        summary_lines = []
        if results:
            summary_lines.append(f"Host: {self.host_id.domain}")
            summary_lines.append(f"Tokens generated: {len(results)}")
            summary_lines.append("")
            summary_lines.extend(results)
        if skipped:
            summary_lines.append("")
            summary_lines.append("Skipped:")
            summary_lines.extend(skipped)

        self.multi_operation_result = '\n'.join(summary_lines)
        self.multi_operation_success = True
        return generated_tokens

    def action_generate_tokens_for_users(self):
        """Generate setup tokens for multiple users on a single host (passkey mode)"""
        self._do_generate_tokens_for_users()
        self.env.cr.commit()

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sunray.authorize.users.wizard',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
            'context': self.env.context,
        }

    # ==========================================
    # Host-to-Users: Email
    # ==========================================

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

        # Send toast notification and close wizard
        self.env.user.ik_notify('success', 'Users Authorized', '\n'.join(message_parts), sticky=False)

        # If welcome emails were sent, notify the admin
        if authorized_users and self.send_welcome_email:
            email_recipients = [u.email for u in authorized_users if u.email]
            if email_recipients:
                self.env.user.ik_notify('info', 'Emails Sent', f'Welcome emails sent to: {", ".join(email_recipients)}')

        return {'type': 'ir.actions.act_window_close'}

    # ==========================================
    # User-to-Hosts: Email
    # ==========================================

    def action_authorize_user_on_hosts(self):
        """Authorize a single user on multiple hosts (email mode, user-to-hosts workflow)"""
        self.ensure_one()

        if not self.host_ids:
            raise UserError('Please select at least one host.')
        if not self.user_id:
            raise UserError('Please select a user.')

        authorized_hosts = []
        already_authorized = []
        skipped_hosts = []

        for host_obj in self.host_ids:
            if not host_obj.enable_email_login:
                skipped_hosts.append(host_obj.domain)
                continue

            if self.user_id in host_obj.user_ids:
                already_authorized.append(host_obj.domain)
            else:
                host_obj.write({'user_ids': [(4, self.user_id.id)]})
                authorized_hosts.append(host_obj)

                self.env['sunray.audit.log'].create_admin_event(
                    event_type='host.user_authorized',
                    details={
                        'username': self.user_id.username,
                        'email': self.user_id.email,
                        'host': host_obj.domain,
                        'authorization_mode': 'email',
                    },
                    sunray_user_id=self.user_id.id,
                    username=self.user_id.username
                )

        # Send welcome emails if enabled
        if authorized_hosts and self.send_welcome_email:
            for host_obj in authorized_hosts:
                self._send_welcome_emails([self.user_id], host_obj)

        # Notification
        message_parts = []
        if authorized_hosts:
            domains = [h.domain for h in authorized_hosts]
            message_parts.append(f"Authorized on {len(authorized_hosts)} host(s): {', '.join(domains)}")
        if already_authorized:
            message_parts.append(f"Already authorized on: {', '.join(already_authorized)}")
        if skipped_hosts:
            message_parts.append(f"Skipped (email login not enabled): {', '.join(skipped_hosts)}")

        self.env.cr.commit()
        self.env.user.ik_notify('success', 'User Authorized', '\n'.join(message_parts), sticky=False)
        return {'type': 'ir.actions.act_window_close'}

    # ==========================================
    # User-to-Hosts: Passkey
    # ==========================================

    def _do_generate_tokens_for_hosts(self):
        """Generate setup tokens for a single user on multiple hosts.

        Returns:
            list of (token_obj, token_value) tuples for generated tokens.
            Also sets multi_operation_result and multi_operation_success.
        """
        self.ensure_one()

        if not self.host_ids:
            raise UserError('Please select at least one host.')
        if not self.user_id:
            raise UserError('Please select a user.')

        generated_tokens = []
        results = []
        skipped = []
        for host_obj in self.host_ids:
            if not host_obj.passkey_enabled:
                skipped.append(f"{host_obj.domain} — passkey not enabled")
                continue

            token_obj, token_value = self.env['sunray.setup.token'].create_setup_token(
                user_id=self.user_id.id,
                host_id=host_obj.id,
                device_name=self.device_name,
                validity_hours=self.validity_hours,
                max_uses=self.max_uses,
                allowed_cidrs=self.allowed_cidrs or ''
            )
            generated_tokens.append((token_obj, token_value))
            results.append(f"{host_obj.domain} | {token_value}")

        # Build summary
        summary_lines = []
        if results:
            summary_lines.append(f"User: {self.user_id.username}")
            summary_lines.append(f"Tokens generated: {len(results)}")
            summary_lines.append("")
            summary_lines.extend(results)
        if skipped:
            summary_lines.append("")
            summary_lines.append("Skipped:")
            summary_lines.extend(skipped)

        self.multi_operation_result = '\n'.join(summary_lines)
        self.multi_operation_success = True
        return generated_tokens

    def action_generate_tokens_for_hosts(self):
        """Generate setup tokens for a single user on multiple hosts (passkey mode)"""
        self._do_generate_tokens_for_hosts()
        self.env.cr.commit()

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sunray.authorize.users.wizard',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
            'context': self.env.context,
        }

    # ==========================================
    # Shared helpers
    # ==========================================

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
