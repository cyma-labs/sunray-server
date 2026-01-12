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

### Advanced Features (Paid)

**Sunray Advanced Core** (`advanced_addons/sunray_advanced_core/`) extends the base system with premium features:

- **Remote Authentication**: Mobile device authentication for shared/untrusted computers
  - Users scan QR code on computer with mobile device
  - WebAuthn verification happens on mobile
  - Separate session management with shorter TTLs
  - Built-in session management UI for users

- **Bulk Setup Token Generation**: Automated user onboarding
  - Generate setup tokens for multiple users at once
  - Email delivery with customizable templates
  - Batch processing for large organizations

- **Advanced Session Management**: Multi-device session control
  - Users can view all active sessions
  - Remote session termination from any device
  - Device fingerprinting and metadata tracking

**Module Structure**:
- Extends base models using `_inherit` pattern
- Adds API endpoints by extending `RestAPI` controller
- Configuration via XML data files (NO code defaults)
- Feature detection via presence check in API responses

## Development Guidelines

### API Development
- **When implementing Server API calls, always refer to the API Contract in `/docs/API_CONTRACT.md`**
- The API Contract is the authoritative source of truth for all worker implementations
- Server enforces all business logic and validation; workers are thin translation layers
- Follow server-centric design principles: no worker-side validation or default values

### Advanced Feature Development
- Advanced/paid features MUST be implemented in `advanced_addons/sunray_advanced_core/` addon
- Extend base models using `_inherit` pattern (never modify core models directly)
- Add API endpoints by extending the `RestAPI` controller class
- Document all new endpoints in `docs/API_CONTRACT.md`
- System parameters MUST be defined via XML data files (NO defaults in code)
- Feature detection: Workers check for feature presence in API responses (e.g., `remote_auth` object)
- Use `protected_host_id` in API documentation/examples (maps to `host_id` internally)

### Passkey Registration Security
- All passkey registrations MUST use setup tokens for authorization
- Setup tokens are validated in the model layer (register_with_setup_token method)
- Comprehensive audit logging tracks all registration attempts

### Worker-Specific Documentation

When working on code in any worker directory, **ALWAYS read the worker's CLAUDE.md first** before making changes. Worker repositories contain their own CLAUDE.md files with:
- Worker-specific architecture and design patterns
- Platform-specific constraints and best practices
- Testing frameworks and conventions
- Deployment procedures
- API client implementation guidelines

**Workflow:**
1. User asks to work on worker code (e.g., "fix the cache logic in the Cloudflare worker")
2. **First action**: Read `./inouk-sunray-worker-cloudflare/CLAUDE.md`
3. Follow worker-specific guidelines from that CLAUDE.md
4. Refer back to this server CLAUDE.md for API contract and server integration details

**Current Workers with CLAUDE.md:**
- `./inouk-sunray-worker-cloudflare/CLAUDE.md` - Cloudflare Worker implementation

**Example:**
```bash
# When user asks to work on worker code, first read:
Read file: ./inouk-sunray-worker-cloudflare/CLAUDE.md

# Then proceed with the requested changes
```

