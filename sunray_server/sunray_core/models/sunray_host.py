# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError
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
    worker_url = fields.Char(
        string='Worker URL',
        required=True,
        help='Cloudflare Worker URL protecting this domain (e.g., https://sunray-worker.example.workers.dev)'
    )
    is_active = fields.Boolean(
        string='Is Sunray Active?', 
        default=True,
        help='When disabled, host becomes publicly accessible through Worker route (no authentication required)'
    )
    
    # Access Rules (new unified approach)
    access_rule_ids = fields.One2many(
        'sunray.access.rule',
        'host_id', 
        string='Access Rules'
    )
    
    
    # Webhook Authentication
    webhook_token_ids = fields.One2many(
        'sunray.webhook.token', 
        'host_id', 
        string='Webhook Tokens'
    )
    
    # Access control  
    user_ids = fields.Many2many(
        'sunray.user',
        'sunray_user_host_rel',
        'host_id',
        'user_id',
        string='Authorized Users'
    )
    
    # Session overrides
    session_duration_s = fields.Integer(
        string='Session Duration (seconds)',
        help='Session timeout in seconds. Examples:\n'
             '- 1h = 3600\n'
             '- 4h = 14400\n'
             '- 8h = 28800\n'
             '- 24h = 86400'
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
    waf_bypass_revalidation_minutes = fields.Integer(
        string='WAF Bypass Revalidation Period (minutes)',
        default=15,
        help='Force cookie revalidation after this period. '
             'Users must re-authenticate if their WAF bypass cookie is older than this. '
             'Shorter periods increase security but may require more frequent re-authentication.'
    )
    
    # Version tracking for cache invalidation
    config_version = fields.Datetime(
        string='Configuration Version',
        default=fields.Datetime.now,
        help='Timestamp of last configuration change, used for cache invalidation'
    )
    
    _sql_constraints = [
        ('domain_unique', 'UNIQUE(domain)', 'Domain must be unique!')
    ]
    
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
        """Generate exceptions tree for Worker using Access Rules
        
        Returns:
            list: Ordered list of access exceptions for worker evaluation
        """
        self.ensure_one()
        
        # Use Access Rules system
        return self.env['sunray.access.rule'].generate_exceptions_tree(self.id)
    
    
    def write(self, vals):
        """Override to update config_version on any change"""
        # Don't update version if we're only updating the version itself
        if vals and not (len(vals) == 1 and 'config_version' in vals):
            vals['config_version'] = fields.Datetime.now()
        return super().write(vals)
    
    def force_cache_refresh(self):
        """Trigger immediate cache refresh for this host via Worker API"""
        for record in self:
            try:
                # Call worker's cache invalidation endpoint
                record._call_worker_cache_invalidate(
                    scope='host',
                    target=record.domain,
                    reason=f'Manual refresh by {self.env.user.name}'
                )
                
                # Log the action
                self.env['sunray.audit.log'].create_admin_event(
                    event_type='cache_invalidation',
                    severity='info',
                    details=f'Cache refresh triggered for host {record.domain}',
                    admin_user_id=self.env.user.id
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
    
    def _call_worker_cache_invalidate(self, scope, target=None, reason=''):
        """Call Worker API to trigger cache invalidation"""
        self.ensure_one()
        
        if not self.worker_url:
            raise UserError(f"Worker URL not configured for host {self.domain}")
        
        # Get API key
        api_key_obj = self.env['sunray.api.key'].sudo().search([
            ('is_active', '=', True)
        ], limit=1)
        
        if not api_key_obj:
            raise UserError('No active API key found for Worker communication')
        
        # Call the worker's invalidation endpoint
        url = f"{self.worker_url}/sunray-wrkr/v1/cache/invalidate"
        headers = {
            'Authorization': f'Bearer {api_key_obj.key}',
            'Content-Type': 'application/json'
        }
        payload = {
            'scope': scope,
            'target': target,
            'reason': reason
        }
        
        _logger.info(f"Calling Worker cache invalidation: {url} with scope={scope}, target={target}")
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=5)
            response.raise_for_status()
            result = response.json()
            _logger.info(f"Worker cache invalidation successful: {result}")
            return result
        except requests.exceptions.RequestException as e:
            _logger.error(f"Worker cache invalidation failed: {str(e)}")
            raise UserError(f"Failed to trigger cache refresh: {str(e)}")