{
    'name': 'Sunray Core',
    'version': '18.0.1.1.0',
    'category': 'Security',
    'summary': 'WebAuthn/Passkey authentication system for Cloudflare Workers',
    'description': """
Sunray Core - Free Edition
==========================

A lightweight, secure, self-hosted solution for authorizing HTTP access
to private cloud services without VPN or fixed IPs.

Features:
---------
* WebAuthn/Passkey authentication
* Session management with JWT
* User and host configuration
* Setup token generation
* Reusable webhook tokens across multiple hosts
* Audit logging
* CIDR bypass rules
* Public URL patterns

Version 1.1.0 Changes:
---------------------
* Webhook tokens are now global and reusable across multiple hosts
* Tokens managed via Access Rules for flexible URL pattern mapping
* Simplified token management with centralized administration

Technical Components:
--------------------
* Admin Server: Odoo 18 addon for configuration
* Cloudflare Worker: Edge authentication
* Security-first: Default locked, whitelist exceptions
    """,
    'author': 'Muppy',
    'website': 'https://github.com/muppy/sunray',
    'license': 'LGPL-3',
    'depends': ['base', 'web', 'inouk_attachments_storage'],
    'data': [
        # Inouk Attachment Storage
        'data/move_attachments_to_db.xml',

        # Security
        'security/sunray_security.xml',
        'security/ir.model.access.csv',
        
        # Data
        'data/ir_config_parameter.xml',
        'data/sunray_data.xml',
        
        # Wizards (must be loaded before views that reference them)
        'wizards/setup_token_wizard_views.xml',
        'wizards/session_revoke_wizard_views.xml',
        'wizards/user_sessions_revoke_wizard_views.xml',
        
        # Views (actions must be defined before menu)
        'views/sunray_user_views.xml',
        'views/sunray_host_views.xml',
        'views/sunray_passkey_views.xml',
        'views/sunray_access_rule_views.xml',
        'views/sunray_session_views.xml',
        'views/sunray_audit_log_views.xml',
        'views/sunray_api_key_views.xml',
        'views/sunray_webhook_token_views.xml',
        'views/sunray_worker_views.xml',

        # Menu (must be last)
        'views/sunray_menu.xml',
    ],
    'demo': [
        'demo/demo_data.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'external_dependencies': {
        'python': ['pyotp', 'qrcode', 'python-jose', 'PyYAML'],
    },
    # 'assets': {
    #     'web.assets_backend': [
    #         'sunray_core/static/src/css/sunray.css',
    #         'sunray_core/static/src/js/sunray.js',
    #     ],
    # },
    'cli': {
        'sunray_core.cli.sunray_cli': ['sunray'],
    },
}