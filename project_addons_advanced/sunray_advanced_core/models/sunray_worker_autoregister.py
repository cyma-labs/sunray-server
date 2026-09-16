# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class SunrayWorkerAutoRegister(models.Model):
    """Extend sunray.worker with auto-registration and SCP configuration fields."""

    _inherit = 'sunray.worker'

    # Auto-register feature toggle
    auto_register_enabled = fields.Boolean(
        string='Enable Auto-Registration',
        default=False,
        help='Enable auto-registration of protected hosts for this worker'
    )

    # TODO: Convert to One2many through intermediate model with a sequence field
    #       to allow admin-controlled evaluation order (like access rules do).
    # SCP linking (Many2many for multi-SCP support)
    auto_register_scp_ids = fields.Many2many(
        'sunray.configuration_proxy',
        'sunray_worker_configuration_proxy_rel',
        'worker_id',
        'scp_id',
        string='Configuration Proxies',
        help='SCPs linked to this worker, evaluated alphabetically by name. '
             'First ACTIVE SCP whose fqdn_regex matches the incoming FQDN is used; '
             'disabled SCPs are skipped.'
    )

    auto_register_no_active_scp = fields.Boolean(
        string='Auto-Register Broken',
        compute='_compute_auto_register_status',
        help='True when auto-registration is enabled but no ACTIVE SCP is linked, '
             'so no host can ever be auto-registered by this worker. Covers both '
             'causes: no SCP linked at all, and every linked SCP disabled.'
    )
    auto_register_status = fields.Char(
        string='Auto-Register',
        compute='_compute_auto_register_status',
        help='One-line auto-registration readiness, for the worker list: whether '
             'it is on, and whether it can actually register anything.'
    )

    # Default configuration values for auto-registered hosts
    auto_register_session_duration_s = fields.Integer(
        string='Session Duration (seconds)',
        default=3600,
        help='Default session duration for auto-registered hosts'
    )
    auto_register_passkey_enabled = fields.Boolean(
        string='Enable Passkey Auth',
        default=False,
        help='Enable passkey authentication (False for v0 — email login only)'
    )
    auto_register_enable_email_login = fields.Boolean(
        string='Enable Email Login',
        default=True,
        help='Enable email OTP login for auto-registered hosts'
    )
    auto_register_email_login_session_duration_s = fields.Integer(
        string='Email Login Session Duration (seconds)',
        default=3600,
        help='Session duration for email-authenticated sessions'
    )
    auto_register_email_otp_validity_s = fields.Integer(
        string='Email OTP Validity (seconds)',
        default=300,
        help='OTP code validity duration'
    )
    auto_register_email_otp_resend_cooldown_s = fields.Integer(
        string='Email OTP Resend Cooldown (seconds)',
        default=60,
        help='Minimum delay between OTP resends'
    )
    auto_register_email_otp_max_attempts = fields.Integer(
        string='Email OTP Max Attempts',
        default=5,
        help='Max failed OTP validations before lockout'
    )

    # Remote Authentication defaults
    auto_register_remote_auth_enabled = fields.Boolean(
        string='Enable Remote Authentication',
        default=False,
        help='Enable remote authentication (mobile QR code) for auto-registered hosts'
    )
    auto_register_remote_auth_session_ttl = fields.Integer(
        string='Remote Auth Session Duration (seconds)',
        default=3600,
        help='Default remote session duration for auto-registered hosts'
    )
    auto_register_remote_auth_max_session_ttl = fields.Integer(
        string='Remote Auth Max Session Duration (seconds)',
        default=7200,
        help='Maximum remote session duration for auto-registered hosts'
    )

    # Session Management defaults
    auto_register_session_mgmt_enabled = fields.Boolean(
        string='Enable Session Management',
        default=True,
        help='Allow users to view/manage sessions on auto-registered hosts'
    )
    auto_register_session_mgmt_ttl = fields.Integer(
        string='Session Management Access Duration (seconds)',
        default=120,
        help='Session management access duration for auto-registered hosts'
    )

    # Deployment Mode defaults
    auto_register_deployment_mode = fields.Boolean(
        string='Enable Deployment Mode',
        default=False,
        help='Enable deployment mode for auto-registered hosts'
    )
    auto_register_deployment_session_ttl = fields.Integer(
        string='Deployment Session Duration (seconds)',
        default=7200,
        help='Deployment mode session TTL for auto-registered hosts'
    )

    # Default rules to prepend to SCP rules
    auto_register_default_rule_ids = fields.Many2many(
        'sunray.access.rule',
        'sunray_worker_default_rule_rel',
        'worker_id',
        'rule_id',
        string='Default Access Rules',
        help='Default rules prepended to SCP rules on every auto-registered host'
    )

    def find_matching_scp(self, fqdn):
        """Find the first *active* SCP whose fqdn_regex matches the given FQDN.

        Disabled SCPs are skipped. `is_active` is a plain Boolean here, not Odoo's
        magic `active` field, so nothing filters them out of the Many2many on its
        own: a SCP left disabled with an empty `fqdn_regex` (= match all) used to
        win over every active one and strand the host on a control plane that no
        longer manages it. Its own help text already says "Disable to stop syncing
        this SCP", so selecting one for auto-register contradicted the intent.

        Args:
            fqdn (str): Fully qualified domain name

        Returns:
            sunray.configuration_proxy: First matching active SCP, or False
        """
        for scp_obj in self.auto_register_scp_ids:
            if not scp_obj.match_fqdn(fqdn):
                continue
            if not scp_obj.is_active:
                # Warning, not debug: this SCP *would* have been selected, so it
                # is the only skip that changes the outcome. No audit event — the
                # caller is an auth='none' endpoint the worker polls every 5s, and
                # one audit row per request would flood the table. The standing
                # signal is auto_register_status / auto_register_no_active_scp,
                # shown in the worker list and on the worker form.
                _logger.warning(
                    "Worker %s: SCP '%s' matches %s but is disabled (is_active=False) "
                    "— skipped. Enable it, or link an active SCP to this worker.",
                    self.name, scp_obj.name, fqdn,
                )
                continue
            return scp_obj
        return False

    @api.depends('auto_register_enabled', 'auto_register_scp_ids',
                 'auto_register_scp_ids.is_active')
    def _compute_auto_register_status(self):
        """Say, in the worker list, whether auto-registration can do anything.

        Enabling auto-register without a usable SCP is silently inert: every
        unknown host is answered 404, the worker serves a 503, and nothing points
        at the worker. That is how a whole environment stopped registering hosts
        while its worker still looked fine in the list. The two causes read the
        same to a host and are reported separately here, because the fix differs:
        link a SCP, versus enable the one already linked.
        """
        for worker_obj in self:
            linked_scp_objs = worker_obj.auto_register_scp_ids
            active_scp_objs = linked_scp_objs.filtered('is_active')

            if not worker_obj.auto_register_enabled:
                worker_obj.auto_register_no_active_scp = False
                worker_obj.auto_register_status = 'Off'
            elif not linked_scp_objs:
                worker_obj.auto_register_no_active_scp = True
                worker_obj.auto_register_status = 'On — no SCP linked'
            elif not active_scp_objs:
                worker_obj.auto_register_no_active_scp = True
                worker_obj.auto_register_status = (
                    f'On — all {len(linked_scp_objs)} SCP(s) disabled'
                )
            else:
                worker_obj.auto_register_no_active_scp = False
                worker_obj.auto_register_status = ', '.join(
                    active_scp_objs.mapped('name')
                )
