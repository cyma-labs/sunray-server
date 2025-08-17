# Sunray Server - Webhook Token Authentication

## Overview

Webhook tokens provide API-based authentication for automated systems and services that need to access protected resources without user interaction. This feature allows external systems, CI/CD pipelines, monitoring tools, and other automated services to securely authenticate against Sunray-protected hosts using pre-configured tokens.

Webhook tokens complement Sunray's WebAuthn/passkey authentication by providing a secure alternative for programmatic access while maintaining the same security principles and audit capabilities.

## Key Features

### = **Secure Token Generation**
- **Auto-generated tokens**: 32-character cryptographically secure random tokens
- **Manual regeneration**: Tokens can be regenerated without breaking existing configurations
- **Unique constraint**: Each token is globally unique across the system

### < **IP-based Access Control**
- **CIDR block restrictions**: Limit token usage to specific IP addresses or network ranges
- **Flexible IP filtering**: Support for single IPs (`192.168.1.100`) or CIDR blocks (`192.168.1.0/24`)
- **Comment support**: Inline documentation for IP restrictions

### � **Expiration Management**
- **Optional expiration dates**: Tokens can be time-limited or permanent
- **Automatic validation**: Expired tokens are automatically rejected
- **Grace period handling**: Clean expiration without breaking existing workflows

### =� **Usage Tracking & Analytics**
- **Usage counters**: Track how many times each token has been used
- **Last used timestamps**: Monitor token activity patterns
- **Active/inactive states**: Temporarily disable tokens without deletion

### = **Comprehensive Audit Logging**
- **Token creation**: Log when tokens are created
- **Token usage**: Log every token authentication attempt
- **Token regeneration**: Track when tokens are rotated
- **Security events**: Log suspicious activity and validation failures

### = **Multiple Authentication Methods**
- **Custom headers**: `X-Sunray-Webhook-Token` (configurable)
- **URL parameters**: `?sunray_token=xxx` (configurable)
- **Bearer tokens**: `Authorization: Bearer xxx`
- **Flexible extraction**: Supports multiple token delivery methods

### <� **Per-Host Configuration**
- **Host-specific tokens**: Each protected host can have its own set of tokens
- **URL pattern matching**: Define which endpoints accept token authentication
- **Custom header/parameter names**: Customize token extraction for each host

## Security Model

### Token Validation Process

1. **Token Extraction**: Worker extracts token from header, URL parameter, or Authorization header
2. **Pattern Matching**: Check if the requested URL matches configured token-protected patterns
3. **Token Validation**: Verify token exists, is active, and hasn't expired
4. **IP Verification**: Check if client IP is within allowed CIDR ranges (if configured)
5. **Usage Logging**: Record successful authentication for audit purposes
6. **Request Forwarding**: Pass authenticated request to backend service

### Security Features

- **Secure Generation**: Uses `secrets.choice()` for cryptographically secure randomness
- **IP Binding**: Optional IP restrictions prevent token theft/misuse
- **Audit Trail**: Complete logging of all token operations
- **Expiration Support**: Time-limited tokens for temporary access
- **Active State Management**: Disable tokens without deletion
- **Pattern-based Access**: Fine-grained control over which endpoints accept tokens

## Configuration

### Creating Webhook Tokens

1. **Navigate to Host Configuration**:
   - Go to Sunray � Hosts � Select your host
   - Scroll to "Webhook Tokens" section

2. **Add New Token**:
   ```
   Name: CI/CD Pipeline
   Token: [auto-generated or custom]
   Active:  Enabled
   Allowed CIDRs:
   192.168.1.0/24      # Internal network
   10.0.0.0/8          # VPN range
   # 203.0.113.0/24    # Commented out range
   
   Expiration: 2024-12-31 23:59:59 (optional)
   ```

3. **Configure URL Patterns**:
   ```
   Token-Protected URL Patterns:
   ^/api/webhooks/.*$
   ^/api/v1/status$
   ^/health.*$
   # ^/debug/.*$        # Commented pattern
   ```

4. **Set Token Extraction Method**:
   ```
   Webhook Header Name: X-API-Token
   Webhook URL Parameter: api_key
   ```

### Host Configuration Example

```python
# Example host configuration
{
    "domain": "api.example.com",
    "token_url_patterns": [
        "^/api/webhooks/.*$",
        "^/api/v1/status$",
        "^/health.*$"
    ],
    "webhook_header_name": "X-API-Token",
    "webhook_param_name": "api_key",
    "webhook_tokens": [
        {
            "name": "CI/CD Pipeline",
            "token": "abc123...xyz789",
            "allowed_cidrs": ["192.168.1.0/24", "10.0.0.0/8"],
            "expires_at": "2024-12-31T23:59:59Z",
            "is_active": true
        }
    ]
}
```

## Usage Examples

### Using Webhook Tokens

