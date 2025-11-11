# Sunray Server API Contract v1

**Sunray** is a comprehensive and affordable Web/HTTP Zero Trust access solution.

This document defines the API that ALL Sunray workers must use. The server provides a rich, comprehensive API that handles all access control business logic, while workers are thin translation layers that enforce access decisions at the edge.

## Design Principles

1. **Server contains ALL access control logic** - Workers are stateless translators
2. **Workers query server for access decisions** - No local policy evaluation
3. **Server responses are cacheable** - Workers can cache for performance
4. **API versioning for backward compatibility** - Ensures worker stability
5. **Consistent error handling** - Standard error responses across endpoints

## Authentication

All API requests must include the `Authorization` header with a Bearer token:

```
Authorization: Bearer your_worker_api_key_here
```

**Optional Worker Headers**:
- `X-Worker-ID`: Worker identifier for auto-registration and tracking
- `X-Worker-Version`: Worker version information

Workers making their first API call will be automatically registered if they include the `X-Worker-ID` header.

## Worker Management

### Auto-Registration System

Workers automatically register with the server on their first API call when they include the `X-Worker-ID` header. This eliminates manual worker setup and ensures immediate visibility in the admin interface.

**Registration Process**:
1. Worker makes first API call with `X-Worker-ID: unique-worker-name`
2. Server automatically creates worker record
3. Worker is linked to the API key being used
4. Worker appears in admin interface immediately
5. Audit event `worker.auto_registered` is logged

**Worker Object Fields**:
- `name`: Unique worker identifier (from X-Worker-ID header)
- `worker_type`: Detected automatically ('cloudflare', 'kubernetes', etc.)
- `api_key_id`: Associated API key
- `first_seen_ts`: Initial registration timestamp
- `last_seen_ts`: Most recent API call timestamp
- `is_active`: Health status based on recent activity
- `version`: Worker version (from headers if provided)

### Host-Worker Binding

**Binding Rules**:
- One worker can protect multiple hosts
- One host can only be protected by one worker
- Binding occurs during worker registration to specific host
- Unauthorized binding attempts are blocked and audited

**Binding States**:
- **Unbound Host**: No worker assigned, first worker binds immediately
- **Bound Host**: Protected by assigned worker, other workers blocked
- **Pending Migration**: Admin has authorized worker replacement

### Worker Health Monitoring

Workers are continuously monitored for health status:

- **Active**: Regular API calls within expected timeframe
- **Idle**: Reduced API activity but within acceptable bounds
- **Offline**: No API calls for extended period
- **Error**: Recent API failures or configuration issues

Health status affects:
- Admin dashboard indicators
- Migration eligibility
- Audit alerting thresholds
- Cache invalidation strategies

## Host Status and Traffic Control

### Dual-Field Semantics

Hosts in Sunray use two orthogonal fields for status management:

1. **`is_active`** - Lifecycle Management
   - `True`: Host is actively managed by Sunray
   - `False`: Host is archived/decommissioned (workers ignores them)

2. **`block_traffic`** - Security Control
   - `True`: Security lockdown, return 403 Forbidden
   - `False`: Normal operation with authentication

**Field Name Mapping**: The server model uses `block_all_traffic` internally (more explicit) but exposes it as `block_traffic` (more concise) in API responses for consistency with this contract. Workers should always use the `block_traffic` field name.

### Host States and API Behavior

| is_active | block_traffic | API Response | Worker Behavior | Use Case |
|-----------|---------------|--------------|-----------------|----------|
| `False` | `False` | Full config with both flags | Return 503 Service Unavailable | Archived/maintenance |
| `False` | `True` | Full config with both flags | Return 403 Forbidden (lockdown priority) | Archived + locked |
| `True` | `False` | Full config with both flags | Normal auth flow | Standard operation |
| `True` | `True` | Full config with both flags | Return 403 Forbidden | Security incident |

### Worker Behavior

#### Archived/Inactive Hosts (`is_active=False`)
- API returns **full configuration** with `is_active=false`
- Worker should return **503 Service Unavailable** with appropriate message
- Worker should log access attempts for monitoring
- Allows admins to re-activate without re-configuration
- Sessions cannot be created on inactive hosts (blocked server-side)

#### Security Lockdown (`block_traffic=True`)
When a host has `block_traffic=True`, the worker MUST:

1. **Block ALL traffic** with HTTP 403 Forbidden
2. **No exceptions** - all requests denied regardless of auth
3. **Audit logging** - log security lockdown blocks
4. **Clear message** - indicate access is intentionally denied

**Example Response**:
```http
HTTP/1.1 403 Forbidden
Content-Type: text/html

<!DOCTYPE html>
<html>
<head><title>Access Denied</title></head>
<body>
<h1>403 Forbidden</h1>
<p>Access to this resource has been denied by security policy.</p>
</body>
</html>
```

### Configuration API Response

All hosts (including inactive ones) receive full configuration with both status flags:

```json
{
  "is_active": true,
  "block_traffic": false,
  "domain": "app.example.com",
  "backend": "https://backend.example.com",
  "exceptions_tree": [ ... ],
  "websocket_url_prefix": "/ws/",
  "session_duration_s": 3600
}
```

**Note**: Both `is_active` and `block_traffic` fields are included for all hosts. Workers use these fields to determine appropriate behavior (503 for inactive, 403 for locked, normal auth for active).

### Audit Events

The server logs these audit events for status changes:

**Lifecycle Events**:
- `host.deactivated`: Host deactivated/archived (`is_active: True → False`)
- `host.activated`: Host activated/reactivated (`is_active: False → True`)

**Security Events**:
- `host.lockdown.activated`: Security lockdown enabled (`block_traffic: False → True`)
- `host.lockdown.cleared`: Security lockdown cleared (`block_traffic: True → False`)

### Backward Compatibility

This change is backward compatible:
- Existing hosts default to `is_active=True`
- Workers without inactive host support will continue to work normally
- Configuration API remains compatible with older worker versions

## Worker Migration System

### Migration Overview

The migration system enables controlled replacement of workers without service interruption. This supports scaling, version upgrades, geographic relocation, and disaster recovery scenarios.

### Migration Workflow

**Phase 1: Preparation**
1. Admin identifies need for worker replacement
2. New worker is deployed with unique identifier
3. Admin sets `pending_worker_name` on target host
4. System prepares for automatic migration

**Phase 2: Execution**
1. New worker attempts registration to host
2. System detects pending worker matches registering worker
3. Migration occurs automatically
4. Old worker binding is replaced
5. Old worker receives error on next API call

**Phase 3: Completion**
1. Old worker stops serving traffic
2. New worker takes over completely
3. Migration timing and success are logged
4. Admin can verify successful migration

