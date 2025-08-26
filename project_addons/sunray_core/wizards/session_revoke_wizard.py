# -*- coding: utf-8 -*-
from odoo import models, fields, api


class SessionRevokeWizard(models.TransientModel):
    _name = 'sunray.session.revoke.wizard'
    _description = 'Revoke Session Wizard'
    
    session_id = fields.Many2one(
        'sunray.session', 
        string='Session',
        required=True, 
        readonly=True
    )
    reason = fields.Text(
        string='Revocation Reason',
        required=True, 
        default='Admin revocation',
        help='Provide a reason for revoking this session'
    )
    
    # Display fields for context
    user_name = fields.Char(
        string='User',
        related='session_id.user_id.username',
        readonly=True
    )
    host_domain = fields.Char(
        string='Host',
        related='session_id.host_id.domain',
        readonly=True
    )
    session_display = fields.Char(
        string='Session ID',
        related='session_id.session_id',
        readonly=True
    )
    
    def action_revoke(self):
        """Revoke the session with provided reason"""
        self.ensure_one()
        if not self.session_id:
            return {'type': 'ir.actions.act_window_close'}
            
        # Call the session's revoke method with the provided reason
        result = self.session_id.action_revoke_session(self.reason)
        
        # Close the wizard and show the result notification
        if result.get('type') == 'ir.actions.client':
            result['params']['next'] = {'type': 'ir.actions.act_window_close'}
            return result
        else:
            return {'type': 'ir.actions.act_window_close'}