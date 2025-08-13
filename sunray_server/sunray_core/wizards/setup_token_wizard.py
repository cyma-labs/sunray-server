# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError
import secrets
import hashlib
import json
from datetime import timedelta


class SetupTokenWizard(models.TransientModel):
    _name = 'sunray.setup.token.wizard'
    _description = 'Generate Setup Token'
    
    user_id = fields.Many2one(
        'sunray.user', 
        required=True,
        string='User'
    )
    device_name = fields.Char(
        string='Device Name', 
        required=True,
        help='Name to identify the device this token is for'
    )
    validity_hours = fields.Integer(
        string='Valid for (hours)', 
        default=24,
        help='How long the token remains valid'
    )
    allowed_cidrs = fields.Text(
        string='Allowed CIDRs (one per line)',
        help='Optional: Restrict token to specific IP addresses or CIDR ranges'
    )
    max_uses = fields.Integer(
        string='Maximum Uses',
        default=1,
        help='Number of times this token can be used'
    )
    
    # Display fields
    generated_token = fields.Char(
        string='Generated Token',
        readonly=True
    )
    token_display = fields.Text(
        string='Setup Instructions',
        readonly=True
    )
    
    def generate_token(self):
        """Generate and display setup token"""
        self.ensure_one()
        
        # Generate secure token
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha512(token.encode()).hexdigest()
        
        # Parse allowed CIDRs
        cidr_list = []
        if self.allowed_cidrs:
            cidr_list = [cidr.strip() for cidr in self.allowed_cidrs.splitlines() if cidr.strip()]
        
        # Create token record
        setup_token_obj = self.env['sunray.setup.token'].create({
            'user_id': self.user_id.id,
            'token_hash': f'sha512:{token_hash}',
            'device_name': self.device_name,
            'expires_at': fields.Datetime.now() + timedelta(hours=self.validity_hours),
            'allowed_cidrs': self.allowed_cidrs,  # Store as text, not JSON
            'max_uses': self.max_uses
        })
        
        # Log event
        self.env['sunray.audit.log'].create({
            'event_type': 'token.generated',
            'user_id': self.user_id.id,
            'username': self.user_id.username,
            'details': json.dumps({
                'device_name': self.device_name,
                'validity_hours': self.validity_hours,
                'max_uses': self.max_uses
            })
        })
        
        # Prepare display instructions
        instructions = f"""
Setup Token Generated Successfully!

Token: {token}
Username: {self.user_id.username}
Device: {self.device_name}
Expires: {setup_token_obj.expires_at}
Max Uses: {self.max_uses}

Instructions:
1. Save this token securely - it will only be shown once
2. Visit your protected domain
3. You'll be redirected to the setup page
4. Enter this token along with your username
5. Follow the passkey registration process

Security Notes:
- This token expires in {self.validity_hours} hours
- It can be used {self.max_uses} time(s)
"""
        
        if cidr_list:
            instructions += f"- Restricted to IPs/CIDRs: {', '.join(cidr_list)}\n"
        
        # Update wizard for display
        self.generated_token = token
        self.token_display = instructions
        
        # Return wizard action to show the token
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sunray.setup.token.wizard',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
            'context': self.env.context,
        }