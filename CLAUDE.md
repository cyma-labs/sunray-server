# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Muppy Sunray is a lightweight, secure, self-hosted solution for authorizing HTTP access to private cloud services without VPN or fixed IPs. The project integrates with Cloudflare's infrastructure to provide enterprise-grade security at a fraction of traditional costs.

### Main Components

1. **Sunray Worker aka Sunray Cloudflare Worker**: Cloudflare Route Workers in charge of edge authentication using WebAuthn/Passkeys
2. **Sunray Server (Odoo 18 Addon)**: Admin interface and configuration management
3. **Sunray CLI (part of Sunray Server)**: An odoo CLI to manage Sunray server's compnents
4. **Protected Hosts**: Web sites/app to protect

## Environment Configuration

**Note**: Sensitive environment-specific information (URLs, API keys, credentials) should be stored in `.claude.local.md` which is not committed to the repository. Create this file locally with your specific environment details.

### URL Structure
- **Sunray Server (Admin)**: The Odoo 18 server with sunray_core addon
  - Provides admin UI and API endpoints at `/sunray-srvr/v1/*`
  - Environment variable: `APP_PRIMARY_URL`

- **Sunray Worker**: Cloudflare Worker handling authentication
  - Provides auth endpoints at `/sunray-wrkr/v1/*`
  - Environment variable: `WORKER_URL`

- **Protected Hosts**: Applications protected by Sunray
  - Configured as hosts in Sunray Server
  - Users must authenticate via Worker to access

## Project Structure

```
/opt/muppy/appserver-sunray18/
├── sunray_worker/             # Cloudflare Worker
│   ├── src/                   # Worker source code
│   ├── wrangler.toml          # Cloudflare configuration
│   └── package.json           # Node dependencies
├── sunray_server/             # Odoo 18 addons
│   ├── sunray_core/           # Free edition addon
│   │   ├── __manifest__.py
│   │   ├── models/
│   │   ├── controllers/
│   │   ├── views/
│   │   └── security/
│   └── sunray_enterprise/     # Advanced edition addon (future)
├── demo-app/                  # Demo application (to be created)
├── docs/                      # Documentation
│   ├── specs/                 # Technical specifications
│   ├── market_analysis_pricing_comparison.md
│   └── mvp_implementation_plan.md
├── config/                    # Configuration examples
├── schema/                    # JSON Schema validation
├── bin/                       # Executable scripts
│   └── sunray-srvr           # Odoo launcher script
└── etc/                       # Configuration files
    └── odoo.buildit.cfg       # Generated Odoo config
```

## Development Commands

### Environment Setup

```bash
# Node.js 20.19.4 and npm 10.8.2 are already installed
node --version  # v20.19.4
npm --version   # 10.8.2

# Install Cloudflare Wrangler globally
npm install -g wrangler

# ikb (inouk buildit) - One-command builder tool for Odoo
# Inspired by buildout but relies on pip
# Builds complete running Odoo environment
# Note: ikb location varies by environment, find it with: which ikb
ikb install   # Processes buildit.json[c] and requirements.txt

# Python dependencies for Sunray modules
# Requirements are automatically processed by ikb from sunray_server/requirements.txt
# The path is configured in .ikb/buildit.jsonc at odoo.requirements.requirements_file
cd sunray_server/
cat > requirements.txt << EOF
pyotp>=2.8.0
qrcode[pil]>=7.4.0
python-jose[cryptography]>=3.3.0
EOF

# After creating/updating requirements.txt, run:
ikb install   # This will process both Odoo and project requirements
```

### Sunray Server (Odoo 18) Development