#### Method 1: Custom Header
```bash
curl -H "X-Sunray-Webhook-Token: your_token_here" \
     https://protected.example.com/api/webhooks/deploy
```

#### Method 2: URL Parameter
```bash
curl "https://protected.example.com/api/status?sunray_token=your_token_here"
```

#### Method 3: Bearer Token
```bash
curl -H "Authorization: Bearer your_token_here" \
     https://protected.example.com/api/health
```

### CI/CD Integration

#### GitHub Actions
```yaml
- name: Deploy via webhook
  run: |
    curl -H "X-API-Token: ${{ secrets.SUNRAY_WEBHOOK_TOKEN }}" \
         -X POST \
         https://protected.example.com/api/webhooks/deploy
```

#### GitLab CI
```yaml
deploy:
  script:
    - curl -H "X-API-Token: $SUNRAY_WEBHOOK_TOKEN"
           -X POST
           https://protected.example.com/api/webhooks/deploy
```

### Monitoring Scripts

#### Health Check with Token
```bash
#!/bin/bash
TOKEN="your_webhook_token"
HEALTH_URL="https://protected.example.com/health"

response=$(curl -s -H "X-Sunray-Webhook-Token: $TOKEN" "$HEALTH_URL")
if [ $? -eq 0 ]; then
    echo "Service is healthy: $response"
else
    echo "Service check failed"
    exit 1
fi
```

## CLI Management

### Managing Webhook Tokens

While webhook tokens are primarily managed through the Sunray web interface, you can view token information using the CLI:

```bash
# View host details including webhook token count
bin/sunray-srvr srctl host get api.example.com

# List all hosts with webhook token counts
bin/sunray-srvr srctl host list --output table
```

## Monitoring & Auditing

### Tracking Token Usage

Monitor token activity through the audit log system:

```bash
# View all webhook-related events
bin/sunray-srvr srctl auditlog list --event-type "webhook.*"

# View recent token usage
bin/sunray-srvr srctl auditlog list --since 1h --event-type "webhook.used"

# Monitor token regeneration events
bin/sunray-srvr srctl auditlog list --event-type "webhook.regenerated"
```

### Audit Log Events

The system tracks these webhook-related events:

- **`webhook.used`**: Token successfully used for authentication
- **`webhook.regenerated`**: Token value was regenerated
- **`webhook.failed`**: Token authentication failed
- **`webhook.expired`**: Attempt to use expired token
- **`webhook.ip_denied`**: IP address not in allowed CIDR ranges

### Usage Analytics

Each webhook token tracks:
- **Usage Count**: Total number of successful authentications
- **Last Used**: Timestamp of most recent usage
- **Created Date**: When the token was first created
- **Expiration Date**: When the token will expire (if set)

## Best Practices

### Token Security

1. **Use Strong Tokens**: Let the system auto-generate tokens for maximum security
2. **Rotate Regularly**: Regenerate tokens periodically (quarterly recommended)
3. **Limit IP Access**: Always configure CIDR restrictions when possible
4. **Set Expiration Dates**: Use time-limited tokens for temporary access
5. **Monitor Usage**: Regularly review token usage patterns and audit logs

### Token Management

1. **Descriptive Names**: Use clear, descriptive names for tokens
2. **Principle of Least Privilege**: Only grant access to necessary URL patterns
3. **Environment Separation**: Use different tokens for dev/staging/production
4. **Documentation**: Comment CIDR ranges and URL patterns for clarity
5. **Deactivate vs Delete**: Deactivate unused tokens instead of deleting for audit trail

### Operational Guidelines

1. **Regular Audits**: Review token usage monthly
2. **Incident Response**: Have procedures for token compromise
3. **Backup Strategy**: Ensure token configurations are included in backups
4. **Team Access**: Control who can create and manage webhook tokens
5. **Integration Testing**: Test token authentication in staging environments

## Troubleshooting

### Common Issues

#### Token Not Working
1. **Check Token Status**: Ensure token is active and not expired
2. **Verify URL Pattern**: Confirm the requested URL matches configured patterns
3. **Check IP Restrictions**: Verify client IP is in allowed CIDR ranges
4. **Review Headers**: Ensure token is sent in correct header/parameter

#### Authentication Failures
1. **Check Audit Logs**: Review webhook events for failure details
2. **Verify Token Value**: Ensure complete token is transmitted
3. **Test with curl**: Use simple curl commands to isolate issues
4. **Check Network**: Verify IP restrictions and network connectivity

### Debug Commands

```bash
# Check host configuration
bin/sunray-srvr srctl host get your-host.com --output yaml

# View recent authentication failures
bin/sunray-srvr srctl auditlog list --event-type "webhook.failed" --since 1h

# Monitor real-time webhook activity
bin/sunray-srvr srctl auditlog list --follow --event-type "webhook.*"
```