### Migration CLI Commands

```bash
# Set up pending migration
bin/sunray-srvr srctl host set-pending-worker <hostname> <new-worker-name>

# Check migration status
bin/sunray-srvr srctl host migration-status <hostname>

# List all pending migrations
bin/sunray-srvr srctl host list-pending-migrations

# Cancel migration (before it occurs)
bin/sunray-srvr srctl host clear-pending-worker <hostname>
```

### Migration API Behavior

The `/config/register` endpoint handles all migration logic:

**Same Worker Re-registering**:
- Returns current configuration (idempotent)
- Logs `worker.re_registered` event
- No service interruption

**Authorized Pending Worker**:
- Performs automatic migration
- Updates host binding
- Logs detailed migration events
- Returns new configuration

**Unauthorized Worker**:
- Registration blocked
- Detailed error returned with current status
- Logs `worker.registration_blocked` event
- Provides migration guidance

### Migration Audit Events

| Event Type | Description | When Logged |
|------------|-------------|-------------|
| `worker.migration_requested` | Admin sets pending worker | Pre-migration setup |
| `worker.migration_started` | New worker begins registration | Migration start |
| `worker.migration_completed` | Successful migration | Migration success |
| `worker.migration_cancelled` | Admin cancels migration | Manual cancellation |
| `worker.registration_blocked` | Unauthorized registration attempt | Security event |

### Migration Use Cases

**Version Upgrades**: Replace worker with newer version containing bug fixes or features
**Scaling**: Deploy additional workers for load distribution
**Geographic Migration**: Move worker to different region for performance
**Disaster Recovery**: Quickly replace failed worker with emergency replacement
**Maintenance**: Replace worker during planned maintenance windows

## Core Endpoints

### GET /sunray-srvr/v1/config

**Purpose**: Returns complete configuration for all hosts and users. 

**⚠️ IMPORTANT**: This endpoint is intended for administrative monitoring purposes only. Workers MUST NOT use this endpoint as it exposes configuration data for all hosts and users, creating security and efficiency concerns. Workers should use the host-specific `/config/{hostname}` endpoint instead.

**Query Parameters**: None

**Response**:
```json
{
  "version": 4,
  "generated_at": "2024-01-01T12:00:00Z",
  "hosts": [
    {
      "domain": "example.com",
      "backend": "https://backend.example.com",
      "nb_authorized_users": 1,
      "session_duration_s": 3600,
      "websocket_url_prefix": "/ws/",
      "exceptions_tree": {
        "public_patterns": ["/health", "/status"],
        "cidr_rules": [
          {
            "priority": 200,
            "patterns": ["/admin/*"],
            "cidrs": ["192.168.1.0/24"]
          }
        ],
        "token_rules": [
          {
            "priority": 300,
            "patterns": ["/api/*", "/webhook/*"],
            "tokens": [
              {
                "name": "API_Token_1",
                "header_name": "X-API-Key",
                "token_source": "header"
              }
            ]
          }
        ],
        "websocket_rules": [
          {
            "priority": 150,
            "patterns": ["^/ws/chat/.*", "^/ws/notifications"],
            "description": "Real-time communication endpoints"
          }
        ]
      },
      "bypass_waf_for_authenticated": true,
      "waf_bypass_revalidation_s": 900,
      "worker_id": 42,
      "worker_name": "demo-worker-001",
      "config_version": "2024-01-01T11:55:00Z",
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
  ]
}
```

**Field Descriptions**:
- `version`: API version (currently 4 with Access Rules support)
- `generated_at`: Timestamp when config was generated
- `hosts`: Array of host configurations

**Host Configuration Fields**:
- `domain`: The protected domain
- `backend`: Backend service URL to proxy to
- `authorized_users`: List of usernames allowed access
- `session_duration_s`: Session duration in seconds (always present, default: 3600)
- `websocket_url_prefix`: String prefix for authenticated WebSocket endpoints (empty string means no WebSocket support)
- `exceptions_tree`: Access rules for public, CIDR, and token-based access
- `bypass_waf_for_authenticated`: Enable WAF bypass for authenticated users
- `waf_bypass_revalidation_s`: WAF bypass cookie revalidation period in seconds (always present, default: 900)
- `worker_id`: ID of the worker protecting this host (null if not yet bound)
- `worker_name`: Name of the worker protecting this host (null if not yet bound)
- `remote_auth` (object, optional): Remote Authentication configuration (Advanced feature - only present if `sunray_advanced_core` is installed)
  - `enabled` (boolean): Whether Remote Authentication is enabled for this host
  - `session_ttl` (integer): Default remote session duration in seconds
  - `max_session_ttl` (integer): Maximum allowed remote session duration in seconds
  - `session_mgmt_enabled` (boolean): Whether session management feature is enabled
  - `session_mgmt_ttl` (integer): Session management access duration in seconds
  - `polling_interval` (integer): Computer polling interval for challenge verification (seconds)
  - `challenge_ttl` (integer): QR code/challenge validity duration (seconds)

**Version Tracking**:
- Each host includes its own `config_version` for cache invalidation
- Workers can use these timestamps for cache invalidation strategies

### GET /sunray-srvr/v1/config/{hostname}

**Purpose**: Get configuration for a specific host only. This is the recommended endpoint for workers to fetch configuration updates after initial registration.

**Path Parameters**:
- `hostname`: The domain name of the host to get configuration for (e.g., "example.com")

**Headers Required**:
- `Authorization: Bearer your_api_key`
- `X-Worker-ID: your_worker_name`

**Security**: Only workers bound to the specified host can access its configuration.

**Response** (Success):
```json
{
  "version": 4,
  "generated_at": "2024-01-01T12:00:00Z",
  "worker_id": 42,
  "worker_name": "demo-worker-001",
  "host": {
    "domain": "example.com",
    "backend": "https://backend.example.com",
    "authorized_users": ["user@example.com"],
    "session_duration_s": 3600,
    "websocket_url_prefix": "/ws/",
    "exceptions_tree": {
      "public_patterns": ["/health", "/status"],
      "cidr_rules": [
        {
          "priority": 200,
          "patterns": ["/admin/*"],
          "cidrs": ["192.168.1.0/24"]
        }
      ],
      "token_rules": [
        {
          "priority": 300,
          "patterns": ["/api/*", "/webhook/*"],
          "tokens": [
            {
              "name": "API_Token_1",
              "header_name": "X-API-Key",
              "token_source": "header"
            }
          ]
        }
      ]
    },
    "bypass_waf_for_authenticated": true,
    "waf_bypass_revalidation_s": 900,
    "config_version": "2024-01-01T11:55:00Z",
    "remote_auth": {
      "enabled": true,
      "session_ttl": 3600,
      "max_session_ttl": 7200,
      "session_mgmt_enabled": true,
      "session_mgmt_ttl": 120,
      "polling_interval": 2,
      "challenge_ttl": 300
    }
  },
  "users": {
    "user@example.com": {
      "email": "user@example.com",
      "display_name": "User Name",
      "created_at": "2023-01-01T00:00:00Z",
      "passkeys": [
        {
          "credential_id": "credential_id_base64",
          "public_key": "public_key_base64",
          "name": "MacBook Pro",
          "created_at": "2023-01-01T00:00:00Z"
        }
      ]
    }
  }
}
```

