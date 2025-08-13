#!/usr/bin/env python3
"""
Generate an API key for Sunray Worker integration
"""

import xmlrpc.client
import sys
import os

# Connection parameters
url = 'http://localhost:8069'
db = os.environ.get('PGDATABASE', 'cmorisse_sunray18_d4_001')
username = 'admin'
password = 'admin'

def main():
    try:
        # Connect to Odoo
        common = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/common')
        uid = common.authenticate(db, username, password, {})
        
        if not uid:
            print("Authentication failed!")
            sys.exit(1)
        
        print(f"✓ Authenticated as user ID: {uid}")
        
        # Get models object
        models = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/object')
        
        # Check if sunray_core is installed
        module_ids = models.execute_kw(db, uid, password,
            'ir.module.module', 'search',
            [[['name', '=', 'sunray_core'], ['state', '=', 'installed']]])
        
        if not module_ids:
            print("✗ sunray_core module is not installed!")
            print("  Run: bin/sunray-srvr -i sunray_core")
            sys.exit(1)
        
        print("✓ sunray_core module is installed")
        
        # Create API key for Worker
        api_key_id = models.execute_kw(db, uid, password,
            'sunray.api_key', 'create',
            [{
                'name': 'Cloudflare Worker Key',
                'description': 'API key for Cloudflare Worker authentication',
                'scopes': 'config:read,user:read,user:write,session:write,audit:write',
                'active': True
            }])
        
        # Read the generated key
        api_key = models.execute_kw(db, uid, password,
            'sunray.api_key', 'read',
            [api_key_id, ['name', 'key']])
        
        if api_key:
            key_value = api_key[0]['key']
            print("\n" + "="*60)
            print("✓ API Key generated successfully!")
            print("="*60)
            print(f"\nAPI Key: {key_value}")
            print("\nTo configure the Worker, run:")
            print(f"cd worker && echo '{key_value}' | wrangler secret put ADMIN_API_KEY")
            print("\nOr set in your .dev.vars file:")
            print(f"ADMIN_API_KEY={key_value}")
            print("="*60)
        else:
            print("✗ Failed to retrieve API key")
            sys.exit(1)
            
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()