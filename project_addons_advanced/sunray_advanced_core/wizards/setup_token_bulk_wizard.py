from odoo import api, fields, models, _
from markupsafe import Markup


class SetupTokenBulkWizard(models.TransientModel):
    _name = 'sunray.setup.token.bulk.wizard'
    _description = "Generate Setup Token Bulk"

    user_ids = fields.Many2many('sunray.user', string="Users", required=True)
    user_count = fields.Integer(
        string="Number of Users",
        compute='_compute_user_count',
        readonly=True,
        store=False
    )
    ignored_user_ids = fields.Many2many(
        'sunray.user',
        'sunray_setup_token_bulk_wizard_ignored_user_rel',
        'wizard_id',
        'user_id',
        string="Ignored Users",
        compute='_compute_ignored_users',
        readonly=True,
        store=False,
        help="Users who already have a valid, unused setup token for this host"
    )
    ignored_user_count = fields.Integer(
        string="Ignored Users",
        compute='_compute_ignored_users',
        readonly=True,
        store=False
    )
    host_id = fields.Many2one('sunray.host', string="Host", required=True)
    validity_days = fields.Integer(
        string="Valid for (days)",
        default=1,
        required=True,
        help="Number of days the tokens will remain valid"
    )
    validity_hours = fields.Integer(
        string="Valid for (hours)",
        compute='_compute_validity_hours',
        readonly=True,
        store=True
    )
    max_uses = fields.Integer(string="Maximum Uses", default=1)

    token_name = fields.Char(
        string="Token Name",
        required=True,
        default="Initial Deployment",
        help="Same token name applied to all generated tokens"
    )
    access_rule_ids = fields.Many2many(
        'sunray.access.rule',
        string='Access Rules (CIDR)',
        domain=[('access_type', '=', 'cidr')],
        help='Select one or more CIDR access rules to combine their IP restrictions for all tokens'
    )
    allowed_cidrs = fields.Text(
        string='Allowed CIDRs (for all users, one per line)',
        help='Optional: IP restrictions applied to all tokens. Leave empty for no restriction.'
    )

    send_email = fields.Boolean(
        string='Email Setup Tokens',
        help='Send setup tokens to users by email (users without email will be skipped)'
    )

    force_regenerate = fields.Boolean(
        string='Force New Tokens for Ignored Users',
        default=False,
        help='Generate new tokens even for users who already have valid tokens (ignored users will receive new tokens)'
    )

    @api.onchange('access_rule_ids')
    def _onchange_access_rule_ids(self):
        """Populate allowed_cidrs by combining all selected access rules"""
        if self.access_rule_ids:
            all_cidrs = []
            for rule in self.access_rule_ids:
                cidrs = rule.get_allowed_cidrs()
                if cidrs:
                    all_cidrs.extend(cidrs)
            # Remove duplicates while preserving order
            unique_cidrs = []
            seen = set()
            for cidr in all_cidrs:
                if cidr not in seen:
                    unique_cidrs.append(cidr)
                    seen.add(cidr)
            self.allowed_cidrs = '\n'.join(unique_cidrs) if unique_cidrs else ''
        else:
            self.allowed_cidrs = ''

    @api.depends('validity_days')
    def _compute_validity_hours(self):
        """Convert validity_days to validity_hours"""
        for wizard in self:
            wizard.validity_hours = wizard.validity_days * 24

    @api.depends('user_ids')
    def _compute_user_count(self):
        """Compute the number of selected users"""
        for wizard in self:
            wizard.user_count = len(wizard.user_ids)

    @api.depends('user_ids', 'host_id')
    def _compute_ignored_users(self):
        """Compute users who already have passkeys or valid setup tokens for this host"""
        for wizard in self:
            ignored_users = self.env['sunray.user']

            if not wizard.host_id or not wizard.user_ids:
                wizard.ignored_user_ids = ignored_users
                wizard.ignored_user_count = 0
                continue

            host_obj = wizard.host_id._origin

            for user_obj in wizard.user_ids._origin:
                # Check if user already has a passkey for this host
                existing_passkey_obj = self.env['sunray.passkey'].search([
                    ('user_id', '=', user_obj.id),
                    ('host_domain', '=', host_obj.domain),
                ], limit=1)

                if existing_passkey_obj:
                    ignored_users |= user_obj
                    continue

                # Check if user has valid, unused setup token for this host
                valid_token_objs = self.env['sunray.setup.token'].search([
                    ('user_id', '=', user_obj.id),
                    ('host_id', '=', host_obj.id),
                    ('consumed', '=', False),
                    ('expires_at', '>', fields.Datetime.now()),
                ], limit=1)

                if valid_token_objs:
                    ignored_users |= user_obj

            wizard.ignored_user_ids = ignored_users
            wizard.ignored_user_count = len(ignored_users)

    @api.model
    def default_get(self, fields_list):
        """Set defaults: send_email from config, user_ids from context"""
        res = super(SetupTokenBulkWizard, self).default_get(fields_list)

        if 'user_ids' in fields_list:
            active_ids = self.env.context.get('active_ids', [])
            if active_ids:
                res['user_ids'] = [(6, 0, active_ids)]

        if 'send_email' in fields_list:
            send_email_default = self.env['ir.config_parameter'].sudo().get_param(
                'sunray.setup_token_send_email_default',
                'True'
            )
            res['send_email'] = send_email_default == 'True'

        return res

    def action_view_ignored_users(self):
        """Open list view of ignored users with breadcrumb"""
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': 'Ignored Users',
            'res_model': 'sunray.user',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.ignored_user_ids.ids)],
            'context': {'create': False},
            'flags': {'mode': 'readonly'},
        }

    def generate_tokens(self):
        """Generate tokens in bulk for all selected users"""
        self.ensure_one()

        tokens_created = 0
        users_skipped = 0
        emails_sent = 0
        emails_failed = 0

        if self.force_regenerate:
            users_to_process = self.user_ids
        else:
            users_to_process = self.user_ids - self.ignored_user_ids
            users_skipped = len(self.ignored_user_ids)

        for user_obj in users_to_process:
            # Use centralized token creation method (same as simple wizard)
            token_obj, token_value = self.env['sunray.setup.token'].create_setup_token(
                user_id=user_obj.id,
                host_id=self.host_id.id,
                device_name=self.token_name,
                validity_hours=self.validity_hours,
                max_uses=self.max_uses,
                allowed_cidrs=self.allowed_cidrs or ''
            )
            tokens_created += 1

            # Send email if requested
            if self.send_email:
                result = token_obj.send_token_email(token_value)
                if result['success']:
                    emails_sent += 1
                else:
                    emails_failed += 1

        # Commit (same reason as simple wizard - prevent worker cache issues)
        self.env.cr.commit()

        message = _('%s tokens generated') % tokens_created
        if self.force_regenerate and self.ignored_user_count > 0:
            message += _(', %s regenerated') % self.ignored_user_count
        elif users_skipped > 0:
            message += _(', %s skipped') % users_skipped
        if self.send_email:
            message += _(', %s emails sent') % emails_sent
            if emails_failed > 0:
                message += _(', %s failed') % emails_failed

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': message,
                'type': 'success' if (emails_failed == 0 and (self.force_regenerate or users_skipped == 0)) else 'warning',
                'sticky': (emails_failed > 0 or (not self.force_regenerate and users_skipped > 0)),
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }
