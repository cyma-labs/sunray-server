# -*- coding: utf-8 -*-
from odoo import models, fields, api
from datetime import timedelta
import json
import uuid


class SunrayAuditLog(models.Model):
    _name = 'sunray.audit.log'
    _description = 'Audit Log'
    _order = 'timestamp desc'
    _rec_name = 'event_type'
    
    # Using dedicated timestamp field for indexing and ordering performance
    timestamp = fields.Datetime(
        default=fields.Datetime.now, 
        index=True,
        required=True,
        string='Timestamp'
    )
    event_type = fields.Selection([
        # Authentication Events
        ('auth.success', 'Authentication Success'),
        ('auth.failure', 'Authentication Failure'),
        # Token Management Events
        ('token.generated', 'Token Generated'),
        ('token.consumed', 'Token Consumed'),
        ('token.cleanup', 'Token Cleanup'),
        # Passkey Events
        ('passkey.registered', 'Passkey Registered'),
        ('passkey.revoked', 'Passkey Revoked'),
        # Configuration Events
        ('config.fetched', 'Config Fetched'),
        ('config.host_fetched', 'Host Config Fetched'),
        ('config.fetched_invalid', 'Config fetched is Invalid'),
        ('config.session_duration_changed', 'Session Duration Changed'),
        ('config.waf_revalidation_changed', 'WAF Revalidation Changed'),
        # Session Management Events
        ('session.created', 'Session Created'),
        ('session.revoked', 'Session Revoked'),
        ('session.expired', 'Session Expired'),
        # Webhook Events
        ('webhook.used', 'Webhook Token Used'),
        ('webhook.regenerated', 'Webhook Token Regenerated'),
        # API Key Events
        ('api_key.created', 'API Key Created'),
        ('api_key.regenerated', 'API Key Regenerated'),
        ('api_key.deleted', 'API Key Deleted'),
        # Cache Events
        ('cache_invalidation', 'Cache Invalidation DEPRECATED'),  # Legacy event type
        ('cache.cleared', 'Cache Cleared'),
        ('cache.clear_failed', 'Cache Clear Failed'),
        ('cache.nuclear_clear', 'Nuclear Cache Clear'),
        # Session Events  
        ('session.revoked', 'Session Revoked'),
        ('session.bulk_revocation', 'Bulk Session Revocation'),
        # WAF Bypass Events
        ('waf_bypass.created', 'WAF Bypass Cookie Created'),
        ('waf_bypass.validated', 'WAF Bypass Validated'),
        ('waf_bypass.expired', 'WAF Bypass Expired'),
        ('waf_bypass.cleared', 'WAF Bypass Cleared'),
        ('waf_bypass.tamper.format', 'WAF Bypass Tamper: Invalid Format'),
        ('waf_bypass.tamper.hmac', 'WAF Bypass Tamper: HMAC Failed'),
        ('waf_bypass.tamper.session', 'WAF Bypass Tamper: Session Mismatch'),
        ('waf_bypass.tamper.ip_change', 'WAF Bypass Tamper: IP Changed'),
        ('waf_bypass.tamper.ua_change', 'WAF Bypass Tamper: User-Agent Changed'),
        ('waf_bypass.error', 'WAF Bypass Error'),
        ('waf_bypass.unknown', 'WAF Bypass Unknown'),
        # Worker Migration Events
        ('worker.registered', 'Worker Registered'),
        ('worker.re_registered', 'Worker Re-registered'),
        ('worker.host_bound', 'Worker Host Bound'),
        ('worker.migration_requested', 'Worker Migration Requested'),
        ('worker.migration_started', 'Worker Migration Started'),
        ('worker.migration_completed', 'Worker Migration Completed'),
        ('worker.migration_cancelled', 'Worker Migration Cancelled'),
        ('worker.registration_failed', 'Worker Registration Failed'),
        ('worker.registration_blocked', 'Worker Registration Blocked'),
        ('worker.registration_success', 'Worker Registration Success'),
        ('worker.deleted', 'Worker Deleted'),
        # Security Events
        ('security.alert', 'Security Alert'),
        ('security.cross_domain_session', 'Cross-Domain Session Attempt'),
        ('security.host_id_mismatch', 'Host ID Mismatch'),
        ('security.unmanaged_host_access', 'Unmanaged Host Access'),
        ('SESSION_FINGERPRINT_MISMATCH', 'Session Fingerprint Mismatch'),
        ('SESSION_IP_CHANGED', 'Session IP Changed'),
        ('SESSION_COUNTRY_CHANGED', 'Session Country Changed'),
        ('SESSION_VALIDATION_FAILED', 'Session Validation Failed'),
    ], required=True, string='Event Type')
    
    # User tracking fields - supports three types of actors
    sunray_admin_user_id = fields.Many2one(
        'res.users',
        string='Admin User',
        help='Admin/operator who performed the action'
    )
    sunray_user_id = fields.Many2one(
        'sunray.user',
        string='Sunray User',
        help='End user affected by the action'
    )
    sunray_worker = fields.Char(
        string='Worker ID',
        help='Cloudflare Worker identification (from X-Worker-ID header)'
    )
    
    # Backward compatibility - keep for deleted users
    username = fields.Char(
        string='Username',
        help='Store even if user deleted'
    )
    
    # Request correlation
    request_id = fields.Char(
        string='Request ID',
        index=True,
        help='CF-Ray ID or generated UUID for request correlation'
    )
    event_source = fields.Selection([
        ('api', 'REST API'),
        ('ui', 'Odoo UI'),
        ('worker', 'Cloudflare Worker'),
        ('cli', 'Command Line'),
        ('system', 'System/Cron')
    ], string='Event Source', help='Where the event originated')
    
    # Network and context information
    ip_address = fields.Char(string='IP Address')
    user_agent = fields.Text(string='User Agent')
    details = fields.Text(
        string='Details',
        help='JSON field for extra data'
    )
    
    # Severity for security events
    severity = fields.Selection([
        ('info', 'Info'),
        ('warning', 'Warning'),
        ('error', 'Error'),
        ('critical', 'Critical')
    ], default='info', string='Severity')
    
    @api.model_create_multi
    def create(self, vals_list):
        """Override create to auto-populate request_id from context
        
        Handles both single record and batch creation properly for Odoo 18
        """
        # Ensure vals_list is always a list for batch processing
        if isinstance(vals_list, dict):
            vals_list = [vals_list]
        
        # Process each record in the batch
        for vals in vals_list:
            # Auto-populate request_id from context if not provided
            if 'request_id' not in vals:
                vals['request_id'] = self.env.context.get('sunray_request_id')
            
            # Auto-populate event_source if not provided
            if 'event_source' not in vals:
                vals['event_source'] = self.env.context.get('sunray_event_source', 'system')
                
            # Auto-populate admin user from context if not provided
            if 'sunray_admin_user_id' not in vals and self.env.context.get('sunray_admin_user_id'):
                vals['sunray_admin_user_id'] = self.env.context.get('sunray_admin_user_id')
        
        return super().create(vals_list)
    
    @api.model
    def _get_or_create_request_id(self, request=None):
        """Generate or extract request ID for correlation
        
        Args:
            request: HTTP request object (optional)
            
        Returns:
            str: Request ID in format 'source:id'
        """
        # Check context first
        existing_id = self.env.context.get('sunray_request_id')
        if existing_id:
            return existing_id
            
        # If we have a request object, check headers
        if request:
            # Check for CF-Ray (Cloudflare requests)
            cf_ray = request.httprequest.headers.get('CF-Ray')
            if cf_ray:
                return f"cf:{cf_ray}"
        
        # Determine source based on context or default to system
        source = self.env.context.get('sunray_event_source', 'system')
        return f"{source}:{uuid.uuid4()}"
    
    @api.model
    def _detect_source_from_request(self, request):
        """Detect event source from request path
        
        Args:
            request: HTTP request object
            
        Returns:
            str: Event source (api/ui/worker)
        """
        if not request:
            return 'system'
            
        path = request.httprequest.path
        if '/sunray-srvr/v1/' in path:
            return 'api'
        elif '/web/' in path or '/sunray_core/' in path:
            return 'ui'
        else:
            return 'api'  # Default for unknown paths
    
    @api.model
    def cleanup_old_logs(self):
        """Keep last 90 days of logs"""
        cutoff = fields.Datetime.now() - timedelta(days=90)
        old_log_objs = self.search([('timestamp', '<', cutoff)])
        
        # Log the cleanup itself
        if old_log_objs:
            self.create_audit_event(
                event_type='security.alert',
                severity='info',
                details={
                    'action': 'audit_log_cleanup',
                    'count': len(old_log_objs)
                },
                event_source='system'
            )
        
        old_log_objs.unlink()
        return True
    
    @api.model
    def create_audit_event(self, event_type, details, severity='info', 
                          sunray_admin_user_id=None, sunray_user_id=None, 
                          sunray_worker=None, ip_address=None, user_agent=None,
                          request_id=None, event_source=None, username=None):
        """Unified method to create audit events - PREFERRED METHOD
        
        Args:
            event_type: Type of audit event
            details: Event details (dict or string)
            severity: Event severity level (info, warning, error, critical)
            sunray_admin_user_id: Admin user ID (res.users)
            sunray_user_id: Sunray user ID (sunray.user)
            sunray_worker: Worker identification
            ip_address: Client IP address
            user_agent: Client user agent
            request_id: Request correlation ID
            event_source: Event source (api/ui/worker/cli/system)
            username: Legacy username field for compatibility
        """
        vals = {
            'event_type': event_type,
            'severity': severity,
            'details': json.dumps(details) if isinstance(details, dict) else details,
            'timestamp': fields.Datetime.now()
        }
        
        # Add user tracking fields if provided
        if sunray_admin_user_id:
            vals['sunray_admin_user_id'] = sunray_admin_user_id
        if sunray_user_id:
            vals['sunray_user_id'] = sunray_user_id
        if sunray_worker:
            vals['sunray_worker'] = sunray_worker
            
        # Add context fields if provided
        if ip_address:
            vals['ip_address'] = ip_address
        if user_agent:
            vals['user_agent'] = user_agent
        if request_id:
            vals['request_id'] = request_id
        if event_source:
            vals['event_source'] = event_source
        if username:
            vals['username'] = username
            
        return self.create(vals)
    
    @api.model
    def create_security_event(self, event_type, details, severity='warning', 
                            sunray_admin_user_id=None, sunray_user_id=None, 
                            sunray_worker=None, ip_address=None, user_agent=None,
                            request_id=None, event_source=None, username=None):
        """DEPRECATED: Use create_audit_event instead. Kept for backward compatibility."""
        return self.create_audit_event(
            event_type=event_type,
            details=details,
            severity=severity,
            sunray_admin_user_id=sunray_admin_user_id,
            sunray_user_id=sunray_user_id,
            sunray_worker=sunray_worker,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
            event_source=event_source,
            username=username
        )
    
    @api.model
    def create_admin_event(self, event_type, details, admin_user_id=None, **kwargs):
        """Create an event for admin/operator actions
        
        Automatically populates admin_user_id from context if not provided
        """
        if not admin_user_id:
            admin_user_id = self.env.context.get('sunray_admin_user_id') or self.env.uid
            
        return self.create_audit_event(
            event_type=event_type,
            details=details,
            sunray_admin_user_id=admin_user_id,
            event_source=self.env.context.get('sunray_event_source', 'ui'),
            **kwargs
        )
    
    @api.model
    def create_user_event(self, event_type, details, sunray_user_id, **kwargs):
        """Create an event for end-user actions"""
        return self.create_audit_event(
            event_type=event_type,
            details=details,
            sunray_user_id=sunray_user_id,
            event_source=self.env.context.get('sunray_event_source', 'api'),
            **kwargs
        )
    
    @api.model
    def create_worker_event(self, event_type, details, sunray_worker, **kwargs):
        """Create an event for worker actions"""
        return self.create_audit_event(
            event_type=event_type,
            details=details,
            sunray_worker=sunray_worker,
            event_source='worker',
            **kwargs
        )
    
    @api.model
    def create_api_event(self, event_type, details, api_key_id=None, **kwargs):
        """Create an event for API actions
        
        Args:
            event_type: Type of event
            details: Event details (dict or string) 
            api_key_id: API key ID for context
            **kwargs: Additional fields for create_audit_event
        """
        # Add API key context to details if provided
        if api_key_id and isinstance(details, dict):
            details['api_key_id'] = api_key_id
        
        return self.create_audit_event(
            event_type=event_type,
            details=details,
            event_source='api',
            **kwargs
        )
    
    def get_details_dict(self):
        """Parse details JSON field"""
        self.ensure_one()
        if self.details:
            try:
                return json.loads(self.details)
            except (json.JSONDecodeError, TypeError):
                return {'raw': self.details}
        return {}