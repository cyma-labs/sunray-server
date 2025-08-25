# Sunray Server API Contract v1

This document defines the API that ALL Sunray workers must use. The server provides a rich, comprehensive API that handles all business logic, while workers are thin translation layers.

## Design Principles

1. **Server contains ALL business logic** - Workers are stateless translators
2. **Workers query server for decisions** - No local policy evaluation
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
  "user_versions": {
    "user@example.com": "2024-01-01T11:58:00Z"
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
          "created_at": "2023-01-01T00:00:00Z",
          "backup_eligible": true,
          "backup_state": true
        }
      ]
    }
  },
  "hosts": [
    {
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
- `user_versions`: Map of recently modified users (last 5 minutes) to modification timestamp
- `users`: Map of username to user details including passkeys
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
- `host_versions` and `user_versions` allow workers to detect configuration changes
- Workers can use these for cache invalidation strategies
- Only recently modified users (last 5 minutes) appear in `user_versions`

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
          "created_at": "2023-01-01T00:00:00Z",
          "backup_eligible": true,
          "backup_state": true
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
          "created_at": "2023-01-01T00:00:00Z",
          "backup_eligible": true,
          "backup_state": true
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

**Purpose**: Validates setup tokens for new device registration.

**Request Body**:
```json
{
  "username": "user@example.com",
  "token": "setup_token_string"
}
```

**Response** (Success):
```json
{
  "success": true,
  "user_id": 123,
  "device_name": "laptop"
}
```

**Response** (Error):
```json
{
  "success": false,
  "error": "Invalid or expired setup token"
}
```

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

**Purpose**: Verifies WebAuthn authentication response (does NOT create session).

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

**Purpose**: Creates a new session after successful authentication.

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
  "details": {
    "additional": "context"
  }
}
```

**Event Types**: For a complete list of supported `event_type` values, refer to the `event_type` field definition in `/project_addons/sunray_core/models/sunray_audit_log.py`. The event types are organized into categories:
- Authentication Events (e.g., `auth.success`, `auth.failure`)
- Token Management Events (e.g., `token.generated`, `token.consumed`)
- Configuration Events (e.g., `config.fetched`, `config.session_duration_changed`)
- Session Events (e.g., `session.created`, `session.expired`)
- WAF Bypass Events (e.g., `waf_bypass.created`, `waf_bypass.tamper.*`)
- Security Events (e.g., `security.alert`, `SESSION_IP_CHANGED`)
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
- Invalidate on: Session revocation, logout
- Cache key: `session_{session_id}`

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

Example log entries:
```
INFO: Config updated for host example.com: session_duration_s=3600, waf_bypass_revalidation_s=900
INFO: Created session for user@example.com with duration 3600s, expires at 2024-01-01T13:00:00Z
INFO: WAF bypass cookie refreshed for user@example.com, expires in 900s
ERROR: Host example.com missing required field 'session_duration_s' in configuration
```

## Worker Implementation Requirements

1. **Always query server for authentication decisions**
2. **Implement proper caching with TTL**
3. **Handle server unavailability gracefully**
4. **Log all authentication events via audit endpoint**
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