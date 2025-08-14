#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import logging
from odoo import api, fields, models, SUPERUSER_ID
from odoo.cli import Command

_logger = logging.getLogger(__name__)


class SunrayCommand(Command):
    """Sunray management CLI command for Odoo"""
    
    name = 'srctl'
    
    def run(self, args):
        """Main entry point for the sunray command"""
        import argparse
        import os
        
        parser = argparse.ArgumentParser(
            prog='%s srctl' % sys.argv[0].split('/')[-1],
            description='Sunray authentication system management'
        )
        
        # Add database argument
        parser.add_argument('--database', '-d', 
                          help='Database name (defaults to PGDATABASE env var)')
        
        subparsers = parser.add_subparsers(dest='resource', help='Resource type')
        
        # API Key commands
        apikey = subparsers.add_parser('apikey', help='Manage API keys')
        apikey_sub = apikey.add_subparsers(dest='action', help='Action')
        
        # apikey list
        apikey_list = apikey_sub.add_parser('list', help='List API keys')
        apikey_list.add_argument('--sr-all', action='store_true', 
                                help='Show inactive keys')
        
        # apikey get
        apikey_get = apikey_sub.add_parser('get', help='Get API key details')
        apikey_get.add_argument('name', help='API key name or ID')
        
        # apikey create
        apikey_create = apikey_sub.add_parser('create', help='Create API key')
        apikey_create.add_argument('name', help='API key name')
        apikey_create.add_argument('--sr-description', help='Description')
        apikey_create.add_argument('--sr-scopes', help='Comma-separated scopes')
        apikey_create.add_argument('--sr-worker', action='store_true',
                                  help='Create key for Worker with default scopes')
        
        # apikey delete
        apikey_delete = apikey_sub.add_parser('delete', help='Delete API key')
        apikey_delete.add_argument('name', help='API key name or ID')
        
        # User commands
        user = subparsers.add_parser('user', help='Manage users')
        user_sub = user.add_subparsers(dest='action', help='Action')
        
        # user list
        user_list = user_sub.add_parser('list', help='List users')
        user_list.add_argument('--sr-host', help='Filter by host')
        
        # user get
        user_get = user_sub.add_parser('get', help='Get user details')
        user_get.add_argument('username', help='Username')
        
        # user create-token
        user_token = user_sub.add_parser('create-token', help='Create setup token')
        user_token.add_argument('username', help='Username')
        user_token.add_argument('--sr-host', help='Host name', required=True)
        user_token.add_argument('--sr-email', help='User email')
        
        # user delete
        user_delete = user_sub.add_parser('delete', help='Delete user')
        user_delete.add_argument('username', help='Username to delete')
        
        # Session commands
        session = subparsers.add_parser('session', help='Manage sessions')
        session_sub = session.add_subparsers(dest='action', help='Action')
        
        # session list
        session_list = session_sub.add_parser('list', help='List sessions')
        session_list.add_argument('--sr-all', action='store_true', 
                                 help='Show all sessions (including expired)')
        session_list.add_argument('--sr-user', help='Filter by username')
        
        # session revoke
        session_revoke = session_sub.add_parser('revoke', help='Revoke session')
        session_revoke.add_argument('session_id', help='Session ID')
        
        # session delete
        session_delete = session_sub.add_parser('delete', help='Delete session')
        session_delete.add_argument('session_id', help='Session ID')
        session_delete.add_argument('--sr-hard', action='store_true',
                                   help='Permanently delete (default: soft delete)')
        
        # Host commands
        host = subparsers.add_parser('host', help='Manage hosts')
        host_sub = host.add_subparsers(dest='action', help='Action')
        
        # host list
        host_list = host_sub.add_parser('list', help='List hosts')
        
        # host get
        host_get = host_sub.add_parser('get', help='Get host details')
        host_get.add_argument('name', help='Host name or domain')
        
        # host create
        host_create = host_sub.add_parser('create', help='Create host')
        host_create.add_argument('domain', help='Domain')
        host_create.add_argument('--sr-backend', help='Backend URL', default='')
        host_create.add_argument('--sr-cidr', help='CIDR whitelist (comma-separated)')
        host_create.add_argument('--sr-public', help='Public URL patterns (comma-separated)')
        
        # host delete
        host_delete = host_sub.add_parser('delete', help='Delete host')
        host_delete.add_argument('domain', help='Host domain to delete')
        host_delete.add_argument('--sr-force', action='store_true',
                                help='Force delete even if users exist')
        
        # Setup Token commands
        setuptoken = subparsers.add_parser('setuptoken', help='Manage setup tokens')
        setuptoken_sub = setuptoken.add_subparsers(dest='action', help='Action')
        
        # setuptoken list
        setuptoken_list = setuptoken_sub.add_parser('list', help='List setup tokens')
        setuptoken_list.add_argument('--sr-all', action='store_true',
                                    help='Show all tokens including consumed/expired')
        setuptoken_list.add_argument('--sr-user', help='Filter by username')
        
        # setuptoken get
        setuptoken_get = setuptoken_sub.add_parser('get', help='Get setup token details')
        setuptoken_get.add_argument('token_id', help='Setup token ID')
        
        # setuptoken create
        setuptoken_create = setuptoken_sub.add_parser('create', help='Create setup token')
        setuptoken_create.add_argument('username', help='Username')
        setuptoken_create.add_argument('--sr-host', required=True, help='Host domain for this token')
        setuptoken_create.add_argument('--sr-device', required=True, help='Device name')
        setuptoken_create.add_argument('--sr-hours', type=int, default=24,
                                      help='Validity in hours (default: 24)')
        setuptoken_create.add_argument('--sr-cidrs', help='Allowed CIDRs/IPs (comma-separated)')
        setuptoken_create.add_argument('--sr-uses', type=int, default=1,
                                      help='Maximum uses (default: 1)')
        
        # setuptoken delete
        setuptoken_delete = setuptoken_sub.add_parser('delete', help='Delete setup token')
        setuptoken_delete.add_argument('token_id', help='Setup token ID')
        
        # Parse arguments
        parsed_args = parser.parse_args(args)
        
        if not parsed_args.resource:
            parser.print_help()
            return 0
        
        # Get database name from args or environment
        database = parsed_args.database or os.environ.get('PGDATABASE')
        if not database:
            print("Error: Database name required. Use --database or set PGDATABASE env var.")
            return 1
        
        # Import Odoo modules
        from odoo.modules.registry import Registry
        
        try:
            # Create registry and cursor
            registry = Registry(database)
            with registry.cursor() as cr:
                env = api.Environment(cr, SUPERUSER_ID, {})
                
                # Route to appropriate handler
                if parsed_args.resource == 'apikey':
                    self._handle_apikey(env, parsed_args)
                elif parsed_args.resource == 'user':
                    self._handle_user(env, parsed_args)
                elif parsed_args.resource == 'session':
                    self._handle_session(env, parsed_args)
                elif parsed_args.resource == 'host':
                    self._handle_host(env, parsed_args)
                elif parsed_args.resource == 'setuptoken':
                    self._handle_setuptoken(env, parsed_args)
                
                # Commit changes for write operations
                if parsed_args.action in ['create', 'delete', 'revoke', 'create-token']:
                    cr.commit()
                    
            return 0
            
        except Exception as e:
            print(f"Error: {e}")
            return 1
    
    def _handle_apikey(self, env, args):
        """Handle API key operations"""
        ApiKey = env['sunray.api.key']
        
        if args.action == 'list':
            domain = [] if args.sr_all else [('is_active', '=', True)]
            keys = ApiKey.search(domain)
            
            if not keys:
                print("No API keys found")
                return
            
            print(f"{'NAME':<30} {'ACTIVE':<8} {'CREATED':<20} {'DESCRIPTION'}")
            print("-" * 80)
            for key in keys:
                active = '✓' if key.is_active else '✗'
                created = key.create_date.strftime('%Y-%m-%d %H:%M:%S')
                desc = (key.description or '')[:30]
                print(f"{key.name:<30} {active:<8} {created:<20} {desc}")
        
        elif args.action == 'get':
            # Search by name or ID
            if args.name.isdigit():
                key = ApiKey.browse(int(args.name))
            else:
                key = ApiKey.search([('name', '=', args.name)], limit=1)
            
            if not key or not key.exists():
                print(f"API key '{args.name}' not found")
                return
            
            print(f"Name:        {key.name}")
            print(f"Key:         {key.key}")
            print(f"Active:      {'Yes' if key.is_active else 'No'}")
            print(f"Scopes:      {key.scopes or 'all'}")
            print(f"Description: {key.description or ''}")
            print(f"Created:     {key.create_date}")
            print(f"Modified:    {key.write_date}")
        
        elif args.action == 'create':
            data = {
                'name': args.name,
                'is_active': True
            }
            
            if args.sr_description:
                data['description'] = args.sr_description
            
            if args.sr_worker:
                # Default scopes for Worker
                data['scopes'] = 'config:read,user:read,user:write,session:write,audit:write'
                data['description'] = data.get('description', 'Cloudflare Worker API Key')
            elif args.sr_scopes:
                data['scopes'] = args.sr_scopes
            
            key = ApiKey.create([data])
            
            print(f"API key created successfully!")
            print(f"Name: {key.name}")
            print(f"Key:  {key.key}")
            
            if args.sr_worker:
                print(f"\nTo configure Worker:")
                print(f"cd worker && echo '{key.key}' | wrangler secret put ADMIN_API_KEY")
                print(f"\nOr add to worker/.dev.vars:")
                print(f"ADMIN_API_KEY={key.key}")
        
        elif args.action == 'delete':
            # Search by name or ID
            if args.name.isdigit():
                key = ApiKey.browse(int(args.name))
            else:
                key = ApiKey.search([('name', '=', args.name)], limit=1)
            
            if not key or not key.exists():
                print(f"API key '{args.name}' not found")
                return
            
            name = key.name
            key.unlink()
            print(f"API key '{name}' deleted")
    
    def _handle_user(self, env, args):
        """Handle user operations"""
        User = env['sunray.user']
        Host = env['sunray.host']
        
        if args.action == 'list':
            domain = []
            if args.sr_host:
                host = Host.search([('domain', '=', args.sr_host)], limit=1)
                if host:
                    domain.append(('host_id', '=', host.id))
            
            users = User.search(domain)
            
            if not users:
                print("No users found")
                return
            
            print(f"{'USERNAME':<20} {'EMAIL':<30} {'ACTIVE':<8} {'HOST':<20} {'LAST LOGIN'}")
            print("-" * 100)
            for user in users:
                active = '✓' if user.is_active else '✗'
                email = (user.email or '')[:30]
                host = (', '.join([h.domain for h in user.host_ids]) if user.host_ids else '')[:20]
                last_login = user.last_login.strftime('%Y-%m-%d %H:%M') if user.last_login else 'Never'
                print(f"{user.username:<20} {email:<30} {active:<8} {host:<20} {last_login}")
        
        elif args.action == 'get':
            user = User.search([('username', '=', args.username)], limit=1)
            
            if not user:
                print(f"User '{args.username}' not found")
                return
            
            print(f"Username:    {user.username}")
            print(f"Email:       {user.email or ''}")
            print(f"Active:      {'Yes' if user.is_active else 'No'}")
            print(f"Hosts:       {', '.join([h.domain for h in user.host_ids]) if user.host_ids else 'None'}")
            print(f"Last Login:  {user.last_login or 'Never'}")
            print(f"Passkeys:    {len(user.passkey_ids)}")
            print(f"Created:     {user.create_date}")
            
            if user.passkey_ids:
                print("\nPasskeys:")
                for pk in user.passkey_ids:
                    print(f"  - {pk.credential_id[:20]}... ({pk.device_name})")
        
        elif args.action == 'create-token':
            # Find or create user
            user = User.search([('username', '=', args.username)], limit=1)
            
            # Find host
            host = Host.search([('domain', '=', args.sr_host)], limit=1)
            if not host:
                print(f"Host '{args.sr_host}' not found")
                return
            
            if not user:
                # Create user
                user_data = {
                    'username': args.username,
                    'host_ids': [(4, host.id)],  # Add host to many2many relation
                    'is_active': True
                }
                if args.sr_email:
                    user_data['email'] = args.sr_email
                user = User.create([user_data])
                print(f"Created user: {user.username}")
            
            # Generate setup token
            from secrets import token_urlsafe
            import hashlib
            from datetime import datetime, timedelta
            
            token_value = token_urlsafe(32)
            token_hash = hashlib.sha512(token_value.encode()).hexdigest()
            
            SetupToken = env['sunray.setup.token']
            token = SetupToken.create([{
                'user_id': user.id,
                'token_hash': token_hash,
                'device_name': f'Device for {user.username}',
                'expires_at': datetime.now() + timedelta(hours=24)
            }])
            
            print(f"Setup token created!")
            print(f"User:     {user.username}")
            print(f"Host:     {host.domain}")
            print(f"Token:    {token_value}")  # Show the actual token value, not the hash
            print(f"Expires:  {token.expires_at}")
            print(f"\nSetup URL: https://{host.domain}/sunray-wrkr/v1/setup")
        
        elif args.action == 'delete':
            user = User.search([('username', '=', args.username)], limit=1)
            
            if not user:
                print(f"User '{args.username}' not found")
                return
            
            # Check for active sessions
            Session = env['sunray.session']
            active_sessions = Session.search([
                ('user_id', '=', user.id),
                ('is_active', '=', True)
            ])
            
            if active_sessions:
                print(f"Warning: User has {len(active_sessions)} active session(s)")
                print("Consider revoking sessions first with: srctl session revoke <session_id>")
            
            # Get related data counts for info
            passkey_count = len(user.passkey_ids)
            token_count = len(user.setup_token_ids)
            
            username = user.username
            user.unlink()
            
            print(f"User '{username}' deleted")
            if passkey_count:
                print(f"  - {passkey_count} passkey(s) removed")
            if token_count:
                print(f"  - {token_count} setup token(s) removed")
    
    def _handle_session(self, env, args):
        """Handle session operations"""
        Session = env['sunray.session']
        
        if args.action == 'list':
            domain = [] if args.sr_all else [('is_active', '=', True)]
            
            if args.sr_user:
                User = env['sunray.user']
                user = User.search([('username', '=', args.sr_user)], limit=1)
                if user:
                    domain.append(('user_id', '=', user.id))
            
            sessions = Session.search(domain, order='created_at desc', limit=50)
            
            if not sessions:
                print("No sessions found")
                return
            
            print(f"{'SESSION ID':<20} {'USER':<15} {'HOST':<20} {'IP ADDRESS':<15} {'STATUS':<10} {'CREATED'}")
            print("-" * 100)
            for session in sessions:
                sid = session.session_id[:18] + '..' if len(session.session_id) > 20 else session.session_id
                user = session.user_id.username if session.user_id else 'Unknown'
                host = (session.host_id.domain if session.host_id else '')[:20]
                ip = session.ip_address or 'Unknown'
                status = 'Active' if session.is_active else 'Expired'
                created = session.created_at.strftime('%Y-%m-%d %H:%M')
                print(f"{sid:<20} {user:<15} {host:<20} {ip:<15} {status:<10} {created}")
        
        elif args.action == 'revoke':
            session = Session.search([('session_id', '=', args.session_id)], limit=1)
            
            if not session:
                # Try partial match
                session = Session.search([('session_id', 'like', args.session_id + '%')], limit=1)
            
            if not session:
                print(f"Session '{args.session_id}' not found")
                return
            
            session.write({'is_active': False})
            print(f"Session revoked: {session.session_id}")
        
        elif args.action == 'delete':
            session = Session.search([('session_id', '=', args.session_id)], limit=1)
            
            if not session:
                # Try partial match
                session = Session.search([('session_id', 'like', args.session_id + '%')], limit=1)
            
            if not session:
                print(f"Session '{args.session_id}' not found")
                return
            
            session_id = session.session_id
            user = session.user_id.username if session.user_id else 'Unknown'
            
            if args.sr_hard:
                # Permanent deletion
                session.unlink()
                print(f"Session permanently deleted: {session_id} (user: {user})")
            else:
                # Soft delete - mark as inactive
                session.write({'is_active': False})
                print(f"Session marked as inactive: {session_id} (user: {user})")
    
    def _handle_host(self, env, args):
        """Handle host operations"""
        Host = env['sunray.host']
        
        if args.action == 'list':
            hosts = Host.search([])
            
            if not hosts:
                print("No hosts found")
                return
            
            print(f"{'DOMAIN':<30} {'ACTIVE':<8} {'CIDR':<10} {'PUBLIC':<10} {'USERS'}")
            print("-" * 80)
            for host in hosts:
                active = '✓' if host.is_active else '✗'
                cidr_count = len(host.allowed_cidrs.split('\n')) if host.allowed_cidrs else 0
                public_count = len(host.public_url_patterns.split('\n')) if host.public_url_patterns else 0
                user_count = len(host.user_ids)
                print(f"{host.domain:<30} {active:<8} {cidr_count:<10} {public_count:<10} {user_count}")
        
        elif args.action == 'get':
            # Search by domain
            host = Host.search([('domain', '=', args.name)], limit=1)
            
            if not host:
                print(f"Host '{args.name}' not found")
                return
            
            print(f"Domain:      {host.domain}")
            print(f"Backend URL: {host.backend_url or 'Not configured'}")
            print(f"Active:      {'Yes' if host.is_active else 'No'}")
            print(f"Users:       {len(host.user_ids)}")
            print(f"Created:     {host.create_date}")
            
            if host.allowed_cidrs:
                print(f"\nAllowed CIDR ranges:")
                for cidr in host.allowed_cidrs.split('\n'):
                    if cidr.strip():
                        print(f"  - {cidr.strip()}")
            
            if host.public_url_patterns:
                print(f"\nPublic URL Patterns:")
                for pattern in host.public_url_patterns.split('\n'):
                    if pattern.strip():
                        print(f"  - {pattern.strip()}")
            
            if host.webhook_token_ids:
                print(f"\nWebhook Tokens: {len(host.webhook_token_ids)}")
        
        elif args.action == 'create':
            data = {
                'domain': args.domain,
                'backend_url': args.sr_backend or '',
                'is_active': True
            }
            
            if args.sr_cidr:
                data['allowed_cidrs'] = '\n'.join(args.sr_cidr.split(','))
            
            if args.sr_public:
                data['public_url_patterns'] = '\n'.join(args.sr_public.split(','))
            
            host = Host.create([data])
            
            print(f"Host created successfully!")
            print(f"Domain: {host.domain}")
            print(f"ID:     {host.id}")
        
        elif args.action == 'delete':
            host = Host.search([('domain', '=', args.domain)], limit=1)
            
            if not host:
                print(f"Host '{args.domain}' not found")
                return
            
            # Check for dependent users
            User = env['sunray.user']
            users = User.search([('host_ids', 'in', host.id)])
            
            if users and not args.sr_force:
                print(f"Error: Host has {len(users)} associated user(s)")
                print("Users:")
                for user in users[:5]:  # Show first 5 users
                    print(f"  - {user.username}")
                if len(users) > 5:
                    print(f"  ... and {len(users) - 5} more")
                print("\nUse --sr-force to delete anyway, or delete users first")
                return
            
            # Check for active sessions
            Session = env['sunray.session']
            active_sessions = Session.search([
                ('host_id', '=', host.id),
                ('is_active', '=', True)
            ])
            
            if active_sessions:
                print(f"Warning: Host has {len(active_sessions)} active session(s)")
            
            domain = host.domain
            webhook_count = len(host.webhook_token_ids)
            
            # Delete the host
            host.unlink()
            
            print(f"Host '{domain}' deleted")
            if users:
                print(f"  - {len(users)} user association(s) removed")
            if webhook_count:
                print(f"  - {webhook_count} webhook token(s) removed")
    
    def _handle_setuptoken(self, env, args):
        """Handle setup token operations"""
        SetupToken = env['sunray.setup.token']
        User = env['sunray.user']
        
        if args.action == 'list':
            # Build domain
            domain = []
            if not args.sr_all:
                # Show only active (not consumed and not expired)
                domain.extend([
                    ('consumed', '=', False),
                    ('expires_at', '>', fields.Datetime.now())
                ])
            
            if args.sr_user:
                user = User.search([('username', '=', args.sr_user)], limit=1)
                if user:
                    domain.append(('user_id', '=', user.id))
            
            tokens = SetupToken.search(domain, order='create_date desc', limit=50)
            
            if not tokens:
                print("No setup tokens found")
                return
            
            print(f"{'ID':<6} {'USER':<15} {'DEVICE':<20} {'STATUS':<12} {'USES':<8} {'EXPIRES':<20} {'CREATED'}")
            print("-" * 110)
            for token in tokens:
                # Determine status
                if token.consumed:
                    status = 'Consumed'
                elif token.expires_at < fields.Datetime.now():
                    status = 'Expired'
                else:
                    status = 'Active'
                
                user = token.user_id.username if token.user_id else 'Unknown'
                device = (token.device_name or '')[:20]
                uses = f"{token.current_uses}/{token.max_uses}"
                expires = token.expires_at.strftime('%Y-%m-%d %H:%M:%S')
                created = token.create_date.strftime('%Y-%m-%d %H:%M')
                
                print(f"{token.id:<6} {user:<15} {device:<20} {status:<12} {uses:<8} {expires:<20} {created}")
        
        elif args.action == 'get':
            # Get token by ID
            if args.token_id.isdigit():
                token = SetupToken.browse(int(args.token_id))
            else:
                print(f"Invalid token ID: {args.token_id}")
                return
            
            if not token or not token.exists():
                print(f"Setup token '{args.token_id}' not found")
                return
            
            # Determine status
            if token.consumed:
                status = 'Consumed'
            elif token.expires_at < fields.Datetime.now():
                status = 'Expired'
            else:
                status = 'Active'
            
            print(f"ID:           {token.id}")
            print(f"User:         {token.user_id.username if token.user_id else 'Unknown'}")
            print(f"Device:       {token.device_name or 'Not specified'}")
            print(f"Status:       {status}")
            print(f"Uses:         {token.current_uses}/{token.max_uses}")
            print(f"Expires:      {token.expires_at}")
            print(f"Created:      {token.create_date}")
            print(f"Created By:   {token.create_uid.name if token.create_uid else 'System'}")
            
            if token.consumed_date:
                print(f"Consumed:     {token.consumed_date}")
            
            if token.allowed_cidrs:
                cidrs = token.get_allowed_cidrs()
                if cidrs:
                    print(f"Allowed CIDRs:")
                    for cidr in cidrs:
                        print(f"  - {cidr}")
        
        elif args.action == 'create':
            # Find user
            user = User.search([('username', '=', args.username)], limit=1)
            if not user:
                print(f"User '{args.username}' not found")
                return
            
            # Find host
            Host = env['sunray.host']
            host = Host.search([('domain', '=', args.sr_host)], limit=1)
            if not host:
                print(f"Error: Host '{args.sr_host}' not found")
                return
            
            # Prepare allowed CIDRs (convert comma-separated to line-separated)
            allowed_cidrs = ''
            if args.sr_cidrs:
                allowed_cidrs = '\n'.join([cidr.strip() for cidr in args.sr_cidrs.split(',') if cidr.strip()])
            
            # Use centralized token creation method
            SetupToken = env['sunray.setup.token']
            token_obj, token_value = SetupToken.create_setup_token(
                user_id=user.id,
                host_id=host.id,
                device_name=args.sr_device,
                validity_hours=args.sr_hours,
                max_uses=args.sr_uses,
                allowed_cidrs=allowed_cidrs
            )
            
            print(f"Setup token created successfully!")
            print(f"ID:       {token_obj.id}")
            print(f"User:     {user.username}")
            print(f"Host:     {host.domain}")
            print(f"Device:   {args.sr_device}")
            print(f"Token:    {token_value}")
            print(f"Expires:  {token_obj.expires_at}")
            print(f"Max Uses: {args.sr_uses}")
            
            if allowed_cidrs:
                print(f"Allowed CIDRs:")
                for cidr in allowed_cidrs.split('\n'):
                    if cidr.strip():
                        print(f"  - {cidr.strip()}")
            
            print(f"\nInstructions:")
            print(f"1. Share this token securely with the user")
            print(f"2. User should visit the setup page")
            print(f"3. Enter username: {user.username}")
            print(f"4. Enter token: {token_value}")
            print(f"5. Complete passkey registration")
        
        elif args.action == 'delete':
            # Get token by ID
            if args.token_id.isdigit():
                token = SetupToken.browse(int(args.token_id))
            else:
                print(f"Invalid token ID: {args.token_id}")
                return
            
            if not token or not token.exists():
                print(f"Setup token '{args.token_id}' not found")
                return
            
            # Store info before deletion
            token_id = token.id
            user = token.user_id.username if token.user_id else 'Unknown'
            device = token.device_name or 'Unknown device'
            
            # Delete token
            token.unlink()
            
            print(f"Setup token deleted:")
            print(f"  ID: {token_id}")
            print(f"  User: {user}")
            print(f"  Device: {device}")


# Register the command
def add_command(subparsers):
    parser = subparsers.add_parser('sunray',
                                  help='Sunray authentication system management')
    parser.set_defaults(run=SunrayCommand.run)