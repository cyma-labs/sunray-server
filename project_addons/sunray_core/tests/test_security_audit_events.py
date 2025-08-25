# -*- coding: utf-8 -*-
"""Test security audit event types"""

from odoo.tests import TransactionCase
import json


class TestSecurityAuditEvents(TransactionCase):
    """Test new security audit event types functionality"""
    
    def setUp(self):
        super().setUp()
        self.AuditLog = self.env['sunray.audit.log']
        self.User = self.env['sunray.user']
        
        # Create test sunray user for testing
        self.sunray_user = self.User.create({
            'username': 'testuser',
            'email': 'test@example.com',
            'is_active': True
        })
    
    def test_cross_domain_session_event(self):
        """Test cross-domain session attempt event creation"""
        event_details = {
            'original_domain': 'app1.company.com',
            'requested_domain': 'app2.company.com', 
            'username': 'testuser',
            'session_id': 'sess_123'
        }
        
        audit_record = self.AuditLog.create_audit_event(
            event_type='security.cross_domain_session',
            details=event_details,
            severity='critical',
            sunray_user_id=self.sunray_user.id,
            sunray_worker='worker-001',
            ip_address='10.0.0.1',
            user_agent='Mozilla/5.0 Test'
        )
        
        self.assertTrue(audit_record)
        self.assertEqual(audit_record.event_type, 'security.cross_domain_session')
        self.assertEqual(audit_record.severity, 'critical')
        self.assertEqual(audit_record.sunray_user_id.id, self.sunray_user.id)
        self.assertEqual(audit_record.sunray_worker, 'worker-001')
        self.assertEqual(audit_record.ip_address, '10.0.0.1')
        
        # Verify details JSON parsing
        parsed_details = audit_record.get_details_dict()
        self.assertEqual(parsed_details['original_domain'], 'app1.company.com')
        self.assertEqual(parsed_details['requested_domain'], 'app2.company.com')
        self.assertEqual(parsed_details['username'], 'testuser')
        self.assertEqual(parsed_details['session_id'], 'sess_123')
    
    def test_host_id_mismatch_event(self):
        """Test host ID mismatch event creation"""
        event_details = {
            'session_host_id': 'host123',
            'expected_host_id': 'host456',
            'username': 'testuser',
            'session_id': 'sess_456'
        }
        
        audit_record = self.AuditLog.create_audit_event(
            event_type='security.host_id_mismatch',
            details=event_details,
            severity='critical',
            sunray_user_id=self.sunray_user.id,
            sunray_worker='worker-002',
            ip_address='192.168.1.10'
        )
        
        self.assertTrue(audit_record)
        self.assertEqual(audit_record.event_type, 'security.host_id_mismatch')
        self.assertEqual(audit_record.severity, 'critical')
        self.assertEqual(audit_record.sunray_worker, 'worker-002')
        
        # Verify details
        parsed_details = audit_record.get_details_dict()
        self.assertEqual(parsed_details['session_host_id'], 'host123')
        self.assertEqual(parsed_details['expected_host_id'], 'host456')
    
    def test_unmanaged_host_access_event(self):
        """Test unmanaged host access event creation"""
        event_details = {
            'hostname': 'unknown.company.com',
            'path': '/admin/dashboard',
            'method': 'GET',
            'client_ip': '203.0.113.42',
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        audit_record = self.AuditLog.create_audit_event(
            event_type='security.unmanaged_host_access',
            details=event_details,
            severity='warning',
            sunray_worker='worker-003',
            ip_address='203.0.113.42',
            user_agent=event_details['user_agent']
        )
        
        self.assertTrue(audit_record)
        self.assertEqual(audit_record.event_type, 'security.unmanaged_host_access')
        self.assertEqual(audit_record.severity, 'warning')
        self.assertEqual(audit_record.sunray_worker, 'worker-003')
        
        # Verify details
        parsed_details = audit_record.get_details_dict()
        self.assertEqual(parsed_details['hostname'], 'unknown.company.com')
        self.assertEqual(parsed_details['path'], '/admin/dashboard')
        self.assertEqual(parsed_details['method'], 'GET')
    
    def test_security_events_searchable(self):
        """Test that security events can be searched and filtered"""
        # Create multiple security events
        self.AuditLog.create_audit_event(
            event_type='security.cross_domain_session',
            details={'original_domain': 'app1.com', 'requested_domain': 'app2.com'},
            severity='critical'
        )
        
        self.AuditLog.create_audit_event(
            event_type='security.host_id_mismatch', 
            details={'session_host_id': 'host1', 'expected_host_id': 'host2'},
            severity='critical'
        )
        
        self.AuditLog.create_audit_event(
            event_type='security.unmanaged_host_access',
            details={'hostname': 'test.com', 'path': '/test'},
            severity='warning'
        )
        
        # Test searching for security events
        security_events = self.AuditLog.search([
            ('event_type', 'like', 'security.')
        ])
        self.assertEqual(len(security_events), 3)
        
        # Test filtering by severity
        critical_events = self.AuditLog.search([
            ('event_type', 'like', 'security.'),
            ('severity', '=', 'critical')
        ])
        self.assertEqual(len(critical_events), 2)
        
        # Test filtering by specific event type
        cross_domain_events = self.AuditLog.search([
            ('event_type', '=', 'security.cross_domain_session')
        ])
        self.assertEqual(len(cross_domain_events), 1)
    
    def test_backward_compatibility(self):
        """Test that existing create_security_event method still works"""
        # This tests the deprecated method for backward compatibility
        audit_record = self.AuditLog.create_security_event(
            event_type='security.cross_domain_session',
            details={'test': 'data'},
            severity='critical',
            sunray_user_id=self.sunray_user.id
        )
        
        self.assertTrue(audit_record)
        self.assertEqual(audit_record.event_type, 'security.cross_domain_session')
        self.assertEqual(audit_record.severity, 'critical')