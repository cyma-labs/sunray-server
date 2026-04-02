# -*- coding: utf-8 -*-
import json
import re
import requests
import logging

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.addons.inouk_message_queue.api import processor_method

_logger = logging.getLogger(__name__)


class SunrayConfigurationProxy(models.Model):
    _name = 'sunray.configuration_proxy'
    _description = 'Sunray Configuration Proxy (SCP) — External API for auto-register'
    _order = 'name asc'

    name = fields.Char(
        string='Name',
        required=True,
        help='Display name for this SCP instance'
    )
    url = fields.Char(
        string='URL',
        required=True,
        help='Full HTTPS URL of the SCP API endpoint (e.g. https://host.example.com/inouk-scp/v1/)'
    )
    token = fields.Char(
        string='Bearer Token',
        help='Bearer token for SCP authentication (never logged or returned)',
    )
    fqdn_regex = fields.Char(
        string='FQDN Regex Pattern',
        help='Regex pattern to match FQDNs this SCP manages. Empty = match all'
    )
    is_active = fields.Boolean(
        string='Active',
        default=True,
        help='Disable to stop syncing this SCP'
    )

    # Relations
    host_ids = fields.One2many(
        'sunray.host',
        'scp_id',
        string='Managed Hosts',
        help='Protected hosts managed by this SCP'
    )
    user_ids = fields.Many2many(
        'sunray.user',
        'sunray_configuration_proxy_user_rel',
        'scp_id',
        'user_id',
        string='Managed Users',
        help='Users currently tracked as managed by this SCP'
    )
    access_rule_ids = fields.One2many(
        'sunray.access.rule',
        'scp_id',
        string='Created Rules',
        help='Access rules created by this SCP'
    )
    worker_ids = fields.Many2many(
        'sunray.worker',
        'sunray_worker_configuration_proxy_rel',
        'scp_id',
        'worker_id',
        string='Linked Workers',
        help='Workers using this SCP for auto-registration'
    )

    # Readonly status fields
    last_sync_ts = fields.Datetime(
        string='Last Sync',
        readonly=True,
        help='Timestamp of last successful SCP sync'
    )
    last_error = fields.Text(
        string='Last Error',
        readonly=True,
        help='Last error message from SCP call or sync'
    )

    # Computed fields
    host_count = fields.Integer(
        string='Host Count',
        compute='_compute_host_count',
        store=True,
        help='Number of hosts managed by this SCP'
    )
    user_count = fields.Integer(
        string='User Count',
        compute='_compute_user_count',
        help='Number of users managed by this SCP'
    )

    @api.depends('host_ids')
    def _compute_host_count(self):
        for scp in self:
            scp.host_count = len(scp.host_ids)

    @api.depends('user_ids')
    def _compute_user_count(self):
        for scp in self:
            scp.user_count = len(scp.user_ids)

    @api.onchange('url')
    def _onchange_url(self):
        if self.url and not self.url.endswith('/'):
            self.url = self.url + '/'

    def match_fqdn(self, fqdn):
        """Check if FQDN matches this SCP's regex pattern.

        Args:
            fqdn (str): Fully qualified domain name

        Returns:
            bool: True if regex matches or pattern is empty, False otherwise
        """
        if not self.fqdn_regex:
            return True
        try:
            return bool(re.fullmatch(self.fqdn_regex, fqdn))
        except re.error as e:
            _logger.error(f"Invalid regex in SCP {self.name}: {self.fqdn_regex} - {e}")
            return False

    def call_scp(self, fqdn=None):
        """Call the SCP API and return parsed JSON response.

        Args:
            fqdn (str, optional): Specific FQDN to query. If None, returns all hosts.

        Returns:
            dict: Parsed JSON response from SCP

        Raises:
            ValidationError: On HTTP error or invalid response
        """
        if not self.url:
            raise ValidationError("SCP URL is not configured")

        headers = {
            'Authorization': f'Bearer {self.token}',
            'Accept': 'application/json'
        }
        params = {}
        if fqdn:
            params['protected_host_fqdn'] = fqdn

        try:
            response = requests.get(
                self.url,
                headers=headers,
                params=params,
                timeout=30,
                verify=True
            )
            response.raise_for_status()
            data = response.json()
            _logger.info(
                f"{self.name}: SCP response ({response.status_code}) "
                f"for {'fqdn=' + fqdn if fqdn else 'all hosts'}: "
                f"{json.dumps(data, default=str)[:2000]}"
            )
            return data
        except requests.exceptions.RequestException as e:
            error_msg = f"SCP API call failed: {str(e)}"
            _logger.error(f"{self.name}: {error_msg}")
            self.sudo().last_error = error_msg
            raise ValidationError(error_msg)
        except ValueError as e:
            error_msg = f"Invalid JSON response from SCP: {str(e)}"
            _logger.error(f"{self.name}: {error_msg}")
            self.sudo().last_error = error_msg
            raise ValidationError(error_msg)

    @processor_method(queue_name='sunray')
    def setup_host_from_scp(self, fqdn, worker_id, _imq_logger=None):
        """Async IMQ job: Set up a protected host from SCP data.

        Finds the stub host created by the controller and updates it with
        full configuration from the SCP response.

        Args:
            fqdn (str): Fully qualified domain name of the host to set up
            worker_id (int): ID of the worker triggering the setup
        """
        self = self.sudo()  # Escalate to SUPERUSER — may be called from auth='none' context
        _task_logger = _imq_logger or _logger
        try:
            _task_logger.info(f"Setting up host {fqdn} from SCP {self.name}")
            # Find the stub host created by the controller
            host_obj = self.env['sunray.host'].search([
                ('domain', '=', fqdn),
                ('scp_id', '=', self.id),
            ], limit=1)

            if not host_obj:
                raise ValidationError(
                    f"Stub host for {fqdn} not found — expected controller to create it"
                )

            # Fetch SCP data for this specific FQDN
            scp_data = self.call_scp(fqdn=fqdn)

            # Find matching host in response
            host_data = None
            for h in scp_data.get('protected_hosts', []):
                if h.get('fqdn') == fqdn:
                    host_data = h
                    break

            if not host_data:
                raise ValidationError(f"FQDN {fqdn} not found in SCP response")

            # Get worker for defaults
            worker_obj = self.env['sunray.worker'].browse(worker_id)
            if not worker_obj.exists():
                raise ValidationError(f"Worker {worker_id} not found")

            # Update the stub host with SCP and worker defaults
            host_values = {
                'scp_sync_enabled': True,
                'backend_url': f'https://{fqdn}/',
                'is_active': True,
                'scp_setup_in_progress': False,
                'scp_last_sync_ts': fields.Datetime.now(),
                # Apply worker defaults
                'session_duration_s': worker_obj.auto_register_session_duration_s,
                'passkey_enabled': worker_obj.auto_register_passkey_enabled,
                'enable_email_login': worker_obj.auto_register_enable_email_login,
                'email_login_session_duration_s': worker_obj.auto_register_email_login_session_duration_s,
                'email_otp_validity_s': worker_obj.auto_register_email_otp_validity_s,
                'email_otp_resend_cooldown_s': worker_obj.auto_register_email_otp_resend_cooldown_s,
                'email_otp_max_attempts': worker_obj.auto_register_email_otp_max_attempts,
                # Remote auth defaults
                'remote_auth_enabled': worker_obj.auto_register_remote_auth_enabled,
                'remote_auth_session_ttl': worker_obj.auto_register_remote_auth_session_ttl,
                'remote_auth_max_session_ttl': worker_obj.auto_register_remote_auth_max_session_ttl,
                'session_mgmt_enabled': worker_obj.auto_register_session_mgmt_enabled,
                'session_mgmt_ttl': worker_obj.auto_register_session_mgmt_ttl,
                # Deployment mode defaults
                'deployment_mode': worker_obj.auto_register_deployment_mode,
                'deployment_session_ttl': worker_obj.auto_register_deployment_session_ttl,
            }

            # Store hash for change detection
            if host_data.get('hash'):
                host_values['scp_hash'] = host_data['hash']

            host_obj.write(host_values)

            # Create or update users from users[] list
            user_emails = {u['email']: u for u in scp_data.get('users', [])}
            new_user_ids = []
            for email, user_data in user_emails.items():
                user_obj = self._find_or_create_user(email, user_data.get('username', email))
                new_user_ids.append(user_obj.id)

            # Add users to scp.user_ids (additive — don't overwrite users from other hosts)
            self.user_ids = [(4, uid, 0) for uid in new_user_ids]

            # Assign allowed_users to host
            allowed_user_emails = host_data.get('allowed_users', [])
            allowed_user_ids = self.env['sunray.user'].sudo().search(
                [('email', 'in', allowed_user_emails)]
            ).ids
            host_obj.user_ids = [(6, 0, allowed_user_ids)]

            # Create access rules from SCP response
            self._create_rules_from_scp(host_obj, host_data, worker_obj)

            _task_logger.info(f"SCP {self.name}: Successfully set up host {fqdn}")

        except Exception as e:
            _task_logger.error(f"SCP {self.name}: Failed to set up host {fqdn}: {str(e)}")
            self.sudo().last_error = f"Host setup failed: {str(e)}"
            # Keep scp_setup_in_progress=True on the stub for retry/manual intervention

    def _find_or_create_user(self, email, username):
        """Find existing user by email, or create a new one.

        If username already exists with a different email, appends
        ' - SCP:<scp_id>' suffix to avoid unique constraint violation.

        Returns:
            sunray.user record
        """
        user_obj = self.env['sunray.user'].search(
            [('email', '=', email)], limit=1
        )
        if user_obj:
            user_obj.write({'is_active': True})
            return user_obj

        # Email not found — check if username is already taken
        existing = self.env['sunray.user'].search(
            [('username', '=', username)], limit=1
        )
        if existing:
            username = f"{username} - SCP:{self.id}"

        return self.env['sunray.user'].create({
            'email': email,
            'username': username,
            'is_active': True,
        })

    def _scp_rule_name(self, fqdn, sequence):
        """Build deterministic rule name in structured label notation.

        Format: scp{scp_id=<id>,fqdn="<fqdn>",seq=<sequence>}
        Parsable via regex: scp\\{scp_id=(\\d+),fqdn="([^"]+)",seq=(\\d+)\\}
        """
        return f'scp{{scp_id={self.id},fqdn="{fqdn}",seq={sequence}}}'

    def _upsert_scp_rule(self, fqdn, sequence, data):
        """Upsert a single SCP-managed access rule.

        Finds or creates a sunray.access.rule by deterministic name (scp_id + name).
        Updates content only if changed.

        Args:
            fqdn (str): FQDN of the protected host this rule belongs to
            sequence (int): Sequence number from SCP response
            data (dict): Rule data from SCP response with keys:
                - allowed_path_regexes (list[str])
                - allowed_cidrs (list[str])
                - allowed_tokens (list, currently unused)

        Returns:
            sunray.access.rule record (found or created)
        """
        rule_name = self._scp_rule_name(fqdn, sequence)
        access_type = self._infer_rule_type(data)
        url_patterns = '\n'.join(data.get('allowed_path_regexes', []))
        allowed_cidrs = '\n'.join(data.get('allowed_cidrs', []))

        rule_obj = self.env['sunray.access.rule'].search([
            ('scp_id', '=', self.id),
            ('name', '=', rule_name),
        ], limit=1)

        rule_vals = {
            'access_type': access_type,
            'url_patterns': url_patterns,
            'allowed_cidrs': allowed_cidrs,
            'is_active': True,
        }

        if rule_obj:
            if (rule_obj.access_type != access_type or
                    rule_obj.url_patterns != url_patterns or
                    rule_obj.allowed_cidrs != allowed_cidrs):
                rule_obj.write(rule_vals)
        else:
            rule_vals.update({'name': rule_name, 'scp_id': self.id})
            rule_obj = self.env['sunray.access.rule'].create(rule_vals)

        return rule_obj

    def _create_rules_from_scp(self, host_obj, host_data, worker_obj):
        """Upsert access rules from SCP host data and attach to host.

        Uses deterministic naming to find-or-create rules, avoiding orphans.
        Removes stale associations for rules no longer in the SCP response.

        Args:
            host_obj: sunray.host record to attach rules to
            host_data (dict): Host data from SCP response
            worker_obj: sunray.worker with default rules
        """
        scp_rule_names_in_response = set()
        priority = 100  # Start after worker defaults

        for rule_data in host_data.get('rules', []):
            seq = rule_data.get('sequence', priority)
            rule_obj = self._upsert_scp_rule(host_obj.domain, seq, rule_data)
            scp_rule_names_in_response.add(rule_obj.name)

            # Ensure association exists on this host
            assoc = self.env['sunray.host.access.rule'].search([
                ('host_id', '=', host_obj.id),
                ('rule_id', '=', rule_obj.id),
            ], limit=1)
            if not assoc:
                self.env['sunray.host.access.rule'].create({
                    'host_id': host_obj.id,
                    'rule_id': rule_obj.id,
                    'priority': priority,
                    'is_active': True,
                })
            priority += 100

        # Remove associations for SCP rules no longer in response
        stale_assocs = self.env['sunray.host.access.rule'].search([
            ('host_id', '=', host_obj.id),
            ('rule_id.scp_id', '=', self.id),
            ('rule_id.name', 'not in', list(scp_rule_names_in_response)),
        ])
        stale_assocs.unlink()

        # Prepend worker default rules
        if worker_obj and worker_obj.auto_register_default_rule_ids:
            default_priority = 1
            for default_rule in worker_obj.auto_register_default_rule_ids:
                assoc = self.env['sunray.host.access.rule'].search([
                    ('host_id', '=', host_obj.id),
                    ('rule_id', '=', default_rule.id),
                ], limit=1)
                if not assoc:
                    self.env['sunray.host.access.rule'].create({
                        'host_id': host_obj.id,
                        'rule_id': default_rule.id,
                        'priority': default_priority,
                        'is_active': True,
                    })
                default_priority += 1

    def _infer_rule_type(self, rule_data):
        """Infer access rule type from SCP rule data.

        Args:
            rule_data (dict): Rule data from SCP

        Returns:
            str: 'public', 'cidr', or 'token'
        """
        if rule_data.get('allowed_cidrs'):
            return 'cidr'
        elif rule_data.get('allowed_tokens'):
            return 'token'
        else:
            return 'public'

    def action_sync_now(self):
        """Manually trigger an immediate SCP sync via IMQ."""
        self.ensure_one()
        result = self.sync_scp_job.run_async(self)
        imq_message_id = result.get('id')
        if imq_message_id:
            self.env.user.ik_notify_with_link(
                'info',
                'SCP Sync launched',
                f'SCP sync job for "{self.name}" has been enqueued.',
                model='imq.message',
                res_id=imq_message_id,
                button_name='Open IMQ Message',
            )
        else:
            self.env.user.ik_notify(
                'warning',
                'Failed to launch SCP Sync',
                f'Could not enqueue sync job: {result}',
            )

    def sync_all_scp(self):
        """Called by cron: Enqueue one IMQ job per active unique SCP.

        This is a convenience method that collects unique active SCPs across all workers
        and enqueues a sync job for each one.
        """
        # Find all unique active SCPs
        scps_to_sync = self.env['sunray.configuration_proxy'].search([
            ('is_active', '=', True)
        ])

        for scp in scps_to_sync:
            scp.sync_scp_job.run_async(scp)

    @processor_method(queue_name='sunray')
    def sync_scp_job(self, _imq_logger=None):
        """Async IMQ job: Sync configuration for all hosts managed by this SCP.

        Handles user record sync, host user assignment, rule replacement, and
        unreachable SCP fallback.
        """
        self = self.sudo()  # Escalate to SUPERUSER — cron context may vary
        _task_logger = _imq_logger or _logger
        try:
            _task_logger.info(f"Starting sync for SCP {self.name}")
            # Fetch all hosts from SCP (no fqdn parameter)
            scp_response = self.call_scp()

            response_hosts = {h['fqdn']: h for h in scp_response.get('protected_hosts', [])}
            response_user_emails = {u['email']: u for u in scp_response.get('users', [])}
            _task_logger.info(
                f"SCP {self.name}: Received {len(response_hosts)} host(s), "
                f"{len(response_user_emails)} user(s) from API"
            )

            # === User Sync Phase ===
            # Capture ALL old SCP user IDs before update (needed for host-level sync)
            old_scp_user_ids = set(self.user_ids.ids)
            new_user_ids = []
            users_created = 0

            # Create or update users from response
            for email in response_user_emails.keys():
                user_obj = self._find_or_create_user(
                    email, response_user_emails[email].get('username', email)
                )
                new_user_ids.append(user_obj.id)
                if user_obj.id not in old_scp_user_ids:
                    users_created += 1

            # Track globally removed users (no longer in SCP at all)
            removed_user_ids = old_scp_user_ids - set(new_user_ids)

            # Update SCP's user_ids to the new set
            self.user_ids = [(6, 0, new_user_ids)]
            _task_logger.info(
                f"SCP {self.name}: User sync — {len(new_user_ids)} active, "
                f"{users_created} newly associated, {len(removed_user_ids)} removed"
            )

            # === Host and Rule Sync Phase ===
            hosts_synced = 0
            hosts_skipped = 0
            hosts_deactivated = 0

            # Detect hosts in SCP response not yet tracked in Sunray
            tracked_domains = set(self.host_ids.filtered(lambda h: h.scp_sync_enabled).mapped('domain'))
            new_domains = set(response_hosts.keys()) - tracked_domains
            if new_domains:
                _task_logger.info(
                    f"SCP {self.name}: New host(s) in SCP response (not yet tracked): "
                    f"{', '.join(sorted(new_domains))}"
                )

            for host_obj in self.host_ids.filtered(lambda h: h.scp_sync_enabled):
                if host_obj.domain not in response_hosts:
                    # Host no longer in SCP response
                    deactivated_users = host_obj.user_ids.mapped('email')
                    host_obj.write({
                        'is_active': False,
                        'scp_last_sync_ts': fields.Datetime.now(),
                    })
                    _task_logger.info(
                        f"SCP {self.name}: Host {host_obj.domain} deactivated — no longer in SCP response "
                        f"(had {len(deactivated_users)} user(s): {', '.join(deactivated_users)})"
                    )
                    hosts_deactivated += 1
                    continue

                host_data = response_hosts[host_obj.domain]

                # Check hash for change detection
                if host_obj.scp_hash and host_obj.scp_hash == host_data.get('hash'):
                    hosts_skipped += 1
                    continue

                # Sync user access: (current − old_scp_users) ∪ new_allowed
                # This removes ALL previously SCP-managed users from the host, then adds
                # back the ones in the new allowed list. Manually-added users (those not
                # in old_scp_user_ids) are preserved.
                new_allowed_emails = host_data.get('allowed_users', [])
                new_allowed_ids = self.env['sunray.user'].sudo().search(
                    [('email', 'in', new_allowed_emails)]
                ).ids

                current_user_ids = set(host_obj.user_ids.ids)
                synced_user_ids = (current_user_ids - old_scp_user_ids) | set(new_allowed_ids)
                host_obj.user_ids = [(6, 0, list(synced_user_ids))]

                # Log per-host user changes
                host_users_added = set(new_allowed_ids) - current_user_ids
                host_users_removed = (current_user_ids & old_scp_user_ids) - set(new_allowed_ids)
                if host_users_added or host_users_removed:
                    added_emails = self.env['sunray.user'].sudo().browse(list(host_users_added)).mapped('email') if host_users_added else []
                    removed_emails = self.env['sunray.user'].sudo().browse(list(host_users_removed)).mapped('email') if host_users_removed else []
                    _task_logger.info(
                        f"SCP {self.name}: Host {host_obj.domain} — "
                        f"users added: {', '.join(added_emails) or 'none'}, "
                        f"users removed: {', '.join(removed_emails) or 'none'}"
                    )

                # Sync rules (delete SCP-managed, recreate from response)
                self._create_rules_from_scp(host_obj, host_data, host_obj.sunray_worker_id)

                # Update hash and sync timestamp
                host_obj.write({
                    'scp_hash': host_data.get('hash'),
                    'scp_last_sync_ts': fields.Datetime.now(),
                })
                hosts_synced += 1

            _task_logger.info(
                f"SCP {self.name}: Host sync — {hosts_synced + hosts_skipped + hosts_deactivated} tracked, "
                f"{hosts_synced} updated, {hosts_skipped} unchanged, {hosts_deactivated} deactivated"
                + (f", {len(new_domains)} new (pending setup)" if new_domains else "")
            )

            # === Removed User Deactivation ===
            for user_id in removed_user_ids:
                user_obj = self.env['sunray.user'].sudo().browse(user_id)
                # Check if any other SCP references this user
                other_scp_count = self.env['sunray.configuration_proxy'].search_count([
                    ('id', '!=', self.id),
                    ('user_ids', 'in', user_id)
                ])
                if other_scp_count == 0:
                    user_obj.write({'is_active': False})
                    _task_logger.info(
                        f"SCP {self.name}: Deactivated user {user_obj.email} — "
                        f"no longer in any SCP's user list"
                    )

            # Update last sync timestamp
            self.write({
                'last_sync_ts': fields.Datetime.now(),
                'last_error': False,
            })

            _task_logger.info(
                f"SCP {self.name}: Sync completed — "
                f"Hosts: {hosts_synced} updated, {hosts_skipped} unchanged, {hosts_deactivated} deactivated | "
                f"Users: {users_created} new, {len(removed_user_ids)} removed"
            )

        except Exception as e:
            error_msg = f"Sync failed: {str(e)}"
            _task_logger.error(f"SCP {self.name}: {error_msg}")
            # TODO: fix me self.sudo().last_error = error_msg

            # Check if SCP is unreachable beyond cache duration
            cache_duration_s = int(
                self.env['ir.config_parameter'].sudo().get_param(
                    'sunray.auto_register_scp_cache_duration_s',
                    '43200'
                )
            )
            last_success = self.last_sync_ts
            if last_success:
                now = fields.Datetime.now()
                time_since_success = (now - last_success).total_seconds()
                if time_since_success > cache_duration_s:
                    # SCP unreachable too long, lockdown all managed hosts
                    self.host_ids.filtered(lambda h: h.scp_sync_enabled).write({
                        'block_all_traffic': True,
                    })
                    _task_logger.warning(
                        f"SCP {self.name}: Unreachable for {time_since_success}s (limit: {cache_duration_s}s), "
                        f"locked down {len(self.host_ids)} hosts"
                    )
