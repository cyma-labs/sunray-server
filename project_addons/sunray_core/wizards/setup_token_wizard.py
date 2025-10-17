# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError


class SetupTokenWizard(models.TransientModel):
    _name = 'sunray.setup.token.wizard'
    _description = 'Generate Setup Token'
    
    user_id = fields.Many2one(
        'sunray.user', 
        required=True,
        string='User'
    )
    host_id = fields.Many2one(
        'sunray.host',
        required=True,
        string='Protected Host',
        help='The host this token will grant access to'
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
        
        # Use centralized token creation method
        token_obj, token_value = self.env['sunray.setup.token'].create_setup_token(
            user_id=self.user_id.id,
            host_id=self.host_id.id,
            device_name=self.device_name,
            validity_hours=self.validity_hours,
            max_uses=self.max_uses,
            allowed_cidrs=self.allowed_cidrs or ''
        )
        
        # Prepare display instructions with improved formatting
        instructions = f"""
✅ Setup Token Generated Successfully!

🔑 TOKEN: {token_value}
👤 Username: {self.user_id.username}
🌐 Host: {self.host_id.domain}
📱 Device: {self.device_name}
⏰ Expires: {token_obj.expires_at}
🔢 Max Uses: {self.max_uses}

📋 INSTRUCTIONS:
1. COPY the token above (it's shown only once!)
2. Visit your protected application at {self.host_id.domain}
3. You'll be redirected to the Sunray setup page
4. Enter this token along with your username
5. Follow the passkey registration process

🔒 SECURITY NOTES:
• Token expires in {self.validity_hours} hours
• Can be used {self.max_uses} time(s)
• Only valid for {self.host_id.domain}
• Format: Groups of 5 characters separated by dashes for easy dictation
"""
        
        if self.allowed_cidrs:
            cidr_list = [cidr.strip() for cidr in self.allowed_cidrs.splitlines() if cidr.strip()]
            if cidr_list:
                instructions += f"• IP restriction: {', '.join(cidr_list)}\n"
        
        # Update wizard for display
        self.generated_token = token_value
        self.token_display = instructions
        
        # We commit now since user may be tempted to use token
        # while it is not commited. This would trigger an API Call 
        # from the worker which will fail and the worker cache 
        # will be set with no token !
        self.env.cr.commit()

        # Return wizard action to show the token
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sunray.setup.token.wizard',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
            'context': self.env.context,
        }