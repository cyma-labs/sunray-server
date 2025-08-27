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
    
    # WebAuthn rpId binding - CRITICAL for security
    host_domain = fields.Char(
        string='Registered Host Domain',
        required=False,  # Allow blank for existing records to force re-registration
        index=True,
        help='The host domain (rpId) this passkey is bound to per WebAuthn spec. Empty value means passkey needs re-registration to comply with WebAuthn security requirements.'
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
        self.env['sunray.audit.log'].create_user_event(
            event_type='passkey.revoked',
            details={
                'passkey_name': self.name,
                'credential_id': self.credential_id
            },
            sunray_user_id=self.user_id.id,
            username=self.user_id.username  # Keep for compatibility
        )
        
        # Delete the passkey
        self.unlink()
        
        return True