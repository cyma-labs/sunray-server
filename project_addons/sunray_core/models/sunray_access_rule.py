# -*- coding: utf-8 -*-
import json
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class SunrayAccessRule(models.Model):
    """Reusable Access Rule Library

    Access rules are now reusable components that can be applied to multiple hosts.
    Each host-rule association has its own priority and active status.
    """
    _name = 'sunray.access.rule'
    _description = 'Reusable Access Rule Library'

    name = fields.Char(
        string='Rule Name',
        required=True,
        index=True,
        help='Short name for this rule library (e.g., "GitLab Webhook", "Office Access", "Health Checks")'
    )

    description = fields.Text(
        string='Description',
        help='Detailed explanation of this rule and its purpose'
    )

    access_type = fields.Selection([
        ('public', 'Public Access'),
        ('cidr', 'IP/CIDR Access'),
        ('token', 'Token Access')
    ], string='Access Type', required=True, default='public',
       help='Type of access exception: public (no auth), CIDR (IP whitelist), or token (API/webhook). '
            'For authenticated WebSocket connections, configure WebSocket URLs on the host instead.')

    # URL Pattern Configuration
    url_patterns = fields.Text(
        string='URL Patterns',
        required=True,
        help='Regex patterns for URLs (one per line, # for comments)\n'
             'Examples:\n'
             '^/*  # This rule is the way to allow all requests!\n'
             '^/api/webhook\n'
             '^/public/.*\n'
             '^/health$\n'
             '^/ws/public  # For **unauthenticated WebSocket access ONLY**'
    )

    # CIDR Configuration (for cidr type)
    allowed_cidrs = fields.Text(
        string='Allowed CIDR Blocks',
        help='CIDR blocks or IP address for IP-based access (one per line, # for comments)\n'
             'Examples:\n'
             '192.168.1.0/24\n'
             '234.170.10.5\n'
             '234.170.10.5/32. # Same as IP\n'
    )

    parsed_allowed_cidrs = fields.Text(
        string="Parsed CIDRs",
        store=True,
        compute='compute_parsed_allowed_cidrs'
    )

    @api.depends('allowed_cidrs')
    def compute_parsed_allowed_cidrs(self):
        for record in self:
            _cidr_list = record.get_allowed_cidrs(format='json')
            record.parsed_allowed_cidrs = json.dumps(_cidr_list, indent=2)

    # Token Configuration (for token type)
    token_ids = fields.Many2many(
        'sunray.webhook.token',
        'sunray_access_rule_token_rel',
        'rule_id',
        'token_id',
        string='Authorized Tokens',
        help='Tokens that can access URLs matching this rule'
    )

    is_active = fields.Boolean(
        string='Active',
        default=True,
        help='Archive this rule to prevent it from being used on any host. '
             'Inactive rules cannot be attached to hosts.'
    )

    # Usage tracking
    host_association_ids = fields.One2many(
        'sunray.host.access.rule',
        'rule_id',
        string='Host Associations'
    )

    host_count = fields.Integer(
        string='Used by # Hosts',
        compute='_compute_usage',
        store=True
    )

    @api.depends('host_association_ids')
    def _compute_usage(self):
        """Compute number of hosts using this rule"""
        for rule in self:
            rule.host_count = len(rule.host_association_ids)

    @api.constrains('access_type', 'url_patterns', 'allowed_cidrs', 'token_ids')
    def _validate_access_rule(self):
        """Comprehensive validation of access rule configuration

        Validates all aspects of an access rule in a single pass for optimal performance:
        - URL patterns must exist and be valid
        - Type-specific requirements (CIDR blocks for cidr type, tokens for token type)
        """
        for rule in self:
            # URL patterns validation (required for all access types)
            patterns = rule.get_url_patterns()
            if not patterns:
                raise ValidationError("At least one valid URL pattern is required!")

            # Type-specific validation
            if rule.access_type == 'cidr' and not rule.allowed_cidrs:
                raise ValidationError("CIDR access type requires CIDR blocks to be specified!")

            if rule.access_type == 'token' and not rule.token_ids:
                raise ValidationError("Token access type requires at least one token to be selected!")

    def btn_refresh(self):
        """Refresh button action"""
        pass

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

    def get_url_patterns(self, format='json'):
        """Parse URL patterns from line-separated format

        Args:
            format: Output format ('json' returns list, future: 'txt', 'yaml')

        Returns:
            Parsed data in requested format
        """
        if format == 'json':
            return self._parse_line_separated_field(self.url_patterns)
        # Future formats can be added here
        else:
            raise ValueError(f"Unsupported format: {format}")

    def get_allowed_cidrs(self, format='json'):
        """Parse allowed CIDRs from line-separated format

        Args:
            format: Output format ('json' returns list, future: 'txt', 'yaml')

        Returns:
            Parsed data in requested format
        """
        if format == 'json':
            return self._parse_line_separated_field(self.allowed_cidrs)
        # Future formats can be added here
        else:
            raise ValueError(f"Unsupported format: {format}")

    def get_worker_config(self):
        """Generate worker configuration for this access rule

        Note: Priority is NOT included here - it's injected by the host
        when generating the exceptions tree from associations.

        Returns:
            dict: Worker configuration for this rule (without priority)
        """
        self.ensure_one()

        config = {
            'access_type': self.access_type,
            'description': self.description or self.name
        }

        # All access types use url_patterns
        if self.access_type in ['public', 'cidr', 'token']:
            config['url_patterns'] = self.get_url_patterns()

        # Type-specific configurations
        if self.access_type == 'cidr':
            config['allowed_cidrs'] = self.get_allowed_cidrs()

        elif self.access_type == 'token':
            config['tokens'] = []
            for token in self.token_ids.filtered('is_active'):
                if token.is_valid():
                    config['tokens'].append(token.get_extraction_config())

        return config

    def name_get(self):
        """Custom name display for better UX"""
        result = []
        for rule in self:
            name = f"{rule.name} ({rule.access_type})"
            result.append((rule.id, name))
        return result

    def action_view_hosts(self):
        """View hosts using this rule"""
        self.ensure_one()
        host_ids = self.host_association_ids.mapped('host_id').ids
        return {
            'name': f'Hosts Using: {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'sunray.host',
            'view_mode': 'list,form',
            'domain': [('id', 'in', host_ids)],
            'context': {'create': False}
        }

    def action_clone_rule(self):
        """Create a customized copy of this rule"""
        self.ensure_one()
        new_rule = self.copy({
            'name': f"{self.name} (Copy)",
            'description': f"Customized from: {self.name}\n\n{self.description or ''}"
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sunray.access.rule',
            'res_id': new_rule.id,
            'view_mode': 'form',
            'target': 'current',
            'context': {'create': True}
        }

    def unlink(self):
        """Prevent deletion of rules that are in use"""
        for rule in self:
            if rule.host_association_ids:
                host_list = ', '.join(rule.host_association_ids.mapped('host_id.domain'))
                raise ValidationError(
                    f"Cannot delete rule '{rule.name}' because it is used by {len(rule.host_association_ids)} host(s): "
                    f"{host_list}\n\n"
                    f"Please remove this rule from all hosts first, or archive it instead."
                )
        return super().unlink()
