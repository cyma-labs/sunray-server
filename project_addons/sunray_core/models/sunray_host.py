# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
import json
import ipaddress
import re
import requests
import logging

_logger = logging.getLogger(__name__)


class SunrayHost(models.Model):
    _name = 'sunray.host'
    _description = 'Protected Host'
    _rec_name = 'domain'
    _order = 'domain'
    
    domain = fields.Char(
        string='Domain', 
        required=True, 
        index=True,
        help='Domain name to protect (e.g., app.example.com)'
    )
    backend_url = fields.Char(
        string='Backend URL', 
        required=True,
        help='Backend service URL to proxy requests to'
    )
    
    sunray_worker_id = fields.Many2one(
        'sunray.worker',
        string='Sunray Worker',
        help='Worker that protects this host. A host can be protected by only one worker, but a worker can protect several hosts.'
    )
    is_active = fields.Boolean(
        string='Active',
        default=True,
        help="Host lifecycle status. When false, host is deactivated/archived. "
             "Workers receive this flag and should return 503 Service Unavailable. "
             "Use for maintenance, decommissioning, or temporary host suspension."
    )

    block_all_traffic = fields.Boolean(
        string='Block Traffic',
        default=False,
        help='Security lockdown - block all traffic with 403 Forbidden. '
             'Use for security incidents or suspected compromise. '
             'When enabled, all requests return 403 regardless of authentication.'
    )
    
    # Access Rules (via association model for reusability)
    access_rule_rel_ids = fields.One2many(
        'sunray.host.access.rule',
        'host_id',
        string='Access Rule Associations'
    )
    
    # WebSocket URL Prefix (authenticated paths that upgrade to WebSocket protocol)
    websocket_url_prefix = fields.Char(
        string='WebSocket URL Prefix',
        default='',
        help='URL prefix for authenticated WebSocket connections (e.g., /ws/). '
             'Leave empty if no WebSocket support needed. '
             'All URLs starting with this prefix will be upgraded to WebSocket protocol after authentication. '
             'For unauthenticated WebSocket access, create a Public access rule instead.'
    )

    # Access control
    user_ids = fields.Many2many(
        'sunray.user',
        'sunray_user_host_rel',
        'host_id',
        'user_id',
        string='Authorized Users'
    )

    # User statistics report (auto-synced with user_ids)
    user_stat_ids = fields.One2many(
        'sunray.protected_host_user_list_report',
        'host_id',
        string='User Statistics',
        help='Statistics for each authorized user. Auto-synced when user_ids changes.'
    )
    
    # Session overrides
    session_duration_s = fields.Integer(
        string='Session Duration (seconds)',
        default=3600,
        help='Session timeout in seconds. Default: 1 hour (3600s).\n'
             'Examples:\n'
             '- 1h = 3600\n'
             '- 4h = 14400\n'
             '- 8h = 28800\n'
             '- 24h = 86400\n'
             'Min: 60s, Max: configured by system parameter'
    )
    
    # WAF integration
    bypass_waf_for_authenticated = fields.Boolean(
        string='Bypass Cloudflare WAF for Authenticated Users',
        default=False,
        help='Enable WAF bypass cookie for authenticated users. '
             'Creates hidden cookie with IP/UA binding that allows Cloudflare firewall rules '
             'to skip WAF processing. Worker still validates authentication for security. '
             'Requires manual Cloudflare firewall rule configuration.'
    )
    waf_bypass_revalidation_s = fields.Integer(
        string='WAF Bypass Revalidation Period (seconds)',
        default=900,
        help='Force cookie revalidation after this period. Default: 15 minutes (900s). '
             'Users must re-authenticate if their WAF bypass cookie is older than this. '
             'Shorter periods increase security but may require more frequent re-authentication. '
             'Min: 60s, Max: configured by system parameter'
    )
    
    # Version tracking for cache invalidation
    config_version = fields.Datetime(
        string='Configuration Version',
        default=fields.Datetime.now,
        help='Timestamp of last configuration change, used for cache invalidation'
    )
    
    # Active sessions
    active_session_ids = fields.One2many(
        'sunray.session',
        'host_id',
        string='Active Sessions',
        domain=[('is_active', '=', True)],
        help='Currently active user sessions on this host'
    )
    active_session_count = fields.Integer(
        string='Active Sessions Count',
        compute='_compute_active_session_count',
        help='Number of currently active sessions on this host'
    )
    active_user_count = fields.Integer(
        string='Active Users Count',
        compute='_compute_active_user_count',
        help='Number of active users authorized for this host'
    )
    
    # cURL helper fields
    server_curl_helper = fields.Text(
        string='Server cURL Helper',
        compute='_compute_server_curl_helper',
        readonly=True,
        help='cURL command to test Server API connectivity'
    )
    
    worker_curl_helper = fields.Text(
        string='Worker cURL Helper', 
        compute='_compute_worker_curl_helper',
        readonly=True,
        help='cURL command to test Worker status endpoint'
    )
    
    # Worker migration fields
    pending_worker_name = fields.Char(
        string='Pending Worker ID',
        help='Worker ID that will replace current worker on next registration. '
             'Used for controlled worker migration (e.g., scaling, version upgrade).'
    )
    migration_requested_at = fields.Datetime(
        string='Migration Requested At',
        readonly=True,
        help='Timestamp when pending worker was set. Helps track migration delays.'
    )
    last_migration_ts = fields.Datetime(
        string='Last Migration',
        readonly=True,
        help='Timestamp of the last successful worker migration for this host.'
    )
    migration_pending_duration = fields.Char(
        string='Migration Pending For',
        compute='_compute_migration_pending_duration',
        help='How long the migration has been pending (human-readable)'
    )
    
    _sql_constraints = [
        ('domain_unique', 'UNIQUE(domain)', 'Domain must be unique!')
    ]
    
    @api.constrains('session_duration_s')
    def _check_session_duration(self):
        """Validate session duration against system parameters"""
        max_duration = int(self.env['ir.config_parameter'].sudo().get_param(
            'sunray.max_session_duration_s', '86400'))
        for record in self:
            if record.session_duration_s < 60:
                raise ValidationError("Session duration must be at least 60 seconds (1 minute)")
            if record.session_duration_s > max_duration:
                raise ValidationError(f"Session duration cannot exceed {max_duration} seconds")
    
    @api.constrains('waf_bypass_revalidation_s')
    def _check_waf_bypass_revalidation(self):
        """Validate WAF bypass revalidation period against system parameters"""
        max_revalidation = int(self.env['ir.config_parameter'].sudo().get_param(
            'sunray.max_waf_bypass_revalidation_s', '3600'))
        for record in self:
            if record.waf_bypass_revalidation_s < 60:
                raise ValidationError("WAF bypass revalidation period must be at least 60 seconds (1 minute)")
            if record.waf_bypass_revalidation_s > max_revalidation:
                raise ValidationError(f"WAF bypass revalidation period cannot exceed {max_revalidation} seconds (cf. System Parameter 'sunray.max_waf_bypass_revalidation_s').")


    @api.depends('migration_requested_at')
    def _compute_migration_pending_duration(self):
        """Compute human-readable duration for pending migrations"""
        for record in self:
            if not record.migration_requested_at:
                record.migration_pending_duration = False
            else:
                now = fields.Datetime.now()
                delta = now - record.migration_requested_at
                record.migration_pending_duration = self._format_time_delta(delta)
    
    def _compute_active_session_count(self):
        """Compute the number of active sessions for this host"""
        for record in self:
            record.active_session_count = len(record.active_session_ids)
    
    def _compute_active_user_count(self):
        """Compute the number of active users authorized for this host"""
        for record in self:
            active_users = record.user_ids.filtered('is_active')
            record.active_user_count = len(active_users)
    
    def _format_time_delta(self, delta):
        """Format timedelta to human-readable string"""
        days = delta.days
        hours = delta.seconds // 3600
        minutes = (delta.seconds % 3600) // 60
        
        if days > 0:
            return f'{days} day{"s" if days > 1 else ""}, {hours} hour{"s" if hours != 1 else ""}'
        elif hours > 0:
            return f'{hours} hour{"s" if hours != 1 else ""}, {minutes} minute{"s" if minutes != 1 else ""}'
        else:
            return f'{minutes} minute{"s" if minutes != 1 else ""}'
    
    def _compute_server_curl_helper(self):
        """Generate cURL command for server API config endpoint"""
        # Get server URL from system parameter
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url', '')
        
        if not base_url:
            # If not set, provide instructions
            base_url = "https://YOUR_SERVER_URL"
        
        for record in self:
            api_key = "UNDEFINED_API_KEY"
            worker_id = "UNDEFINED_WORKER"
            
            # Get API key and worker ID from bound worker
            if record.sunray_worker_id and record.sunray_worker_id.api_key_id:
                api_key = record.sunray_worker_id.api_key_id.key
                worker_id = record.sunray_worker_id.name
            
            record.server_curl_helper = f'''curl -X GET "{base_url}/sunray-srvr/v1/config" \\
    -H "Authorization: Bearer {api_key}" \\
    -H "Content-Type: application/json" \\
    -H "X-Worker-ID: {worker_id}"'''

    def _compute_worker_curl_helper(self):
        """Generate cURL command for worker status endpoint"""
        for record in self:
            api_key = "UNDEFINED_API_KEY"
            
            # Get API key from bound worker
            if record.sunray_worker_id and record.sunray_worker_id.api_key_id:
                api_key = record.sunray_worker_id.api_key_id.key
            
            # Use the host's domain for the worker endpoint
            record.worker_curl_helper = f'''curl -X GET "https://{record.domain}/sunray-wrkr/v1/health" \\
    -H "Authorization: Bearer {api_key}" \\
    -H "Content-Type: application/json"'''

    def btn_refresh(self):
        pass

    def set_pending_worker(self, worker_name):
        """Set pending worker for migration
        
        Args:
            worker_name: The worker ID that will replace current worker
            
        Raises:
            ValidationError: If migration already pending or worker name invalid
        """
        self.ensure_one()
        
        if not worker_name or not worker_name.strip():
            raise ValidationError('Worker name cannot be empty')
            
        if self.pending_worker_name:
            raise ValidationError(
                f'Migration already pending to "{self.pending_worker_name}". '
                'Clear existing migration first.'
            )
        
        # Check if worker exists
        worker_obj = self.env['sunray.worker'].search([('name', '=', worker_name)], limit=1)
        if not worker_obj:
            # Allow setting pending worker even if not registered yet
            # This supports the workflow where admin sets pending before deploying
            pass
        
        self.write({
            'pending_worker_name': worker_name,
            'migration_requested_at': fields.Datetime.now()
        })
        
        # Audit log the migration request
        self.env['sunray.audit.log'].create_admin_event(
            event_type='worker.migration_requested',
            details={
                'host': self.domain,
                'current_worker': self.sunray_worker_id.name if self.sunray_worker_id else 'none',
                'pending_worker': worker_name,
                'host_id': self.id
            }
        )
    
    def clear_pending_worker(self):
        """Clear pending migration (cancel migration)"""
        self.ensure_one()
        
        if not self.pending_worker_name:
            raise ValidationError('No pending migration to clear')
        
        pending_worker = self.pending_worker_name
        
        self.write({
            'pending_worker_name': False,
            'migration_requested_at': False
        })
        
        # Audit log the migration cancellation
        self.env['sunray.audit.log'].create_admin_event(
            event_type='worker.migration_cancelled',
            details={
                'host': self.domain,
                'current_worker': self.sunray_worker_id.name if self.sunray_worker_id else 'none',
                'cancelled_worker': pending_worker,
                'host_id': self.id
            }
        )
    
    def action_clear_pending_migration(self):
        """UI action to clear pending migration"""
        self.ensure_one()
        
        if not self.pending_worker_name:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'No Pending Migration',
                    'message': 'There is no pending migration to clear.',
                    'type': 'info',
                }
            }
        
        try:
            pending_worker = self.pending_worker_name
            self.clear_pending_worker()
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Migration Cleared',
                    'message': f'Pending migration to "{pending_worker}" has been cleared.',
                    'type': 'success',
                }
            }
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error',
                    'message': f'Failed to clear pending migration: {str(e)}',
                    'type': 'danger',
                    'sticky': True,
                }
            }
    
    def _parse_line_separated_field(self, field_value):
        """Parse line-separated field with comment support
        
        Format:
        - One value per line
        - Lines starting with # are ignored (comments)
        - # can be used for inline comments
        
        Args:
            field_value: The raw field value to parse
            
        Returns:
            list: Array of parsed values
        """
        if not field_value:
            return []
        
        result = []
        for line in field_value.split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            # Remove inline comments
            if '#' in line:
                line = line.split('#')[0].strip()
            if line:
                result.append(line)
        return result
    
    def get_exceptions_tree(self):
        """Generate exceptions tree for Worker using Access Rule associations

        Returns:
            list: Ordered list of access exceptions for worker evaluation
        """
        self.ensure_one()

        # Get active associations (both rule and association must be active)
        associations = self.access_rule_rel_ids.filtered(
            lambda rel: rel.is_active and rel.rule_id.is_active
        ).sorted(key=lambda rel: (rel.priority, rel.id))

        exceptions_tree = []
        for assoc in associations:
            rule = assoc.rule_id
            # Get rule config without priority
            rule_config = rule.get_worker_config()

            # Inject priority from association
            rule_config['priority'] = assoc.priority

            # Only include rules with valid patterns
            if rule_config.get('url_patterns'):
                exceptions_tree.append(rule_config)

        return exceptions_tree
    
    def get_config_data(self):
        """Generate configuration data for API endpoints

        This method consolidates host configuration data generation used by
        multiple API endpoints (/config, /config/register, /config/<hostname>).

        Returns: List of host configuration dicts for all hosts (including inactive)

        Both is_active and block_traffic fields are included in all responses.
        Workers use these fields to decide how to handle requests:
        - is_active=False: Worker should return 503 Service Unavailable
        - block_traffic=True: Worker should return 403 Forbidden
        """
        if not self:
            return []

        # Return ALL hosts - workers need both is_active and block_traffic flags
        result = []
        for host_obj in self:
            config = {
                'id': host_obj.id,
                'domain': host_obj.domain,
                'is_active': host_obj.is_active,
                'block_traffic': host_obj.block_all_traffic,
                'backend': host_obj.backend_url,
                'nb_authorized_users': len(host_obj.user_ids.filtered(lambda u: u.is_active)),
                'session_duration_s': host_obj.session_duration_s,
                'websocket_url_prefix': host_obj.websocket_url_prefix,
                'exceptions_tree': host_obj.get_exceptions_tree(),
                'bypass_waf_for_authenticated': host_obj.bypass_waf_for_authenticated,
                'waf_bypass_revalidation_s': host_obj.waf_bypass_revalidation_s,
                'config_version': host_obj.config_version.isoformat() if host_obj.config_version else None,
                'worker_id': host_obj.sunray_worker_id.id if host_obj.sunray_worker_id else None,
                'worker_name': host_obj.sunray_worker_id.name if host_obj.sunray_worker_id else None,
            }
            result.append(config)
        return result

    @api.model
    def default_get(self, fields_list):
        """Override to add default access rules to new hosts"""
        defaults = super().default_get(fields_list)

        if 'access_rule_rel_ids' in fields_list:
            default_rules = self.env['sunray.access.rule'].search([
                ('is_default_rule', '=', True),
                ('is_active', '=', True)
            ], order='default_priority, id')

            rule_associations = []
            for rule in default_rules:
                rule_associations.append((0, 0, {
                    'rule_id': rule.id,
                    'priority': rule.default_priority,
                    'is_active': True
                }))

            if rule_associations:
                defaults['access_rule_rel_ids'] = rule_associations

        return defaults

    def write(self, vals):
        """Override to update config_version on any change and audit timing changes"""
        # Track timing field changes for audit logging
        for record in self:
            # Log session duration changes
            if 'session_duration_s' in vals and vals['session_duration_s'] != record.session_duration_s:
                old_value = record.session_duration_s or 'unset'
                new_value = vals['session_duration_s']
                self.env['sunray.audit.log'].create_admin_event(
                    event_type='config.session_duration_changed',
                    severity='info',
                    details=f'Session duration changed for host {record.domain}: {old_value}s → {new_value}s',
                    admin_user_id=self.env.user.id
                )
                
            # Log WAF revalidation period changes
            if 'waf_bypass_revalidation_s' in vals and vals['waf_bypass_revalidation_s'] != record.waf_bypass_revalidation_s:
                old_value = record.waf_bypass_revalidation_s or 'unset'
                new_value = vals['waf_bypass_revalidation_s']
                self.env['sunray.audit.log'].create_admin_event(
                    event_type='config.waf_revalidation_changed',
                    severity='info',
                    details=f'WAF bypass revalidation period changed for host {record.domain}: {old_value}s → {new_value}s',
                    admin_user_id=self.env.user.id
                )
                
            # Log lifecycle changes (is_active)
            if 'is_active' in vals and vals['is_active'] != record.is_active:
                if vals['is_active']:
                    event_type = 'host.activated'
                    severity = 'info'
                else:
                    event_type = 'host.deactivated'
                    severity = 'warning'
                self.env['sunray.audit.log'].create_admin_event(
                    event_type=event_type,
                    severity=severity,
                    details={
                        'host': record.domain,
                        'previous_state': 'is_active=True' if record.is_active else 'is_active=False',
                        'new_state': 'is_active=True' if vals['is_active'] else 'is_active=False',
                        'active_sessions': len(record.active_session_ids),
                        'authorized_users': len(record.user_ids),
                        'host_id': record.id
                    },
                    admin_user_id=self.env.user.id
                )

            # Log security lockdown changes (block_all_traffic)
            if 'block_all_traffic' in vals and vals['block_all_traffic'] != record.block_all_traffic:
                if vals['block_all_traffic']:
                    event_type = 'host.lockdown.activated'
                    severity = 'critical'
                else:
                    event_type = 'host.lockdown.cleared'
                    severity = 'warning'
                self.env['sunray.audit.log'].create_admin_event(
                    event_type=event_type,
                    severity=severity,
                    details={
                        'host': record.domain,
                        'previous_state': 'locked' if record.block_all_traffic else 'normal',
                        'new_state': 'locked' if vals['block_all_traffic'] else 'normal',
                        'active_sessions': len(record.active_session_ids),
                        'host_id': record.id
                    },
                    admin_user_id=self.env.user.id
                )
        
        # Don't update version if we're only updating the version itself
        if vals and not (len(vals) == 1 and 'config_version' in vals):
            vals['config_version'] = fields.Datetime.now()
        return super().write(vals)
    
    def force_cache_refresh(self):
        """Trigger immediate cache refresh for this host via Worker API"""
        for record in self:
            # Check if host is bound to a worker
            if not record.sunray_worker_id:
                raise UserError(f"Host {record.domain} is not yet bound to a worker. "
                               "Worker binding happens automatically when the worker first calls the API.")
            
            try:
                # Call worker's cache clear endpoint via protected host URL
                record._call_worker_cache_clear(
                    scope='host',
                    target={'hostname': record.domain},
                    reason=f'Manual refresh by {self.env.user.name}'
                )
                
                # Log the action
                self.env['sunray.audit.log'].create_audit_event(
                    event_type='cache.cleared',
                    severity='info',
                    details={
                        'scope': 'host',
                        'hostname': record.domain,
                        'operation': 'manual_host_cache_refresh',
                        'reason': f'Manual host cache refresh by {self.env.user.name}'
                    },
                    sunray_admin_user_id=self.env.user.id
                )
            except Exception as e:
                _logger.error(f"Failed to trigger cache refresh for host {record.domain}: {str(e)}")
                raise UserError(f"Failed to trigger cache refresh: {str(e)}")
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Cache Refresh Triggered',
                'message': f'Worker caches will refresh for {len(self)} host(s) within 60 seconds',
                'type': 'warning',
            }
        }
    
    def action_clear_all_sessions(self):
        """Clear all active sessions for this host (scope: allusers-protectedhost)"""
        self.ensure_one()
        
        if not self.sunray_worker_id:
            raise UserError(f"Host {self.domain} is not bound to a worker. "
                           "Worker binding happens automatically when the worker first calls the API.")
        
        active_sessions_count = len(self.active_session_ids)
        if active_sessions_count == 0:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'No Active Sessions',
                    'message': 'This host has no active sessions to clear.',
                    'type': 'info',
                }
            }
        
        try:
            # Call worker's cache clear endpoint for all users on this host
            result = self._call_worker_cache_clear(
                scope='allusers-protectedhost',
                target={'hostname': self.domain},
                reason=f'All sessions cleared by {self.env.user.name}'
            )
            
            # Mark local sessions as inactive
            self.active_session_ids.write({
                'is_active': False,
                'revoked': True,
                'revoked_at': fields.Datetime.now(),
                'revoked_reason': 'Bulk revocation - all sessions cleared on host'
            })
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'All Sessions Cleared',
                    'message': f'Successfully cleared {active_sessions_count} active session(s) for this host. Users will need to re-authenticate.',
                    'type': 'success',
                }
            }
        except Exception as e:
            _logger.error(f"Failed to clear all sessions for host {self.domain}: {str(e)}")
            raise UserError(f"Failed to clear sessions: {str(e)}")
    
    def _call_worker_cache_clear(self, scope, target=None, reason=''):
        """Call Worker API to trigger cache clearing using new cache/clear endpoint
        
        Args:
            scope: One of the 7 supported scopes:
                - user-session: Delete specific user session (requires hostname, username, sessionId)
                - user-protectedhost: Delete all sessions for user on host (requires username, hostname)  
                - user-worker: Delete all sessions for user across worker (requires username)
                - allusers-protectedhost: Delete all sessions on host (requires hostname)
                - allusers-worker: Delete ALL sessions across worker (no target needed)
                - host: Clear configuration for host (requires hostname)
                - config: Clear all configuration caches (no target needed)
            target: Target parameters dict based on scope
            reason: Reason for the cache clear operation
        """
        self.ensure_one()
        
        if not self.sunray_worker_id:
            raise UserError(f"Host {self.domain} is not bound to a worker")
        
        # Get the worker's API key
        api_key_obj = self.sunray_worker_id.api_key_id
        
        if not api_key_obj or not api_key_obj.is_active:
            raise UserError(f'No active API key found for worker {self.sunray_worker_id.name}')
        
        # Call the worker's cache clear endpoint using protected host URL
        # We use the protected host URL, not the worker.dev URL
        url = f"https://{self.domain}/sunray-wrkr/v1/cache/clear"
        headers = {
            'Authorization': f'Bearer {api_key_obj.key}',
            'Content-Type': 'application/json'
        }
        
        # Construct payload according to new API format
        payload = {
            'scope': scope,
            'reason': reason or f'Server-initiated cache clear for {scope}'
        }
        
        # Add target object if provided
        if target is not None:
            payload['target'] = target
        
        _logger.info(f"Calling Worker cache clear: {url} with scope={scope}, target={target}")
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            response.raise_for_status()
            result = response.json()
            _logger.info(f"Worker cache clear successful: {result}")
            
            # Log successful cache clear operation
            self.env['sunray.audit.log'].create_api_event(
                event_type='cache.cleared',
                api_key_id=api_key_obj.id,
                details={
                    'scope': scope,
                    'target': target,
                    'reason': reason,
                    'host': self.domain,
                    'worker': self.sunray_worker_id.name,
                    'cleared_items': result.get('cleared', [])
                },
                severity='info'
            )
            
            return result
        except requests.exceptions.RequestException as e:
            _logger.error(f"Worker cache clear failed: {str(e)}")
            
            # Log failed cache clear attempt
            self.env['sunray.audit.log'].create_api_event(
                event_type='cache.clear_failed',
                api_key_id=api_key_obj.id,
                details={
                    'scope': scope,
                    'target': target,
                    'reason': reason,
                    'host': self.domain,
                    'worker': self.sunray_worker_id.name,
                    'error': str(e)
                },
                severity='error'
            )
            
            raise UserError(f"Failed to clear worker cache: {str(e)}")
    
    
    def action_view_active_users(self):
        """Open list of active users authorized for this host"""
        self.ensure_one()
        
        action = self.env.ref('sunray_core.action_sunray_users').read()[0]
        action.update({
            'display_name': f'Active Users for {self.domain}',
            'domain': [('host_ids', 'in', [self.id])],
            'context': {
                'default_host_ids': [(4, self.id)],
                'default_is_active': True,
                'search_default_active': 1,  # Activate the 'Active' filter by default
            }
        })
        return action