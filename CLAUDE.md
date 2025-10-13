# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) and all others IA when working with code in this repository.

## Project Overview

**Sunray** is a comprehensive and affordable Web/HTTP Zero Trust access solution that integrates with various edge platforms to provide enterprise-grade security at a fraction of traditional costs.

### ⚠️ IMPORTANT: What Sunray Is and Is Not

**Sunray is NOT an authentication system.** It is a Web/HTTP Zero Trust access solution that controls who can reach protected applications. Key distinctions:

- **Sunray**: Decides if you can REACH the application (access control)
- **Application**: Decides WHO you are and WHAT you can do (authentication & authorization)

Think of Sunray as a security bouncer at a club entrance:
- The bouncer (Sunray) checks if you're on the guest list to enter the club
- Once inside, you still need to pay for drinks, show ID at the bar, etc. (application authentication)

**Always refer to Sunray as:**
- "Web/HTTP Zero Trust access solution"
- "Access control system" 
- "Security gateway"

**Never refer to Sunray as:**
- "Authentication system"
- "Login system" 
- "Identity provider"

### Architecture: Server-Centric Design

**Sunray Server** provides a rich, comprehensive API that handles ALL business logic. Workers are thin translation layers that adapt platform-specific requests to the server's universal API.

### Main Components

1. **Sunray Server (Odoo 18 Addon)**: Core authentication server with complete business logic
   - Admin interface and configuration management 
   - Rich REST API for all worker types
   - WebAuthn/Passkeys, access rules, session management
   - Universal backend supporting multiple worker implementations

2. **Sunray Workers**: Thin platform-specific adapters
   - **inouk-sunray-worker-cloudflare**: Cloudflare Workers implementation 
   - **inouk-sunray-worker-k8s**: Kubernetes ForwardAuth implementation (future)
   - Each worker translates platform requests to server API calls

3. **Sunray CLI (part of Sunray Server)**: An odoo CLI to manage Sunray server's components
4. **Protected Hosts**: Web sites/app to protect

## Development Guidelines

### API Development
- **When implementing Server API calls, always refer to the API Contract in `/docs/API_CONTRACT.md`**
- The API Contract is the authoritative source of truth for all worker implementations
- Server enforces all business logic and validation; workers are thin translation layers
- Follow server-centric design principles: no worker-side validation or default values

### Passkey Registration Security
- All passkey registrations MUST use setup tokens for authorization
- Setup tokens are validated in the model layer (register_with_setup_token method)
- Comprehensive audit logging tracks all registration attempts

## Environment Configuration

**Note**: Sensitive environment-specific information (URLs, API keys, credentials) should be stored in `.claude.local.md` which is not committed to the repository. Create this file locally with your specific environment details.

### Security Notes
- The environment variable `$MPY_REPO_GIT_TOKEN` contains a valid GitLab token
- **NEVER** write the actual token value in any documentation or logs
- The token can be used in tool commands for authenticated Git operations
- **For production deployments, see [Sunray Deployment Security Guide](docs/sunray_deployment_security.md)**

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

## Repository Structure

Sunray is organized as separate repositories following a server-centric architecture:

### inouk-sunray-server (this repository)
```
/opt/muppy/appserver-sunray18/
├── project_addons/            # Odoo 18 addons (ikb standard)
│   ├── sunray_core/           # Free edition addon
│   │   ├── __manifest__.py
│   │   ├── models/
│   │   ├── controllers/
│   │   ├── views/
│   │   └── security/
│   └── sunray_enterprise/     # Advanced edition addon (future)
├── docs/                      # Documentation
│   ├── market_analysis_pricing_comparison.md
│   └── mvp_implementation_plan.md
├── config/                    # Configuration examples
├── schema/                    # JSON Schema validation
├── bin/                       # Executable scripts (all project tools & utilities)
│   ├── sunray-srvr            # Odoo launcher script
│   ├── test_server.sh         # Internal Odoo test runner
│   └── test_rest_api.sh       # External REST API tester
├── specs/                     # PRD / Technical specifications 
└── etc/                       # Configuration files
    └── odoo.buildit.cfg       # Generated Odoo config
```

### inouk-sunray-worker-cloudflare (separate repository)
```
inouk-sunray-worker-cloudflare/
├── src/                       # Worker source code
├── wrangler.toml              # Cloudflare configuration
├── package.json               # Node dependencies
├── deploy.sh                  # Deployment script
└── README.md                  # Cloudflare-specific docs
```

