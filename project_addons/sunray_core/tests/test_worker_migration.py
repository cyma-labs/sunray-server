# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError
from odoo import fields
from unittest.mock import patch
import json


class TestWorkerMigration(TransactionCase):
    
    def setUp(self):
        super().setUp()
        
        # Create test API keys
        self.api_key1 = self.env['sunray.api.key'].create({
            'name': 'worker1_key',
            'is_active': True,
            'scopes': 'config:read'
        })
        
        self.api_key2 = self.env['sunray.api.key'].create({
            'name': 'worker2_key',
            'is_active': True,
            'scopes': 'config:read'
        })
        
        # Create test workers
        self.worker1 = self.env['sunray.worker'].create({
            'name': 'prod-worker-001',
            'worker_type': 'cloudflare',
            'worker_url': 'https://worker1.example.com',
            'api_key_id': self.api_key1.id,
            'is_active': True
        })
        
        self.worker2 = self.env['sunray.worker'].create({
            'name': 'prod-worker-002',
            'worker_type': 'cloudflare',
            'worker_url': 'https://worker2.example.com',
            'api_key_id': self.api_key2.id,
            'is_active': True
        })
        
        # Create test host
        self.host = self.env['sunray.host'].create({
            'domain': 'api.example.com',
            'sunray_worker_id': self.worker1.id,
            'backend_url': 'https://backend.example.com',
            'is_active': True
        })
    
    def test_set_pending_worker_success(self):
        """Test successfully setting a pending worker"""
        # Initially no pending worker
        self.assertFalse(self.host.pending_worker_name)
        self.assertFalse(self.host.migration_requested_at)
        
        # Set pending worker
        self.host.set_pending_worker('prod-worker-002')
        
        # Check fields are set
        self.assertEqual(self.host.pending_worker_name, 'prod-worker-002')
        self.assertTrue(self.host.migration_requested_at)
        self.assertTrue(self.host.migration_pending_duration)
    
    def test_set_pending_worker_already_exists(self):
        """Test error when trying to set pending worker when one already exists"""
        # Set first pending worker
        self.host.set_pending_worker('prod-worker-002')
        
        # Try to set another pending worker
        with self.assertRaises(ValidationError) as cm:
            self.host.set_pending_worker('prod-worker-003')
        
        self.assertIn('Migration already pending', str(cm.exception))
    
    def test_set_pending_worker_empty_name(self):
        """Test error when setting empty worker name"""
        with self.assertRaises(ValidationError) as cm:
            self.host.set_pending_worker('')
        
        self.assertIn('Worker name cannot be empty', str(cm.exception))
    
    def test_clear_pending_worker_success(self):
        """Test successfully clearing a pending worker"""
        # Set pending worker first
        self.host.set_pending_worker('prod-worker-002')
        self.assertTrue(self.host.pending_worker_name)
        
        # Clear it
        self.host.clear_pending_worker()
        
        # Check it's cleared
        self.assertFalse(self.host.pending_worker_name)
        self.assertFalse(self.host.migration_requested_at)
    
    def test_clear_pending_worker_none_exists(self):
        """Test error when clearing pending worker when none exists"""
        with self.assertRaises(ValidationError) as cm:
            self.host.clear_pending_worker()
        
        self.assertIn('No pending migration to clear', str(cm.exception))
    
    def test_migration_pending_duration_computation(self):
        """Test the migration pending duration computation"""
        # Set pending worker
        self.host.set_pending_worker('prod-worker-002')
        
        # Duration should be computed
        self.assertTrue(self.host.migration_pending_duration)
        self.assertIn('minute', self.host.migration_pending_duration)
    
    def test_action_clear_pending_migration_success(self):
        """Test UI action for clearing pending migration"""
        # Set pending worker
        self.host.set_pending_worker('prod-worker-002')
        
        # Call UI action
        result = self.host.action_clear_pending_migration()
        
        # Check result
        self.assertEqual(result['type'], 'ir.actions.client')
        self.assertEqual(result['params']['type'], 'success')
        self.assertIn('cleared', result['params']['message'])
        
        # Check migration is cleared
        self.assertFalse(self.host.pending_worker_name)
    
    def test_action_clear_pending_migration_none_exists(self):
        """Test UI action when no pending migration exists"""
        result = self.host.action_clear_pending_migration()

        self.assertEqual(result['type'], 'ir.actions.client')
        self.assertEqual(result['params']['type'], 'info')
        self.assertIn('There is no pending migration', result['params']['message'])
    
    def test_worker_get_migration_status(self):
        """Test worker migration status method"""
        # Set pending migration
        self.host.set_pending_worker('prod-worker-002')
        
        # Get migration status for worker1 (current)
        status = self.worker1.get_migration_status()
        
        # Check structure
        self.assertEqual(status['worker_name'], 'prod-worker-001')
        self.assertEqual(status['protected_hosts'], 1)
        self.assertEqual(len(status['pending_outbound']), 1)
        self.assertEqual(status['pending_outbound'][0]['host'], 'api.example.com')
        self.assertEqual(status['pending_outbound'][0]['pending_worker'], 'prod-worker-002')
        
        # Get migration status for worker2 (pending)
        status2 = self.worker2.get_migration_status()
        
        self.assertEqual(len(status2['pending_inbound']), 1)
        self.assertEqual(status2['pending_inbound'][0]['host'], 'api.example.com')
    
    def test_format_time_delta(self):
        """Test time delta formatting"""
        from datetime import timedelta
        
        # Test minutes
        delta = timedelta(minutes=5)
        result = self.host._format_time_delta(delta)
        self.assertEqual(result, '5 minutes')
        
        # Test singular minute
        delta = timedelta(minutes=1)
        result = self.host._format_time_delta(delta)
        self.assertEqual(result, '1 minute')
        
        # Test hours and minutes
        delta = timedelta(hours=2, minutes=30)
        result = self.host._format_time_delta(delta)
        self.assertEqual(result, '2 hours, 30 minutes')
        
        # Test days
        delta = timedelta(days=1, hours=5)
        result = self.host._format_time_delta(delta)
        self.assertEqual(result, '1 day, 5 hours')
    
    def test_migration_workflow_scenario(self):
        """Test complete migration workflow"""
        # Initial state: host bound to worker1
        self.assertEqual(self.host.sunray_worker_id.id, self.worker1.id)
        self.assertFalse(self.host.pending_worker_name)
        
        # Step 1: Admin sets pending worker
        self.host.set_pending_worker('prod-worker-002')
        self.assertEqual(self.host.pending_worker_name, 'prod-worker-002')
        initial_requested_at = self.host.migration_requested_at
        
        # Step 2: Simulate worker2 registration (would trigger migration)
        # This would normally happen through the registration API
        # For testing, simulate the migration directly
        old_worker = self.host.sunray_worker_id
        self.host.write({
            'sunray_worker_id': self.worker2.id,
            'pending_worker_name': False,
            'migration_requested_at': False,
            'last_migration_ts': fields.Datetime.now()
        })
        
        # Step 3: Verify migration completed
        self.assertEqual(self.host.sunray_worker_id.id, self.worker2.id)
        self.assertFalse(self.host.pending_worker_name)
        self.assertFalse(self.host.migration_requested_at)
        self.assertTrue(self.host.last_migration_ts)
        
        # Previous worker should no longer be bound to this host
        self.assertNotEqual(old_worker.id, self.host.sunray_worker_id.id)


