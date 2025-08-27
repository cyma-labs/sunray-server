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
  "config_version": "2024-01-01T12:00:00Z",
  "host_versions": {
    "example.com": "2024-01-01T11:55:00Z"
  },
  "hosts": [
    {
      "domain": "example.com",
      "backend": "https://backend.example.com",
      "nb_authorized_users": 1,
      "session_duration_s": 3600,
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
      "worker_id": 42,
      "worker_name": "demo-worker-001"
    }
  ]
}
```

**Field Descriptions**:
- `version`: API version (currently 4 with Access Rules support)
- `generated_at`: Timestamp when config was generated
- `config_version`: Global configuration version timestamp
- `host_versions`: Map of domain to last modification timestamp
- `hosts`: Array of host configurations

**Host Configuration Fields**:
- `domain`: The protected domain
- `backend`: Backend service URL to proxy to
- `authorized_users`: List of usernames allowed access
- `session_duration_s`: Session duration in seconds (always present, default: 3600)
- `exceptions_tree`: Access rules for public, CIDR, and token-based access
- `bypass_waf_for_authenticated`: Enable WAF bypass for authenticated users
- `waf_bypass_revalidation_s`: WAF bypass cookie revalidation period in seconds (always present, default: 900)
- `worker_id`: ID of the worker protecting this host (null if not yet bound)
- `worker_name`: Name of the worker protecting this host (null if not yet bound)

**Version Tracking**:
- `host_versions` allows workers to detect configuration changes
- Workers can use these for cache invalidation strategies

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
    "config_version": "2024-01-01T11:55:00Z"
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
    "config_version": "2024-01-01T11:55:00Z"
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

### POST /sunray-srvr/v1/setup-tokens/validate

**Purpose**: Validates and consumes setup tokens for new device registration. **⚠️ CRITICAL**: This endpoint increments token usage count and will consume the token when usage limit is reached. Every token is bound to a specific host and MUST be validated against that host.

**Request Body**:
```json
{
  "username": "user@example.com",
  "token_hash": "sha512:hex_hash_value",
  "client_ip": "192.168.1.100",
  "host_domain": "app.example.com"
}
```

**Required Fields**:
- `username`: Username associated with the token
- `token_hash`: SHA-512 hash of the token (format: "sha512:hex_value")
- `client_ip`: Client IP address for CIDR validation
- `host_domain`: Domain where token is being used (MUST match token's bound host)

**Token Consumption Behavior**:
- Each successful validation increments `current_uses` counter
- Token becomes consumed when `current_uses >= max_uses`
- Default `max_uses` is 1 (single-use token)
- Consumed tokens return error on subsequent validation attempts
- Audit event `token.consumed` is logged on each successful validation
- **Important**: Token consumption happens even if subsequent operations fail

**Validation Steps**:
1. Verify all required fields are present
2. Check user exists and is active
3. Verify token exists and hasn't expired
4. Check token isn't already consumed
5. **Validate host binding** - token MUST be for the specified host_domain
6. Check client IP against allowed CIDRs (if configured)
7. Verify usage limit not exceeded
8. Increment usage count and mark consumed if limit reached

**Response** (Success):
```json
{
  "valid": true,
  "user": {
    "username": "user@example.com",
    "email": "user@example.com",
    "display_name": "User Name"
  }
}
```

**Response** (Error):
```json
{
  "valid": false,
  "error": "<error_message>"
}
```

**Possible Error Messages**:
- `"Missing required fields"` - One or more required fields not provided
- `"User not found"` - Username doesn't exist or inactive
- `"Invalid or expired token"` - Token not found, expired, or already consumed
- `"Unknown host"` - host_domain not recognized in system
- `"Token not valid for this host"` - Token is bound to a different host
- `"IP not allowed"` - Client IP doesn't match CIDR restrictions
- `"Token usage limit exceeded"` - Token already consumed (reached max_uses)

**Security Considerations**:
- **Host Binding**: Every token is cryptographically bound to a specific host - this is enforced
- **Token Storage**: Tokens are stored as SHA-512 hashes, never in plaintext
- **IP Validation**: Optional CIDR blocks restrict token usage to specific networks
- **Single Use Default**: Tokens are single-use by default for security
- **Audit Trail**: All validation attempts are logged with IP, host, and outcome
- **Zero Trust**: Each validation requires full context (user, host, IP) - no assumptions

**Example Usage**:
```bash
# Worker validates a setup token for user registration
curl -X POST https://sunray-server.example.com/sunray-srvr/v1/setup-tokens/validate \
  -H "Authorization: Bearer your_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "user@example.com",
    "token_hash": "sha512:a1b2c3d4e5f6...",
    "client_ip": "192.168.1.100",
    "host_domain": "app.example.com"
  }'
```

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
  "config_version": "2024-01-15T09:00:00Z"
}
```

**Error Responses**:
- `401 Unauthorized`: Invalid or missing API key
- `404 Not Found`: User not found
- `400 Bad Request`: Invalid username parameter

**Usage**: 
- Check user existence (404 = doesn't exist, 200 = exists)
- Retrieve user details for administrative purposes
- Get user configuration version for cache invalidation

### POST /sunray-srvr/v1/users/{username}/passkeys

**Purpose**: Registers a new passkey for a user.

**Path Parameters**:
- `username`: The username to register the passkey for

**Request Body**:
```json
{
  "credential": {
    "id": "credential_id",
    "rawId": "base64_raw_id",
    "response": {
      "attestationObject": "base64_attestation",
      "clientDataJSON": "base64_client_data"
    },
    "type": "public-key"
  },
  "setup_token": "valid_setup_token"
}
```

**Response**:
```json
{
  "success": true,
  "passkey_id": "new_passkey_id"
}
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

### POST /sunray-srvr/v1/auth/challenge

**Purpose**: Initiates WebAuthn authentication challenge.

**Request Body**:
```json
{
  "username": "user@example.com",
  "host": "example.com"
}
```

**Response**:
```json
{
  "challenge": "base64_challenge",
  "allowCredentials": [
    {
      "id": "credential_id",
      "type": "public-key"
    }
  ],
  "timeout": 60000
}
```

### POST /sunray-srvr/v1/auth/verify

**Purpose**: Verify passkey authentication. Verifies WebAuthn access control response (does NOT create session).

**Request Body**:
```json
{
  "username": "user@example.com",
  "credential": {
    "id": "credential_id",
    "rawId": "base64_raw_id",
    "response": {
      "authenticatorData": "base64_auth_data",
      "clientDataJSON": "base64_client_data",
      "signature": "base64_signature"
    },
    "type": "public-key"
  },
  "challenge": "base64_challenge",
  "host_domain": "example.com",
  "client_ip": "client_ip_address"
}
```

**Response**:
```json
{
  "success": true,
  "user": {
    "id": 123,
    "username": "user@example.com",
    "email": "user@example.com",
    "display_name": "User Name"
  }
}
```

### POST /sunray-srvr/v1/sessions

**Purpose**: Creates a new session after successful access control verification.

**Request Body**:
```json
{
  "session_id": "generated_session_id",
  "username": "user@example.com",
  "host_domain": "example.com",
  "duration": 28800,
  "credential_id": "credential_id_used",
  "created_ip": "client_ip",
  "device_fingerprint": "browser_fingerprint",
  "user_agent": "Mozilla/5.0...",
  "csrf_token": "csrf_token_value"
}
```

**Response**:
```json
{
  "success": true,
  "session_id": "generated_session_id"
}
```

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
- Session Events (e.g., `session.created`, `session.expired`)
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
- `500`: Internal Server Error

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