```bash
# Start Sunray Server
bin/sunray-srvr                              # Normal startup
bin/sunray-srvr --dev=all                    # Development mode with auto-reload

# Start server with logging and monitor output
cd /opt/muppy/appserver-sunray18 && bin/sunray-srvr --workers=4 --logfile=./sunray-srvr-debug.log & tail -f /opt/muppy/appserver-sunray18/sunray-srvr-debug.log

# Module Management
bin/sunray-srvr -u sunray_core               # Update sunray_core module
bin/sunray-srvr -u all --stop-after-init     # Update all modules and exit
bin/sunray-srvr -i sunray_core               # Install sunray_core module

# Testing
bin/sunray-srvr --test-enable --stop-after-init -u sunray_core
bin/sunray-srvr --log-level=debug_sql --test-enable --stop-after-init -u sunray_core

# Fresh Database for Testing
export TESTDB="sunray_test_$(date +%s)"
dropdb ${TESTDB} 2>/dev/null || true
createdb ${TESTDB}
bin/sunray-srvr --database=${TESTDB} --init=base --without-demo=all --stop-after-init
bin/sunray-srvr --database=${TESTDB} -i sunray_core
```

**Note**: `bin/sunray-srvr` is a wrapper that:
- Selects the correct Python environment with all required packages
- Injects the configuration file (`-c etc/odoo.buildit.cfg`)
- Maps PostgreSQL environment variables (PGUSER, PGPASSWORD, PGDATABASE) to Odoo equivalents

### Worker Development

```bash
# Navigate to worker directory
cd sunray_worker/

# Install dependencies
npm install

# Run local development server
wrangler dev

# Deploy to Cloudflare
wrangler deploy

# Run tests with Vitest
npm test                      # Run all tests
npm run test:watch           # Run tests in watch mode
npm run test:coverage        # Run tests with coverage report
```

#### Testing Framework

The Cloudflare Worker uses **Vitest** as its testing framework. Vitest is chosen for:
- First-class support for ES modules and modern JavaScript/TypeScript
- Fast execution and hot module replacement (HMR) in watch mode
- Built-in mocking capabilities for Cloudflare Worker APIs
- Compatible with Wrangler's testing utilities
- Zero-config TypeScript support

**Important Test File Requirements:**
- Test files MUST be located in the `src/` directory (NOT in `test/` directory)
- Test files MUST use `.test.js` extension (e.g., `src/example.test.js`)
- Vitest uses glob pattern `**/*.{test,spec}.?(c|m)[jt]s?(x)` to find tests
- Files in `test/` directory are NOT automatically discovered by Vitest

**Correct test file locations:**
```bash
# ✅ CORRECT - These will be found and run
src/cache.test.js
src/invalidation-tracker.test.js  
src/multi-provider-tokens.test.js

# ❌ INCORRECT - These will NOT be found
test/test-multi-provider.js
test/webhook-tests.js
```

**Running tests:**
```bash
# Run all tests (finds *.test.js in src/)
npm test

# Run specific test file
npm test src/multi-provider-tokens.test.js

# Run tests with specific pattern
npx vitest run src/cache.test.js

# Watch mode for development
npm run test:watch
```

Example test structure:
```javascript
// src/example.test.js
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { handleRequest } from './handler';

describe('Worker Handler', () => {
  it('should return 200 for valid requests', async () => {
    const request = new Request('https://example.com');
    const response = await handleRequest(request);
    expect(response.status).toBe(200);
  });
});
```

**Testing Worker Functions:**
When testing worker functions that aren't exported from the main module, you can:
1. Copy the function code into the test file (for unit testing)
2. Move functions to separate modules and import them
3. Use dynamic imports or require() if needed

Example for testing internal functions:
```javascript
// src/token-validation.test.js
import { describe, it, expect } from 'vitest';

// Copy function from handler.js for testing
function extractTokenByConfig(request, tokenConfig, url, logger) {
  // ... function implementation
}

describe('Token Extraction', () => {
  it('should extract Shopify token from header', () => {
    const request = new Request('https://api.example.com', {
      headers: { 'X-Shopify-Hmac-Sha256': 'test_token' }
    });
    const tokenConfig = {
      name: 'Shopify',
      header_name: 'X-Shopify-Hmac-Sha256',
      token_source: 'header'
    };
    const result = extractTokenByConfig(request, tokenConfig, new URL(request.url), console);
    expect(result).toBe('test_token');
  });
});
```

### Sunray CLI (srctl)

A CLI exists to manage Sunray objects. It provides `create`, `get`, `list`, and `delete` operations for: `apikey`, `user`, `session`, `host`, and `setuptoken`.

