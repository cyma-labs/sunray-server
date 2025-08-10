# -*- coding: utf-8 -*-
from odoo import models, fields, api


class SunrayPasskey(models.Model):
    _name = 'sunray.passkey'
    _description = 'Sunray Passkey'
    _rec_name = 'name'
    _order = 'create_date desc'
    
    user_id = fields.Many2one(
        'sunray.user', 
        required=True, 
        ondelete='cascade',
        string='User'
    )
    credential_id = fields.Char(
        string='Credential ID', 
        required=True, 
        index=True,
        help='WebAuthn credential identifier'
    )
    public_key = fields.Text(
        string='Public Key', 
        required=True,
        help='WebAuthn public key in base64'
    )
    name = fields.Char(
        string='Device Name', 
        required=True,
        help='User-friendly name for this passkey'
    )
    last_used = fields.Datetime(
        string='Last Used',
        help='Last authentication timestamp'
    )
    backup_eligible = fields.Boolean(
        string='Backup Eligible',
        help='Whether this passkey is backed up in cloud'
    )
    backup_state = fields.Boolean(
        string='Backup State',
        help='Current backup status'
    )
    
    # Audit fields
    created_ip = fields.Char(
        string='Registration IP',
        help='IP address used during passkey registration'
    )
    created_user_agent = fields.Text(
        string='Registration User Agent',
        help='Browser user agent during registration'
    )
    
    _sql_constraints = [
        ('credential_unique', 'UNIQUE(credential_id)', 'Credential ID must be unique!')
    ]
    
    def revoke(self):
        """Revoke this passkey"""
        self.ensure_one()
        
        # Log the revocation
        self.env['sunray.audit.log'].create({
            'event_type': 'passkey.revoked',
            'user_id': self.user_id.id,
            'username': self.user_id.username,
            'details': f'{{"passkey_name": "{self.name}", "credential_id": "{self.credential_id}"}}'
        })
        
        # Delete the passkey
        self.unlink()
        
        return True