### Future Workers
- `inouk-sunray-worker-k8s`: Kubernetes ForwardAuth implementation
- `inouk-sunray-worker-nginx`: NGINX auth_request implementation
- `inouk-sunray-worker-traefik`: Traefik ForwardAuth implementation

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
# Requirements are automatically processed by ikb from user_addons/requirements.txt
# The path is configured in .ikb/buildit.jsonc at odoo.requirements.requirements_file
cd user_addons/
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

# Testing - Pure Launcher Philosophy
# The test launcher is a thin parameter translator - Odoo handles ALL output directly
bin/test_server.sh                           # Run ALL tests with real-time output
bin/test_server.sh --list-tests              # Discover available test classes (dynamic)
bin/test_server.sh --test TestClassName      # Run specific test class
bin/test_server.sh --verbose                 # Enable debug logging
bin/test_server.sh --log                     # Save output to timestamped log file
bin/test_server.sh --log mytest.log          # Save output to specific log file

# IMPORTANT: Before running tests, ensure module syntax is valid:
bin/sunray-srvr -u sunray_core --stop-after-init
```

**Note**: `bin/sunray-srvr` is a wrapper that:
- Selects the correct Python environment with all required packages
- Injects the configuration file (`-c etc/odoo.buildit.cfg`)
- Maps PostgreSQL environment variables (PGUSER, PGPASSWORD, PGDATABASE) to Odoo equivalents

### Running Tests - Pure Launcher Approach

The test runner (`bin/test_server.sh`) is a **pure launcher** that translates user-friendly options into Odoo test commands. It does NOT parse or validate test output - Odoo handles everything directly.

#### Key Philosophy
- **Real-time output**: See tests as they execute
- **No wrapping**: Direct Odoo output, no parsing
- **Enhanced UX**: Colored tool messages for clarity
- **Simple logging**: Optional output capture with --log

#### Available Options
```bash
--help              # Show colored help with examples
--test CLASS        # Run specific test class (case-sensitive!)
--method METHOD     # Run specific test method (requires --test)
--verbose           # Enable Odoo debug logging  
--log [FILE]        # Save output to log file (optional filename)
--list-tests        # Dynamically discover all test classes
--module MODULE     # Test specific module (default: sunray_core)
--all               # Run tests for all modules
```

#### Discovering Tests

Always use dynamic discovery to find exact class names:

```bash
# List all available test classes with colored output
bin/test_server.sh --list-tests

# Example output:
# [CYAN] Available Test Classes
# [GREEN] Run ALL tests:
#   ./bin/test_server.sh
# [YELLOW] From test_cache_invalidation:
# [BLUE]   TestCacheInvalidation
# [GREEN]     ./bin/test_server.sh --test TestCacheInvalidation
```

#### Running Tests

```bash
# Run ALL tests - see real-time progress
bin/test_server.sh

# Run specific test class - immediate feedback
bin/test_server.sh --test TestPasskeyRegistrationSecurity

# Run specific method
bin/test_server.sh --test TestCacheInvalidation --method test_bulk_cache_refresh

# Debug failing test - verbose output
bin/test_server.sh --test TestAccessRules --verbose

# Capture output for CI/CD - log to file
bin/test_server.sh --log test_results.log

# Capture with custom filename
bin/test_server.sh --test TestCacheInvalidation --log my_test.log
```

#### Understanding Output

The launcher shows colored status messages, then Odoo's native output:

```
[CYAN] ================================================
[CYAN]  Sunray Server Test Runner
[CYAN] ================================================
[GREEN] ✓ Prerequisites check passed
[BLUE] Running test class: TestCacheInvalidation
[YELLOW] Command: bin/sunray-srvr --test-enable --stop-after-init --workers=0 -u sunray_core --test-tags=/sunray_core:TestCacheInvalidation