```bash
# Usage: bin/sunray-srvr srctl <object> <action> [options]
bin/sunray-srvr srctl apikey list
bin/sunray-srvr srctl user create "username" --sr-email "user@example.com"
bin/sunray-srvr srctl setuptoken create "username" --sr-device "laptop" --sr-hours 24
```

## Architecture Details

### Authentication Flow (WebAuthn/Passkeys)

1. **User Registration**:
   - Admin generates setup token in Sunray Server
   - User visits `/sunray-wrkr/v1/setup` page
   - WebAuthn passkey created and stored

2. **Authentication**:
   - User attempts to access protected resource
   - Redirected to `/sunray-wrkr/v1/auth`
   - Passkey authentication via WebAuthn
   - Session cookie set upon success

### API Endpoints

**Worker Endpoints** (`/sunray-wrkr/v1/*`):
- `/setup/validate` - Validate setup token
- `/setup/register` - Complete passkey registration
- `/auth/challenge` - Get authentication challenge
- `/auth/verify` - Verify passkey and create session
- `/auth/logout` - Clear session

**Server Endpoints** (`/sunray-srvr/v1/*`):
- `/config` - Get configuration (Worker → Server)
- `/setup-tokens/validate` - Validate setup token
- `/users/<username>/passkeys` - Register passkey

### Security Model

- **Default Locked**: All resources protected by default
- **Whitelist Exceptions**:
  - CIDR ranges for IP-based access
  - Public URL patterns (regex)
  - Webhook tokens for API access
- **WebAuthn/Passkeys**: Primary authentication method
- **Session Management**: Secure cookies with configurable TTL

## Odoo Development Guidelines

### Module Structure
```python
sunray_core/
├── __manifest__.py           # Module metadata
├── models/
│   ├── sunray_user.py       # User model
│   ├── sunray_host.py       # Host configuration
│   └── sunray_session.py    # Session management
├── controllers/
│   └── main.py              # API endpoints
├── views/
│   └── sunray_views.xml     # UI definitions
├── security/
│   └── ir.model.access.csv  # Access rights
└── tests/
    └── test_sunray.py       # Unit tests
```

### Development Guidelines

- **Feature-First Approach**: When you need to manipulate Sunray server data and no feature exists for that purpose, you MUST propose to develop a proper feature (GUI or CLI) instead of writing SQL or creating ad-hoc Odoo/Python scripts. Only if the user rejects the feature development option can you propose ad-hoc scripts/commands.

### Coding Conventions

- **Odoo 18 View Syntax**: Use new attribute syntax instead of `attrs`
  ```xml
  <!-- DON'T DO THIS (Odoo 17 and earlier): -->
  <field name="field_name" attrs="{'invisible': [('other_field', '=', False)]}"/>
  
  <!-- DO THIS (Odoo 18+): -->
  <field name="field_name" invisible="not other_field"/>
  <field name="field_name" readonly="state == 'done'"/>
  <field name="field_name" required="is_required"/>
  ```

- **Odoo Recordsets**: Suffix with `_obj` or `_objs`
  ```python
  user_obj = self.env['sunray.user'].browse(user_id)
  host_objs = self.env['sunray.host'].search([])
  ```

- **Relational Fields**: Suffix with `_id` or `_ids`
  ```python
  class SunrayUser(models.Model):
      host_id = fields.Many2one('sunray.host')
      passkey_ids = fields.One2many('sunray.passkey', 'user_id')
  ```

- **Return Convention**: Use `False` (not `None`) for empty recordsets
  ```python
  def get_user(self, username):
      user_obj = self.env['sunray.user'].search([('username', '=', username)])
      return user_obj or False
  ```

- **List Views**: When creating list views, make all fields `optional="show"` so users can easily adapt the displayed columns
  ```xml
  <list>
      <field name="name"/>
      <field name="description" optional="show"/>
      <field name="create_date" optional="show"/>
      <field name="is_active" widget="boolean_toggle"/>
  </list>
  ```

