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
        apikey_list.add_argument('--output', '-o', choices=['table', 'json', 'yaml'],
                                default='table', help='Output format (default: table)')
        
        # apikey get
        apikey_get = apikey_sub.add_parser('get', help='Get API key details')
        apikey_get.add_argument('identifier', help='API key name or ID')
        apikey_get.add_argument('--output', '-o', choices=['table', 'json', 'yaml'],
                               default='table', help='Output format (default: table)')
        
        # apikey create
        apikey_create = apikey_sub.add_parser('create', help='Create API key')
        apikey_create.add_argument('name', help='API key name')
        apikey_create.add_argument('--sr-description', help='Description')
        apikey_create.add_argument('--sr-scopes', help='Comma-separated scopes')
        apikey_create.add_argument('--sr-worker', action='store_true',
                                  help='Create key for Worker with default scopes')
        
        # apikey delete
        apikey_delete = apikey_sub.add_parser('delete', help='Delete API key')
        apikey_delete.add_argument('identifier', help='API key name or ID')
        
        # User commands
        user = subparsers.add_parser('user', help='Manage users')
        user_sub = user.add_subparsers(dest='action', help='Action')
        
        # user list
        user_list = user_sub.add_parser('list', help='List users')
        user_list.add_argument('--sr-host', help='Filter by host')
        user_list.add_argument('--output', '-o', choices=['table', 'json', 'yaml'],
                              default='table', help='Output format (default: table)')
        
        # user get
        user_get = user_sub.add_parser('get', help='Get user details')
        user_get.add_argument('username', help='Username')
        user_get.add_argument('--output', '-o', choices=['table', 'json', 'yaml'],
                             default='table', help='Output format (default: table)')
        
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
        session_list.add_argument('--output', '-o', choices=['table', 'json', 'yaml'],
                                 default='table', help='Output format (default: table)')
        
        # session get
        session_get = session_sub.add_parser('get', help='Get session details')
        session_get.add_argument('session_id', help='Session ID')
        session_get.add_argument('--output', '-o', choices=['table', 'json', 'yaml'],
                                default='table', help='Output format (default: table)')
        
        # session delete 
        session_delete = session_sub.add_parser('delete', help='Delete session')
        session_delete.add_argument('session_id', help='Session ID')
        session_delete.add_argument('--sr-hard', action='store_true',
                                   help='Permanently delete (default: soft delete)')
        
        # session revoke
        session_revoke = session_sub.add_parser('revoke', help='Revoke session with audit trail')
        session_revoke.add_argument('session_id', help='Session ID')
        session_revoke.add_argument('--reason', help='Revocation reason for audit trail')
        
        # session cleanup
        session_cleanup = session_sub.add_parser('cleanup', help='Remove expired sessions')
        session_cleanup.add_argument('--dry-run', action='store_true',
                                    help='Show what would be removed without doing it')
        
        # session stats
        session_stats = session_sub.add_parser('stats', help='Show session statistics')
        session_stats.add_argument('--output', '-o', choices=['table', 'json', 'yaml'],
                                  default='table', help='Output format (default: table)')
        
        # Host commands
        host = subparsers.add_parser('host', help='Manage hosts')
        host_sub = host.add_subparsers(dest='action', help='Action')
        
        # host list
        host_list = host_sub.add_parser('list', help='List hosts')
        host_list.add_argument('--output', '-o', choices=['table', 'json', 'yaml'],
                              default='table', help='Output format (default: table)')
        
        # host get
        host_get = host_sub.add_parser('get', help='Get host details')
        host_get.add_argument('name', help='Host name or domain')
        host_get.add_argument('--output', '-o', choices=['table', 'json', 'yaml'],
                             default='table', help='Output format (default: table)')
        
        # host create
        host_create = host_sub.add_parser('create', help='Create host')
        host_create.add_argument('domain', help='Domain')
        host_create.add_argument('--sr-backend', help='Backend URL', default='')
        host_create.add_argument('--sr-worker-url', help='Cloudflare Worker URL', required=True)
        host_create.add_argument('--sr-cidr', help='CIDR whitelist (comma-separated)')
        host_create.add_argument('--sr-public', help='Public URL patterns (comma-separated)')
        
        # host delete
        host_delete = host_sub.add_parser('delete', help='Delete host')
        host_delete.add_argument('domain', help='Host domain to delete')
        host_delete.add_argument('--sr-force', action='store_true',
                                help='Force delete even if users exist')
        
        # Cron commands
        cron = subparsers.add_parser('cron', help='Manage cron jobs')
        cron_sub = cron.add_subparsers(dest='action', help='Action')
        
        # cron list
        cron_list = cron_sub.add_parser('list', help='List cron jobs')
        cron_list.add_argument('--output', '-o', choices=['table', 'json', 'yaml'],
                              default='table', help='Output format (default: table)')
        
        # cron get
        cron_get = cron_sub.add_parser('get', help='Get cron job details')
        cron_get.add_argument('cron_id', type=int, help='Cron job ID')
        cron_get.add_argument('--output', '-o', choices=['table', 'json', 'yaml'],
                             default='table', help='Output format (default: table)')
        
        # cron trigger
        cron_trigger = cron_sub.add_parser('trigger', help='Trigger cron job via Odoo Run Now')
        cron_trigger.add_argument('cron_id', type=int, help='Cron job ID')
        
        # Setup Token commands
        setuptoken = subparsers.add_parser('setuptoken', help='Manage setup tokens')
        setuptoken_sub = setuptoken.add_subparsers(dest='action', help='Action')
        
        # setuptoken list
        setuptoken_list = setuptoken_sub.add_parser('list', help='List setup tokens')
        setuptoken_list.add_argument('--sr-all', action='store_true',
                                    help='Show all tokens including consumed/expired')
        setuptoken_list.add_argument('--sr-user', help='Filter by username')
        setuptoken_list.add_argument('--output', '-o', choices=['table', 'json', 'yaml'],
                                    default='table', help='Output format (default: table)')
        
        # setuptoken get
        setuptoken_get = setuptoken_sub.add_parser('get', help='Get setup token details')
        setuptoken_get.add_argument('token_id', help='Setup token ID')
        setuptoken_get.add_argument('--output', '-o', choices=['table', 'json', 'yaml'],
                                   default='table', help='Output format (default: table)')
        
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
        
        # Cache commands
        cache = subparsers.add_parser('cache', help='Manage worker cache')
        cache_sub = cache.add_subparsers(dest='action', help='Action')
        
        # cache status
        cache_status = cache_sub.add_parser('status', help='Get cache status from worker')
        
        # cache invalidate
        cache_invalidate = cache_sub.add_parser('invalidate', help='Trigger cache invalidation')
        cache_invalidate.add_argument('--sr-scope', required=True,
                                     choices=['global', 'user', 'host', 'config'],
                                     help='Invalidation scope')
        cache_invalidate.add_argument('--sr-target', help='Target for user/host scope')
        cache_invalidate.add_argument('--sr-reason', help='Reason for invalidation')
        
        # cache clear
        cache_clear = cache_sub.add_parser('clear', help='Clear cache directly')
        cache_clear.add_argument('--sr-scope', required=True,
                               choices=['all', 'config', 'sessions'],
                               help='Cache scope to clear')
        cache_clear.add_argument('--sr-target', help='Target for sessions scope')
        
        # Audit log commands
        auditlog = subparsers.add_parser('auditlog', help='Manage audit logs')
        auditlog_sub = auditlog.add_subparsers(dest='action', help='Action')
        
        # auditlog get/list
        auditlog_get = auditlog_sub.add_parser('get', help='Get audit logs')
        auditlog_get.add_argument('--since', default='24h',
                                 help='Time duration (e.g., 1h, 24h, 7d) (default: 24h)')
        auditlog_get.add_argument('--event-type', action='append',
                                 help='Filter by event type (can be used multiple times)')
        auditlog_get.add_argument('--severity', choices=['info', 'warning', 'error', 'critical'],
                                 help='Filter by severity level')
        auditlog_get.add_argument('--user', help='Filter by sunray username')
        auditlog_get.add_argument('--admin', help='Filter by admin username')
        auditlog_get.add_argument('--worker', help='Filter by worker ID')
        auditlog_get.add_argument('--request-id', help='Filter by request ID')
        auditlog_get.add_argument('--sublimation-only', action='store_true',
                                 help='Only show WAF bypass (sublimation) cookie events')
        auditlog_get.add_argument('--limit', type=int, default=100,
                                 help='Maximum results (default: 100)')
        auditlog_get.add_argument('--output', '-o', choices=['table', 'json', 'yaml'],
                                 default='table', help='Output format (default: table)')
        auditlog_get.add_argument('--follow', '-f', action='store_true',
                                 help='Follow/stream new events (not implemented yet)')
        auditlog_get.add_argument('--no-headers', action='store_true',
                                 help='Omit headers in table output')
        
        # auditlog list (alias for get)
        auditlog_list = auditlog_sub.add_parser('list', help='List audit logs (alias for get)')
        auditlog_list.add_argument('--since', default='24h',
                                  help='Time duration (e.g., 1h, 24h, 7d) (default: 24h)')
        auditlog_list.add_argument('--event-type', action='append',
                                  help='Filter by event type (can be used multiple times)')
        auditlog_list.add_argument('--severity', choices=['info', 'warning', 'error', 'critical'],
                                  help='Filter by severity level')
        auditlog_list.add_argument('--user', help='Filter by sunray username')
        auditlog_list.add_argument('--admin', help='Filter by admin username')
        auditlog_list.add_argument('--worker', help='Filter by worker ID')
        auditlog_list.add_argument('--request-id', help='Filter by request ID')
        auditlog_list.add_argument('--sublimation-only', action='store_true',
                                  help='Only show WAF bypass (sublimation) cookie events')
        auditlog_list.add_argument('--limit', type=int, default=100,
                                  help='Maximum results (default: 100)')
        auditlog_list.add_argument('--output', '-o', choices=['table', 'json', 'yaml'],
                                  default='table', help='Output format (default: table)')
        auditlog_list.add_argument('--no-headers', action='store_true',
                                  help='Omit headers in table output')
        
        # auditlog describe
        auditlog_describe = auditlog_sub.add_parser('describe', help='Describe specific audit log entry')
        auditlog_describe.add_argument('log_id', type=int, help='Audit log entry ID')
        auditlog_describe.add_argument('--output', '-o', choices=['table', 'json', 'yaml'],
                                      default='table', help='Output format (default: table)')
        
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
                # Setup CLI context for audit logging
                import uuid
                request_id = f"cli:{uuid.uuid4()}"
                context = {
                    'sunray_request_id': request_id,
                    'sunray_event_source': 'cli',
                    'sunray_admin_user_id': SUPERUSER_ID
                }
                env = api.Environment(cr, SUPERUSER_ID, context)
                
                # Route to appropriate handler
                if parsed_args.resource == 'apikey':
                    self._handle_apikey(env, parsed_args)
                elif parsed_args.resource == 'user':
                    self._handle_user(env, parsed_args)
                elif parsed_args.resource == 'session':
                    self._handle_session(env, parsed_args)
                elif parsed_args.resource == 'host':
                    self._handle_host(env, parsed_args)
                elif parsed_args.resource == 'cron':
                    self._handle_cron(env, parsed_args)
                elif parsed_args.resource == 'setuptoken':
                    self._handle_setuptoken(env, parsed_args)
                elif parsed_args.resource == 'cache':
                    self._handle_cache(env, parsed_args)
                elif parsed_args.resource == 'auditlog':
                    self._handle_auditlog(env, parsed_args)
                
                # Commit changes for write operations
                if parsed_args.action in ['create', 'delete', 'revoke', 'create-token', 'cleanup', 'trigger']:
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
            
            # Format output
            if args.output == 'json':
                self._output_apikeys_json(keys)
            elif args.output == 'yaml':
                self._output_apikeys_yaml(keys)
            else:
                self._output_apikeys_table(keys)
        
        elif args.action == 'get':
            # Search by name or ID
            if args.identifier.isdigit():
                key = ApiKey.browse(int(args.identifier))
                if not key.exists():
                    key = False
            else:
                key = ApiKey.search([('name', '=', args.identifier)], limit=1)
            
            if not key:
                print(f"API key '{args.identifier}' not found")
                return
            
            # Format output
            if args.output == 'json':
                self._output_apikeys_json([key])
            elif args.output == 'yaml':
                self._output_apikeys_yaml([key])
            else:
                self._output_apikey_detailed(key)
        
        elif args.action == 'create':
            # Check if API key with same name already exists
            existing_key = ApiKey.search([('name', '=', args.name)], limit=1)
            if existing_key:
                print(f"Error: API key with name '{args.name}' already exists (ID: {existing_key.id})")
                return
            
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
            print(f"ID:   {key.id}")
            print(f"Name: {key.name}")
            print(f"Key:  {key.key}")
            
            if args.sr_worker:
                print(f"\nTo configure Worker:")
                print(f"cd worker && echo '{key.key}' | wrangler secret put ADMIN_API_KEY")
                print(f"\nOr add to worker/.dev.vars:")
                print(f"ADMIN_API_KEY={key.key}")
        
        elif args.action == 'delete':
            # Search by name or ID
            if args.identifier.isdigit():
                key = ApiKey.browse(int(args.identifier))
                if not key.exists():
                    key = False
            else:
                key = ApiKey.search([('name', '=', args.identifier)], limit=1)
            
            if not key:
                print(f"API key '{args.identifier}' not found")
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
            
            # Format output
            if args.output == 'json':
                self._output_sessions_json(sessions)
            elif args.output == 'yaml':
                self._output_sessions_yaml(sessions)
            else:
                self._output_sessions_table(sessions)
        
        elif args.action == 'get':
            session = self._find_session(Session, args.session_id)
            if not session:
                print(f"Session '{args.session_id}' not found")
                return
            
            # Format output
            if args.output == 'json':
                self._output_sessions_json([session], detailed=True)
            elif args.output == 'yaml':
                self._output_sessions_yaml([session], detailed=True)
            else:
                self._output_session_detailed(session)
        
        elif args.action == 'delete':
            session = self._find_session(Session, args.session_id)
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
        
        elif args.action == 'revoke':
            session = self._find_session(Session, args.session_id)
            if not session:
                print(f"Session '{args.session_id}' not found")
                return
            
            reason = args.reason or 'CLI revocation'
            session.revoke(reason=reason)
            print(f"Session revoked: {session.session_id}")
            print(f"Reason: {reason}")
        
        elif args.action == 'cleanup':
            # Find expired sessions
            expired_sessions = Session.search([
                ('expires_at', '<', fields.Datetime.now()),
                ('is_active', '=', True)
            ])
            
            if not expired_sessions:
                print("No expired sessions found")
                return
            
            if args.dry_run:
                print(f"Would remove {len(expired_sessions)} expired sessions:")
                for session in expired_sessions:
                    print(f"  - {session.session_id} (user: {session.user_id.username}, expired: {session.expires_at})")
            else:
                count = len(expired_sessions)
                expired_sessions.write({'is_active': False})
                print(f"Cleaned up {count} expired sessions")
        
        elif args.action == 'stats':
            stats = self._calculate_session_stats(Session)
            
            if args.output == 'json':
                import json
                print(json.dumps(stats, indent=2))
            elif args.output == 'yaml':
                import yaml
                print(yaml.dump(stats, default_flow_style=False))
            else:
                self._output_session_stats_table(stats)
    
    def _handle_host(self, env, args):
        """Handle host operations"""
        Host = env['sunray.host']
        
        if args.action == 'list':
            hosts = Host.search([])
            
            if not hosts:
                print("No hosts found")
                return
            
            print(f"{'DOMAIN':<25} {'WORKER URL':<35} {'ACTIVE':<8} {'RULES':<10} {'USERS':<8} {'SESSION':<8}")
            print("-" * 100)
            for host in hosts:
                active = '✓' if host.is_active else '✗'
                worker_url = host.worker_url[:32] + '...' if len(host.worker_url) > 35 else host.worker_url
                rules_count = len(host.access_rule_ids)
                user_count = len(host.user_ids)
                session_duration = f"{host.session_duration_s}s"
                print(f"{host.domain:<25} {worker_url:<35} {active:<8} {rules_count:<10} {user_count:<8} {session_duration:<8}")
        
        elif args.action == 'get':
            # Search by domain
            host = Host.search([('domain', '=', args.name)], limit=1)
            
            if not host:
                print(f"Host '{args.name}' not found")
                return
            
            print(f"Domain:                     {host.domain}")
            print(f"Worker URL:                 {host.worker_url}")
            print(f"Backend URL:                {host.backend_url or 'Not configured'}")
            print(f"Active:                     {'Yes' if host.is_active else 'No'}")
            print(f"Users:                      {len(host.user_ids)}")
            print(f"Session Duration:           {host.session_duration_s}s ({host.session_duration_s//3600}h {(host.session_duration_s%3600)//60}m)")
            print(f"WAF Bypass Revalidation:    {host.waf_bypass_revalidation_s}s ({host.waf_bypass_revalidation_s//60}m)")
            print(f"WAF Bypass Enabled:         {'Yes' if host.bypass_waf_for_authenticated else 'No'}")
            print(f"Created:                    {host.create_date}")
            
            if host.access_rule_ids:
                print(f"\nAccess Rules: {len(host.access_rule_ids)}")
                for rule in host.access_rule_ids.sorted('priority'):
                    access_type = rule.access_type.replace('_', ' ').title()
                    patterns = ', '.join(rule.get_url_patterns()[:2])  # Show first 2 patterns
                    if len(rule.get_url_patterns()) > 2:
                        patterns += f" (+ {len(rule.get_url_patterns())-2} more)"
                    print(f"  - Priority {rule.priority}: {access_type} - {patterns}")
            
            if host.webhook_token_ids:
                print(f"\nWebhook Tokens: {len(host.webhook_token_ids)}")
                for token in host.webhook_token_ids:
                    status = "Active" if not token.expires_at or token.expires_at > fields.Datetime.now() else "Expired"
                    print(f"  - {token.name}: {status}")
        
        elif args.action == 'create':
            data = {
                'domain': args.domain,
                'backend_url': args.sr_backend or '',
                'worker_url': args.sr_worker_url,
                'is_active': True
            }
            
            host = Host.create([data])
            
            print(f"Host created successfully!")
            print(f"Domain: {host.domain}")
            print(f"ID:     {host.id}")
            print(f"Session Duration: {host.session_duration_s}s (default)")
            print(f"WAF Revalidation: {host.waf_bypass_revalidation_s}s (default)")
            
            # Note: Access rules can be added via the UI or separate commands
            if args.sr_cidr or args.sr_public:
                print("\nNote: --sr-cidr and --sr-public options are no longer supported.")
                print("Please use the Sunray admin UI to configure Access Rules for this host.")
        
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
    
    def _handle_cache(self, env, args):
        """Handle cache operations"""
        
        if args.action == 'status':
            # For status, get all unique worker URLs
            Host = env['sunray.host']
            hosts = Host.search([('is_active', '=', True)])
            worker_urls = list(set(host.worker_url for host in hosts if host.worker_url))
            
            if not worker_urls:
                print("Error: No active hosts with worker URLs found")
                return
            
            # Query each worker
            for worker_url in worker_urls:
                print(f"\n=== Worker: {worker_url} ===")
                self._query_worker_status(env, worker_url)
                
        elif args.action == 'invalidate':
            # Use model method for invalidation
            self._handle_cache_invalidate(env, args)
            
        elif args.action == 'clear':
            print("Clear cache not implemented - use invalidate instead")
    
    def _query_worker_status(self, env, worker_url):
        """Query a single worker's cache status"""
        import requests
        
        # Get API key
        api_key_obj = env['sunray.api.key'].sudo().search([
            ('is_active', '=', True)
        ], limit=1)
        
        if not api_key_obj:
            print("Error: No active API key found")
            return
        
        headers = {
            'Authorization': f'Bearer {api_key_obj.key}',
            'Content-Type': 'application/json'
        }
        
        url = f"{worker_url}/sunray-wrkr/v1/cache"
        try:
            response = requests.get(url, headers=headers, timeout=5)
            response.raise_for_status()
            status = response.json()
            
            print("Cache Status:")
            print(f"  Worker ID: {status.get('worker_id', 'N/A')}")
            print(f"  Timestamp: {status.get('timestamp', 'N/A')}")
            
            if 'caches' in status:
                caches = status['caches']
                if 'config' in caches:
                    config = caches['config']
                    print("\nConfiguration Cache:")
                    print(f"  Exists: {config.get('exists', False)}")
                    if config.get('exists'):
                        print(f"  Age: {config.get('age_seconds', 0)} seconds")
                        print(f"  TTL: {config.get('ttl_seconds', 0)} seconds")
                        print(f"  Last Version Check: {config.get('last_version_check', 'N/A')}")
            
            if 'invalidation_tracker' in status:
                tracker = status['invalidation_tracker']
                print("\nInvalidation Tracker:")
                print(f"  Processed Count: {tracker.get('processed_count', 0)}")
                print(f"  Last Invalidation: {tracker.get('last_invalidation', 'Never')}")
                
        except requests.exceptions.RequestException as e:
            print(f"Error getting cache status: {e}")
    
    def _handle_cache_invalidate(self, env, args):
        """Handle cache invalidation using model methods"""
        if args.sr_scope == 'host':
            # Invalidate specific host cache
            if not args.sr_target:
                print("Error: --sr-target required for host scope")
                return
                
            Host = env['sunray.host']
            host = Host.search([('domain', '=', args.sr_target)], limit=1)
            if not host:
                print(f"Error: Host '{args.sr_target}' not found")
                return
            
            try:
                result = host._call_worker_cache_invalidate(
                    scope=args.sr_scope,
                    target=args.sr_target,
                    reason=args.sr_reason or f'CLI invalidation by {env.user.name}'
                )
                print(f"✓ Cache invalidation triggered for host {args.sr_target}")
                print(f"  Message: {result.get('message', 'Success')}")
            except Exception as e:
                print(f"✗ Cache invalidation failed: {e}")
        
        else:
            # For global/user scope, invalidate across all workers
            Host = env['sunray.host']
            hosts = Host.search([('is_active', '=', True)])
            worker_urls = list(set(host.worker_url for host in hosts if host.worker_url))
            
            if not worker_urls:
                print("Error: No active hosts with worker URLs found")
                return
            
            success_count = 0
            for worker_url in worker_urls:
                # Pick any host with this worker_url to call the method
                host = hosts.filtered(lambda h: h.worker_url == worker_url)[0]
                try:
                    result = host._call_worker_cache_invalidate(
                        scope=args.sr_scope,
                        target=args.sr_target,
                        reason=args.sr_reason or f'CLI invalidation by {env.user.name}'
                    )
                    print(f"✓ Cache invalidation triggered on {worker_url}")
                    success_count += 1
                except Exception as e:
                    print(f"✗ Failed to invalidate cache on {worker_url}: {e}")
            
            print(f"\nInvalidated cache on {success_count}/{len(worker_urls)} workers")

    def _handle_auditlog(self, env, args):
        """Handle audit log commands"""
        import json
        from datetime import datetime, timedelta
        
        AuditLog = env['sunray.audit.log']
        
        if args.action in ['get', 'list']:
            # Parse time duration
            since_filter = self._parse_time_duration(args.since)
            
            # Build domain filter
            domain = [('timestamp', '>=', since_filter)]
            
            if args.event_type:
                domain.append(('event_type', 'in', args.event_type))
            
            if getattr(args, 'sublimation_only', False):
                domain.append(('event_type', 'like', 'waf_bypass.%'))
            
            if args.severity:
                domain.append(('severity', '=', args.severity))
            
            if args.user:
                # Search by sunray username
                sunray_user = env['sunray.user'].search([('username', '=', args.user)], limit=1)
                if sunray_user:
                    domain.append(('sunray_user_id', '=', sunray_user.id))
                else:
                    # Also check username field for backward compatibility
                    domain.append(('username', '=', args.user))
            
            if args.admin:
                # Search by admin username
                admin_user = env['res.users'].search([('login', '=', args.admin)], limit=1)
                if admin_user:
                    domain.append(('sunray_admin_user_id', '=', admin_user.id))
            
            if args.worker:
                domain.append(('sunray_worker', 'ilike', args.worker))
            
            if args.request_id:
                domain.append(('request_id', '=', args.request_id))
            
            # Search audit logs
            logs = AuditLog.search(domain, limit=args.limit, order='timestamp desc')
            
            if not logs:
                print("No audit logs found matching the criteria.")
                return
            
            # Format output
            if args.output == 'json':
                self._output_auditlog_json(logs)
            elif args.output == 'yaml':
                self._output_auditlog_yaml(logs)
            else:
                self._output_auditlog_table(logs, args.no_headers)
                
        elif args.action == 'describe':
            # Get specific log entry
            log = AuditLog.browse(args.log_id)
            if not log.exists():
                print(f"Error: Audit log entry {args.log_id} not found")
                return
            
            if args.output == 'json':
                self._output_auditlog_json([log], detailed=True)
            elif args.output == 'yaml':
                self._output_auditlog_yaml([log], detailed=True)
            else:
                self._output_auditlog_describe(log)
    
    def _parse_time_duration(self, duration_str):
        """Parse duration string like '1h', '24h', '7d' into datetime"""
        from datetime import datetime, timedelta
        
        if duration_str.endswith('h'):
            hours = int(duration_str[:-1])
            return datetime.now() - timedelta(hours=hours)
        elif duration_str.endswith('d'):
            days = int(duration_str[:-1])
            return datetime.now() - timedelta(days=days)
        elif duration_str.endswith('m'):
            minutes = int(duration_str[:-1])
            return datetime.now() - timedelta(minutes=minutes)
        else:
            raise ValueError(f"Invalid duration format: {duration_str}. Use format like '1h', '24h', '7d'")
    
    def _output_auditlog_table(self, logs, no_headers=False):
        """Output audit logs in table format"""
        if not no_headers:
            print(f"{'ID':<6} {'Timestamp':<20} {'Event Type':<25} {'Severity':<8} {'Admin User':<15} {'Sunray User':<15} {'Worker':<12} {'Request ID':<20}")
            print("-" * 140)
        
        for log in logs:
            timestamp = log.timestamp.strftime('%Y-%m-%d %H:%M:%S') if log.timestamp else 'N/A'
            admin_user = log.sunray_admin_user_id.login if log.sunray_admin_user_id else ''
            sunray_user = log.sunray_user_id.username if log.sunray_user_id else (log.username or '')
            worker = log.sunray_worker[:11] + '..' if log.sunray_worker and len(log.sunray_worker) > 12 else (log.sunray_worker or '')
            request_id = log.request_id[:19] + '..' if log.request_id and len(log.request_id) > 20 else (log.request_id or '')
            
            print(f"{log.id:<6} {timestamp:<20} {log.event_type:<25} {log.severity:<8} {admin_user:<15} {sunray_user:<15} {worker:<12} {request_id:<20}")
    
    def _output_auditlog_json(self, logs, detailed=False):
        """Output audit logs in JSON format"""
        import json
        
        result = []
        for log in logs:
            entry = {
                'id': log.id,
                'timestamp': log.timestamp.isoformat() if log.timestamp else None,
                'event_type': log.event_type,
                'severity': log.severity,
                'sunray_admin_user_id': log.sunray_admin_user_id.id if log.sunray_admin_user_id else None,
                'sunray_admin_user_login': log.sunray_admin_user_id.login if log.sunray_admin_user_id else None,
                'sunray_user_id': log.sunray_user_id.id if log.sunray_user_id else None,
                'sunray_user_username': log.sunray_user_id.username if log.sunray_user_id else None,
                'sunray_worker': log.sunray_worker,
                'request_id': log.request_id,
                'event_source': log.event_source,
                'ip_address': log.ip_address,
                'username': log.username,  # Legacy field
            }
            
            if detailed:
                entry.update({
                    'user_agent': log.user_agent,
                    'details': log.get_details_dict(),
                })
            
            result.append(entry)
        
        print(json.dumps(result, indent=2))
    
    def _output_auditlog_yaml(self, logs, detailed=False):
        """Output audit logs in YAML format"""
        import yaml
        
        result = []
        for log in logs:
            entry = {
                'id': log.id,
                'timestamp': log.timestamp.isoformat() if log.timestamp else None,
                'event_type': log.event_type,
                'severity': log.severity,
                'sunray_admin_user_id': log.sunray_admin_user_id.id if log.sunray_admin_user_id else None,
                'sunray_admin_user_login': log.sunray_admin_user_id.login if log.sunray_admin_user_id else None,
                'sunray_user_id': log.sunray_user_id.id if log.sunray_user_id else None,
                'sunray_user_username': log.sunray_user_id.username if log.sunray_user_id else None,
                'sunray_worker': log.sunray_worker,
                'request_id': log.request_id,
                'event_source': log.event_source,
                'ip_address': log.ip_address,
                'username': log.username,  # Legacy field
            }
            
            if detailed:
                entry.update({
                    'user_agent': log.user_agent,
                    'details': log.get_details_dict(),
                })
            
            result.append(entry)
        
        print(yaml.dump(result, default_flow_style=False))
    
    def _output_auditlog_describe(self, log):
        """Output detailed audit log entry in human-readable format"""
        print(f"Audit Log Entry #{log.id}")
        print("-" * 40)
        print(f"Timestamp:      {log.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC') if log.timestamp else 'N/A'}")
        print(f"Event Type:     {log.event_type}")
        print(f"Severity:       {log.severity}")
        print(f"Event Source:   {log.event_source or 'N/A'}")
        print(f"Request ID:     {log.request_id or 'N/A'}")
        print()
        print("User Information:")
        print(f"  Admin User:   {log.sunray_admin_user_id.login if log.sunray_admin_user_id else 'N/A'}")
        print(f"  Sunray User:  {log.sunray_user_id.username if log.sunray_user_id else 'N/A'}")
        print(f"  Worker:       {log.sunray_worker or 'N/A'}")
        print(f"  Username:     {log.username or 'N/A'} (legacy field)")
        print()
        print("Network Information:")
        print(f"  IP Address:   {log.ip_address or 'N/A'}")
        print(f"  User Agent:   {log.user_agent or 'N/A'}")
        print()
        if log.details:
            print("Event Details:")
            details = log.get_details_dict()
            if isinstance(details, dict):
                for key, value in details.items():
                    print(f"  {key}: {value}")
            else:
                print(f"  {details}")
    
    def _handle_cron(self, env, args):
        """Handle cron job operations"""
        Cron = env['ir.cron']
        
        if args.action == 'list':
            # Search for Sunray-related cron jobs
            crons = Cron.search([('name', 'like', 'Sunray:%')], order='name')
            
            if not crons:
                print("No Sunray cron jobs found")
                return
            
            if args.output == 'json':
                self._output_crons_json(crons)
            elif args.output == 'yaml':
                self._output_crons_yaml(crons)
            else:
                self._output_crons_table(crons)
        
        elif args.action == 'get':
            cron = Cron.browse(args.cron_id)
            if not cron.exists():
                print(f"Cron job {args.cron_id} not found")
                return
            
            if args.output == 'json':
                self._output_crons_json([cron], detailed=True)
            elif args.output == 'yaml':
                self._output_crons_yaml([cron], detailed=True)
            else:
                self._output_cron_detailed(cron)
        
        elif args.action == 'trigger':
            cron = Cron.browse(args.cron_id)
            if not cron.exists():
                print(f"Cron job {args.cron_id} not found")
                return
            
            # Trigger the cron job via Odoo's "Run Now" method
            try:
                cron.method_direct_trigger()
                print(f"✓ Cron job '{cron.name}' triggered successfully")
                print(f"  ID: {cron.id}")
                print(f"  Last run: {cron.lastcall or 'Never'}")
            except Exception as e:
                print(f"✗ Failed to trigger cron job: {e}")
    
    def _find_session(self, Session, session_id):
        """Find session by exact ID or partial match"""
        session = Session.search([('session_id', '=', session_id)], limit=1)
        if not session:
            # Try partial match
            session = Session.search([('session_id', 'like', session_id + '%')], limit=1)
        return session
    
    def _output_sessions_table(self, sessions):
        """Output sessions in table format"""
        print(f"{'SESSION ID':<20} {'USER':<15} {'HOST':<20} {'IP ADDRESS':<15} {'STATUS':<10} {'CREATED'}")
        print("-" * 100)
        for session in sessions:
            sid = session.session_id[:18] + '..' if len(session.session_id) > 20 else session.session_id
            user = session.user_id.username if session.user_id else 'Unknown'
            host = (session.host_id.domain if session.host_id else '')[:20]
            ip = session.created_ip or 'Unknown'
            status = 'Active' if session.is_active else 'Expired'
            created = session.created_at.strftime('%Y-%m-%d %H:%M')
            print(f"{sid:<20} {user:<15} {host:<20} {ip:<15} {status:<10} {created}")
    
    def _output_session_detailed(self, session):
        """Output detailed session information with computed fields marked [C]"""
        from datetime import datetime
        
        print(f"Session ID:       {session.session_id}")
        print(f"User:             {session.user_id.username if session.user_id else 'Unknown'}")
        print(f"Host:             {session.host_id.domain if session.host_id else 'Unknown'}")
        print(f"Active:           {'Yes' if session.is_active else 'No'}")
        print(f"Revoked:          {'Yes' if session.revoked else 'No'}")
        
        if session.revoked:
            print(f"Revoked At:       {session.revoked_at or 'Unknown'}")
            print(f"Revoked Reason:   {session.revoked_reason or 'None specified'}")
        
        print(f"Created At:       {session.created_at}")
        print(f"Last Activity:    {session.last_activity}")
        print(f"Expires At:       {session.expires_at}")
        
        # Computed fields with [C] marker
        now = fields.Datetime.now()
        if session.expires_at:
            expired = session.expires_at < now
            if expired:
                time_diff = now - session.expires_at
                print(f"[C] Expired:      Yes ({time_diff} ago)")
            else:
                time_diff = session.expires_at - now
                print(f"[C] Expired:      No ({time_diff} remaining)")
        else:
            print(f"[C] Expired:      Unknown (no expiry set)")
        
        print(f"Created IP:       {session.created_ip or 'Unknown'}")
        print(f"Last IP:          {session.last_ip or 'Same as created'}")
        print(f"User Agent:       {(session.user_agent or 'Unknown')[:80]}")
        print(f"Device Fingerprint: {session.device_fingerprint or 'None'}")
        print(f"Passkey Used:     {session.passkey_id.credential_id[:20] + '...' if session.passkey_id else 'Unknown'}")
        print(f"CSRF Token:       {session.csrf_token[:20] + '...' if session.csrf_token else 'None'}")
        
        if session.totp_verified:
            print(f"TOTP Verified:    Yes (at {session.totp_verified_at})")
        else:
            print(f"TOTP Verified:    No")
        
        if session.risk_score:
            print(f"Risk Score:       {session.risk_score}")
    
    def _output_sessions_json(self, sessions, detailed=False):
        """Output sessions in JSON format"""
        import json
        
        result = []
        for session in sessions:
            entry = {
                'session_id': session.session_id,
                'user_id': session.user_id.id if session.user_id else None,
                'username': session.user_id.username if session.user_id else None,
                'host_id': session.host_id.id if session.host_id else None,
                'host_domain': session.host_id.domain if session.host_id else None,
                'is_active': session.is_active,
                'revoked': session.revoked,
                'created_at': session.created_at.isoformat() if session.created_at else None,
                'last_activity': session.last_activity.isoformat() if session.last_activity else None,
                'expires_at': session.expires_at.isoformat() if session.expires_at else None,
                'created_ip': session.created_ip,
                'last_ip': session.last_ip,
            }
            
            if detailed:
                now = fields.Datetime.now()
                entry.update({
                    'revoked_at': session.revoked_at.isoformat() if session.revoked_at else None,
                    'revoked_reason': session.revoked_reason,
                    'user_agent': session.user_agent,
                    'device_fingerprint': session.device_fingerprint,
                    'credential_id': session.credential_id,
                    'csrf_token': session.csrf_token,
                    'totp_verified': session.totp_verified,
                    'totp_verified_at': session.totp_verified_at.isoformat() if session.totp_verified_at else None,
                    'risk_score': session.risk_score,
                    # Computed fields
                    'computed_expired': session.expires_at < now if session.expires_at else None,
                    'computed_time_to_expiry': str(session.expires_at - now) if session.expires_at and session.expires_at > now else None,
                })
            
            result.append(entry)
        
        print(json.dumps(result, indent=2))
    
    def _output_sessions_yaml(self, sessions, detailed=False):
        """Output sessions in YAML format"""
        import yaml
        
        result = []
        for session in sessions:
            entry = {
                'session_id': session.session_id,
                'user_id': session.user_id.id if session.user_id else None,
                'username': session.user_id.username if session.user_id else None,
                'host_id': session.host_id.id if session.host_id else None,
                'host_domain': session.host_id.domain if session.host_id else None,
                'is_active': session.is_active,
                'revoked': session.revoked,
                'created_at': session.created_at.isoformat() if session.created_at else None,
                'last_activity': session.last_activity.isoformat() if session.last_activity else None,
                'expires_at': session.expires_at.isoformat() if session.expires_at else None,
                'created_ip': session.created_ip,
                'last_ip': session.last_ip,
            }
            
            if detailed:
                now = fields.Datetime.now()
                entry.update({
                    'revoked_at': session.revoked_at.isoformat() if session.revoked_at else None,
                    'revoked_reason': session.revoked_reason,
                    'user_agent': session.user_agent,
                    'device_fingerprint': session.device_fingerprint,
                    'credential_id': session.credential_id,
                    'csrf_token': session.csrf_token,
                    'totp_verified': session.totp_verified,
                    'totp_verified_at': session.totp_verified_at.isoformat() if session.totp_verified_at else None,
                    'risk_score': session.risk_score,
                    # Computed fields
                    'computed_expired': session.expires_at < now if session.expires_at else None,
                    'computed_time_to_expiry': str(session.expires_at - now) if session.expires_at and session.expires_at > now else None,
                })
            
            result.append(entry)
        
        print(yaml.dump(result, default_flow_style=False))
    
    def _calculate_session_stats(self, Session):
        """Calculate session statistics"""
        now = fields.Datetime.now()
        
        # Active sessions
        active_count = Session.search_count([('is_active', '=', True)])
        
        # Expired but not cleaned up
        expired_count = Session.search_count([
            ('expires_at', '<', now),
            ('is_active', '=', True)
        ])
        
        # Total sessions
        total_count = Session.search_count([])
        
        # Revoked sessions
        revoked_count = Session.search_count([('revoked', '=', True)])
        
        # Sessions by user (top 10)
        users_query = """
            SELECT su.username, COUNT(ss.id) as session_count
            FROM sunray_session ss
            JOIN sunray_user su ON ss.user_id = su.id
            WHERE ss.is_active = true
            GROUP BY su.username
            ORDER BY session_count DESC
            LIMIT 10
        """
        Session.env.cr.execute(users_query)
        users_stats = Session.env.cr.fetchall()
        
        return {
            'active_sessions': active_count,
            'expired_sessions': expired_count,
            'total_sessions': total_count,
            'revoked_sessions': revoked_count,
            'cleanup_needed': expired_count > 0,
            'top_users': [{'username': u[0], 'session_count': u[1]} for u in users_stats]
        }
    
    def _output_session_stats_table(self, stats):
        """Output session statistics in table format"""
        print("Session Statistics")
        print("-" * 40)
        print(f"Active Sessions:     {stats['active_sessions']}")
        print(f"Expired Sessions:    {stats['expired_sessions']}")
        print(f"Total Sessions:      {stats['total_sessions']}")
        print(f"Revoked Sessions:    {stats['revoked_sessions']}")
        print(f"Cleanup Needed:      {'Yes' if stats['cleanup_needed'] else 'No'}")
        
        if stats['top_users']:
            print("\nTop Users by Active Sessions:")
            print(f"{'USERNAME':<20} {'SESSIONS'}")
            print("-" * 30)
            for user_stat in stats['top_users']:
                print(f"{user_stat['username']:<20} {user_stat['session_count']}")
    
    def _output_crons_table(self, crons):
        """Output cron jobs in table format"""
        print(f"{'ID':<6} {'NAME':<40} {'SCHEDULE':<15} {'ACTIVE':<8} {'LAST RUN':<20}")
        print("-" * 100)
        for cron in crons:
            schedule = f"{cron.interval_number}{cron.interval_type[0]}"  # e.g., "1d", "6h"
            active = '✓' if cron.active else '✗'
            last_run = cron.lastcall.strftime('%Y-%m-%d %H:%M') if cron.lastcall else 'Never'
            name = cron.name[:38] + '..' if len(cron.name) > 40 else cron.name
            print(f"{cron.id:<6} {name:<40} {schedule:<15} {active:<8} {last_run:<20}")
    
    def _output_cron_detailed(self, cron):
        """Output detailed cron job information with computed fields marked [C]"""
        from datetime import datetime, timedelta
        
        print(f"ID:               {cron.id}")
        print(f"Name:             {cron.name}")
        print(f"Model:            {cron.model_id.model if cron.model_id else 'Unknown'}")
        print(f"Function:         {cron.state}")
        print(f"Code:             {cron.code or 'N/A'}")
        print(f"Active:           {'Yes' if cron.active else 'No'}")
        print(f"User:             {cron.user_id.name if cron.user_id else 'System'}")
        print(f"Interval:         Every {cron.interval_number} {cron.interval_type}")
        print(f"Last Run:         {cron.lastcall or 'Never'}")
        print(f"Next Run:         {cron.nextcall or 'Not scheduled'}")
        
        # Computed fields with [C] marker
        if cron.lastcall:
            now = fields.Datetime.now()
            time_since = now - cron.lastcall
            print(f"[C] Time Since Last Run: {time_since}")
        
        if cron.nextcall:
            now = fields.Datetime.now()
            if cron.nextcall > now:
                time_until = cron.nextcall - now
                print(f"[C] Time Until Next Run: {time_until}")
            else:
                time_overdue = now - cron.nextcall
                print(f"[C] Overdue By:     {time_overdue}")
        
        print(f"Priority:         {cron.priority or 5}")
        print(f"Number of Calls:  {getattr(cron, 'numbercall', 'Unlimited') or 'Unlimited'}")
        if getattr(cron, 'doall', False):
            print(f"Execute Missed:   Yes")
        
        print(f"Created:          {cron.create_date}")
        print(f"Modified:         {cron.write_date}")
    
    def _output_crons_json(self, crons, detailed=False):
        """Output cron jobs in JSON format"""
        import json
        
        result = []
        for cron in crons:
            entry = {
                'id': cron.id,
                'name': cron.name,
                'model': cron.model_id.model if cron.model_id else None,
                'state': cron.state,
                'code': cron.code,
                'active': cron.active,
                'interval_number': cron.interval_number,
                'interval_type': cron.interval_type,
                'lastcall': cron.lastcall.isoformat() if cron.lastcall else None,
                'nextcall': cron.nextcall.isoformat() if cron.nextcall else None,
            }
            
            if detailed:
                now = fields.Datetime.now()
                entry.update({
                    'user_id': cron.user_id.id if cron.user_id else None,
                    'user_name': cron.user_id.name if cron.user_id else None,
                    'priority': cron.priority,
                    'numbercall': getattr(cron, 'numbercall', None),
                    'doall': getattr(cron, 'doall', False),
                    'create_date': cron.create_date.isoformat() if cron.create_date else None,
                    'write_date': cron.write_date.isoformat() if cron.write_date else None,
                    # Computed fields
                    'computed_time_since_last_run': str(now - cron.lastcall) if cron.lastcall else None,
                    'computed_time_until_next_run': str(cron.nextcall - now) if cron.nextcall and cron.nextcall > now else None,
                    'computed_overdue': cron.nextcall < now if cron.nextcall else False,
                })
            
            result.append(entry)
        
        print(json.dumps(result, indent=2))
    
    def _output_crons_yaml(self, crons, detailed=False):
        """Output cron jobs in YAML format"""
        import yaml
        
        result = []
        for cron in crons:
            entry = {
                'id': cron.id,
                'name': cron.name,
                'model': cron.model_id.model if cron.model_id else None,
                'state': cron.state,
                'code': cron.code,
                'active': cron.active,
                'interval_number': cron.interval_number,
                'interval_type': cron.interval_type,
                'lastcall': cron.lastcall.isoformat() if cron.lastcall else None,
                'nextcall': cron.nextcall.isoformat() if cron.nextcall else None,
            }
            
            if detailed:
                now = fields.Datetime.now()
                entry.update({
                    'user_id': cron.user_id.id if cron.user_id else None,
                    'user_name': cron.user_id.name if cron.user_id else None,
                    'priority': cron.priority,
                    'numbercall': getattr(cron, 'numbercall', None),
                    'doall': getattr(cron, 'doall', False),
                    'create_date': cron.create_date.isoformat() if cron.create_date else None,
                    'write_date': cron.write_date.isoformat() if cron.write_date else None,
                    # Computed fields
                    'computed_time_since_last_run': str(now - cron.lastcall) if cron.lastcall else None,
                    'computed_time_until_next_run': str(cron.nextcall - now) if cron.nextcall and cron.nextcall > now else None,
                    'computed_overdue': cron.nextcall < now if cron.nextcall else False,
                })
            
            result.append(entry)
        
        print(yaml.dump(result, default_flow_style=False))
    
    def _output_apikeys_table(self, keys):
        """Output API keys in table format"""
        print(f"{'ID':<6} {'NAME':<30} {'ACTIVE':<8} {'CREATED':<20} {'DESCRIPTION'}")
        print("-" * 90)
        for key in keys:
            active = '✓' if key.is_active else '✗'
            created = key.create_date.strftime('%Y-%m-%d %H:%M:%S')
            desc = (key.description or '')[:30]
            print(f"{key.id:<6} {key.name:<30} {active:<8} {created:<20} {desc}")
    
    def _output_apikeys_json(self, keys):
        """Output API keys in JSON format"""
        import json
        
        result = []
        for key in keys:
            entry = {
                'id': key.id,
                'name': key.name,
                'key': key.key,  # Show full key in JSON
                'is_active': key.is_active,
                'scopes': key.scopes,
                'description': key.description,
                'create_date': key.create_date.isoformat() if key.create_date else None,
                'write_date': key.write_date.isoformat() if key.write_date else None,
            }
            result.append(entry)
        
        print(json.dumps(result, indent=2))
    
    def _output_apikeys_yaml(self, keys):
        """Output API keys in YAML format"""
        import yaml
        
        result = []
        for key in keys:
            entry = {
                'id': key.id,
                'name': key.name,
                'key': key.key,  # Show full key in YAML
                'is_active': key.is_active,
                'scopes': key.scopes,
                'description': key.description,
                'create_date': key.create_date.isoformat() if key.create_date else None,
                'write_date': key.write_date.isoformat() if key.write_date else None,
            }
            result.append(entry)
        
        print(yaml.dump(result, default_flow_style=False))
    
    def _output_apikey_detailed(self, key):
        """Output detailed API key information"""
        print(f"ID:          {key.id}")
        print(f"Name:        {key.name}")
        print(f"Key:         {key.key}")
        print(f"Active:      {'Yes' if key.is_active else 'No'}")
        print(f"Scopes:      {key.scopes or 'all'}")
        print(f"Description: {key.description or ''}")
        print(f"Created:     {key.create_date}")
        print(f"Modified:    {key.write_date}")


# Register the command
def add_command(subparsers):
    parser = subparsers.add_parser('sunray',
                                  help='Sunray authentication system management')
    parser.set_defaults(run=SunrayCommand.run)