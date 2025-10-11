import json
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class SunrayAccessRule(models.Model):
    _name = 'sunray.access.rule'
    _description = 'Sunray Access Rule'
    _rec_name = 'description'
    _order = 'priority, id'
    
    host_id = fields.Many2one(
        'sunray.host', 
        required=True, 
        ondelete='cascade',
        string='Host'
    )
    description = fields.Char(
        string='Description', 
        required=True,
        help='Descriptive name for this access rule (e.g., "GitLab Incoming Webhook for CI/CD")'
    )
    priority = fields.Integer(
        string='Priority',
        default=100,
        help='Lower number = higher priority. First matching rule wins.'
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
        help='Deactivate to temporarily disable this access rule'
    )
    
    # SQL constraints removed to allow Python constraints to provide better error handling
    # Unified Python constraint in _validate_access_rule() provides comprehensive validation
    # with user-friendly error messages and optimal performance
    
    @api.constrains('access_type', 'url_patterns', 'allowed_cidrs', 'token_ids', 'priority')
    def _validate_access_rule(self):
        """Comprehensive validation of access rule configuration
        
        Validates all aspects of an access rule in a single pass for optimal performance:
        - Priority must be positive
        - URL patterns must exist and be valid
        - Type-specific requirements (CIDR blocks for cidr type, tokens for token type)
        """
        for rule in self:
            # Priority validation
            if rule.priority <= 0:
                raise ValidationError("Priority must be positive!")
            
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

        Returns:
            dict: Worker configuration for this rule
        """
        self.ensure_one()

        config = {
            'priority': self.priority,
            'access_type': self.access_type,
            'description': self.description
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
    
    @api.model
    def generate_exceptions_tree(self, host_id):
        """Generate exceptions tree for a specific host
        
        Args:
            host_id: ID of the host to generate tree for
            
        Returns:
            list: Ordered list of exception rules for worker
        """
        rules = self.search([
            ('host_id', '=', host_id),
            ('is_active', '=', True)
        ], order='priority, id')
        
        exceptions_tree = []
        for rule in rules:
            rule_config = rule.get_worker_config()
            if rule_config['url_patterns']:  # Only include rules with valid patterns
                exceptions_tree.append(rule_config)
        
        return exceptions_tree
    
    def name_get(self):
        """Custom name display for better UX"""
        result = []
        for rule in self:
            name = f"[{rule.priority}] {rule.description} ({rule.access_type})"
            result.append((rule.id, name))
        return result
    
    def btn_refresh(self):
        pass