**Response** (Errors):
```json
{
  "error": "Worker 'worker-name' not found"
}
```
```json
{
  "error": "Host 'hostname' not found"
}
```
```json
{
  "error": "Worker 'worker-name' not authorized for host 'hostname'"
}
```

**Benefits**:
- **Security**: Workers only access configuration for their assigned host
- **Efficiency**: Minimal data transfer (only relevant host and users)
- **Performance**: Faster response times with focused data
- **Privacy**: No exposure of other hosts' configurations

**Recommended Worker Flow**:
1. **Initial Setup**: `POST /config/register` to bind worker to host
2. **Configuration Updates**: `GET /config/{hostname}` for periodic updates
3. **Cache Management**: Use `host.config_version` for cache invalidation

### POST /sunray-srvr/v1/config/register

**Purpose**: Register worker to a specific host and return host-specific configuration. This endpoint enables automatic worker-host binding and returns only the configuration for the specified host.

**Headers Required**:
- `Authorization: Bearer your_api_key`
- `X-Worker-ID: your_worker_name`

**Request Body**:
```json
{
  "hostname": "example.com"
}
```

**Response** (Success):
```json
{
  "version": 4,
  "generated_at": "2024-01-01T12:00:00Z",
  "worker_id": 42,
  "worker_name": "demo-worker-001",
  "host": {
    "domain": "example.com",
    "backend": "https://backend.example.com",
    "authorized_users": ["user@example.com"],
    "session_duration_s": 3600,
    "websocket_url_prefix": "/ws/",
    "exceptions_tree": {
      "public_patterns": ["/health", "/status"],
      "cidr_rules": [
        {
          "priority": 200,
          "patterns": ["/admin/*"],
          "cidrs": ["192.168.1.0/24"]
        }
      ],
      "token_rules": [
        {
          "priority": 300,
          "patterns": ["/api/*", "/webhook/*"],
          "tokens": [
            {
              "name": "API_Token_1",
              "header_name": "X-API-Key",
              "token_source": "header"
            }
          ]
        }
      ]
    },
    "bypass_waf_for_authenticated": true,
    "waf_bypass_revalidation_s": 900,
    "config_version": "2024-01-01T11:55:00Z",
    "remote_auth": {
      "enabled": true,
      "session_ttl": 3600,
      "max_session_ttl": 7200,
      "session_mgmt_enabled": true,
      "session_mgmt_ttl": 120,
      "polling_interval": 2,
      "challenge_ttl": 300
    }
  },
  "users": {
    "user@example.com": {
      "email": "user@example.com",
      "display_name": "User Name",
      "created_at": "2023-01-01T00:00:00Z",
      "passkeys": [
        {
          "credential_id": "credential_id_base64",
          "public_key": "public_key_base64",
          "name": "MacBook Pro",
          "created_at": "2023-01-01T00:00:00Z"
        }
      ]
    }
  }
}
```

**Response** (Error):
```json
{
  "error": "Worker 'worker-name' not found"
}
```
```json
{
  "error": "Host 'hostname' not found"
}
```
```json
{
  "error": "registration_blocked",
  "message": "Host is bound to another worker",
  "details": {
    "current_worker": "prod-worker-001",
    "pending_worker": "prod-worker-002",
    "host": "example.com",
    "action_required": "Contact administrator for migration approval"
  },
  "timestamp": "2024-01-20T10:30:00Z"
}
```

**Behavior**:
1. Auto-registers the worker if not already registered (using X-Worker-ID header)
2. **Host-Worker Binding Logic**:
   - **Host has no worker**: Binds worker immediately
   - **Same worker re-registering**: Idempotent operation (returns configuration)
   - **Pending worker registering**: Performs migration (replaces current worker)
   - **Unauthorized worker**: Returns error with migration details
3. Returns host-specific configuration (only for the requested host)
4. Includes only users authorized for the specific host
5. **Migration Support**: Enables controlled worker replacement via pending worker mechanism

**Migration Workflow**:
1. Administrator sets pending worker ID on host via UI or CLI
2. New worker registers with matching worker ID → migration occurs automatically
3. Old worker receives error on next request → stops serving
4. All migration events are audit logged for tracking


### GET /sunray-srvr/v1/users/{username}

**Purpose**: Retrieves detailed information about a specific user.

**Authentication**: API key required

**Path Parameters**:
- `username`: The username to retrieve information for

**Response** (User found):
```json
{
  "username": "user@example.com",
  "email": "user@example.com",
  "display_name": "user@example.com",
  "is_active": true,
  "passkey_count": 2,
  "active_session_count": 1,
  "last_login": "2024-01-15T10:30:00Z",
  "authorized_hosts": [
    {
      "domain": "app.example.com",
      "name": "Application Server"
    }
  ],
  "passkeys": [
    {
      "credential_id": "AbC123dEF456...",
      "public_key": "pQECAyYgASFYIH0B...",
      "public_key_format": "cbor_cose",
      "name": "Chrome - Dec 28, 2024",
      "counter": 42,
      "created_at": "2024-12-28T10:00:00Z",
      "last_used_at": "2024-12-28T15:30:00Z"
    }
  ],
  "config_version": "2024-01-15T09:00:00Z"
}
```

**Passkey Fields**:
- `credential_id`: Base64URL encoded credential ID to match against credential.id in authentication assertion
- `public_key`: Base64-encoded CBOR/COSE public key for signature verification (WebAuthn compliant format)
- `public_key_format`: Always `"cbor_cose"` - indicates the format of the public key
- `name`: User-friendly device/passkey name for identification and debugging
- `counter`: WebAuthn authentication counter for replay attack prevention (must be greater than last used value)
- `created_at`: When the passkey was registered (ISO 8601 format)
- `last_used_at`: When the passkey was last used for authentication (null if never used)

**Error Responses**:
- `401 Unauthorized`: Invalid or missing API key
- `404 Not Found`: User not found
- `400 Bad Request`: Invalid username parameter

