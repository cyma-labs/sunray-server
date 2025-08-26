# -*- coding: utf-8 -*-
from odoo import models, fields, api


class UserSessionsRevokeWizard(models.TransientModel):
    _name = 'sunray.user.sessions.revoke.wizard'
    _description = 'Revoke User Sessions Wizard'
    
    user_id = fields.Many2one(
        'sunray.user', 
        string='User',
        required=True, 
        readonly=True
    )
    host_id = fields.Many2one(
        'sunray.host',
        string='Host',
        readonly=True
    )
    worker_id = fields.Many2one(
        'sunray.worker',
        string='Worker',
        readonly=True
    )
    
    scope = fields.Selection([
        ('host', 'Specific Host'),
        ('worker', 'All Hosts on Worker')
    ], string='Scope', required=True, readonly=True)
    
    reason = fields.Text(
        string='Revocation Reason',
        required=True, 
        default='Admin revocation of user sessions',
        help='Provide a reason for revoking these sessions'
    )
    
    # Display fields for context
    user_name = fields.Char(
        string='Username',
        related='user_id.username',
        readonly=True
    )
    host_domain = fields.Char(
        string='Host Domain',
        related='host_id.domain',
        readonly=True
    )
    worker_name = fields.Char(
        string='Worker Name',
        related='worker_id.name',
        readonly=True
    )
    
    @api.model
    def default_get(self, fields_list):
        """Set default values based on context"""
        defaults = super().default_get(fields_list)
        
        if self.env.context.get('default_host_id'):
            defaults['scope'] = 'host'
        elif self.env.context.get('default_worker_id'):
            defaults['scope'] = 'worker'
            
        return defaults
    
    def action_revoke_sessions(self):
        """Revoke the user sessions based on scope"""
        self.ensure_one()
        
        if self.scope == 'host' and self.host_id:
            result = self.user_id.action_revoke_sessions_on_host(self.host_id.id)
        elif self.scope == 'worker' and self.worker_id:
            result = self.user_id.action_revoke_sessions_on_worker(self.worker_id.id)
        else:
            return {'type': 'ir.actions.act_window_close'}
        
        # Close the wizard and show the result notification
        if result.get('type') == 'ir.actions.client':
            result['params']['next'] = {'type': 'ir.actions.act_window_close'}
            return result
        else:
            return {'type': 'ir.actions.act_window_close'}