# -*- coding: utf-8 -*-
import json
import re
import requests
import logging
import time
import traceback

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
    auto_lockdown_on_unreachable = fields.Boolean(
        string='Lockdown Hosts on Unreachable',
        default=False,
        help="When enabled, all managed hosts are locked (block_all_traffic=True) "
             "if SCP remains unreachable beyond scp_cache_duration_s."
    )
    scp_cache_duration_s = fields.Integer(
        string="Cache Duration (seconds)",
        help="Maximum time the SCP can be unreachable before the unreachable-lockdown "
             "mechanism kicks in (subject to auto_lockdown_on_unreachable). "
             "Default value is taken from system parameter "
             "sunray.auto_register_scp_cache_duration_s at creation time."
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

    @api.model
    def default_get(self, fields_list):
        defaults = super().default_get(fields_list)
        if 'scp_cache_duration_s' in fields_list:
            defaults['scp_cache_duration_s'] = int(
                self.env['ir.config_parameter'].sudo().get_param(
                    'sunray.auto_register_scp_cache_duration_s', '0'
                )
            )
        return defaults

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
        # Track current step for diagnostic logging in the except block.
        # Updated at every meaningful phase so a failure can pinpoint where.
        current_step = 'init'
        t_start = time.monotonic()
        try:
            _task_logger.info(
                f"===== setup_host_from_scp START — "
                f"fqdn={fqdn} scp={self.name} scp_id={self.id} worker_id={worker_id} ====="
            )

            # --- Step 1: Find the stub host created by the controller -----------
            current_step = 'stub_lookup'
            _task_logger.info(
                f"[stub_lookup] Searching stub host: "
                f"domain='{fqdn}' AND scp_id={self.id}"
            )
            host_obj = self.env['sunray.host'].search([
                ('domain', '=', fqdn),
                ('scp_id', '=', self.id),
            ], limit=1)

            if not host_obj:
                # Diagnostic: any host with this domain at all? Help admin understand
                # whether the stub was deleted, never created, or linked to a different SCP.
                any_with_domain = self.env['sunray.host'].search([('domain', '=', fqdn)])
                _task_logger.error(
                    f"[stub_lookup] No stub found for domain='{fqdn}' under scp_id={self.id}. "
                    f"Hosts with same domain (any SCP): "
                    f"{[(h.id, h.scp_id.id, h.is_active, h.scp_setup_in_progress) for h in any_with_domain]} "
                    f"(format: [(host_id, scp_id, is_active, setup_in_progress), ...])"
                )
                raise ValidationError(
                    f"Stub host for {fqdn} not found — expected controller to create it"
                )

            _task_logger.info(
                f"[stub_lookup] Stub found: id={host_obj.id} "
                f"is_active={host_obj.is_active} "
                f"scp_setup_in_progress={host_obj.scp_setup_in_progress} "
                f"scp_sync_enabled={host_obj.scp_sync_enabled} "
                f"sunray_worker_id={host_obj.sunray_worker_id.id}"
            )

            # --- Step 2: Fetch SCP data for this specific FQDN ------------------
            current_step = 'scp_call'
            _task_logger.info(
                f"[scp_call] Calling SCP {self.name} (url={self.url}) for fqdn={fqdn}"
            )
            scp_data = self.call_scp(fqdn=fqdn)
            response_hosts = scp_data.get('protected_hosts', []) or []
            response_users = scp_data.get('users', []) or []
            _task_logger.info(
                f"[scp_call] SCP response received: "
                f"{len(response_hosts)} host(s), {len(response_users)} user(s)"
            )

            # --- Step 3: Find matching host in response -------------------------
            current_step = 'fqdn_match'
            available_fqdns = [h.get('fqdn') for h in response_hosts]
            _task_logger.info(
                f"[fqdn_match] Searching '{fqdn}' in SCP response. "
                f"Available FQDNs: {available_fqdns}"
            )
            host_data = None
            for h in response_hosts:
                if h.get('fqdn') == fqdn:
                    host_data = h
                    break

            if not host_data:
                _task_logger.error(
                    f"[fqdn_match] FQDN '{fqdn}' NOT FOUND in SCP response. "
                    f"Available FQDNs were: {available_fqdns}"
                )
                raise ValidationError(f"FQDN {fqdn} not found in SCP response")

            _task_logger.info(
                f"[fqdn_match] Match found: fqdn='{fqdn}' "
                f"rules={len(host_data.get('rules', []) or [])} "
                f"allowed_users={len(host_data.get('allowed_users', []) or [])} "
                f"has_hash={bool(host_data.get('hash'))}"
            )

            # --- Step 4: Get worker for defaults --------------------------------
            current_step = 'worker_lookup'
            _task_logger.info(f"[worker_lookup] Looking up worker id={worker_id}")
            worker_obj = self.env['sunray.worker'].browse(worker_id)
            if not worker_obj.exists():
                _task_logger.error(
                    f"[worker_lookup] Worker id={worker_id} does not exist in database"
                )
                raise ValidationError(f"Worker {worker_id} not found")
            _task_logger.info(
                f"[worker_lookup] Worker found: id={worker_obj.id} name='{worker_obj.name}'"
            )

            # --- Step 5: Build host values + write ------------------------------
            current_step = 'host_write'
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

            _task_logger.info(
                f"[host_write] Writing {len(host_values)} field(s) on host id={host_obj.id}. "
                f"Key transitions: "
                f"is_active {host_obj.is_active}→{host_values['is_active']}, "
                f"scp_setup_in_progress {host_obj.scp_setup_in_progress}→"
                f"{host_values['scp_setup_in_progress']}, "
                f"scp_sync_enabled {host_obj.scp_sync_enabled}→{host_values['scp_sync_enabled']}"
            )
            host_obj.write(host_values)
            _task_logger.info(f"[host_write] write() returned (no exception raised)")

            # --- Step 6: Create or update users from users[] list ---------------
            current_step = 'user_sync'
            user_emails = {u['email']: u for u in response_users}
            _task_logger.info(
                f"[user_sync] Resolving {len(user_emails)} user(s) from SCP response: "
                f"{list(user_emails.keys())}"
            )
            new_user_ids = []
            for email, user_data in user_emails.items():
                user_obj = self._find_or_create_user(email, user_data.get('username', email))
                new_user_ids.append(user_obj.id)
            _task_logger.info(
                f"[user_sync] Resolved {len(new_user_ids)} sunray.user record(s) "
                f"(ids={new_user_ids}); linking to SCP {self.name} (additive)"
            )

            # Add users to scp.user_ids (additive — don't overwrite users from other hosts)
            self.user_ids = [(4, uid, 0) for uid in new_user_ids]

            # --- Step 7: Assign allowed_users to host ---------------------------
            current_step = 'host_user_assign'
            allowed_user_emails = host_data.get('allowed_users', []) or []
            _task_logger.info(
                f"[host_user_assign] SCP host_data allowed_users ({len(allowed_user_emails)}): "
                f"{allowed_user_emails}"
            )
            allowed_user_ids = self.env['sunray.user'].sudo().search(
                [('email', 'in', allowed_user_emails)]
            ).ids
            unresolved = set(allowed_user_emails) - set(
                self.env['sunray.user'].sudo().browse(allowed_user_ids).mapped('email')
            )
            if unresolved:
                _task_logger.warning(
                    f"[host_user_assign] {len(unresolved)} allowed_user email(s) could not be "
                    f"resolved to sunray.user records: {sorted(unresolved)}"
                )
            _task_logger.info(
                f"[host_user_assign] Assigning {len(allowed_user_ids)} user(s) to host "
                f"id={host_obj.id} (ids={allowed_user_ids})"
            )
            host_obj.user_ids = [(6, 0, allowed_user_ids)]

            # --- Step 8: Create access rules from SCP response ------------------
            current_step = 'rule_sync'
            _task_logger.info(
                f"[rule_sync] Creating/updating rules from SCP host_data "
                f"({len(host_data.get('rules', []) or [])} rule(s) in payload)"
            )
            rule_counts = self._create_rules_from_scp(host_obj, host_data, worker_obj)

            _task_logger.info(
                f"SCP {self.name}:\n"
                f"    Host {fqdn}\n"
                f"    rules:\n"
                f"       created:   {rule_counts['created']}\n"
                f"       updated:   {rule_counts['updated']}\n"
                f"       unchanged: {rule_counts['unchanged']}\n"
                f"       removed:   {rule_counts['removed']}\n"
                f"       total_now: {rule_counts['total']}"
            )

            current_step = 'success'
            elapsed_ms = int((time.monotonic() - t_start) * 1000)
            _task_logger.info(
                f"===== setup_host_from_scp END (success) — "
                f"fqdn={fqdn} duration={elapsed_ms}ms ====="
            )

        except Exception as e:
            elapsed_ms = int((time.monotonic() - t_start) * 1000)
            _task_logger.error(
                f"[FAILED at step='{current_step}'] SCP {self.name}: "
                f"Failed to set up host {fqdn} after {elapsed_ms}ms: {str(e)}"
            )
            _task_logger.error(f"Traceback:\n{traceback.format_exc()}")
            _task_logger.info(
                f"===== setup_host_from_scp END (failure at step='{current_step}') — "
                f"fqdn={fqdn} duration={elapsed_ms}ms ====="
            )
            self.sudo().last_error = (
                f"Host setup failed at step '{current_step}': {str(e)}"
            )
            # Keep scp_setup_in_progress=True on the stub for retry/manual intervention

    def _find_or_create_user(self, email, username):
        """Find existing user by email, or create a new one.

        If username already exists with a different email, appends
        ' - SCP:<scp_id>' suffix. If the suffixed username also exists
        (e.g. email changed in SCP), reuses that user record.

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
            suffixed = f"{username} - SCP:{self.id}"
            # Check if the SCP-suffixed username already exists (email changed in SCP)
            suffixed_user = self.env['sunray.user'].search(
                [('username', '=', suffixed)], limit=1
            )
            if suffixed_user:
                suffixed_user.write({'email': email, 'is_active': True})
                return suffixed_user
            username = suffixed

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
            Tuple of (sunray.access.rule record, status) where status is one of
            'created', 'updated', or 'unchanged'.
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
                return rule_obj, 'updated'
            return rule_obj, 'unchanged'

        rule_vals.update({'name': rule_name, 'scp_id': self.id})
        rule_obj = self.env['sunray.access.rule'].create(rule_vals)
        return rule_obj, 'created'

    def _create_rules_from_scp(self, host_obj, host_data, worker_obj):
        """Upsert access rules from SCP host data and attach to host.

        Uses deterministic naming to find-or-create rules, avoiding orphans.
        Removes stale associations for rules no longer in the SCP response.

        Args:
            host_obj: sunray.host record to attach rules to
            host_data (dict): Host data from SCP response
            worker_obj: sunray.worker with default rules

        Returns:
            dict: {'created', 'updated', 'unchanged', 'removed', 'total'} counters.
        """
        counts = {'created': 0, 'updated': 0, 'unchanged': 0, 'removed': 0, 'total': 0}
        scp_rule_names_in_response = set()
        priority = 100  # Start after worker defaults

        for rule_data in host_data.get('rules', []):
            seq = rule_data.get('sequence', priority)
            rule_obj, status = self._upsert_scp_rule(host_obj.domain, seq, rule_data)
            counts[status] += 1
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
        counts['removed'] = len(stale_assocs)
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

        # Total host.access.rule associations currently on this host (all sources)
        counts['total'] = self.env['sunray.host.access.rule'].search_count([
            ('host_id', '=', host_obj.id),
        ])
        return counts

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
        # Savepoint protects the transaction: if sync crashes (e.g. UniqueViolation),
        # the savepoint is rolled back and the except handler can still execute SQL
        # for lockdown, audit events, and last_error.
        sp = self.env.cr.savepoint(flush=True)
        try:
            _task_logger.info(f"===== SCP {self.name} sync START =====")
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
            rules_totals = {'created': 0, 'updated': 0, 'unchanged': 0, 'removed': 0}
            untracked_counts = {'new': 0, 'stub': 0, 'unlinked': 0}

            # Detect hosts in SCP response not yet tracked in Sunray
            tracked_domains = set(self.host_ids.filtered(lambda h: h.scp_sync_enabled).mapped('domain'))
            untracked_domains = sorted(set(response_hosts.keys()) - tracked_domains)
            if untracked_domains:
                # Classify each untracked FQDN by looking at existing sunray.host records
                classifications = []  # list of (fqdn, state, detail, host_data)
                for fqdn in untracked_domains:
                    existing = self.env['sunray.host'].search(
                        [('domain', '=', fqdn)], limit=1
                    )
                    hd = response_hosts[fqdn]
                    if not existing:
                        classifications.append((fqdn, 'NEW', '', hd))
                        untracked_counts['new'] += 1
                    elif (existing.scp_id.id == self.id
                          and getattr(existing, 'scp_setup_in_progress', False)):
                        classifications.append((fqdn, 'PENDING SETUP', '', hd))
                        untracked_counts['stub'] += 1
                    else:
                        scp_label = existing.scp_id.id or None
                        detail = (
                            f"scp_id={scp_label}, "
                            f"sync={bool(existing.scp_sync_enabled)}"
                        )
                        classifications.append((fqdn, 'UNLINKED', detail, hd))
                        untracked_counts['unlinked'] += 1

                header_lines = [
                    f"SCP {self.name}: {len(classifications)} untracked host(s) in SCP response:"
                ]
                for fqdn, state, detail, _hd in classifications:
                    tag = f"{state} ({detail})" if detail and state != 'UNLINKED' else state
                    header_lines.append(f"  - {fqdn} : {tag}")
                _task_logger.info("\n".join(header_lines))

                # Per-host detail block with rule/user counts from payload
                for fqdn, state, detail, hd in classifications:
                    n_rules = len(hd.get('rules', []) or [])
                    n_users = len(hd.get('allowed_users', []) or [])
                    if state == 'NEW':
                        _task_logger.info(
                            f"SCP {self.name}:\n"
                            f"     Host {fqdn} NEW — no host record in Sunray.\n"
                            f"     SCP response: {n_rules} rule(s), {n_users} user(s).\n"
                            f"     Skipped."
                        )
                    elif state == 'PENDING SETUP':
                        _task_logger.info(
                            f"SCP {self.name}:\n"
                            f"     Host {fqdn} PENDING SETUP — stub awaiting setup_host_from_scp.\n"
                            f"     SCP response: {n_rules} rule(s), {n_users} user(s).\n"
                            f"     Skipped."
                        )
                    else:  # UNLINKED
                        _task_logger.info(
                            f"SCP {self.name}:\n"
                            f"     Host {fqdn} : UNLINKED\n"
                            f"     reason: host exists but {detail}.\n"
                            f"     SCP payload ignored ({n_rules} rule(s), {n_users} user(s) in SCP response).\n"
                            f"     Admin must link/enable SCP sync manually."
                        )

            for host_obj in self.host_ids.filtered(lambda h: h.scp_sync_enabled):
                if host_obj.domain not in response_hosts:
                    # Host no longer in SCP response
                    deactivated_users = host_obj.user_ids.mapped('email')
                    host_obj.write({
                        'is_active': False,
                        'scp_last_sync_ts': fields.Datetime.now(),
                    })
                    if len(deactivated_users) > 1:
                        users_block = "\n".join(
                            f"      - {e}" for e in deactivated_users
                        )
                        _task_logger.info(
                            f"SCP {self.name}:\n"
                            f"    Host {host_obj.domain} : DEACTIVATED\n"
                            f"    no longer in SCP response "
                            f"(had {len(deactivated_users)} user(s)):\n{users_block}"
                        )
                    else:
                        inline = deactivated_users[0] if deactivated_users else 'none'
                        _task_logger.info(
                            f"SCP {self.name}:\n"
                            f"    Host {host_obj.domain} : DEACTIVATED\n"
                            f"    no longer in SCP response "
                            f"(had {len(deactivated_users)} user(s): {inline})"
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
                        f"SCP {self.name}:\n"
                        f"    Host {host_obj.domain}\n"
                        f"    users added: {', '.join(added_emails) or 'none'}\n"
                        f"    users removed: {', '.join(removed_emails) or 'none'}"
                    )
                else:
                    _task_logger.info(
                        f"SCP {self.name}:\n"
                        f"    Host {host_obj.domain}\n"
                        f"    users: no change ({len(synced_user_ids)} user(s))"
                    )

                # Sync rules (delete SCP-managed, recreate from response)
                rule_counts = self._create_rules_from_scp(
                    host_obj, host_data, host_obj.sunray_worker_id
                )
                for k in ('created', 'updated', 'unchanged', 'removed'):
                    rules_totals[k] += rule_counts[k]
                _task_logger.info(
                    f"SCP {self.name}:\n"
                    f"    Host {host_obj.domain}\n"
                    f"    rules:\n"
                    f"       created:   {rule_counts['created']}\n"
                    f"       updated:   {rule_counts['updated']}\n"
                    f"       unchanged: {rule_counts['unchanged']}\n"
                    f"       removed:   {rule_counts['removed']}\n"
                    f"       total_now: {rule_counts['total']}"
                )

                # Update hash and sync timestamp
                host_obj.write({
                    'scp_hash': host_data.get('hash'),
                    'scp_last_sync_ts': fields.Datetime.now(),
                })
                hosts_synced += 1

            _task_logger.info(
                f"SCP {self.name}: Host sync — "
                f"{hosts_synced + hosts_skipped + hosts_deactivated} tracked, "
                f"{hosts_synced} updated, {hosts_skipped} unchanged, "
                f"{hosts_deactivated} deactivated"
                + (
                    f" | Untracked: {untracked_counts['new']} NEW, "
                    f"{untracked_counts['stub']} PENDING SETUP, "
                    f"{untracked_counts['unlinked']} UNLINKED"
                    if untracked_domains else ""
                )
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
                f"Hosts: {hosts_synced} updated, {hosts_skipped} unchanged, "
                f"{hosts_deactivated} deactivated | "
                f"Users: {users_created} new, {len(removed_user_ids)} removed | "
                f"Rules: {rules_totals['created']} created, "
                f"{rules_totals['updated']} updated, "
                f"{rules_totals['removed']} removed "
                f"({rules_totals['unchanged']} unchanged) | "
                f"Untracked: {untracked_counts['new']} NEW, "
                f"{untracked_counts['stub']} PENDING SETUP, "
                f"{untracked_counts['unlinked']} UNLINKED"
            )
            _task_logger.info(f"===== SCP {self.name} sync END =====")
            sp.close(rollback=False)  # Release savepoint on success

        except Exception as e:
            # Rollback savepoint to recover from failed transaction state
            # (e.g. UniqueViolation puts PG into InFailedSqlTransaction).
            # After rollback, the transaction is clean and the handler can
            # execute SQL for lockdown, audit events, and last_error.
            sp.close(rollback=True)

            error_msg = f"Sync failed: {str(e)}"
            _task_logger.error(f"SCP {self.name}: {error_msg}")
            _task_logger.info(f"===== SCP {self.name} sync END (error) =====")
            self.last_error = error_msg

            # Check if SCP is unreachable beyond per-SCP cache duration
            cache_duration_s = self.scp_cache_duration_s
            last_success = self.last_sync_ts
            if last_success:
                now = fields.Datetime.now()
                time_since_success = (now - last_success).total_seconds()
                if time_since_success > cache_duration_s:
                    managed_hosts = self.host_ids.filtered(lambda h: h.scp_sync_enabled)
                    lockdown_enabled = self.auto_lockdown_on_unreachable

                    if lockdown_enabled:
                        message = (
                            f"Failed to reach SCP '{self.name}' for {int(time_since_success)}sec "
                            f"> scp_cache_duration_s = {cache_duration_s}. "
                            f"Locking down all hosts."
                        )
                        severity = 'critical'
                    else:
                        message = (
                            f"Failed to reach SCP '{self.name}' for {int(time_since_success)}sec "
                            f"> scp_cache_duration_s = {cache_duration_s}. "
                            f"Lockdown SKIPPED (auto_lockdown_on_unreachable=False)."
                        )
                        severity = 'warning'

                    self.env['sunray.audit.log'].sudo().create_audit_event(
                        event_type='scp.unreachable_lockdown',
                        severity=severity,
                        event_source='system',
                        details={
                            'message': message,
                            'scp_name': self.name,
                            'scp_id': self.id,
                            'time_unreachable_s': int(time_since_success),
                            'threshold_s': cache_duration_s,
                            'last_sync_ts': fields.Datetime.to_string(last_success),
                            'managed_host_count': len(managed_hosts),
                            'managed_host_ids': managed_hosts.ids,
                            'lockdown_enabled': lockdown_enabled,
                            'lockdown_applied': lockdown_enabled,
                            'sync_error': str(e),
                        },
                    )

                    if lockdown_enabled:
                        managed_hosts.write({'block_all_traffic': True})
                    _task_logger.warning(message)
