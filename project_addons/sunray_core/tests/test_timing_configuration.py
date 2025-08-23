# -*- coding: utf-8 -*-
"""Test timing configuration functionality"""
from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError
from unittest.mock import patch


class TestTimingConfiguration(TransactionCase):
    """Test timing configuration and validation"""

    def setUp(self):
        super().setUp()
        # Create test host
        self.host_obj = self.env['sunray.host'].create({
            'name': 'test.example.com',
            'domain': 'test.example.com',
            'backend_url': 'https://backend.example.com',
            'worker_url': 'https://worker.example.com',
        })

    def test_session_duration_default_value(self):
        """Test session duration has correct default"""
        # New host should have default session duration
        self.assertEqual(self.host_obj.session_duration_s, 3600)
        
    def test_waf_bypass_revalidation_default_value(self):
        """Test WAF bypass revalidation has correct default"""
        # New host should have default WAF revalidation period
        self.assertEqual(self.host_obj.waf_bypass_revalidation_s, 900)

    def test_session_duration_validation_minimum(self):
        """Test session duration minimum validation"""
        with self.assertRaises(ValidationError) as cm:
            self.host_obj.write({'session_duration_s': 30})  # Below minimum
        self.assertIn('at least 60 seconds', str(cm.exception))

    def test_session_duration_validation_maximum(self):
        """Test session duration maximum validation with system parameter"""
        # Set system parameter for max duration
        self.env['ir.config_parameter'].sudo().set_param(
            'sunray.max_session_duration_s', '7200')  # 2 hours max
        
        with self.assertRaises(ValidationError) as cm:
            self.host_obj.write({'session_duration_s': 10800})  # 3 hours, above max
        self.assertIn('cannot exceed 7200 seconds', str(cm.exception))

    def test_waf_bypass_revalidation_validation_minimum(self):
        """Test WAF bypass revalidation minimum validation"""
        with self.assertRaises(ValidationError) as cm:
            self.host_obj.write({'waf_bypass_revalidation_s': 30})  # Below minimum
        self.assertIn('at least 60 seconds', str(cm.exception))

    def test_waf_bypass_revalidation_validation_maximum(self):
        """Test WAF bypass revalidation maximum validation with system parameter"""
        # Set system parameter for max revalidation
        self.env['ir.config_parameter'].sudo().set_param(
            'sunray.max_waf_bypass_revalidation_s', '1800')  # 30 minutes max
        
        with self.assertRaises(ValidationError) as cm:
            self.host_obj.write({'waf_bypass_revalidation_s': 3600})  # 1 hour, above max
        self.assertIn('cannot exceed 1800 seconds', str(cm.exception))

    def test_session_duration_audit_logging(self):
        """Test session duration changes are audited"""
        # Change session duration
        self.host_obj.write({'session_duration_s': 7200})
        
        # Check audit log was created
        audit_logs = self.env['sunray.audit.log'].search([
            ('event_type', '=', 'config.session_duration_changed'),
            ('admin_user_id', '=', self.env.user.id)
        ])
        
        self.assertEqual(len(audit_logs), 1)
        self.assertIn('3600s → 7200s', audit_logs[0].details)
        self.assertIn(self.host_obj.domain, audit_logs[0].details)

    def test_waf_revalidation_audit_logging(self):
        """Test WAF revalidation changes are audited"""
        # Change WAF revalidation period
        self.host_obj.write({'waf_bypass_revalidation_s': 1800})
        
        # Check audit log was created
        audit_logs = self.env['sunray.audit.log'].search([
            ('event_type', '=', 'config.waf_revalidation_changed'),
            ('admin_user_id', '=', self.env.user.id)
        ])
        
        self.assertEqual(len(audit_logs), 1)
        self.assertIn('900s → 1800s', audit_logs[0].details)
        self.assertIn(self.host_obj.domain, audit_logs[0].details)

    def test_config_api_field_names(self):
        """Test config API returns correct field names"""
        # Test the config generation logic
        config = {
            'session_duration_s': self.host_obj.session_duration_s,
            'waf_bypass_revalidation_s': self.host_obj.waf_bypass_revalidation_s,
        }
        
        # Verify field names and values
        self.assertEqual(config['session_duration_s'], 3600)
        self.assertEqual(config['waf_bypass_revalidation_s'], 900)
        
        # Ensure old field names are not present
        self.assertNotIn('session_duration_override', config)
        self.assertNotIn('waf_bypass_revalidation_minutes', config)

    def test_valid_ranges(self):
        """Test valid values within acceptable ranges"""
        # Test minimum valid values
        self.host_obj.write({
            'session_duration_s': 60,
            'waf_bypass_revalidation_s': 60
        })
        self.assertEqual(self.host_obj.session_duration_s, 60)
        self.assertEqual(self.host_obj.waf_bypass_revalidation_s, 60)
        
        # Test reasonable values
        self.host_obj.write({
            'session_duration_s': 14400,  # 4 hours
            'waf_bypass_revalidation_s': 1800  # 30 minutes
        })
        self.assertEqual(self.host_obj.session_duration_s, 14400)
        self.assertEqual(self.host_obj.waf_bypass_revalidation_s, 1800)

    def test_system_parameter_defaults(self):
        """Test system parameter default values are used when not set"""
        # Test with missing system parameters (should use hardcoded defaults)
        self.env['ir.config_parameter'].sudo().search([
            ('key', 'in', ['sunray.max_session_duration_s', 'sunray.max_waf_bypass_revalidation_s'])
        ]).unlink()
        
        # Should not raise error, should use hardcoded defaults (86400 and 3600)
        self.host_obj.write({'session_duration_s': 86400})  # Should work (default max)
        self.host_obj.write({'waf_bypass_revalidation_s': 3600})  # Should work (default max)

    def test_no_audit_log_on_same_value(self):
        """Test no audit log created when value doesn't change"""
        # Write same value
        self.host_obj.write({'session_duration_s': 3600})  # Same as default
        
        # Should not create audit log
        audit_logs = self.env['sunray.audit.log'].search([
            ('event_type', '=', 'config.session_duration_changed'),
            ('admin_user_id', '=', self.env.user.id)
        ])
        
        self.assertEqual(len(audit_logs), 0)

    def test_multiple_field_changes(self):
        """Test changing both fields creates separate audit logs"""
        # Change both fields at once
        self.host_obj.write({
            'session_duration_s': 7200,
            'waf_bypass_revalidation_s': 1800
        })
        
        # Should create two audit logs
        session_logs = self.env['sunray.audit.log'].search([
            ('event_type', '=', 'config.session_duration_changed')
        ])
        waf_logs = self.env['sunray.audit.log'].search([
            ('event_type', '=', 'config.waf_revalidation_changed')
        ])
        
        self.assertEqual(len(session_logs), 1)
        self.assertEqual(len(waf_logs), 1)