**Why This Matters:**
- Workers have platform-specific constraints (e.g., Cloudflare's 128MB memory limit)
- Different testing frameworks (Vitest vs Odoo test framework)
- Different deployment processes (wrangler deploy vs Odoo module updates)
- Worker-specific code organization and conventions

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
│   ├── sunray_core/           # Free/Core edition addon
│   │   ├── __manifest__.py
│   │   ├── models/
│   │   ├── controllers/
│   │   ├── views/
│   │   └── security/
├── advanced_addons/           # Paid/Advanced features
│   └── sunray_advanced_core/  # Advanced edition addon
│       ├── __manifest__.py
│       ├── models/
│       │   ├── sunray_host.py      # Remote auth config fields
│       │   └── sunray_session.py   # Session type tracking
│       ├── controllers/
│       │   └── rest_api.py         # Remote auth endpoints
│       ├── data/
│       │   └── ir_config_parameter.xml  # Remote auth system params
│       ├── views/
│       │   └── sunray_host_views.xml    # Remote auth UI
│       └── wizards/
│           └── setup_token_bulk_wizard.py  # Bulk token generation
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

### inouk-sunray-worker-cloudflare (cloned locally)

**Location**: `/opt/muppy/appserver-sunray18/inouk-sunray-worker-cloudflare/`

The worker repository has been cloned locally for development convenience. All worker development commands should be run from this directory.

```
inouk-sunray-worker-cloudflare/
├── src/                       # Worker source code
├── wrangler.toml              # Cloudflare configuration
├── package.json               # Node dependencies
├── deploy.sh                  # Deployment script
├── CLAUDE.md                  # Worker-specific documentation
└── README.md                  # Cloudflare-specific docs
```

**Working with the cloned worker:**
```bash
# Navigate to worker directory
cd /opt/muppy/appserver-sunray18/inouk-sunray-worker-cloudflare/

# Or use relative path from server root
cd inouk-sunray-worker-cloudflare/
```

### Future Workers
- `inouk-sunray-worker-k8s`: Kubernetes ForwardAuth implementation
- `inouk-sunray-worker-nginx`: NGINX auth_request implementation
- `inouk-sunray-worker-traefik`: Traefik ForwardAuth implementation

## Development Commands

### Environment Setup

#### Modular Layer Scripts

The project includes modular installation scripts in `.muppy/scripts/` for setting up development environments in both Docker and LXC/bare metal systems. These scripts follow the **Manganese Development Layer Architecture**.

**Available Scripts:**
- `mpy_install_100_sys_minimum.sh` - Layer 1: System utilities (curl, wget, vim, tmux, etc.)
- `mpy_install_300_nodejs_dev.sh` - Layer 3: Node.js LTS 20.x from NodeSource
- `mpy_install_400_pg_client.sh` - Layer 4: PostgreSQL client from official repository
- `mpy_install_500_odoo18_deps.sh` - Layer 5: Odoo 18 dependencies (Python, wkhtmltopdf, ikb)

**Numbering Scheme:**
Scripts use numbered prefixes (000-599) to enforce installation order. See [.muppy/scripts/README.md](.muppy/scripts/README.md#numbering-scheme) for complete layer definitions.

**Key Features:**
- Idempotent (safe to re-run)
- Context-aware (adapts to Docker vs LXC vs bare metal)
- Environment variable configuration (e.g., `PG_VERSION=16`, `NODE_VERSION=20`, `IKB_PYTHON_VERSION=cpython@3.12.8`)
- Numbered execution order (100 runs before 300)

**Usage Examples:**
```bash
# System minimum (Layer 1)
sudo ./.muppy/scripts/mpy_install_100_sys_minimum.sh

# Node.js development (Layer 3)
sudo ./.muppy/scripts/mpy_install_300_nodejs_dev.sh

# PostgreSQL client (Layer 4)
sudo ./.muppy/scripts/mpy_install_400_pg_client.sh
sudo PG_VERSION=15 ./.muppy/scripts/mpy_install_400_pg_client.sh

# Odoo 18 dependencies (Layer 5)
sudo ./.muppy/scripts/mpy_install_500_odoo18_deps.sh
sudo IKB_DEV_MODE=True ./.muppy/scripts/mpy_install_500_odoo18_deps.sh

# Complete Odoo 18 development environment setup
sudo ./.muppy/scripts/mpy_install_100_sys_minimum.sh
sudo ./.muppy/scripts/mpy_install_400_pg_client.sh
sudo ./.muppy/scripts/mpy_install_300_nodejs_dev.sh
sudo ./.muppy/scripts/mpy_install_500_odoo18_deps.sh
```

**Documentation:** See [.muppy/scripts/README.md](.muppy/scripts/README.md) for complete details.

#### Legacy Environment Setup

```bash
# Node.js 20.19.4 and npm 10.8.2 are already installed
# (or use modular script: sudo ./.muppy/scripts/mpy_install_300_nodejs_dev.sh)
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

# IMPORTANT: Module Update/Install Procedure
# Always follow these steps when updating/installing modules:
# 1. Kill any running sunray-srvr processes
pkill -f sunray-srvr

# 2. Remove old log file to avoid confusion
rm -f ./sunray-srvr-update.log

# 3. Run update with fresh log file
bin/sunray-srvr -u all --stop-after-init --logfile=./sunray-srvr-update.log

# 4. Analyze the log for errors (look at the END of the log, not intermediate errors)
tail -130 sunray-srvr-update.log
# Check for final result line: "Registry loaded in X.XXs" indicates SUCCESS
# Look for "CRITICAL" or "ERROR" near the end for actual failures

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

The Cloudflare Worker repository is cloned locally at `./inouk-sunray-worker-cloudflare/`. All commands should be run from this directory.

```bash
# Navigate to worker directory
cd inouk-sunray-worker-cloudflare/

# Install dependencies (if not already done)
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

**Note**: The worker can also be cloned separately if needed:
```bash
git clone https://gitlab.com/cmorisse/inouk-sunray-worker-cloudflare.git
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

- **XML Record IDs**: Use double underscore (`__`) separator for XML IDs
  ```xml
  <!-- View IDs: {{object_name}}__{{view_type}} -->
  <record id="sunray_host__formview" model="ir.ui.view">
  <record id="sunray_host__treeview" model="ir.ui.view">
  <record id="sunray_host__searchview" model="ir.ui.view">
  <record id="sunray_host__kanbanview" model="ir.ui.view">

  <!-- Action IDs: {{object_name}}__actwindow -->
  <record id="sunray_host__actwindow" model="ir.actions.act_window">

  <!-- Menu IDs: {{object_name}}__menu OR {{menu_name}}__menu -->
  <menuitem id="sunray_host__menu" .../>

  <!-- Wizard IDs follow same pattern -->
  <record id="authorize_users_wizard__formview" model="ir.ui.view">
  <record id="authorize_users_wizard__actwindow" model="ir.actions.act_window">

  <!-- Embedded views in form/tree don't need separate IDs -->
  ```

- **Model Technical Names**: Use `sunray.` prefix for all Sunray models
  ```python
  # Main models: sunray.{{object_name}}
  _name = 'sunray.host'
  _name = 'sunray.user'
  _name = 'sunray.session'

  # Association models: sunray.{{parent}}.{{child}}
  _name = 'sunray.host.access.rule'

  # Wizards: sunray.{{wizard_name}}.wizard
  _name = 'sunray.authorize.users.wizard'
  ```

- **Selection Widget for Boolean Choices**: Use `selection` field with radio widget for yes/no choices
  ```python
  # DON'T DO THIS for user choices:
  is_enabled = fields.Boolean(string='Enabled')

  # DO THIS instead - clearer UI with radio buttons:
  auth_mode = fields.Selection([
      ('passkey', 'Passkey Authentication'),
      ('email', 'Email Login'),
  ], string='Authentication Mode')
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

### Remote Authentication (Advanced Feature) ✅

**Implementation Status: COMPLETED**

**Module**: `advanced_addons/sunray_advanced_core/` (Paid feature)

Remote Authentication enables users to authenticate to Protected Hosts using their mobile device's passkey while accessing from an untrusted device (e.g., shared computer, kiosk, library terminal).

**Architecture - Hybrid Model:**
```
┌────────────────────────────────────────────────────────┐
│  1. Computer displays QR code (Worker generates)      │
└────────────────────────────────────────────────────────┘
                      ↓ User scans with mobile
┌────────────────────────────────────────────────────────┐
│  2. Mobile: WebAuthn verification (Worker handles)    │
│     - Credential fetch from Server                    │
│     - Local cryptographic verification                │
│     - Challenge validation                            │
└────────────────────────────────────────────────────────┘
                      ↓ Verification successful
┌────────────────────────────────────────────────────────┐
│  3. Server: Session creation (POST /sessions/remote)  │
│     - Shorter TTL than normal sessions                │
│     - Session type = 'remote'                         │
│     - Device metadata stored                          │
└────────────────────────────────────────────────────────┘
                      ↓ Session created
┌────────────────────────────────────────────────────────┐
│  4. Worker: JWT token generation & computer access    │
└────────────────────────────────────────────────────────┘
```

**Why Hybrid?**
- **Server**: Stores credentials, manages sessions, enforces policies
- **Worker**: Performs WebAuthn verification (low latency, user proximity)
- **Benefits**: Fast authentication, centralized management, network resilience

**Key Features:**

1. **Per-Host Configuration** (in `sunray.host` model):
   - `remote_auth_enabled`: Feature toggle (boolean)
   - `remote_auth_session_ttl`: Default session duration (3600s = 1h)
   - `remote_auth_max_session_ttl`: Maximum allowed duration (7200s = 2h)
   - `session_mgmt_enabled`: Allow users to view/manage sessions
   - `session_mgmt_ttl`: Session management access duration (120s)

2. **Session Type Tracking** (in `sunray.session` model):
   - `session_type`: 'normal' or 'remote'
   - `created_via`: JSON metadata (device info, browser, IP)
   - Enables differentiated policies and UI display

3. **API Endpoints** (`/sunray-srvr/v1/`):
   - `POST /sessions/remote` - Create remote session after Worker verification
   - `GET /sessions/list/{user_id}` - List all user sessions (with filtering)
   - `DELETE /sessions/{session_id}` - Terminate specific session

4. **System Parameters** (via XML data files):
   - `remote_auth.polling_interval`: Computer polling interval (2s)
   - `remote_auth.challenge_ttl`: QR code validity (300s = 5min)
   - **NO code defaults** - parameters MUST exist in database

**Configuration API Changes:**

The `/config` endpoint now includes a `remote_auth` object for hosts with the feature enabled:

```json
{
  "host": {
    "domain": "app.example.com",
    "remote_auth": {
      "enabled": true,
      "session_ttl": 3600,
      "max_session_ttl": 7200,
      "session_mgmt_enabled": true,
      "session_mgmt_ttl": 120,
      "polling_interval": 2,
      "challenge_ttl": 300
    }
  }
}
```

**Feature Detection:**
Workers detect Remote Authentication availability by checking for the `remote_auth` object in the config response. If absent, feature is not available.

**Security Considerations:**
- Remote sessions have shorter TTLs by default (1h vs 8h for normal)
- Users can't extend beyond configured maximum
- Session management requires recent passkey verification
- All remote auth actions generate audit events
- Device metadata tracked for forensics

**User Workflow:**
1. Computer: Visit protected host → Redirected to auth page
2. Computer: Click "Sign in with Mobile" → QR code displayed
3. Mobile: Open mobile app → Scan QR code
4. Mobile: Approve with biometric/passkey → Choose session duration
5. Computer: Automatically logged in → Access granted
6. Mobile: View all sessions → Terminate suspicious sessions

**Admin Workflow:**
1. Navigate to Sunray → Protected Hosts → Select host
2. Go to "Remote Authentication" tab
3. Enable feature and configure session durations
4. Save → Workers auto-detect feature via config refresh

**Related Documentation:**
- API Specification: `docs/API_CONTRACT.md` (Remote Authentication section)
- Implementation Spec: `inouk-sunray-worker-cloudflare/specs/remote_authentication_server_spec.md`
- User Guide: `docs/remote_authentication_guide.md` (future)

**Implementation Files:**
```
advanced_addons/sunray_advanced_core/
├── models/
│   ├── sunray_host.py         # 5 new fields for remote auth config
│   └── sunray_session.py      # 2 new fields for session tracking
├── controllers/
│   └── rest_api.py            # 3 new endpoints + extended config
├── data/
│   └── ir_config_parameter.xml  # System parameters (NO code defaults)
└── views/
    └── sunray_host_views.xml  # Remote Authentication tab in host form
```

**Future Enhancements:**
- Mobile app for QR code scanning
- Push notifications for session requests
- Geo-fencing for remote authentication
- Time-based remote auth policies
- Multi-factor authentication chains

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
