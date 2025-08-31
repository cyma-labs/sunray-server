# Inouk Cloudflare Long Polling Patch

## Overview

This Odoo 18 addon module automatically adjusts the bus system timeouts to be compatible with Cloudflare Workers' 30-second execution limit.

## Problem

Cloudflare Workers have a hard 30-second execution limit, but Odoo's default timeouts exceed this:
- Long polling: 50 seconds
- WebSocket connection: 60 seconds  
- WebSocket inactivity: 45 seconds

This causes timeout errors when Odoo is accessed through Cloudflare Workers.

## Solution

This module reduces all timeouts to 25 seconds or less, leaving a 5-second safety buffer.

## Installation

1. Place this module in your `project_addons` directory
2. Update the module list in Odoo
3. Install "Inouk Cloudflare Long Polling Patch" module
4. Timeouts are automatically adjusted

## Configuration

The module is active by default when installed. To temporarily disable without uninstalling:

```bash
export ODOO_LONGPOLLING_CLOUDFLARE_COMPAT=0
```

## Modified Timeouts

| Parameter | Original | Modified | Purpose |
|-----------|----------|----------|---------|
| Long polling timeout | 50s | 25s | HTTP long polling requests |
| WebSocket connection | 60s | 25s | Total connection lifetime |
| WebSocket inactivity | 45s | 20s | Time before ping frame |
| Keep-alive timeout | varies | 25s | Maximum session duration |

## Compatibility

- **Odoo Version**: 18.0
- **Dependencies**: bus module (core)
- **Python**: 3.8+

## Side Effects

- More frequent reconnections (every 25s instead of 50s)
- Slightly increased server load from reconnections
- Potential for brief message delays during reconnection

## Uninstallation

Simply uninstall the module to restore original timeouts. No data migration needed.

## Support

For issues or questions, please use the repository issue tracker:
https://gitlab.com/cmorisse/inouk-sunray-server

## Author

@cmorisse

## License

This module is licensed under GPL-3.