# Then Odoo's real-time output follows:
2025-08-28 INFO Starting TestCacheInvalidation.test_bulk_cache_refresh...
2025-08-28 INFO Starting TestCacheInvalidation.test_config_endpoint...
...
2025-08-28 INFO sunray_core: 13 tests 4.13s 259 queries
2025-08-28 INFO 0 failed, 0 error(s) of 13 tests
```

#### Key Odoo Output Indicators

From Odoo's native output, look for:
- `X tests` - Total tests executed
- `X failed` - Number of failures  
- `X error(s)` - Number of errors
- `Xs` - Execution time
- `X queries` - Database queries

**Exit Codes:**
- 0 = All tests passed
- Non-zero = Tests failed or errored

#### Troubleshooting

| Symptom | What Odoo Shows | Solution |
|---------|-----------------|----------|
| No tests found | "0 failed, 0 error(s) of 0 tests" | Use `--list-tests` for exact class names |
| Import errors | Module errors before tests start | Run `bin/sunray-srvr -u sunray_core --stop-after-init` |
| Need more details | Brief output | Add `--verbose` for debug logging |
| Want to save output | Terminal only | Add `--log` to capture to file |
| Test takes long | Long execution time | Normal - watch real-time progress |

#### Adding New Tests

New test files should:
1. Be placed in `project_addons/sunray_core/tests/`
2. Start with `test_` prefix (e.g., `test_my_feature.py`)
3. Import from `odoo.tests.common`
4. Use class names starting with `Test` (e.g., `TestMyFeature`)
5. Use method names starting with `test_` (e.g., `test_my_scenario`)

After adding tests, they will automatically appear in `--list-tests` output.

### Worker Development

Workers are now in separate repositories. For Cloudflare Worker:

```bash
# Clone the worker repository
git clone https://gitlab.com/cmorisse/inouk-sunray-worker-cloudflare.git
cd inouk-sunray-worker-cloudflare/

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

#### Setup Token Handling

Workers MUST normalize setup tokens before hashing and sending to the server:

```javascript
function normalizeSetupToken(token) {
    // Remove dashes, spaces, and convert to uppercase
    return token.replace(/-/g, '').replace(/ /g, '').toUpperCase();
}

// Usage in worker
const userToken = "A2B3C-4D5E6-F7G8H-9J2K3";
const normalized = normalizeSetupToken(userToken);
const tokenHash = "sha512:" + crypto.createHash('sha512').update(normalized).digest('hex');
```

This normalization ensures compatibility with both old (urlsafe) and new (readable) token formats.

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
- **Access Rules System** (unified exceptions management):
  - Priority-based rule evaluation (lower number = higher priority)
  - **Public Access**: No authentication required
  - **CIDR Access**: IP address/range whitelist  
  - **Token Access**: API/webhook token authentication
  - First matching rule determines access type
- **WebSocket URLs** (authenticated WebSocket endpoints):
  - Configured at host level, not in access rules
  - Always require valid session cookies
  - Upgraded to WebSocket protocol after authentication
  - For unauthenticated WebSocket access, use public access rules
- **WebAuthn/Passkeys**: Primary authentication method
- **Session Management**: Secure cookies with configurable TTL

### Worker Migration System

**Purpose**: Enables controlled replacement of workers serving protected hosts without service interruption.

**Key Features**:
- **Controlled Migration**: Admin sets pending worker, migration occurs when new worker registers
- **Automatic Cutover**: Old worker receives error on next request and stops serving
- **Complete Audit Trail**: All migration events logged for compliance and troubleshooting
- **Safety Mechanisms**: No accidental replacements, explicit admin approval required

**Migration Workflow**:
1. **Preparation**: Admin identifies need for new worker (scaling, version upgrade, replacement)
2. **Deployment**: Admin creates and deploys new worker with unique worker ID
3. **Authorization**: Admin sets pending worker ID in Sunray Server (UI or CLI)
4. **Activation**: New worker registers → automatic migration occurs
5. **Deactivation**: Old worker gets error response → stops serving traffic
6. **Verification**: Admin monitors audit logs and worker health status

**CLI Commands**:
```bash
# Set pending worker for controlled migration
bin/sunray-srvr srctl host set-pending-worker app.example.com new-worker-001

# Monitor migration status
bin/sunray-srvr srctl host migration-status app.example.com

# List all pending migrations
bin/sunray-srvr srctl host list-pending-migrations

# Cancel pending migration if needed
bin/sunray-srvr srctl host clear-pending-worker app.example.com
```

**UI Features**:
- Migration status banner in host form view
- Pending worker field for setting migration target
- Clear pending migration button for cancellation
- List view columns showing migration status and duration
- Search filters for hosts with pending migrations

**Audit Events**:
- `worker.migration_requested`: Admin sets pending worker
- `worker.migration_started`: New worker begins registration
- `worker.migration_completed`: Successful migration with timing data
- `worker.migration_cancelled`: Admin cancels pending migration
- `worker.re_registered`: Same worker re-registers (idempotent)
- `worker.registration_blocked`: Unauthorized registration attempt

