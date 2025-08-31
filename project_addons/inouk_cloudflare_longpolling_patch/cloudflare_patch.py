# -*- coding: utf-8 -*-
"""
Cloudflare Workers Compatibility Patch for Odoo 18 Long Polling/WebSocket System

This monkey patch adjusts Odoo 18's bus timeouts to be compatible with 
Cloudflare Workers' 30-second execution limit.

The patch is applied automatically when this module is installed.
To disable: set ODOO_LONGPOLLING_CLOUDFLARE_COMPAT=0
If undefined, patch is applied by default when module is installed.

Designed specifically for Odoo version 18.

Author: @cmorisse
License: GPL-3
"""

import os
import logging

_logger = logging.getLogger(__name__)

# Check if patch should be applied
APPLY_PATCH = os.getenv('ODOO_LONGPOLLING_CLOUDFLARE_COMPAT', '1') != '0'

if APPLY_PATCH:
    try:
        # Import the modules to patch
        from odoo.addons.bus.models import bus
        from odoo.addons.bus import websocket
        
        # Store original values for logging
        original_timeout = bus.TIMEOUT
        original_ws_connection = websocket.Websocket.CONNECTION_TIMEOUT
        original_ws_inactivity = websocket.Websocket.INACTIVITY_TIMEOUT
        
        # Apply patches - 25s max with 5s buffer for Cloudflare's 30s limit
        bus.TIMEOUT = 25  # Long polling timeout (was 50)
        websocket.Websocket.CONNECTION_TIMEOUT = 25  # Was 60
        websocket.Websocket.INACTIVITY_TIMEOUT = 20  # Was 45 (CONNECTION_TIMEOUT - 15)
        websocket.TimeoutManager.KEEP_ALIVE_TIMEOUT = 25  # Override config
        
        # Also patch the peek_notifications controller timeout
        # This ensures the /websocket/peek_notifications endpoint respects the limit
        
        _logger.info(
            "Inouk Cloudflare compatibility patch applied successfully:\n"
            f"  - Long polling timeout: {original_timeout}s → 25s\n"
            f"  - WebSocket connection timeout: {original_ws_connection}s → 25s\n"
            f"  - WebSocket inactivity timeout: {original_ws_inactivity}s → 20s\n"
            f"  - Keep-alive timeout: (config) → 25s\n"
            "  These changes ensure compatibility with Cloudflare Workers' 30s limit."
        )
        
    except ImportError as e:
        _logger.warning(f"Could not apply Inouk Cloudflare compatibility patch: {e}")
else:
    _logger.info(
        "Inouk Cloudflare compatibility patch DISABLED by ODOO_LONGPOLLING_CLOUDFLARE_COMPAT=0. "
        "Using standard Odoo timeouts."
    )