## API Integration

### Worker Configuration Endpoint

The webhook tokens are automatically included in the worker configuration:

```bash
GET /sunray-srvr/v1/config
Authorization: Bearer admin_api_key

Response:
{
    "hosts": [
        {
            "domain": "api.example.com",
            "webhook_tokens": [
                {
                    "token": "abc123...xyz789",
                    "name": "CI/CD Pipeline",
                    "allowed_cidrs": ["192.168.1.0/24"],
                    "expires_at": "2024-12-31T23:59:59Z"
                }
            ],
            "webhook_header_name": "X-API-Token",
            "webhook_param_name": "api_key",
            "token_url_patterns": [
                "^/api/webhooks/.*$"
            ]
        }
    ]
}
```

## Advanced Configuration

### Custom Token Formats

While the system generates secure tokens automatically, you can specify custom token formats if needed for legacy system integration:

```python
# Custom token (use with caution)
webhook_token = env['sunray.webhook.token'].create({
    'name': 'Legacy System',
    'token': 'custom-legacy-token-123',
    'host_id': host.id
})
```

### Programmatic Token Management

```python
# Create token programmatically
host = env['sunray.host'].search([('domain', '=', 'api.example.com')])
token = env['sunray.webhook.token'].create({
    'name': 'Automated Script',
    'host_id': host.id,
    'allowed_cidrs': '192.168.1.0/24\n10.0.0.0/8',
    'expires_at': '2024-12-31 23:59:59'
})

# Regenerate token
new_token_value = token.regenerate_token()

# Check token validity
is_valid = token.is_valid(client_ip='192.168.1.100')
```

## Multi-Provider Webhook Support

### Overview

**NEW**: Sunray now supports multiple webhook providers on the same host with per-token authentication configuration. This eliminates the previous limitation where all tokens on a host had to use the same header or parameter name.

### Real-World Multi-Provider Scenario

```python
# Example: E-commerce platform receiving webhooks from multiple providers
host_config = {
    'domain': 'api.shop.example.com',
    'webhook_tokens': [
        {
            'name': 'Shopify Order Updates',
            'token': 'shopify_webhook_secret_xyz',
            'header_name': 'X-Shopify-Hmac-Sha256',
            'token_source': 'header'
        },
        {
            'name': 'Stripe Payment Events', 
            'token': 'stripe_webhook_secret_abc',
            'header_name': 'Stripe-Signature',
            'token_source': 'header'
        },
        {
            'name': 'Mirakl Marketplace API',
            'token': 'mirakl_api_key_123',
            'header_name': 'Authorization',
            'token_source': 'header'
        },
        {
            'name': 'Legacy Inventory System',
            'token': 'legacy_api_token_456',
            'param_name': 'api_key',
            'token_source': 'param'
        }
    ]
}
```

### Token Source Options

- **`header`**: Extract token from specified HTTP header only
- **`param`**: Extract token from specified URL parameter only  
- **`both`**: Try header first, fall back to parameter if header not found

### Configuration Examples

#### Shopify Webhooks
```
Name: Shopify Order Webhook
Header Name: X-Shopify-Hmac-Sha256
Token Source: Header Only
Token: [auto-generated secure token]
```

#### Stripe Webhooks
```
Name: Stripe Payment Webhook
Header Name: Stripe-Signature
Token Source: Header Only
Token: [auto-generated secure token]
```

#### GitHub Webhooks
```
Name: GitHub Repository Webhook
Header Name: X-Hub-Signature-256
Token Source: Header Only
Token: [auto-generated secure token]
```

#### Legacy API Integration
```
Name: Legacy System API
Parameter Name: api_key
Token Source: Parameter Only
Token: [auto-generated secure token]
```

#### Flexible API (supports both)
```
Name: Flexible API Client
Header Name: X-API-Key
Parameter Name: key
Token Source: Both (Header First)
Token: [auto-generated secure token]
```

### Migration from Previous Version

**Automatic Compatibility**: Existing deployments continue to work without changes. The host-level `webhook_header_name` and `webhook_param_name` fields are still supported for backward compatibility but are now marked as deprecated.

**Recommended Upgrade Path**:
1. Create new tokens with per-token configuration
2. Update client systems to use provider-specific headers
3. Test thoroughly in staging environment
4. Remove old host-level configuration when ready

### Benefits

- **True Multi-Provider Support**: Host the same application behind Sunray and receive webhooks from Shopify, Stripe, GitHub, etc.
- **Provider-Specific Security**: Each provider can use its own authentication method
- **Simplified Configuration**: No more conflicts between different webhook formats
- **Better Audit Trail**: Token usage logs show which provider authenticated
- **Flexible Deployment**: Same configuration works for development, staging, and production

---

For additional support or advanced configuration needs, consult the main Sunray documentation or contact your system administrator.