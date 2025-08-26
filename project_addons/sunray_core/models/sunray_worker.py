# -*- coding: utf-8 -*-
from odoo import models, fields, api
from datetime import datetime, timedelta


class SunrayWorker(models.Model):
    _name = 'sunray.worker'
    _description = 'Sunray Worker Instance'
    _rec_name = 'name'
    _order = 'name'
    
    name = fields.Char(
        string='Worker Name',
        required=True,
        index=True,
        help='Unique identifier for this worker instance'
    )
    
    worker_type = fields.Selection([
        ('cloudflare', 'Cloudflare Worker'),
        ('kubernetes', 'Kubernetes ForwardAuth'),
        ('nginx', 'NGINX auth_request'),
        ('traefik', 'Traefik ForwardAuth'),
    ], string='Worker Type',
        default='cloudflare',
        required=True,
        help='Type of worker implementation'
    )
    
    worker_url = fields.Char(
        string='Worker URL',
        help='The worker\'s public URL endpoint'
    )
    
    api_key_id = fields.Many2one(
        'sunray.api.key',
        string='API Key',
        help='The API key this worker uses for authentication'
    )
    
    last_seen_ts = fields.Datetime(
        string='Last Seen',
        compute='_compute_last_seen',
        store=True,
        help='Last time this worker made an API call'
    )
    
    first_seen_ts = fields.Datetime(
        string='First Seen',
        readonly=True,
        help='First registration timestamp'
    )
    
    is_active = fields.Boolean(
        string='Active',
        default=True,
        help='Whether the worker is currently active'
    )
    
    host_ids = fields.One2many(
        'sunray.host',
        'sunray_worker_id',
        string='Protected Hosts',
        help='Hosts that this worker protects'
    )
    
    version = fields.Char(
        string='Version',
        help='Worker version (from X-Worker-Version header if provided)'
    )
    
    last_ip = fields.Char(
        string='Last IP Address',
        help='Last IP address the worker connected from'
    )
    
    # Statistics
    host_count = fields.Integer(
        string='Host Count',
        compute='_compute_host_count',
        store=True,
        help='Number of hosts this worker protects'
    )
    
    # Health check
    is_healthy = fields.Boolean(
        string='Healthy',
        compute='_compute_health',
        help='Worker health status based on last seen time'
    )
    
    health_status = fields.Char(
        string='Health Status',
        compute='_compute_health',
        help='Descriptive health status'
    )
    
    @api.depends('host_ids')
    def _compute_host_count(self):
        for record in self:
            record.host_count = len(record.host_ids)
    
    @api.depends('last_seen_ts')
    def _compute_health(self):
        """Compute worker health based on last seen time"""
        now = datetime.now()
        for record in self:
            if not record.last_seen_ts:
                record.is_healthy = False
                record.health_status = 'Never seen'
            else:
                time_diff = now - record.last_seen_ts
                if time_diff < timedelta(minutes=5):
                    record.is_healthy = True
                    record.health_status = 'Healthy'
                elif time_diff < timedelta(minutes=15):
                    record.is_healthy = True
                    record.health_status = 'Warning - No recent activity'
                else:
                    record.is_healthy = False
                    record.health_status = f'Offline - Last seen {self._format_time_ago(time_diff)}'
    
    def _format_time_ago(self, timedelta_obj):
        """Format timedelta to human readable string"""
        days = timedelta_obj.days
        hours = timedelta_obj.seconds // 3600
        minutes = (timedelta_obj.seconds % 3600) // 60
        
        if days > 0:
            return f'{days} day{"s" if days > 1 else ""} ago'
        elif hours > 0:
            return f'{hours} hour{"s" if hours > 1 else ""} ago'
        else:
            return f'{minutes} minute{"s" if minutes > 1 else ""} ago'
    
    @api.model
    def _compute_last_seen(self):
        """Compute last seen from audit logs"""
        for record in self:
            # Get the most recent audit log for this worker
            audit_log = self.env['sunray.audit.log'].search([
                ('details', 'ilike', f'"worker_id": {record.id}')
            ], order='create_date desc', limit=1)
            
            if audit_log:
                record.last_seen_ts = audit_log.create_date
    
    @api.model
    def auto_register(self, worker_name, api_key_obj, worker_type='cloudflare', 
                     version=None, ip_address=None):
        """Auto-register or update a worker when it makes an API call
        
        Args:
            worker_name: Worker identifier from X-Worker-ID header
            api_key_obj: The API key record being used
            worker_type: Type of worker (default: cloudflare)
            version: Worker version from X-Worker-Version header
            ip_address: IP address of the worker
            
        Returns:
            Worker record
        """
        # Look for existing worker
        worker_obj = self.search([('name', '=', worker_name)], limit=1)
        
        if not worker_obj:
            # Create new worker
            worker_obj = self.create({
                'name': worker_name,
                'worker_type': worker_type,
                'api_key_id': api_key_obj.id,
                'first_seen_ts': fields.Datetime.now(),
                'last_seen_ts': fields.Datetime.now(),
                'version': version,
                'last_ip': ip_address,
                'is_active': True
            })
            
            # Audit log the registration
            self.env['sunray.audit.log'].create_api_event(
                event_type='worker.registered',
                api_key_id=api_key_obj.id,
                details={
                    'worker_name': worker_name,
                    'worker_id': worker_obj.id,
                    'worker_type': worker_type,
                    'version': version,
                    'ip_address': ip_address
                },
                ip_address=ip_address
            )
        else:
            # Update existing worker
            update_vals = {
                'last_seen_ts': fields.Datetime.now(),
                'last_ip': ip_address,
                'is_active': True
            }
            
            # Update version if provided and different
            if version and version != worker_obj.version:
                update_vals['version'] = version
                
            # Update API key if different
            if api_key_obj.id != worker_obj.api_key_id.id:
                update_vals['api_key_id'] = api_key_obj.id
                
            worker_obj.write(update_vals)
        
        return worker_obj
    
    def force_cache_refresh(self):
        """Force cache refresh on all hosts protected by this worker"""
        self.ensure_one()
        
        if not self.host_ids:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'No Hosts',
                    'message': 'This worker does not protect any hosts.',
                    'type': 'warning',
                }
            }
        
        success_count = 0
        failed_hosts = []
        
        for host_obj in self.host_ids:
            try:
                host_obj.force_cache_refresh()
                success_count += 1
            except Exception as e:
                failed_hosts.append(f'{host_obj.name}: {str(e)}')
        
        if failed_hosts:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Cache Refresh Partial Success',
                    'message': f'Refreshed {success_count} hosts. Failed: {", ".join(failed_hosts)}',
                    'type': 'warning',
                    'sticky': True,
                }
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Cache Refreshed',
                    'message': f'Successfully refreshed cache for {success_count} host(s).',
                    'type': 'success',
                }
            }
    
    def action_view_hosts(self):
        """Open the hosts protected by this worker"""
        self.ensure_one()
        return {
            'name': f'Hosts protected by {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'sunray.host',
            'view_mode': 'list,form',
            'domain': [('sunray_worker_id', '=', self.id)],
            'context': {'default_sunray_worker_id': self.id}
        }
    
    @api.model
    def get_by_api_key(self, api_key_obj):
        """Get worker associated with an API key"""
        return self.search([('api_key_id', '=', api_key_obj.id)], limit=1)
    
    def action_clear_all_sessions_nuclear(self):
        """Nuclear option: Clear ALL user sessions across ALL hosts protected by this worker"""
        self.ensure_one()
        
        if not self.host_ids:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'No Protected Hosts',
                    'message': 'This worker does not protect any hosts.',
                    'type': 'info',
                }
            }
        
        # Count total active sessions across all hosts
        total_active_sessions = sum(len(host.active_session_ids) for host in self.host_ids)
        
        if total_active_sessions == 0:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'No Active Sessions',
                    'message': 'No active sessions found across all hosts protected by this worker.',
                    'type': 'info',
                }
            }
        
        try:
            # Use the first host to call the worker (all hosts share the same worker)
            first_host = self.host_ids[0]
            result = first_host._call_worker_cache_clear(
                scope='allusers-worker',
                target={},  # No target needed for allusers-worker scope
                reason=f'NUCLEAR: All sessions cleared on worker {self.name} by {self.env.user.name}'
            )
            
            # Mark all local sessions as inactive across all hosts
            all_active_sessions = self.env['sunray.session'].search([
                ('host_id', 'in', self.host_ids.ids),
                ('is_active', '=', True)
            ])
            
            all_active_sessions.write({
                'is_active': False,
                'revoked': True,
                'revoked_at': fields.Datetime.now(),
                'revoked_reason': f'NUCLEAR: All sessions cleared on worker {self.name}'
            })
            
            # Create critical audit log entry
            self.env['sunray.audit.log'].create_admin_event(
                event_type='cache.nuclear_clear',
                details={
                    'worker': self.name,
                    'worker_id': self.id,
                    'hosts_affected': len(self.host_ids),
                    'sessions_cleared': len(all_active_sessions),
                    'host_domains': self.host_ids.mapped('domain')
                },
                severity='critical'
            )
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'NUCLEAR CLEAR COMPLETE',
                    'message': f'Cleared {len(all_active_sessions)} active session(s) across {len(self.host_ids)} host(s). All users will need to re-authenticate on all protected applications.',
                    'type': 'warning',
                    'sticky': True,
                }
            }
        except Exception as e:
            _logger.error(f"Failed nuclear session clear for worker {self.name}: {str(e)}")
            raise UserError(f"Failed to perform nuclear session clear: {str(e)}")
    
    def action_force_config_refresh_all(self):
        """Force configuration refresh for ALL hosts protected by this worker"""
        self.ensure_one()
        
        if not self.host_ids:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'No Protected Hosts',
                    'message': 'This worker does not protect any hosts.',
                    'type': 'info',
                }
            }
        
        try:
            # Use the first host to call the worker (all hosts share the same worker)
            first_host = self.host_ids[0]
            result = first_host._call_worker_cache_clear(
                scope='config',
                target={},  # No target needed for config scope
                reason=f'Configuration refresh for all hosts on worker {self.name} by {self.env.user.name}'
            )
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Configuration Refresh Triggered',
                    'message': f'Configuration refresh triggered for all {len(self.host_ids)} host(s) protected by this worker. Changes will take effect within 60 seconds.',
                    'type': 'success',
                }
            }
        except Exception as e:
            _logger.error(f"Failed config refresh for worker {self.name}: {str(e)}")
            raise UserError(f"Failed to refresh configuration: {str(e)}")
    
    def get_migration_status(self):
        """Get migration status for this worker's hosts
        
        Returns:
            dict: Migration status information
        """
        self.ensure_one()
        
        pending_migrations = []
        recent_migrations = []
        
        for host_obj in self.host_ids:
            # Check for pending migrations
            if host_obj.pending_worker_name:
                pending_migrations.append({
                    'host': host_obj.domain,
                    'pending_worker': host_obj.pending_worker_name,
                    'requested_at': host_obj.migration_requested_at.isoformat() if host_obj.migration_requested_at else None,
                    'pending_duration': host_obj.migration_pending_duration
                })
            
            # Check for recent migrations (last 7 days)
            if host_obj.last_migration_ts:
                from datetime import timedelta
                seven_days_ago = fields.Datetime.now() - timedelta(days=7)
                if host_obj.last_migration_ts >= seven_days_ago:
                    recent_migrations.append({
                        'host': host_obj.domain,
                        'migrated_at': host_obj.last_migration_ts.isoformat()
                    })
        
        # Check for pending inbound migrations (hosts waiting for this worker)
        inbound_migrations = self.env['sunray.host'].search([
            ('pending_worker_name', '=', self.name)
        ])
        
        pending_inbound = []
        for host_obj in inbound_migrations:
            pending_inbound.append({
                'host': host_obj.domain,
                'current_worker': host_obj.sunray_worker_id.name if host_obj.sunray_worker_id else 'none',
                'requested_at': host_obj.migration_requested_at.isoformat() if host_obj.migration_requested_at else None,
                'pending_duration': host_obj.migration_pending_duration
            })
        
        return {
            'worker_name': self.name,
            'protected_hosts': len(self.host_ids),
            'pending_outbound': pending_migrations,
            'pending_inbound': pending_inbound,
            'recent_migrations': recent_migrations
        }
    
    def unlink(self):
        """Override unlink to audit worker deletion"""
        for record in self:
            # Check if worker has protected hosts
            if record.host_ids:
                raise models.ValidationError(
                    f'Cannot delete worker "{record.name}" because it protects {len(record.host_ids)} host(s). '
                    'Please reassign or remove the hosts first.'
                )
            
            # Audit log the deletion
            self.env['sunray.audit.log'].create_admin_event(
                event_type='worker.deleted',
                details={
                    'worker_name': record.name,
                    'worker_id': record.id,
                    'worker_type': record.worker_type,
                    'host_count': record.host_count,
                    'last_seen': record.last_seen_ts.isoformat() if record.last_seen_ts else None
                }
            )
        
        return super().unlink()