**Registration API Behavior**:
- **Same Worker**: Idempotent (returns configuration)
- **Pending Worker**: Performs migration automatically
- **Unauthorized Worker**: Returns detailed error with current status
- **Unbound Host**: Binds worker immediately

**Use Cases**:
- **Scaling**: Deploy additional workers for load distribution
- **Version Updates**: Replace workers with newer versions
- **Geographic Migration**: Move workers to different regions
- **Disaster Recovery**: Replace failed workers quickly

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

- **API Contract Updates**: When updating any code in the Sunray server REST API controller (`project_addons/sunray_core/controllers/main.py`), you MUST update `docs/API_CONTRACT.md` with the changes if they affect the API contract (new endpoints, changed parameters, modified responses, etc.).

- **Audit Logging Policy**: All audit events MUST be created using the `sunray.audit.log` model's `create_audit_event()` method. DO NOT create new logging methods - use the existing unified method with appropriate parameters:
  - **Required parameters**: `event_type`, `details`, `severity`
  - **Optional parameters**: `sunray_admin_user_id`, `sunray_user_id`, `sunray_worker`, `ip_address`, `user_agent`, `request_id`, `event_source`, `username`
  - **Severity levels**: 'info', 'warning', 'error', 'critical' (use 'critical' for security events)
  - **Example usage**: `audit_log.create_audit_event(event_type='security.cross_domain_session', details={'original_domain': 'app1.com', 'requested_domain': 'app2.com'}, severity='critical')`

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

#### Important Test Notes

**Expected Database Constraint Violations**: The test `TestWebhookTokenMultiProvider.test_token_validation_constraints` intentionally generates 2 database constraint violation ERRORs in the log as part of testing invalid token configurations. These are expected and do not indicate test failures.

**Test Success Verification**: Always check the final test result lines, not intermediate database errors:
```
2025-08-26 16:07:00,241 INFO odoo.tests.stats: sunray_core: 49 tests 9.37s 767 queries 
2025-08-26 16:07:00,242 INFO odoo.tests.result: 0 failed, 0 error(s) of 41 tests
```
The key indicator is `0 failed, 0 error(s)` in the final result line, not database constraint violations that appear during test execution.

### Test Launcher Script

**Policy**: All project tools must be in the `bin/` directory.

#### Server Tests (`bin/test_server.sh`)
A **pure launcher** for Odoo's test framework - no parsing, direct execution.

**Philosophy:**
- Translates user options to Odoo test commands
- Shows real-time test execution
- No output parsing or validation
- Optional logging with --log

**Examples:**
```bash
# Run all tests - watch them execute in real-time
bin/test_server.sh

# Run specific test class
bin/test_server.sh --test TestCacheInvalidation

# Run specific method
bin/test_server.sh --test TestPasskeyRegistrationSecurity --method test_01_successful_registration

# Verbose mode for debugging
bin/test_server.sh --test TestAccessRules --verbose

# Save output for later analysis
bin/test_server.sh --log
# Creates: test_logs_and_coverage/test_20250828_094344.log

# Dynamic test discovery
bin/test_server.sh --list-tests
```

**What You'll See:**
1. Colored launcher messages (status, command)
2. Real-time Odoo test execution
3. Individual test progress
4. Final results from Odoo

**No More:**
- Parsing test output
- Validation errors
- Hanging issues
- Complex result extraction

#### REST API Tests (`bin/test_rest_api.sh`)
External API testing that simulates Worker-Server communication.

```bash
# Run all REST API tests (requires API URL and key)
export SUNRAY_API_URL="https://sunray.example.com"
export SUNRAY_API_KEY="your-api-key-here"
bin/test_rest_api.sh

# Run specific endpoint test
bin/test_rest_api.sh --url https://sunray.example.com --key YOUR_KEY --test config

# Run only non-authenticated tests
bin/test_rest_api.sh --url https://sunray.example.com --skip-auth

# Verbose mode with custom username
bin/test_rest_api.sh -v --username admin

# Output results in JSON format
bin/test_rest_api.sh --json

# List all available tests
bin/test_rest_api.sh --list-tests
```

#### Worker Tests (`./test_worker.sh`)
```bash
# Run all worker tests
./test_worker.sh

# Interactive development mode (auto-rerun on changes)
./test_worker.sh --watch

# Generate coverage report
./test_worker.sh --coverage

# Run specific test file
./test_worker.sh access-rules.test.js

# Run with UI interface
./test_worker.sh --ui

# List available test files
./test_worker.sh --list-tests
```

