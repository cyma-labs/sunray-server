# -*- coding: utf-8 -*-
from odoo import models, fields, api
import secrets


class SunrayApiKey(models.Model):
    _name = 'sunray.api.key'
    _description = 'API Key for Worker Authentication'
    _rec_name = 'name'
    _order = 'name'
    
    name = fields.Char(
        string='Name', 
        required=True,
        help='Descriptive name for this API key'
    )
    
    api_key_type = fields.Selection([
        ('worker', 'Worker'),
        ('admin', 'Administrative'),
        ('cli', 'CLI Tool'),
    ], string='Key Type',
        default='worker',
        required=True,
        help='Type of API key usage'
    )
    
    owner_name = fields.Char(
        string='Owner Name',
        help='Worker identifier for worker type, admin username for admin type, CLI user for cli type'
    )
    
    worker_id = fields.Many2one(
        'sunray.worker',
        string='Associated Worker',
        help='The worker that uses this API key (auto-populated)'
    )
    key = fields.Char(
        string='API Key', 
        required=False,  # Allow empty for auto-generation in GUI
        index=True,
        help='The API key value'
    )
    is_active = fields.Boolean(
        string='Active', 
        default=True,
        help='Deactivate to disable this API key'
    )
    description = fields.Text(
        string='Description',
        help='Purpose and usage of this API key'
    )
    scopes = fields.Text(
        string='Scopes',
        help='Permission scopes (e.g., config:read,user:write,session:all)',
        default='all'
    )
    
    # Display fields
    key_display = fields.Char(
        string='API Key',
        compute='_compute_key_display',
        help='Partial view of API key for security'
    )
    
    show_full_key = fields.Boolean(
        string='Show Full Key',
        default=False,
        help='Toggle to show full API key'
    )
    
    # Usage tracking
    last_used = fields.Datetime(
        string='Last Used',
        help='Last time this API key was used'
    )
    usage_count = fields.Integer(
        string='Usage Count', 
        default=0,
        help='Number of API calls made with this key'
    )
    
    _sql_constraints = [
        ('key_unique', 'UNIQUE(key)', 'API key must be unique!'),
        ('key_required', 'CHECK(key IS NOT NULL AND key != \'\')', 'API key cannot be empty!')
    ]
    
    @api.depends('key', 'show_full_key')
    def _compute_key_display(self):
        for record in self:
            if not record.key:
                record.key_display = ''
            elif record.show_full_key:
                record.key_display = record.key
            else:
                # Show first 8 and last 4 characters
                if len(record.key) > 16:
                    record.key_display = f"{record.key[:8]}...{record.key[-4:]}"
                else:
                    record.key_display = record.key[:4] + '...' if len(record.key) > 4 else record.key
    
    @api.model_create_multi
    def create(self, vals_list):
        """Override create to auto-generate key if not provided"""
        # Track which keys were auto-generated
        auto_generated = []
        for i, vals in enumerate(vals_list):
            if 'key' not in vals or not vals['key']:
                vals['key'] = self.generate_key()
                auto_generated.append(True)
            else:
                auto_generated.append(False)
            # Reset show_full_key to False for new records
            vals['show_full_key'] = False
            
            # Auto-populate owner_name for worker type if not provided
            if vals.get('api_key_type') == 'worker' and not vals.get('owner_name'):
                vals['owner_name'] = vals.get('name', '')
        
        # Create the records
        records = super().create(vals_list)
        
        # Log creation for each record
        for i, record in enumerate(records):
            self.env['sunray.audit.log'].create_admin_event(
                event_type='api_key.created',
                details={
                    'key_name': record.name,
                    'key_id': record.id,
                    'key_type': record.api_key_type,
                    'owner_name': record.owner_name,
                    'scopes': record.scopes,
                    'auto_generated': auto_generated[i]  # Track if auto-generated
                }
            )
        
        return records
    
    @api.model
    def generate_key(self):
        """Generate a secure API key"""
        return secrets.token_urlsafe(32)
    
    def regenerate_key(self):
        """Generate a new API key"""
        self.ensure_one()
        new_key = self.generate_key()
        
        # Log key regeneration
        self.env['sunray.audit.log'].create_admin_event(
            event_type='api_key.regenerated',
            details={'key_name': self.name}
        )
        
        self.write({
            'key': new_key,
            'show_full_key': True  # Show full key after regeneration
        })
        
        # Return notification
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Key Regenerated',
                'message': 'New API key generated. Copy it now as it won\'t be shown again in full.',
                'type': 'warning',
                'sticky': True,
            }
        }
    
    def track_usage(self, worker_name=None, ip_address=None):
        """Update usage statistics and auto-register worker if needed
        
        Args:
            worker_name: Optional worker identifier from X-Worker-ID header
            ip_address: Optional IP address of the requester
        """
        # Update usage stats
        self.write({
            'last_used': fields.Datetime.now(),
            'usage_count': self.usage_count + 1
        })
        
        # Auto-register worker if worker_name provided and this is a worker key
        if worker_name and self.api_key_type == 'worker':
            worker_obj = self.env['sunray.worker'].auto_register(
                worker_name=worker_name,
                api_key_obj=self,
                ip_address=ip_address
            )
            
            # Link this API key to the worker if not already linked
            if not self.worker_id and worker_obj:
                self.worker_id = worker_obj
                
                # Update owner_name if not set
                if not self.owner_name:
                    self.owner_name = worker_name
        
        return True
    
    def has_scope(self, required_scope):
        """Check if this API key has the required scope"""
        self.ensure_one()
        
        # 'all' scope grants everything
        if self.scopes == 'all':
            return True
        
        # Check if the required scope is in the key's scopes
        key_scopes = set(s.strip() for s in (self.scopes or '').split(','))
        
        # Check exact match
        if required_scope in key_scopes:
            return True
        
        # Check wildcard match (e.g., 'user:*' matches 'user:read')
        resource, action = required_scope.split(':', 1) if ':' in required_scope else (required_scope, '')
        for scope in key_scopes:
            if scope == f"{resource}:all" or scope == f"{resource}:*":
                return True
        
        return False
    
    def unlink(self):
        """Override unlink to audit API key deletion"""
        # Collect info before deletion
        for record in self:
            self.env['sunray.audit.log'].create_admin_event(
                event_type='api_key.deleted',
                details={
                    'key_name': record.name,
                    'key_id': record.id,
                    'was_active': record.is_active,
                    'usage_count': record.usage_count,
                    'last_used': record.last_used.isoformat() if record.last_used else None
                }
            )
        
        # Perform the deletion
        return super().unlink()