class TestWorkerRegistrationAPI(TransactionCase):
    """Test the registration API with migration logic"""
    
    def setUp(self):
        super().setUp()
        
        # Create test API keys
        self.api_key1 = self.env['sunray.api.key'].create({
            'name': 'worker1_key',
            'key': 'test_key_123',
            'is_active': True,
            'scopes': 'config:read'
        })
        
        # Create test workers
        self.worker1 = self.env['sunray.worker'].create({
            'name': 'prod-worker-001',
            'worker_type': 'cloudflare',
            'api_key_id': self.api_key1.id,
            'is_active': True
        })
        
        # Create test host
        self.host = self.env['sunray.host'].create({
            'domain': 'api.example.com',
            'sunray_worker_id': self.worker1.id,
            'backend_url': 'https://backend.example.com',
            'is_active': True
        })
    
    def test_registration_same_worker_idempotent(self):
        """Test that same worker re-registering is idempotent"""
        # Initial state: host is bound to worker1
        self.assertEqual(self.host.sunray_worker_id.id, self.worker1.id)
        initial_worker_id = self.host.sunray_worker_id.id

        # Simulate the registration logic from the controller
        # This mimics what happens in register_worker when same worker registers
        worker_name = 'prod-worker-001'
        hostname = 'api.example.com'

        # Find the worker (should be worker1)
        worker_obj = self.env['sunray.worker'].sudo().search([
            ('name', '=', worker_name)
        ], limit=1)

        self.assertTrue(worker_obj, "Worker should exist")
        self.assertEqual(worker_obj.id, self.worker1.id, "Should find the correct worker")

        # Find the host
        host_obj = self.env['sunray.host'].sudo().search([
            ('domain', '=', hostname)
        ], limit=1)

        self.assertTrue(host_obj, "Host should exist")
        self.assertEqual(host_obj.id, self.host.id, "Should find the correct host")

        # Simulate the idempotent case: same worker re-registering
        if host_obj.sunray_worker_id.id == worker_obj.id:
            # This is the idempotent path - should not change anything
            # Create audit event for re-registration
            self.env['sunray.audit.log'].sudo().create_api_event(
                event_type='worker.re_registered',
                api_key_id=self.api_key1.id,
                details={
                    'worker_id': worker_obj.id,
                    'worker_name': worker_name,
                    'host_id': host_obj.id,
                    'hostname': hostname
                },
                ip_address='192.168.1.100'
            )

        # Verify the host is still bound to the same worker (idempotent)
        self.assertEqual(host_obj.sunray_worker_id.id, initial_worker_id)
        self.assertEqual(host_obj.sunray_worker_id.id, worker_obj.id)

        # Verify no pending migration was set
        self.assertFalse(host_obj.pending_worker_name)
        self.assertFalse(host_obj.migration_requested_at)

        # Verify audit log was created
        audit_log = self.env['sunray.audit.log'].sudo().search([
            ('event_type', '=', 'worker.re_registered'),
            ('details', 'ilike', f'"worker_id": {worker_obj.id}')
        ], order='create_date desc', limit=1)

        self.assertTrue(audit_log, "Should have created re-registration audit log")

        # Parse the details JSON
        details_dict = audit_log.get_details_dict()
        self.assertEqual(details_dict.get('worker_name'), worker_name)
        self.assertEqual(details_dict.get('hostname'), hostname)
    
    def test_pending_migration_logic(self):
        """Test pending migration triggers migration"""
        # Create second worker
        worker2 = self.env['sunray.worker'].create({
            'name': 'prod-worker-002',
            'worker_type': 'cloudflare',
            'api_key_id': self.api_key1.id,
            'is_active': True
        })
        
        # Set pending worker
        self.host.set_pending_worker('prod-worker-002')
        
        # Simulate the migration logic from registration API
        if self.host.pending_worker_name == worker2.name:
            old_worker = self.host.sunray_worker_id
            
            # Perform migration
            self.host.write({
                'sunray_worker_id': worker2.id,
                'pending_worker_name': False,
                'migration_requested_at': False,
                'last_migration_ts': fields.Datetime.now()
            })
            
            # Verify migration
            self.assertEqual(self.host.sunray_worker_id.id, worker2.id)
            self.assertFalse(self.host.pending_worker_name)
            self.assertTrue(self.host.last_migration_ts)