**Usage**: 
- Check user existence (404 = doesn't exist, 200 = exists)
- Retrieve user details for administrative purposes
- Get user configuration version for cache invalidation
- Access passkey information for authentication and security monitoring

## Setup Token Management

> **⚠️ CRITICAL: Token Normalization Required**
> 
> Workers MUST normalize setup tokens before hashing:
> 1. Remove all dashes (-) and spaces
> 2. Convert to uppercase  
> 3. Then compute SHA-512 hash
> 
> Example: "a2b3c-4d5e6" → normalize → "A2B3C4D5E6" → hash

### POST /sunray-srvr/v1/setup-tokens/validate

**Purpose**: Validate a setup token before WebAuthn registration ceremony.

**Use Case**: Workers call this endpoint when a user clicks "Create Passkeys" to validate the token before initiating the WebAuthn registration process. This provides early feedback and better user experience by catching invalid tokens before the WebAuthn ceremony.

**Authentication**: Requires valid API key and Worker ID.

**Request Headers**:
- `Authorization: Bearer {api_key}` - Required API key for authentication
- `X-Worker-ID: {worker_id}` - Required worker identifier for tracking
- `Content-Type: application/json` - Required

**Request Body**:
```json
{
  "username": "john.doe@example.com",
  "token_hash": "sha512:7d865e959b2466918c9863afca942d0fb89d7c9ac0c99bafc3749504ded97730",
  "client_ip": "192.168.1.100", 
  "host_domain": "app.example.com"
}
```

**Response** (Valid Token - 200 OK):
```json
{
  "valid": true
}
```

**Response** (Invalid Token - 200 OK):
```json
{
  "valid": false
}
```

**Request Body Fields**:
- `username` (string, required): Username associated with the token
- `token_hash` (string, required): SHA-512 hash of setup token, prefixed with "sha512:"
- `client_ip` (string, required): Client IP address for CIDR validation
- `host_domain` (string, required): Domain being protected

**Validation Performed**:
1. API key and worker authentication
2. User existence and active status
3. Token hash lookup and user association
4. Token expiry validation
5. Token consumption status check
6. Token usage limit enforcement
7. Host domain validation and matching
8. CIDR IP address restrictions (if configured on token)

**Error Conditions**:
All validation failures return `{"valid": false}` with appropriate audit logging:
- User not found or inactive
- Token hash not found or invalid
- Token expired or already consumed
- Token usage limit exceeded
- Host domain unknown or mismatch
- IP address outside allowed CIDRs

**Security Features**:
- Comprehensive audit logging for all validation attempts
- No sensitive information exposed in responses
- IP-based access restrictions (if configured)
- Request correlation tracking via Worker ID

**Example Usage**:
```bash
curl -X POST https://sunray-server.example.com/sunray-srvr/v1/setup-tokens/validate \
  -H "Authorization: Bearer YOUR_ADMIN_API_KEY" \
  -H "X-Worker-ID: sunray-worker-prod" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "john.doe@example.com",
    "token_hash": "sha512:7d865e959b2466918c9863afca942d0fb89d7c9ac0c99bafc3749504ded97730",
    "client_ip": "192.168.1.100",
    "host_domain": "app.example.com"
  }'
```

**Token Hash Generation**:
The token hash is computed by workers as follows:
```javascript
// If user's setup token is "ABCD-1234-EFGH-5678"
const crypto = require('crypto');
const token = "ABCD-1234-EFGH-5678";

// IMPORTANT: Normalize token before hashing (remove dashes/spaces, uppercase)
const normalizedToken = token.replace(/-/g, '').replace(/ /g, '').toUpperCase();
// normalizedToken is now "ABCD1234EFGH5678"

const hash = crypto.createHash('sha512').update(normalizedToken).digest('hex');
const token_hash = `sha512:${hash}`;
```

**Audit Events Generated**:
- `token.validation.success` - Token validation succeeded
- `token.validation.user_not_found` - User doesn't exist
- `token.validation.user_inactive` - User is inactive
- `token.validation.token_not_found` - Invalid token hash
- `token.validation.expired` - Token has expired
- `token.validation.consumed` - Token already used
- `token.validation.usage_exceeded` - Token usage limit reached
- `token.validation.unknown_host` - Host domain not found
- `token.validation.host_mismatch` - Token not for requested host
- `token.validation.ip_restricted` - IP not in allowed CIDRs
- `token.validation.system_error` - Unexpected system error

## Passkey Management

### POST /sunray-srvr/v1/users/{username}/passkeys

**Purpose**: Register a new passkey for a user with mandatory setup token validation.

**Security**: This endpoint implements comprehensive security validation and audit logging to prevent unauthorized passkey registration.

**Authentication**: Requires valid API key

**Path Parameters**:
- `username`: The username to register the passkey for

**Request Body**:
```json
{
  "setup_token_hash": "sha512:3c9909afbf37f3d...", // REQUIRED: SHA-512 hash of setup token
  "credential": {                                   // REQUIRED: WebAuthn credential object
    "id": "credential_id",                          // REQUIRED: Unique credential identifier
    "public_key": "base64_public_key"               // REQUIRED: Public key data (fundamental for WebAuthn)
  },
  "host_domain": "app.example.com",                 // REQUIRED: Target host domain
  "name": "My Device"                               // Optional: Device name (default: "Passkey")
}
```

## Public Key Storage Requirements

WebAuthn public keys are provided by workers for server storage:

**Format**: As provided by the worker (typically CBOR-encoded COSE_Key structure, base64-encoded)
**Storage**: Server stores the public key data exactly as provided by the worker
**Validation**: Server does NOT validate public key format - validation is performed by the worker
**Standards**: Worker should ensure compliance with WebAuthn Level 2/3 specifications

**Example COSE Key Structure (before CBOR encoding)**:
```json
{
    1: 2,        // kty: EC2 key type
    3: -7,       // alg: ES256 algorithm
    -1: 1,       // crv: P-256 curve
    -2: "base64-x-coordinate",
    -3: "base64-y-coordinate"
}
```

**Worker Implementation Requirements**:
- Extract public key from `attestationObject.authData.attestedCredentialData`
- Ensure key is in COSE format before base64 encoding
- Perform CBOR validation in worker-side code before sending to server
- Store key for signature verification during authentication

**Important Note**: The `public_key` field is REQUIRED because it's the fundamental component of WebAuthn/Passkey authentication. The worker performs all signature verification - the server acts as a storage layer only.

**Validation Flow**:
1. API key authentication
2. JSON request parsing
3. Required field validation (setup_token_hash, credential, host_domain)
4. User existence and active status
5. Setup token hash validation (direct hash comparison)
6. Token expiry check
7. Token consumption status
8. Token usage limit
9. Host domain validation
10. Token-host binding verification
11. User-host authorization
12. IP CIDR restrictions (if configured)
13. Public key presence check (worker-provided data stored as-is)
14. Duplicate credential check
15. Atomic passkey creation and token consumption

**Response (Success)**:
```json
{
  "success": true,
  "passkey_id": 123,
  "message": "Passkey registered successfully",
  "token_consumed": true
}
```

**Response (Error)**:
```json
{
  "error": "<specific_error_message>"
}
```

**Error Responses**:

| Status | Error Message                           | Cause                                |
|--------|----------------------------------------|--------------------------------------|
| 400    | Missing required fields: {fields}      | Required fields not provided         |
| 400    | Invalid JSON                           | Malformed request body               |
| 400    | Invalid credential format              | Credential not a dict or missing ID  |
| 400    | Unknown host domain: {domain}          | Host doesn't exist or inactive       |
| 401    | Unauthorized                           | Invalid or missing API key           |
| 401    | Invalid setup token                    | Token hash doesn't match             |
| 401    | Setup token expired                    | Token past expiry date               |
| 403    | Token already consumed                 | Token already used                   |
| 403    | Token usage limit exceeded             | Token at max uses                    |
| 403    | Token not valid for this host          | Token bound to different host        |
| 403    | User not authorized for host: {domain} | User not in host's user list         |
| 403    | IP not allowed                         | Client IP outside allowed CIDRs      |
| 404    | User not found                         | Username doesn't exist or inactive   |
| 409    | Credential already registered          | Duplicate credential ID              |
| 500    | Registration failed                    | Database or system error             |

**Security Audit Events**:
All registration attempts are logged with comprehensive details:
- `passkey.registered` - Successful registration
- `security.passkey.*` - Various security violations
- All events include: timestamp, user, IP, user agent, worker ID, and context

**Transaction Behavior**:
- Business operations (passkey + token) are atomic
- Audit logs are always committed regardless of outcome
- On error: business data rolled back, audit persists

**Example**:
```bash
# First compute the hash (in worker code):
# Normalize token: "ABC-123-DEF-456" becomes "ABC123DEF456"
# setup_token_hash = "sha512:" + hashlib.sha512("ABC123DEF456".encode()).hexdigest()

curl -X POST https://sunray.example.com/sunray-srvr/v1/users/user@example.com/passkeys \
  -H "Authorization: Bearer your_api_key" \
  -H "Content-Type: application/json" \
  -H "X-Worker-ID: worker-001" \
  -d '{
    "setup_token_hash": "sha512:3c9909afbf37f3d3bd054c1f8a9c8f5a2b4e6d8f9a1b2c3d4e5f6a7b8c9d0e1f2",
    "credential": {
      "id": "YmFzZTY0X2NyZWRlbnRpYWxfaWQ=",
      "public_key": "YmFzZTY0X3B1YmxpY19rZXk="
    },
    "host_domain": "app.example.com",
    "name": "Chrome on MacBook"
  }'
```

### POST /sunray-srvr/v1/sessions/validate

**Purpose**: Validates an existing session.

**Request Body**:
```json
{
  "session_id": "session_id_string",
  "ip_address": "client_ip",
  "user_agent": "client_user_agent"
}
```

**Response** (Valid):
```json
{
  "valid": true,
  "username": "user@example.com",
  "expires_at": "2024-01-01T12:00:00Z"
}
```

**Response** (Invalid):
```json
{
  "valid": false,
  "reason": "expired"
}
```



### POST /sunray-srvr/v1/sessions

**Purpose**: Creates a new session record. Server acts as storage layer - worker manages counter validation and session expiration calculation.

**Request Body**:
```json
{
  "session_id": "generated_session_id",
  "username": "user@example.com",
  "host_domain": "example.com",
  "expires_at": "2024-01-01T20:00:00Z",
  "credential_id": "credential_id_used",
  "counter": 42,
  "created_ip": "client_ip",
  "device_fingerprint": "browser_fingerprint",
  "user_agent": "Mozilla/5.0...",
  "csrf_token": "csrf_token_value"
}
```

**Field Descriptions**:
- `expires_at` (string, required): Session expiration datetime. Worker calculates this based on its configuration.
  - **Supported formats**: Any ISO 8601 format including:
    - `2024-01-01T20:00:00Z` (recommended - UTC with indicator)
    - `2024-01-01T20:00:00` (basic ISO 8601)
    - `2024-01-01T20:00:00+00:00` (with timezone offset)
    - `2024-01-01T20:00:00.123456Z` (with microseconds)
    - `2024-01-01 20:00:00` (Odoo format - backward compatibility)
  - **Timezone handling**: Timezone information is automatically stripped (server stores as naive datetime)
- `counter` (integer, required): WebAuthn authentication counter value managed by worker. Server stores for debugging and audit purposes.
  - Worker is responsible for counter validation per WebAuthn specification
  - Server updates passkey counter and last_used timestamp if credential_id provided
  - No server-side validation - pure storage operation for admin debugging

**Response**:
```json
{
  "success": true,
  "session_id": "generated_session_id"
}
```

**Error Responses**:
- `400 Bad Request`: Missing required fields (expires_at, counter) or invalid expires_at format
- `401 Unauthorized`: Invalid or missing API key  
- `404 Not Found`: User not found

**Worker Responsibilities**:
- Counter validation per WebAuthn specification (server only stores for debugging)
- Session expiration calculation based on host configuration
- Proper ISO 8601 expires_at formatting

**Server Behavior**:
- Stores all provided data without validation
- Updates passkey counter and last_used if credential_id matches existing passkey
- Maintains audit trail for debugging and compliance

### POST /sunray-srvr/v1/sessions/<session_id>/revoke

**Purpose**: Revokes a specific session (admin/system-initiated).

**Authentication**: API key required

**Request Body**:
```json
{
  "reason": "Admin revocation"  // Optional, defaults to "API revocation"
}
```

**Response**:
```json
{
  "success": true
}
```

**Error Responses**:
- `404 Not Found`: Session not found
- `401 Unauthorized`: Invalid or missing API key

**Usage**: Primarily for administrative session management and system-initiated revocations.

### POST /sunray-srvr/v1/logout

**Purpose**: User-initiated logout endpoint that revokes session and logs logout event.

**Authentication**: API key required

**Request Body**:
```json
{
  "session_id": "session_id_to_logout",
  "ip_address": "client_ip"  // Optional, for audit logging
}
```

**Response**:
```json
{
  "success": true,
  "message": "User logged out successfully"
}
```

**Error Responses**:
- `400 Bad Request`: Missing session_id or invalid JSON
- `404 Not Found`: Session not found
- `401 Unauthorized`: Invalid or missing API key

**Usage**: For user-initiated logouts from workers. Creates `auth.logout` audit event.

**Worker Flow**:
1. Clear session cookies on client
2. Call logout endpoint
3. Redirect to logout confirmation page

## Remote Authentication (Advanced Feature)

**Availability**: This is a **PAID feature** available only in Sunray Advanced Core (`sunray_advanced_core` addon).

**Feature Detection**: Workers detect Remote Authentication availability by checking for the presence of a `remote_auth` object in the `/sunray-srvr/v1/config` response. If the object is missing, the feature is not available.

**Feature Overview**:
Remote Authentication allows users to authenticate to Protected Hosts using their mobile device's passkey while accessing from a different device (e.g., shared computer, kiosk). This enables secure access from untrusted devices without exposing credentials.

**Architecture - Hybrid Model**:
The system uses a hybrid authentication approach for optimal security and performance:

1. **Server Role**:
   - Stores and manages WebAuthn credentials
   - Provides user credentials to Workers for verification
   - Creates and manages sessions after Worker verification
   - Enforces session policies and TTL constraints

2. **Worker Role**:
   - Performs local WebAuthn verification using credentials from Server
   - Generates and manages JWT tokens
   - Handles QR code generation and challenge management
   - Provides session management UI to users

This design ensures:
- Cryptographic operations happen close to the user (low latency)
- Centralized credential and session management (security)
- Reduced network roundtrips during authentication
- Better resilience to network issues

---

### POST /sunray-srvr/v1/sessions/remote

**Purpose**: Creates a remote session after Worker has verified WebAuthn credential locally.

**Authentication**: API key required

**Flow**:
1. Worker performs local WebAuthn verification
2. Worker calls this endpoint with verification results
3. Server trusts Worker verification and creates session
4. Worker generates JWT token for the session

**Request Body**:
```json
{
  "worker_id": "sunray-worker-01",
  "protected_host_id": 123,
  "user_id": 456,
  "session_duration": 3600,
  "device_info": {
    "user_agent": "Mozilla/5.0...",
    "ip_address": "192.168.1.50",
    "device_type": "mobile",
    "browser": "Chrome Mobile"
  }
}
```

**Field Descriptions**:
- `worker_id` (string, required): Worker identifier
- `protected_host_id` (integer, required): Host ID (maps internally to `host_id`)
- `user_id` (integer, required): User ID who is authenticating
- `session_duration` (integer, optional): Requested session duration in seconds
  - If not provided, uses host's `remote_auth_session_ttl` default
  - Cannot exceed host's `remote_auth_max_session_ttl`
  - Minimum 300 seconds (5 minutes)
  - Maximum 86400 seconds (24 hours)
- `device_info` (object, required): Device metadata from Worker
  - `user_agent` (string, required): Full user agent string
  - `ip_address` (string, required): Client IP address
  - `device_type` (string, optional): "mobile", "desktop", "tablet"
  - `browser` (string, optional): Browser name and version

**Response** (Success):
```json
{
  "success": true,
  "session_id": "sess_abc123def456",
  "user_id": 456,
  "username": "user@example.com",
  "expires_at": "2025-10-17T14:00:00Z",
  "session_type": "remote",
  "created_at": "2025-10-17T13:00:00Z"
}
```

**Error Responses**:
```json
// Host not found
{
  "error": "Host not found",
  "code": 404
}

// Remote auth not enabled for host
{
  "error": "Remote authentication not enabled for this host",
  "code": 501
}

// Session duration exceeds maximum
{
  "error": "Session duration cannot exceed 7200 seconds",
  "code": 422
}

// Missing TTL configuration
{
  "error": "Remote auth TTL not configured for this host",
  "code": 500
}

// Missing required fields
{
  "error": "Missing required fields",
  "code": 400
}
```

**HTTP Status Codes**:
- `200`: Session created successfully
- `400`: Missing required fields or invalid request
- `401`: Unauthorized (invalid API key)
- `404`: Host or user not found
- `422`: Validation error (duration constraints)
- `500`: Server configuration error
- `501`: Feature not enabled for host

**Audit Events**: Creates `session.remote_created` audit event.

**Example**:
```bash
curl -X POST https://sunray.example.com/sunray-srvr/v1/sessions/remote \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "worker_id": "sunray-worker-cf-001",
    "protected_host_id": 42,
    "user_id": 123,
    "session_duration": 3600,
    "device_info": {
      "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)",
      "ip_address": "203.0.113.45",
      "device_type": "mobile",
      "browser": "Safari Mobile"
    }
  }'
```

---

### GET /sunray-srvr/v1/sessions/list/{user_id}

**Purpose**: Lists all active sessions for a specific user, optionally filtered by host.

**Authentication**: API key required

**URL Parameters**:
- `user_id` (integer, required): User ID to list sessions for

**Query Parameters**:
- `protected_host_id` (integer, optional): Filter sessions by specific host

**Request Example**:
```bash
# All sessions for user
GET /sunray-srvr/v1/sessions/list/456

# Sessions for user on specific host
GET /sunray-srvr/v1/sessions/list/456?protected_host_id=123
```

**Response** (Success):
```json
{
  "success": true,
  "user_id": 456,
  "username": "user@example.com",
  "total_sessions": 3,
  "sessions": [
    {
      "session_id": "sess_abc123",
      "session_type": "remote",
      "host_id": 123,
      "host_domain": "app.example.com",
      "created_at": "2025-10-17T13:00:00Z",
      "expires_at": "2025-10-17T14:00:00Z",
      "last_activity": "2025-10-17T13:45:00Z",
      "device_info": {
        "user_agent": "Mozilla/5.0...",
        "ip_address": "192.168.1.50",
        "device_type": "mobile",
        "browser": "Chrome Mobile"
      }
    },
    {
      "session_id": "sess_def456",
      "session_type": "normal",
      "host_id": 124,
      "host_domain": "admin.example.com",
      "created_at": "2025-10-17T12:00:00Z",
      "expires_at": "2025-10-17T20:00:00Z",
      "last_activity": "2025-10-17T13:30:00Z",
      "device_info": {
        "user_agent": "Mozilla/5.0...",
        "ip_address": "192.168.1.100",
        "device_type": "desktop",
        "browser": "Firefox"
      }
    }
  ]
}
```

**Response** (No sessions):
```json
{
  "success": true,
  "user_id": 456,
  "username": "user@example.com",
  "total_sessions": 0,
  "sessions": []
}
```

**Error Responses**:
```json
// User not found
{
  "error": "User not found",
  "code": 404
}

// Unauthorized
{
  "error": "Unauthorized",
  "code": 401
}
```

**HTTP Status Codes**:
- `200`: Success (including empty list)
- `401`: Unauthorized (invalid API key)
- `404`: User not found

**Use Cases**:
- Display active sessions in mobile app
- Allow users to review devices with access
- Enable users to identify suspicious sessions
- Support "Where you're signed in" feature

**Example**:
```bash
# List all sessions for user 456
curl https://sunray.example.com/sunray-srvr/v1/sessions/list/456 \
  -H "Authorization: Bearer YOUR_API_KEY"

# List sessions for user 456 on host 123
curl "https://sunray.example.com/sunray-srvr/v1/sessions/list/456?protected_host_id=123" \
  -H "Authorization: Bearer YOUR_API_KEY"
```

---

### DELETE /sunray-srvr/v1/sessions/{session_id}

**Purpose**: Terminates a specific session by ID. Used for session management features.

**Authentication**: API key required

**Authorization**: Users can only terminate their own sessions (enforced server-side).

**URL Parameters**:
- `session_id` (string, required): Session ID to terminate

**Request Body**: None required

**Response** (Success):
```json
{
  "success": true,
  "session_id": "sess_abc123",
  "message": "Session terminated successfully"
}
```

**Error Responses**:
```json
// Session not found
{
  "error": "Session not found",
  "code": 404
}

// Unauthorized (invalid API key)
{
  "error": "Unauthorized",
  "code": 401
}

// Forbidden (session belongs to different user)
{
  "error": "Cannot terminate session for another user",
  "code": 403
}
```

**HTTP Status Codes**:
- `200`: Session terminated successfully
- `401`: Unauthorized (invalid API key)
- `403`: Forbidden (cannot terminate another user's session)
- `404`: Session not found or already expired

**Audit Events**: Creates `session.terminated` audit event.

**Use Cases**:
- User terminates suspicious session from mobile app
- User logs out from specific device
- "Sign out everywhere else" functionality
- Remote device management

**Example**:
```bash
curl -X DELETE https://sunray.example.com/sunray-srvr/v1/sessions/sess_abc123 \
  -H "Authorization: Bearer YOUR_API_KEY"
```

**Worker Implementation Notes**:
1. Worker obtains user_id from JWT context
2. Worker passes session_id to Server
3. Server validates session belongs to user
4. Server terminates session and logs audit event
5. Worker returns success response to client

---

### POST /sunray-srvr/v1/audit

**Purpose**: Records audit events from workers.

**Request Body**:
```json
{
  "event_type": "auth.success",
  "username": "user@example.com",
  "host": "example.com", 
  "ip_address": "client_ip",
  "user_agent": "client_user_agent",
  "severity": "info",
  "details": {
    "additional": "context"
  }
}
```

**Parameters**:
- `event_type` (required): Type of audit event (see event types below)
- `username` (optional): Username associated with the event
- `host` (optional): Host domain associated with the event  
- `ip_address` (optional): Client IP address
- `user_agent` (optional): Client user agent
- `severity` (optional): Event severity level - `info` (default), `warning`, `error`, `critical`
- `details` (optional): Additional context data as JSON object

**Event Types**: For a complete list of supported `event_type` values, refer to the `event_type` field definition in `/project_addons/sunray_core/models/sunray_audit_log.py`. The event types are organized into categories:
- Access Control Events (e.g., `auth.success`, `auth.failure`)
- Token Management Events (e.g., `token.generated`, `token.consumed`)
- Configuration Events (e.g., `config.fetched`, `config.session_duration_changed`)
- Session Events (e.g., `session.created`, `session.expired`, `session.remote_created`, `session.terminated`)
- WAF Bypass Events (e.g., `waf_bypass.created`, `waf_bypass.tamper.*`)
- Security Events (e.g., `security.alert`, `security.cross_domain_session`, `security.host_id_mismatch`, `security.unmanaged_host_access`, `SESSION_IP_CHANGED`)
- Worker Migration Events (e.g., `worker.migration_requested`, `worker.migration_completed`, `worker.registration_blocked`)

**Response**:
```json
{
  "success": true,
  "audit_id": 12345
}
```

## Error Handling

All endpoints use consistent error responses:

```json
{
  "error": "Error description",
  "code": "ERROR_CODE",
  "details": {
    "additional": "context"
  }
}
```

Common HTTP status codes:
- `200`: Success
- `400`: Bad Request (invalid input)
- `401`: Unauthorized (invalid API key)
- `403`: Forbidden (access denied)
- `404`: Not Found (resource doesn't exist)
- `422`: Unprocessable Entity (validation error, e.g., TTL constraints)
- `500`: Internal Server Error
- `501`: Not Implemented (feature not enabled or not available)

## Caching Guidelines

### Configuration Endpoint
- Cache duration: 5 minutes
- Invalidate on: Worker restart, server config changes
- Cache key: `config_{host}`

### Token Validation
- Cache duration: 1 hour
- Invalidate on: Token revocation
- Cache key: `token_{token_hash}`

### Session Validation
- Cache duration: 30 seconds
- Cache key: `session_{session_id}`
- **Invalidate immediately on**:
  - Session revocation (via `/sessions/<session_id>/revoke`)
  - User logout (via `/logout`)
  - Session expiry (handled by cleanup cron)
  - Administrative "revoke all sessions" action
- **Worker responsibilities**:
  - Clear local cache when receiving 404/invalid session responses
  - Implement cache-busting for revoked sessions
  - Use 30-second TTL as safety net for edge cases
- **Cache invalidation flow**:
  1. Worker detects invalid session (validation returns false)
  2. Worker immediately removes from local cache
  3. Worker redirects user to authentication

## Version Compatibility

- **v1**: Current stable version
- **v2**: Future version with additional features
- Workers should specify API version in `Accept` header: `application/vnd.sunray.v1+json`
- Server maintains backward compatibility for at least one major version

## Session Management Instructions for Worker Implementers

### **Overview**

Sunray Server provides two critical timing parameters per host that control session and security cookie behavior. Both are managed identically: server-authoritative, pre-validated, and required.

### **Timing Parameters**

#### **Session Duration (`session_duration_s`)**
- **Purpose**: Controls how long a user session remains valid after authentication
- **Unit**: Seconds
- **Server Default**: 3600 (1 hour)
- **Valid Range**: 60 to system-configured maximum (default 86400)
- **Usage**: Set session cookie Max-Age, calculate session expiration

#### **WAF Bypass Revalidation Period (`waf_bypass_revalidation_s`)**
- **Purpose**: Controls how often the WAF bypass cookie must be refreshed
- **Unit**: Seconds
- **Server Default**: 900 (15 minutes)
- **Valid Range**: 60 to system-configured maximum (default 3600)
- **Usage**: Set WAF bypass cookie expiration, trigger re-authentication

### **Key Principles**

1. **Unified Management**: Both parameters follow identical patterns
2. **Server Authority**: Server provides validated values, no worker-side defaults needed
3. **Always Present**: Both fields are guaranteed in host configuration
4. **Pre-validated**: Values are within acceptable ranges (server enforces constraints)
5. **No Fallbacks**: Workers must not implement any default logic

### **Implementation Requirements**

Workers receive both parameters in the host configuration from `/sunray-srvr/v1/config`:
```json
{
  "domain": "example.com",
  "session_duration_s": 3600,        // Always present, always valid
  "waf_bypass_revalidation_s": 900,  // Always present, always valid
  // ... other host fields
}
```

#### **Configuration Handling**
Workers must:
- Extract both `session_duration_s` and `waf_bypass_revalidation_s` values from host config
- Store these values for use in session and cookie management
- Log received values for debugging (e.g., "Host example.com: session_duration_s=3600, waf_bypass_revalidation_s=900")
- Treat absence of either field as a critical configuration error

#### **Session Cookie Management**
When creating sessions after successful authentication:
- Set session cookie `Max-Age` to `session_duration_s` seconds
- Calculate expiry: `current_time + session_duration_s`
- Include duration in session creation request to server
- Never override server-provided duration values

#### **WAF Bypass Cookie Management** (if enabled)
When managing WAF bypass cookies:
- Set cookie `Max-Age` to `waf_bypass_revalidation_s` seconds
- Calculate expiry: `current_time + waf_bypass_revalidation_s`
- Refresh cookie before expiration during active sessions
- Include IP address and User-Agent binding for security

#### **Validation and Error Handling**
Workers must NOT validate timing values:
- Server guarantees all values are within acceptable ranges
- Do not implement min/max checks (server handles all validation)
- Do not attempt to "correct" unusual values
- Trust server-provided values completely

If timing fields are missing from configuration:
1. Log critical error indicating server configuration problem
2. Refuse to process authentication requests for that host
3. Return appropriate error responses to clients
4. Do not use hardcoded default values

#### **Logging Requirements**
Workers should log:
- Timing values received during configuration updates
- Session creation events with duration used
- WAF cookie refresh events with revalidation period
- Configuration errors for missing timing fields

#### **Security Event Logging Requirements**

Workers must log these critical security events using the audit log endpoint:

**security.cross_domain_session** (Critical):
- **When**: User attempts to use authenticated session from domain A on domain B
- **Details**: `{"original_domain": "app1.company.com", "requested_domain": "app2.company.com", "username": "user", "session_id": "xxx"}`
- **Indicates**: Potential session hijacking, credential stuffing, or misconfigured client

**security.host_id_mismatch** (Critical):
- **When**: Valid session's host_id claim doesn't match expected host_id from configuration
- **Details**: `{"session_host_id": "host123", "expected_host_id": "host456", "username": "user", "session_id": "xxx"}`
- **Indicates**: Session replay attack, host configuration change, or worker synchronization issue

**security.unmanaged_host_access** (Warning):
- **When**: Worker receives request for hostname not registered as Protected Host
- **Details**: `{"hostname": "unknown.company.com", "path": "/admin", "method": "GET", "client_ip": "10.0.0.1", "user_agent": "Mozilla/..."}`
- **Indicates**: Misconfigured DNS/routes, reconnaissance attempts, or forgotten host registrations

Example log entries:
```
INFO: Config updated for host example.com: session_duration_s=3600, waf_bypass_revalidation_s=900
INFO: Created session for user@example.com with duration 3600s, expires at 2024-01-01T13:00:00Z
INFO: WAF bypass cookie refreshed for user@example.com, expires in 900s
ERROR: Host example.com missing required field 'session_duration_s' in configuration
```

### **WebSocket URL Prefix (`websocket_url_prefix`)**

#### **Purpose**
The `websocket_url_prefix` field defines a URL prefix for authenticated WebSocket endpoints that require valid session cookies but should be upgraded to WebSocket protocol.

#### **Format**
- **Type**: String
- **Pattern**: Simple URL prefix (e.g., "/ws/", "/websocket/", "/socket/")
- **Authentication**: All WebSocket URLs require valid session cookies
- **Protocol**: Requests with paths starting with this prefix are upgraded to WebSocket
- **Empty String**: No WebSocket support if empty or not set

#### **Usage**
```json
{
  "websocket_url_prefix": "/ws/"
}
```

#### **Worker Behavior**
- **Authentication Check**: Validate session cookie before WebSocket upgrade
- **Prefix Matching**: Use fast string.startsWith() to match request paths
- **Protocol Upgrade**: Allow WebSocket upgrade for authenticated requests
- **Rejection**: Deny unauthenticated WebSocket connection attempts
- **Performance**: ~100x faster than regex matching

#### **Architectural Notes**
- **Host-Level Configuration**: WebSocket URL prefix is configured per host, not in access rules
- **Authentication Required**: Unlike access rules, WebSocket URLs always require authentication
- **Unauthenticated WebSocket**: Use public access rules if unauthenticated WebSocket access is needed
- **No Bypass**: WebSocket URLs cannot be bypassed - authentication is always required
- **Simplicity**: Covers 99% of real-world WebSocket use cases with single prefix

#### **Example Implementation**
```javascript
// Worker WebSocket handling
if (isWebSocketUpgrade(request)) {
  const path = new URL(request.url).pathname;
  const isWebSocketPath = config.websocket_url_prefix && 
    path.startsWith(config.websocket_url_prefix);
  
  if (isWebSocketPath) {
    // Validate session cookie
    const session = await validateSession(request);
    if (session.valid) {
      return upgradeToWebSocket(request);
    } else {
      return new Response('Unauthorized', { status: 401 });
    }
  }
  
  // Not a configured WebSocket path
  return new Response('WebSocket not allowed', { status: 403 });
}
```

## Worker Implementation Requirements

1. **Always query server for access control decisions**
2. **Implement proper caching with TTL**
3. **Handle server unavailability gracefully**
4. **Log all access control events via audit endpoint**
5. **Validate server responses before acting**
6. **Use secure defaults (deny access) on errors**

## Example Worker Flow

1. **Request Interception**: Worker intercepts incoming request
2. **Cache Check**: Check if config/session is cached and valid
3. **Server Query**: Query server API for decisions if needed
4. **Action**: Allow/deny/redirect based on server response
5. **Audit**: Log the decision via audit endpoint
6. **Cache Update**: Update local cache with server responses

This API contract ensures all workers behave consistently while allowing platform-specific optimizations.