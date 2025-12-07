# -*- coding: utf-8 -*-
import logging

from datetime import date, timedelta
from odoo import models, fields, api
from odoo.exceptions import ValidationError

from odoo.addons.inouk_message_queue.api import processor_method

_logger = logging.getLogger(__name__)


SUNRAY_HOST_STATE_LIST = [
    ('archived', 'Archived'),
    ('unprotected', 'Unprotected'),
    ('locked', 'Locked'),
    ('deployment', 'Deployment'),
    ('protected', 'Protected'),
]

class SunrayHost(models.Model):
    """
    Extends sunray.host model with Remote Authentication configuration.
    This is a PAID feature available only in Sunray Advanced Core.
    """
    _inherit = 'sunray.host'

    # Deployment mode configuration fields
    deployment_mode = fields.Boolean(
        default=False,
        help="Enable deployment mode to allow temporary unverified access before go-live. "
             "When enabled with a future go-live date, users can authenticate with temporary "
             "sessions (shorter TTL) without passkeys. After go-live, passkey-only access is enforced. "
             "Use this during initial rollout to give users time to enroll their passkeys."
    )
    golive_date = fields.Date(
        string='Go Live Date',
        help='Admin activates deployment mode with a target go-live date, '
             'which modifies the authentication page behavior for all users '
             'attempting to access the Protected Host.'
    )

    state = fields.Selection(
        SUNRAY_HOST_STATE_LIST,
        string='State',
        compute='_compute_state',
        store=True,
        help='Host protection state:\n'
             '- Archived: Host is decommissioned (is_active=False)\n'
             '- Unprotected: Active host with no worker assigned\n'
             '- Locked: Security lockdown active (block_all_traffic=True)\n'
             '- Deployment: Deployment mode with future go-live date\n'
             '- Protected: Normal operation with worker assigned'
    )

    deployment_session_ttl = fields.Integer(
        string="Deployment Mode Session Duration (seconds)",
        default=7200,  # 2 hours
        help="Duration of unverified sessions created during deployment mode. "
             "Shorter sessions encourage users to enroll passkeys quickly."
    )

    days_until_golive = fields.Integer(
        string="Days Until Go-Live",
        compute='_compute_days_until_golive',
        store=False,
        help="Days remaining until deployment mode ends and passkey-only access begins"
    )


    # Remote Authentication configuration fields
    remote_auth_enabled = fields.Boolean(
        string='Enable Remote Authentication',
        default=False,
        help='Allow users to authenticate via mobile device QR code scanning'
    )

    remote_auth_session_ttl = fields.Integer(
        string='Default Remote Session Duration',
        default=3600,  # 1 hour
        help='Default duration for remote authentication sessions (in seconds)'
    )

    remote_auth_max_session_ttl = fields.Integer(
        string='Maximum Remote Session Duration',
        default=7200,  # 2 hours
        help='Maximum duration users can select for remote sessions (in seconds)'
    )

    # Session Management configuration
    session_mgmt_enabled = fields.Boolean(
        string='Enable Session Management',
        default=True,
        help='Allow users to view and terminate their active sessions'
    )

    session_mgmt_ttl = fields.Integer(
        string='Session Management Access Duration',
        default=120,  # 2 minutes
        help='How long session management access remains valid after passkey authentication (in seconds)'
    )

    @api.constrains('remote_auth_session_ttl', 'remote_auth_max_session_ttl')
    def _check_remote_auth_ttl(self):
        """
        Validate remote authentication TTL configuration.
        Ensures logical constraints are met for session durations.
        """
        for record in self:
            if record.remote_auth_enabled:
                # Check that default doesn't exceed maximum
                if record.remote_auth_session_ttl > record.remote_auth_max_session_ttl:
                    raise ValidationError(
                        "Default remote session duration cannot exceed maximum duration. "
                        f"Default: {record.remote_auth_session_ttl}s, Maximum: {record.remote_auth_max_session_ttl}s"
                    )

                # Check minimum values (5 minutes minimum)
                if record.remote_auth_session_ttl < 300:
                    raise ValidationError(
                        "Remote session duration must be at least 300 seconds (5 minutes)"
                    )

                # Check maximum cap (24 hours maximum)
                if record.remote_auth_max_session_ttl > 86400:
                    raise ValidationError(
                        "Maximum remote session duration cannot exceed 86400 seconds (24 hours)"
                    )

    @api.constrains('session_mgmt_ttl')
    def _check_session_mgmt_ttl(self):
        """
        Validate session management TTL configuration.
        Ensures the access duration is within reasonable bounds.
        """
        for record in self:
            if record.session_mgmt_enabled:
                # Check minimum (30 seconds)
                if record.session_mgmt_ttl < 30:
                    raise ValidationError(
                        "Session management access duration must be at least 30 seconds"
                    )

                # Check maximum (10 minutes)
                if record.session_mgmt_ttl > 600:
                    raise ValidationError(
                        "Session management access duration cannot exceed 600 seconds (10 minutes)"
                    )

    
    @api.depends('sunray_worker_id', 'is_active', 'block_all_traffic', 'access_rule_rel_ids',
                 'access_rule_rel_ids.is_active', 'access_rule_rel_ids.rule_id.is_active',
                 'golive_date', 'deployment_mode')
    def _compute_state(self):
        """Compute the host protection state based on configuration

        State logic:
        1. Archived: Host is not active (is_active=False)
        2. Unprotected: Active but no worker assigned
        3. Locked: Active with security lockdown (block_all_traffic=True)
        4. Deployment: deployment_mode enabled and (no golive_date OR future golive_date)
        5. Protected: All other cases with worker assigned
        """
        today = date.today()

        for record in self:
            if not record.is_active:
                record.state = 'archived'
            elif not record.sunray_worker_id:
                record.state = 'unprotected'
            elif record.block_all_traffic:
                record.state = 'locked'
            elif record.deployment_mode and (not record.golive_date or record.golive_date > today):
                record.state = 'deployment'
            else:
                record.state = 'protected'

    @api.depends('golive_date')
    def _compute_days_until_golive(self):
        """Calculate days until go-live date"""
        today = fields.Date.context_today(self)
        for record in self:
            if record.golive_date and record.state == 'deployment':
                delta = record.golive_date - today
                record.days_until_golive = max(0, delta.days)
            else:
                record.days_until_golive = 0

    @api.model
    def default_get(self, fields_list):
        defaults = super().default_get(fields_list)

        if 'deployment_mode' in fields_list:
            defaults['deployment_mode'] = True
            golive_days = self.env['ir.config_parameter'].sudo().get_param(
                'sunray.config_default_golive_period_duration_days'
            )
            if golive_days and 'golive_date' in fields_list:
                defaults['golive_date'] = fields.Datetime.now() + timedelta(days=int(golive_days))

        return defaults

    def get_deployment_mode_config(self):
        """Get deployment mode configuration for API responses"""
        self.ensure_one()
        return {
            'enabled': self.deployment_mode,
            'golive_date': self.golive_date.isoformat() if self.golive_date else None,
            'days_until_golive': self.days_until_golive,
            'session_ttl': self.deployment_session_ttl
        }

    @api.model
    def _cron_process_deployment_hosts(self):
        """Cron job to update host states when go-live dates pass

        This method is called daily to recalculate states for hosts
        where the go-live date has passed, transitioning them from
        'deployment' to 'protected' state.
        """
        self._process_deployment_hosts_batch.run_async(self)

    @processor_method('sunray')
    def _process_deployment_hosts_batch(self, _imq_logger=None):
        """Process a batch of hosts whose go-live date has passed.

        For each host still in 'deployment' state with a go-live date <= today,
        triggers the individual state recomputation and potential transition
        to 'protected'.
        """
        task_logger = _logger or _imq_logger

        today = date.today()
        deployment_host_objs = self.search([
            ('state', '=', 'deployment'),
            ('golive_date', '!=', False),
            ('golive_date', '<=', today)
        ])

        for host_obj in deployment_host_objs:
            host_obj.process_deployment_host.run_async(host_obj)

        return f"Updated {len(deployment_host_objs)} host(s) from deployment to protected state"

    @processor_method('sunray')
    def process_deployment_host(self, _imq_logger=None):
        """Process state transition for host '{0.name}'"""
        task_logger = _logger or _imq_logger

        self._compute_state()
        
        if self.state == 'protected':
            self.env['sunray.audit.log'].create_audit_event(
                event_type='host.golive_transition',
                severity='info',
                details={
                    'host': self.domain,
                    'golive_date': str(self.golive_date),
                    'previous_state': 'deployment',
                    'new_state': 'protected',
                    'message': f'Host {self.domain} transitioned from deployment to protected (go-live date reached)'
                }
            )

    def get_config_data(self):
        """ Overload to generate remote authentication and deployment mode configuration for this host .
        Used by the config API endpoint.

        :returns: super() list of host's dicts augmented with remote auth settings
        """
        host_config_list = super().get_config_data()

        # Get system parameters - NO DEFAULTS
        IrConfigParameter = self.env['ir.config_parameter'].sudo()

        polling_interval = IrConfigParameter.get_param('remote_auth.polling_interval')
        challenge_ttl = IrConfigParameter.get_param('remote_auth.challenge_ttl')

        if not polling_interval or not challenge_ttl:
            raise ValueError(
                "Missing required remote auth system parameters. "
                "Check ir.config_parameter for 'remote_auth.polling_interval' and 'remote_auth.challenge_ttl'"
            )

        for host_config_dict in host_config_list:
            host_obj = self.browse(host_config_dict['id'])
            # Validate host-specific configuration
            if host_obj.remote_auth_enabled:
                if not host_obj.remote_auth_session_ttl or not host_obj.remote_auth_max_session_ttl:
                    raise ValueError(
                        f"Missing remote auth TTL configuration for host {host_obj.domain}"
                    )

            host_config_dict['remote_auth'] = {
                'enabled': host_obj.remote_auth_enabled,
                'session_ttl': host_obj.remote_auth_session_ttl,
                'max_session_ttl': host_obj.remote_auth_max_session_ttl,
                'session_mgmt_enabled': host_obj.session_mgmt_enabled,
                'session_mgmt_ttl': host_obj.session_mgmt_ttl,
                'polling_interval': int(polling_interval),
                'challenge_ttl': int(challenge_ttl)
            }

            if 'domain' in host_config_dict:
                host_config_dict['deployment_mode'] = host_obj.get_deployment_mode_config()

        return host_config_list

    def get_remote_auth_config(self):
        """
        Get remote authentication configuration for this host.
        Used by the config API endpoint.

        :return: Dictionary with remote auth settings
        """
        self.ensure_one()

        # Get system parameters - NO DEFAULTS
        IrConfigParameter = self.env['ir.config_parameter'].sudo()

        polling_interval = IrConfigParameter.get_param('remote_auth.polling_interval')
        challenge_ttl = IrConfigParameter.get_param('remote_auth.challenge_ttl')

        if not polling_interval or not challenge_ttl:
            raise ValueError(
                "Missing required remote auth system parameters. "
                "Check ir.config_parameter for 'remote_auth.polling_interval' and 'remote_auth.challenge_ttl'"
            )

        # Validate host-specific configuration
        if self.remote_auth_enabled:
            if not self.remote_auth_session_ttl or not self.remote_auth_max_session_ttl:
                raise ValueError(
                    f"Missing remote auth TTL configuration for host {self.domain}"
                )

        return {
            'enabled': self.remote_auth_enabled,
            'session_ttl': self.remote_auth_session_ttl,
            'max_session_ttl': self.remote_auth_max_session_ttl,
            'session_mgmt_enabled': self.session_mgmt_enabled,
            'session_mgmt_ttl': self.session_mgmt_ttl,
            'polling_interval': int(polling_interval),
            'challenge_ttl': int(challenge_ttl)
        }