#### Test Features
- **Comprehensive Logging**: All test runs logged to `test_logs_and_coverage/` directory
- **Coverage Reports**: HTML coverage reports in `test_logs_and_coverage/` directory
- **Colored Output**: Clear visual feedback on test results
- **Parallel Execution**: Fast test runs with automatic parallelization
- **Environment Validation**: Checks dependencies and configuration
- **Specific Test Targeting**: Run individual classes, methods, or files

## Current Development Status

### Access Rules System - Reusable Library Architecture ✅

**Implementation Status: COMPLETED**

Access rules are now **reusable libraries** that can be applied to multiple hosts with different priorities and active statuses per host.

**Architecture:**
```
┌─────────────────────────────────────────┐
│  sunray.access.rule (Reusable Library) │
│  - name: "GitLab Webhook"               │
│  - access_type: token                   │
│  - url_patterns: [...]                  │
│  - token_ids: [...]                     │
│  - is_active: True (library level)      │
└─────────────────────────────────────────┘
                ↓ Referenced by
┌─────────────────────────────────────────┐
│  sunray.host.access.rule (Association)  │
│  - host_id: Host A                      │
│  - rule_id: "GitLab Webhook"            │
│  - priority: 100 (per-host priority)    │
│  - is_active: True (per-host status)    │
└─────────────────────────────────────────┘
```

**Key Features:**
- **Rule Library**: Create rules once (e.g., "Health Checks", "Office Access"), reuse everywhere
- **Per-Host Priority**: Same rule can have different priorities on different hosts
- **Per-Host Activation**: Enable/disable rules per host without affecting others
- **Token Reuse**: Tokens are also reusable across rules and hosts
- **Usage Tracking**: See which hosts use each rule
- **Deletion Protection**: Cannot delete rules that are in use
- **Priority Management**: Drag-and-drop reordering in host view

**Benefits Achieved:**
- **Centralized Management**: Update "Office IPs" once, affects all 50 hosts automatically
- **Reduced Duplication**: Define "Health Checks" rule once instead of 100 times
- **Flexible Composition**: Mix library rules with different priorities per host
- **Clear Ownership**: Rules are named and described for team collaboration
- **Audit Trail**: Track rule usage and changes
- **Worker Simplification**: Business logic in server, worker executes flat config

### Configuration Example
```
Rule Library:
├── "Health Checks" (Public)
│   └── URL Patterns: [/health, /status, /ping]
├── "Office Access" (CIDR)
│   ├── URL Patterns: [/admin/.*]
│   └── CIDRs: [192.168.1.0/24, 10.0.0.0/8]
└── "GitLab Webhook" (Token)
    ├── URL Patterns: [/api/gitlab/webhook]
    └── Tokens: [GitLab Token]

Host Configuration (app.example.com):
├── WebSocket URLs (authenticated)
│   └── Prefix: /ws/
└── Access Rule Associations
    ├── [100] "Health Checks" (active)
    ├── [200] "Office Access" (active)
    └── [300] "GitLab Webhook" (inactive on this host)

Worker Receives (exceptions_tree):
├── {priority: 100, type: public, patterns: [/health, /status, /ping]}
└── {priority: 200, type: cidr, patterns: [/admin/.*], cidrs: [...]}
```

**Usage Workflow:**
1. **Create Rules**: Navigate to Sunray → Access Rule Library
2. **Attach to Hosts**: In host form, add rules with desired priorities
3. **Manage Per-Host**: Drag to reorder, toggle active/inactive per host
4. **Update Centrally**: Changes to library rules affect all using hosts

### Implementation Details

**Models:**
- `sunray.access.rule`: Reusable rule library (name, access_type, url_patterns, cidrs, tokens)
- `sunray.host.access.rule`: Association with host-specific priority and active status
- No migration needed (not public yet)

**API Impact:**
- Zero changes to worker API
- Workers still receive flat `exceptions_tree` array
- Priority injection happens server-side during tree generation

**Future Enhancements:**
- Time-based access rules (schedule-based activation)
- Geographic restrictions
- Rule templates and sharing
- Advanced audit reporting

## Configuration Management

### Build Configuration
- `.ikb/buildit.jsonc`: ikb configuration file
  - `odoo.addons.project_addons`: Points to `./project_addons` for addon discovery
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
