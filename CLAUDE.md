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

**Sunray Advanced Core** (`project_addons_advanced/sunray_advanced_core/`) extends the base system with premium features:

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

### API Development (STD-05)
- **When implementing Server API calls, always refer to the API Contract in `/docs/API_CONTRACT.md`**
- The API Contract is the authoritative source of truth for all worker implementations
- Server enforces all business logic and validation; workers are thin translation layers
- Follow server-centric design principles: no worker-side validation or default values

### Advanced Feature Development (STD-01, STD-02, STD-03)
- Advanced/paid features MUST be implemented in `project_addons_advanced/sunray_advanced_core/` addon
- Extend base models using `_inherit` pattern (never modify core models directly)
- Add API endpoints by extending the `RestAPI` controller class
- Document all new endpoints in `docs/API_CONTRACT.md`
- System parameters MUST be defined via XML data files (NO defaults in code)
- Feature detection: Workers check for feature presence in API responses (e.g., `remote_auth` object)
- Use `protected_host_id` in API documentation/examples (maps to `host_id` internally)

### Passkey Registration Security (STD-07)
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
├── project_addons_advanced/   # Paid/Advanced features (Sunray Enterprise — ELv2)
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

### ⛔ Server & Service Operations — the Makefile is the entry point

The repo root ships a **`Makefile`** that is the canonical way to run every server operation.
**Prefer `make <target>` over reconstructing raw `bin/sunray-srvr` / `pkill` command lines** —
the targets encode the easy-to-get-wrong details (kill-before-upgrade ordering, log rotation,
the `[s]unray-srvr` self-match trap, `--workers=0` on tests vs `--workers=4` on the GUI, fixed
log paths) so nobody has to re-derive them. Run `make help` to list them.

| Target | What it does | Log to read after |
|---|---|---|
| `make update [ADDONS=<m>]` | kill + `sunray-srvr -u <ADDONS> --stop-after-init` (default `all`) | `sunray-srvr-update.log` |
| `make test [ADDONS=<m>] [TAGS=<t>]` | kill + `sunray-srvr --test-enable --workers=0 --stop-after-init` | `sunray-srvr-tests.log` |
| `make test-list` | list test classes + their ready-to-paste `make test` lines | — |
| `make run-gui [DEV=xml]` | long-running GUI/web server (blocking; tails its log) | `sunray-srvr.log` |
| `make run-wrkr [QUEUES=<q>]` | one IMQ worker, needs `sunray_advanced_core` (blocking) | `sunray-srvr-wrkr.log` |
| `make kill` | SIGKILL the GUI + IMQ worker in one shot | — |
| `make clean-logs` | remove `sunray-srvr*.log` (current + rotations) | — |
| `make backup-db` | `pg_dump -Fc` of PGDATABASE → `sunray-db-<timestamp>.pg_dump` at the repo root | — |
| `make initdb` | fresh DB (drop/create + `sunray_init_db.sh --interactive`) — **destructive** | — |
| `make diff-vs-default [DEFAULT=<b>]` | branch diff vs its base (default `main`) | — |
| `make code-review` | print what the 5 Claude review commands cover | — |

**AGENT RULE**: every target except `help`, `diff-vs-default`, `code-review` and `test-list`
boots, stops or upgrades the sunray server or an IMQ worker. Claude must **NOT** run those
itself. The handoff is:

1. Hand the user the exact `make …` line to paste.
2. Wait for their confirmation that it has run.
3. Then do the read-only follow-up yourself — read the log named above, analyze it, report.

`help`, `diff-vs-default`, `code-review` and `test-list` are pure read-only/print and are safe
to run unprompted. The only exception to the rule is an explicit, in-the-moment "run it
yourself" from the user — a general past approval does not count.

**Prerequisite**: `bin/sunray-srvr` is generated by `ikb install` and is gitignored. If it is
missing, no target works — run `ikb install` first.

#### Stop the systemd units before a dev session

On a provisioned App Server (this box is one) the Odoo server and the IMQ worker run as
**supervised systemd units**, so `make kill` cannot hold them down: it kills the process and
systemd respawns it within seconds. The respawned worker keeps a DB/registry lock, which is
exactly what `make update` and `make test` kill things to avoid — leaving them up makes both
targets flaky.

