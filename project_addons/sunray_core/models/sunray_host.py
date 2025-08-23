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
                raise ValidationError(f"WAF bypass revalidation period cannot exceed {max_revalidation} seconds")
    
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