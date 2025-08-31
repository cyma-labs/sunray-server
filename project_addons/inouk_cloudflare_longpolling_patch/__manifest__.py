{
    'name': 'Inouk Cloudflare Long Polling Patch',
    'version': '18.0.1.0.0',
    'category': 'Technical',
    'summary': 'Adapts Odoo 18 long polling/WebSocket timeouts for Cloudflare Workers 30s limit',
    'description': """
Inouk Cloudflare Long Polling Compatibility Patch
==================================================

This technical module adjusts Odoo 18's bus/WebSocket timeouts to be compatible 
with Cloudflare Workers' 30-second execution limit.

Features:
---------
* Reduces long polling timeout from 50s to 25s
* Adjusts WebSocket inactivity timeout from 45s to 20s  
* Sets connection timeout to 25s (from 60s)
* Configurable via environment variable
* Zero configuration needed - just install to activate

Technical Details:
------------------
* Designed specifically for Odoo version 18
* Uses monkey patching at module load time
* Can be overridden with ODOO_LONGPOLLING_CLOUDFLARE_COMPAT=0
* Leaves 5-second buffer for Cloudflare's 30s limit
* Preserves all other bus functionality

When to Use:
------------
Install this module if:
- Your Odoo instance is accessed through Cloudflare Workers
- You experience timeout errors with long polling
- You need WebSocket compatibility with CF Workers

Warning:
--------
This module modifies core timeout values. Only install if you understand
the implications for your real-time messaging performance.
    """,
    'author': '@cmorisse',
    'website': 'https://gitlab.com/cmorisse/inouk-sunray-server',
    'license': 'GPL-3',
    'depends': ['bus'],
    'data': [],
    'installable': True,
    'application': False,
    'auto_install': False,
    'post_init_hook': 'post_init_hook',
}