```bash
sudo systemctl stop  mpy_anyv2_appsrv_sunray_srv.service mpy_anyv2_appsrv_sunray_imqwrkr0.service
#  ... dev session: make run-gui / make update / make test ...
sudo systemctl start mpy_anyv2_appsrv_sunray_srv.service mpy_anyv2_appsrv_sunray_imqwrkr0.service
```

The tell-tale that you forgot: `make kill` reports `N killed, 1 still running`.

There are **three** units, and only the first two are this Makefile's business:

| Unit | Component | Reached by `make kill`? |
|---|---|---|
| `mpy_anyv2_appsrv_sunray_srv.service` | Odoo server (GUI/web) | yes |
| `mpy_anyv2_appsrv_sunray_imqwrkr0.service` | IMQ worker (`sunray-srvr imq-worker`) | yes |
| `mpy_anyv2_appsrv_sunray_wrkr.service` | **FastAPI** ForwardAuth worker (`uvicorn`, port 8065) | **no** |

The FastAPI worker is a different component (`sunray-worker-fastapi/`, its own submodule); its
command line doesn't match `[s]unray-srvr`, so nothing here touches it. Leave it running unless
you are specifically testing it.

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

All of it goes through `make` — see [⛔ Server & Service Operations](#-server--service-operations--the-makefile-is-the-entry-point)
for the full target list and the agent handoff rule.

```bash
make run-gui                      # start the GUI/web server (--dev=xml, tails sunray-srvr.log)
make run-gui DEV=                 # ... without the live view reload
make update                       # kill + upgrade ALL modules, then print ERROR/CRITICAL lines
make update ADDONS=sunray_core    # ... a single module
make kill                         # stop the server + IMQ worker
make test ADDONS=sunray_core      # kill + run that module's tests
```

`make update` already does what the old hand-written procedure did — kill first, rotate the
log, run with `--stop-after-init`, then surface the ERROR/CRITICAL lines — so there is no
sequence left to remember. Success is still `Registry loaded in X.XXs` at the end of
`sunray-srvr-update.log`; intermediate errors during a module load are not necessarily
failures.

Installing a module for the first time (`-i` rather than `-u`) has no target: run
`bin/sunray-srvr -i <module> --stop-after-init` directly, or use `make initdb` for a full
fresh database.

**Note**: `bin/sunray-srvr` is a wrapper that:
- Selects the correct Python environment with all required packages
- Injects the configuration file (`-c etc/odoo.buildit.cfg`)
- Maps PostgreSQL environment variables (PGUSER, PGPASSWORD, PGDATABASE) to Odoo equivalents

### Running Tests

Tests run through `make test`, which kills any running server first, forces `--workers=0`
(Odoo will not run tests otherwise), rotates `sunray-srvr-tests.log` and prints the
`odoo.tests` summary at the end.

#### Discovering Tests

Never guess a class name — class names are case-sensitive and now live under two addon roots.
`make test-list` prints every class with its ready-to-paste command:

```bash
make test-list

# From sunray_advanced_core/test_config_serialization:
#   TestSessionDurationSerialization
#     bin/test_server.sh --module sunray_advanced_core --test TestSessionDurationSerialization
#     make test ADDONS=sunray_advanced_core TAGS=/sunray_advanced_core:TestSessionDurationSerialization
```

#### Running Tests

```bash
make test                                                   # every module
make test ADDONS=sunray_core                                # one module
make test ADDONS=sunray_core TAGS=/sunray_core:TestAccessRules              # one class
make test ADDONS=sunray_core TAGS=/sunray_core:TestCacheInvalidation.test_bulk_cache_refresh   # one method
```

`TAGS` is passed straight to Odoo's `--test-tags`, so the `/<module>:<Class>.<method>` form is
the full targeting syntax — there is no separate `--test`/`--method` split at the make level.

`bin/test_server.sh` remains available for the few things make does not wrap: `--verbose`
(Odoo debug logging) and `--log <file>` (capture into `test_logs_and_coverage/`). It is a
**pure launcher** — it translates options into an Odoo command and does not parse the output.

#### Understanding Output

`make test` writes Odoo's full output to `sunray-srvr-tests.log` and echoes the summary lines
at the end of the run:

```
--- odoo.tests summary (sunray-srvr-tests.log) ---
2026-08-07 INFO odoo.tests.stats: sunray_core: 13 tests 4.13s 259 queries
2026-08-07 INFO odoo.tests.result: 0 failed, 0 error(s) of 13 tests
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
| No tests found | "0 failed, 0 error(s) of 0 tests" | `make test-list` for the exact class name + module |
| Import errors | Module errors before tests start | `make update ADDONS=sunray_core` first |
| No `odoo.tests` line at all | make prints "did the tests run at all?" | The module failed to load — read `sunray-srvr-tests.log` from the top |
| Need more details | Brief output | `bin/test_server.sh --verbose` (not wrapped by make) |
| Test takes long | Long execution time | Normal — `tail -f sunray-srvr-tests.log` to watch it live |

#### Adding New Tests

New test files should:
1. Be placed in the addon's `tests/` directory (`project_addons/<addon>/tests/` or
   `project_addons_advanced/<addon>/tests/` — both roots are discovered)
2. Start with `test_` prefix (e.g., `test_my_feature.py`)
3. Import from `odoo.tests.common`
4. Use class names starting with `Test` (e.g., `TestMyFeature`)
5. Use method names starting with `test_` (e.g., `test_my_scenario`)

After adding tests, they will automatically appear in `make test-list` output.

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

### Code Review Standards Checklist

The conventions in this "Development Guidelines" section (and the "Coding Conventions" below it)
are the full prose explanation, with rationale and code examples. **`.claude/code_review_standards.md`**
is a separate, compact distillation of the same conventions into a numbered checklist
(`STD-01`, `STD-02`, ...) written for review — it does not redefine the rules, it references this
file's content in shorthand form so a reviewer (human or agent) doesn't have to re-derive a
checkable rule from prose each time. When either drifts from the other, this file (CLAUDE.md) is
the canonical source — fix the checklist to match, not the reverse.

Run `/standards-review` (or launch the `sunray-standards-review` subagent directly) to check a
diff against that checklist. It is a **conformance** pass only — correctness bugs are
`/code-review`'s job and vulnerabilities are `/security-review`'s, not this one.
`make code-review` (read-only, safe to run unprompted) prints a short explainer of all five
review commands.

**The `(STD-NN)` tags throughout this file** (e.g. "**Audit Logging Policy** (STD-06)") are the
link back to the checklist: they mark which prose section a given `STD-NN` entry distills, so the
two files can be cross-checked instead of drifting apart silently. Not every `STD-NN` has a tag
here — some are **checklist-native** (`STD-21`/`STD-22`, the accessibility and alert-box rules,
were written from reviewing views rather than distilled from this file). An untagged id isn't
automatically a bug — run `/standards-sync` to audit which gaps are expected (checklist-native)
vs. real drift (a convention that changed here without the checklist following, or a stale tag
pointing at a renumbered id).

When you add or change a house convention here, mirror the update into
`.claude/code_review_standards.md` (new `STD-NN` entries are append-only — never renumber an
existing id) so the checklist doesn't silently go stale relative to this file.

### Development Guidelines

- **Feature-First Approach** (STD-24): When you need to manipulate Sunray server data and no feature exists for that purpose, you MUST propose to develop a proper feature (GUI or CLI) instead of writing SQL or creating ad-hoc Odoo/Python scripts. Only if the user rejects the feature development option can you propose ad-hoc scripts/commands.

- **API Contract Updates** (STD-04): When updating any code in the Sunray server REST API controllers (`project_addons/sunray_core/controllers/rest_api.py`, `project_addons_advanced/sunray_advanced_core/controllers/rest_api.py`), you MUST update `docs/API_CONTRACT.md` with the changes if they affect the API contract (new endpoints, changed parameters, modified responses, etc.).

- **Audit Logging Policy** (STD-06): All audit events MUST be created using the `sunray.audit.log` model's `create_audit_event()` method. DO NOT create new logging methods - use the existing unified method with appropriate parameters:
  - **Required parameters**: `event_type`, `details`, `severity`
  - **Optional parameters**: `sunray_admin_user_id`, `sunray_user_id`, `sunray_worker`, `ip_address`, `user_agent`, `request_id`, `event_source`, `username`
  - **Severity levels**: 'info', 'warning', 'error', 'critical' (use 'critical' for security events)
  - **Example usage**: `audit_log.create_audit_event(event_type='security.cross_domain_session', details={'original_domain': 'app1.com', 'requested_domain': 'app2.com'}, severity='critical')`

- **IMQ Processor Method Pattern** (STD-08, STD-09): Methods decorated with `@processor_method` MUST follow this pattern:
  - **`self = self.sudo()` as first line**: IMQ captures `uid` from the record's env at enqueue time. When enqueued from `auth='none'` controllers, `uid=False` (public user), causing FK violations on `write_uid` and type errors in SQL queries. Always escalate to SUPERUSER at the start of the method — the method is the one doing privileged operations, so it should own that escalation.
  - **`_imq_logger` for logging**: The IMQ worker injects `_imq_logger` as a kwarg — it writes to the IMQ message log (visible in `imq-ctl`). When running outside IMQ, `_imq_logger` is None and the method falls back to the module `_logger`.
  - **Accept `_imq_logger=None`** as the last kwarg, create `_task_logger = _imq_logger or _logger` after the `sudo()` line, use `_task_logger` for all logging inside that method.
  - **Nested calls**: Pass `_imq_logger` (NOT `_task_logger`) so each callee builds its own `_task_logger` with its own module `_logger` as fallback.
  - **Variable naming**: Always use `_task_logger` (with leading underscore) to emphasize it's local to the method.
  - **Example**:
    ```python
    @processor_method(queue_name='sunray')
    def my_async_job(self, some_arg, _imq_logger=None):
        """IMQ message name derived from this docstring."""
        self = self.sudo()  # Required — IMQ may run with uid=False
        _task_logger = _imq_logger or _logger
        _task_logger.info(f"Starting job for {self.name}")
        try:
            # ... business logic (no need for .sudo() on individual calls) ...
            _task_logger.info("Job completed successfully")
            return "Success message shown in imq-ctl"  # Return value = message result
        except Exception as e:
            _task_logger.error(f"Job failed: {e}")
            self.last_error = str(e)  # No sudo() needed — self is already sudo'd
    ```

### Coding Conventions

- **Odoo 18 View Syntax** (STD-10): Use new attribute syntax instead of `attrs`
  ```xml
  <!-- DON'T DO THIS (Odoo 17 and earlier): -->
  <field name="field_name" attrs="{'invisible': [('other_field', '=', False)]}"/>
  
  <!-- DO THIS (Odoo 18+): -->
  <field name="field_name" invisible="not other_field"/>
  <field name="field_name" readonly="state == 'done'"/>
  <field name="field_name" required="is_required"/>
  ```

- **Odoo Recordsets** (STD-11): Suffix with `_obj` or `_objs`
  ```python
  user_obj = self.env['sunray.user'].browse(user_id)
  host_objs = self.env['sunray.host'].search([])
  ```

- **Relational Fields** (STD-12): Suffix with `_id` or `_ids`
  ```python
  class SunrayUser(models.Model):
      host_id = fields.Many2one('sunray.host')
      passkey_ids = fields.One2many('sunray.passkey', 'user_id')
  ```

- **Return Convention** (STD-13): Use `False` (not `None`) for empty recordsets
  ```python
  def get_user(self, username):
      user_obj = self.env['sunray.user'].search([('username', '=', username)])
      return user_obj or False
  ```

- **List Views** (STD-14): When creating list views, make all fields `optional="show"` so users can easily adapt the displayed columns
  ```xml
  <list>
      <field name="name"/>
      <field name="description" optional="show"/>
      <field name="create_date" optional="show"/>
      <field name="is_active" widget="boolean_toggle"/>
  </list>
  ```

- **Audit Fields** (STD-15): Never create `created_by`, `created_date`, `modified_by`, or `modified_date` fields
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

- **XML Record IDs** (STD-16): Use double underscore (`__`) separator for XML IDs
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

- **Model Technical Names** (STD-17): Use `sunray.` prefix for all Sunray models
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

- **Selection Widget for Boolean Choices** (STD-18): Use `selection` field with radio widget for yes/no choices
  ```python
  # DON'T DO THIS for user choices:
  is_enabled = fields.Boolean(string='Enabled')

  # DO THIS instead - clearer UI with radio buttons:
  auth_mode = fields.Selection([
      ('passkey', 'Passkey Authentication'),
      ('email', 'Email Login'),
  ], string='Authentication Mode')
  ```

- **Smart Buttons (pure-XML pattern)** (STD-19): To navigate from a parent record to a filtered list of related records, use a dedicated `ir.actions.act_window` whose `domain` references `active_id`. No Python method is needed — `active_id` is resolved to the current record id at click time.

  **Action record** (one per smart button):
  ```xml
  <record id="sunray_configuration_proxy__hosts_actwindow" model="ir.actions.act_window">
      <field name="name">Hosts</field>
      <field name="res_model">sunray.host</field>
      <field name="view_mode">list,form</field>
      <field name="domain">[('scp_id', '=', active_id)]</field>
      <field name="context">{'default_scp_id': active_id}</field>
  </record>
  ```

  **Form view** — button-box as first child of `<sheet>`:
  ```xml
  <sheet>
      <div class="oe_button_box" name="button_box">
          <button name="%(sunray_configuration_proxy__hosts_actwindow)d"
                  type="action" class="oe_stat_button" icon="fa-sitemap">
              <field name="host_count" widget="statinfo" string="Hosts"/>
          </button>
      </div>
      ...
  </sheet>
  ```

  **Count field** on the parent model:
  ```python
  host_count = fields.Integer(compute='_compute_host_count', store=True)

  @api.depends('host_ids')
  def _compute_host_count(self):
      for record in self:
          record.host_count = len(record.host_ids)
  ```

  Conventions:
  - Action XML id: `{parent_model}__{related}_actwindow`.
  - `domain` filters on the inverse Many2one (e.g. `scp_id`) — simpler than going through `host_ids`.
  - `context` pre-fills the inverse field so creation from the filtered list auto-links.
  - Use `type="action"` (not `type="object"`) — no Python method to maintain.
  - Reserve a Python `action_view_xxx` method only when the domain is dynamic (e.g. depends on aggregated data, computed at runtime).

### Toast Notifications (inouk_notifications)

- **Module**: `inouk_notifications` - adds `ik_notify` and `ik_notify_with_link` methods to `res.users`
- **Use case**: Send instant toast notifications to users (e.g., approval requests, async task completion)
- **Requires**: Odoo in multiprocessing mode (`--workers=...`)

**ik_notify_with_link** (recommended for notifications with action):
```python
self.env.user.ik_notify_with_link(
    'warning',                    # type: "danger", "warning", "success", "info"
    'Approval Required',          # title
    f"Request for {action}...",   # message (HTML supported)
    model='my.model',             # model to open
    res_id=record.id,             # record ID
    button_name='Open Request',   # button label (default: "Open")
    sticky=True,                  # must be closed manually (default: True)
)
```

**ik_notify** (basic notification):
```python
self.env.user.ik_notify(
    'success',                    # type
    'Task Complete',              # title
    'Server provisioned.',        # message
    sticky=False,                 # auto-closes after 4s (default)
    autoclose_delay=6000,         # optional: custom delay in ms
)
```

**Message types**:
- `success`: Green, positive feedback
- `info`: Blue, neutral information
- `warning`: Orange, caution
- `danger`: Red, error/critical

**Key differences**:
- `ik_notify_with_link`: Includes action button to open a record, `sticky=True` by default
- `ik_notify`: Simple notification, `sticky=False` by default

**Example - Notify on permission request creation**:
```python
if hasattr(self.requesting_user_id, 'ik_notify_with_link'):
    self.requesting_user_id.ik_notify_with_link(
        'warning',
        'Approval Required',
        f"Your request to {self.method_name} on {self.record_display} requires approval.",
        model='ik.mcp_permission_request',
        res_id=self.id,
        button_name='Open Request',
        sticky=True,
    )
```

### Field Format Pattern (STD-20)

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

### Testing Best Practices (STD-23)

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

**Policy** (STD-25): All project tools must be in the `bin/` directory.

#### Server Tests
Go through `make test` / `make test-list` — see [Running Tests](#running-tests) above.
`bin/test_server.sh` is the underlying launcher, kept for `--verbose` and `--log`.

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

**Module**: `project_addons_advanced/sunray_advanced_core/` (Paid feature)

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
project_addons_advanced/sunray_advanced_core/
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
- Snapshot it with **`make backup-db`** before anything risky (a `-u all`, a migration, a
  `make initdb`). It writes `sunray-db-<timestamp>.pg_dump` at the repo root, next to the logs,
  via `pg_dump -Fc` (custom format, compressed). The server does **not** need to be stopped.
  ```bash
  make backup-db
  # restore (the exact line is printed by the target):
  pg_restore -d $PGDATABASE --clean --if-exists sunray-db-20260808-093000.pg_dump
  ```
  The dumps are gitignored (`*.pg_dump`) and deliberately **not** matched by
  `make clean-logs`' `sunray-srvr*.log` glob — cleaning logs must never delete a backup.

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