- **Audit Fields**: Never create `created_by`, `created_date`, `modified_by`, or `modified_date` fields
  ```python
  # DON'T DO THIS - Odoo provides these automatically:
  # created_by = fields.Many2one('res.users')  # Use create_uid instead
  # created_date = fields.Datetime()           # Use create_date instead
  # modified_by = fields.Many2one('res.users') # Use write_uid instead  
  # modified_date = fields.Datetime()          # Use write_date instead
  
  # These fields are automatically available on all models:
  # - create_uid: User who created the record
  # - create_date: When the record was created
  # - write_uid: User who last modified the record
  # - write_date: When the record was last modified
  ```

### Field Format Pattern

For multi-value configuration fields (IPs, CIDRs, URL patterns, etc.):

- **Storage Format**: One value per line in Text fields
- **Comment Support**: Lines starting with `#` are ignored
- **Inline Comments**: Use `#` after value for inline comments
- **Accessor Methods**: Each field has an accessor method with format parameter
  ```python
  # Field definition
  allowed_cidrs = fields.Text(
      string='Allowed CIDR Blocks',
      help='CIDR blocks that bypass authentication (one per line, # for comments)'
  )
  
  # Accessor method with format parameter (default 'json')
  def get_allowed_cidrs(self, format='json'):
      """Parse field from line-separated format
      
      Args:
          format: Output format ('json' returns list, future: 'txt', 'yaml')
      """
      if format == 'json':
          return self._parse_line_separated_field(self.allowed_cidrs)
      # Future formats: 'txt', 'yaml', etc.
  ```

- **Example Input**:
  ```
  10.0.0.0/8          # Private network
  192.168.0.0/16      # Local network
  # This line is ignored
  172.16.0.0/12
  ```

- **Example Output** (JSON format):
  ```python
  ['10.0.0.0/8', '192.168.0.0/16', '172.16.0.0/12']
  ```

### Testing Best Practices

```python
# Minimal viable test records
def setUp(self):
    super().setUp()
    self.host_obj = self.env['sunray.host'].create({
        'name': 'test.example.com',  # Required field
        'domain': 'test.example.com', # Required field
    })

# Mock external dependencies
from unittest.mock import patch

@patch('requests.post')
def test_webhook(self, mock_post):
    mock_post.return_value.status_code = 200
    # Test code here
```

## Current Development Status

### MVP Implementation (4-week timeline)

**Week 1**: Core Infrastructure ✓
- Project structure setup
- Basic Odoo addon scaffolding
- Worker project initialization

**Week 2**: Authentication Implementation (Current)
- WebAuthn integration in Worker
- Passkey storage in Odoo
- Session management

**Week 3**: Admin Interface
- Odoo views for user management
- Host configuration UI
- Setup token generation

**Week 4**: Testing & Documentation
- Integration tests
- Demo application
- Deployment documentation

### Next Steps

1. Create Worker implementation with WebAuthn
2. Implement sunray_core Odoo addon
3. Set up demo application
4. Write comprehensive tests

## Configuration Management

### Build Configuration
- `.ikb/buildit.jsonc`: ikb configuration file
  - `odoo.addons.project_addons`: Points to `./sunray_server` for addon discovery
  - `odoo.requirements.requirements_file`: Points to `sunray_server/requirements.txt` for Python dependencies
- `sunray_server/requirements.txt`: Python dependencies automatically processed by ikb install
- `wrangler.toml`: Cloudflare Worker configuration
- `etc/odoo.buildit.cfg`: Generated Odoo configuration by ikb

### Environment Variables

#### PostgreSQL
- Connection via standard PG environment variables (pre-configured)
- `PGUSER`, `PGPASSWORD`, `PGDATABASE`, `PGHOST`, `PGPORT`
- Direct `psql` access works without additional configuration

#### Odoo Server  
- `APP_PRIMARY_URL`: HTTPS URL for the Odoo server (provided by environment)
- Default admin credentials: See `.claude.local.md` for development credentials
- User management via `inouk_odoo_cli` addon

#### Cloudflare Worker
- `ADMIN_API_ENDPOINT`: Set to `$APP_PRIMARY_URL`
- `ADMIN_API_KEY`: Generated after sunray_core installation (store in `.claude.local.md`)
- `SESSION_SECRET`: Generate with `openssl rand -base64 32`
- `WORKER_ID`: Unique identifier for worker instance
- `WORKER_URL`: The Worker's public URL (store in `.claude.local.md`)

## Backup Strategy

### Development Environment
- Database will be regenerated as needed during development
- Keep SQL dumps of key test scenarios:
  ```bash
  pg_dump $PGDATABASE > backups/sunray_$(date +%Y%m%d_%H%M%S).sql
  ```

### Production Recommendations
1. **Before Major Updates**: Full database backup
2. **Daily Incremental**: Backup audit logs and session data
3. **Weekly Full**: Complete database dump
4. **Configuration Backup**: Version control for `buildit.json[c]` and module code

## TODO: WAF Bypass Documentation

### Feature: Authenticated User WAF Bypass
**Status:** Implementation in progress

#### Overview
Allows authenticated users to bypass Cloudflare WAF rules using a security-hardened cookie mechanism with comprehensive audit logging.

#### Performance Overhead
- **Cookie Generation:** ~5ms on authentication (one-time)
- **Cookie Validation:** <2ms per request (negligible)
- **Cookie Size:** ~200 bytes additional
- **Overall Impact:** <0.1% latency increase for authenticated users

#### Security Features
- IP address binding (prevents cookie theft)
- User-Agent fingerprinting (detects browser changes)
- Time-based revalidation (15-minute default)
- HMAC signature (prevents tampering)
- Hidden cookie name `sunray_sublimation` (reduces discoverability)
- **Comprehensive audit logging of all manipulation attempts**

#### Audit Events Tracked
- `waf_bypass.created` - Sublimation cookie created
- `waf_bypass.validated` - Successful validation
- `waf_bypass.expired` - Cookie expired naturally
- `waf_bypass.cleared` - Cookie cleared on logout
- `waf_bypass.tamper.format` - Invalid cookie format
- `waf_bypass.tamper.hmac` - HMAC verification failed (forgery attempt)
- `waf_bypass.tamper.session` - Session ID mismatch
- `waf_bypass.tamper.ip_change` - IP address changed
- `waf_bypass.tamper.ua_change` - User-Agent changed
- `waf_bypass.error` - Validation error

#### Monitoring Sublimation Manipulation
```bash
# View all WAF bypass events
bin/sunray-srvr srctl auditlog get --sublimation-only

# View manipulation attempts only
bin/sunray-srvr srctl auditlog get --event-type "waf_bypass.tamper.*"

# Monitor in real-time
bin/sunray-srvr srctl auditlog get --since 1m --sublimation-only --follow
```

#### Configuration Required
1. Enable `bypass_waf_for_authenticated` on desired hosts in Sunray Server UI
2. Configure Cloudflare firewall rule:
   ```
   Name: Sunray Authenticated Bypass
   Expression: (http.cookie contains "sunray_sublimation")
   Action: Skip → All remaining custom rules
   Priority: Very High (before OWASP rules)
   ```
3. Set environment variable: `WAF_BYPASS_SECRET` (or uses SESSION_SECRET)

#### Testing Checklist
- [ ] Cookie creation on authentication
- [ ] IP change detection and audit logging
- [ ] User-Agent change detection and audit logging
- [ ] Time-based expiry and audit logging
- [ ] HMAC validation and forgery attempt logging
- [ ] WAF rule bypass verification
- [ ] Audit log entries for all manipulation types
- [ ] Performance benchmarks

#### Rollback Procedure
1. Disable `bypass_waf_for_authenticated` on affected hosts
2. Remove Cloudflare firewall rule
3. Review audit logs for any exploitation attempts:
   ```bash
   bin/sunray-srvr srctl auditlog get --event-type "waf_bypass.tamper.*" --since 24h
   ```
4. No data migration required (graceful degradation)

## Important Notes

- This is the transition from ED25519 signatures to WebAuthn/Passkeys
- The Chrome Extension mentioned in old docs is being replaced by native passkey support
- TocToc mode has been removed in favor of WebAuthn-only authentication
- Focus on MVP with sunray_core only; enterprise features come later
