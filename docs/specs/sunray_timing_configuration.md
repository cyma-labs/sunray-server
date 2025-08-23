# Sunray Timing Configuration Reference

## ⏱️ Overview

This document provides a comprehensive reference for all timing parameters, delays, and durations configured in the Sunray authentication system. These parameters control everything from session lifetimes to security timeouts, affecting both user experience and system security.

## 📋 Quick Reference Table

| Parameter | Default | Range | Configuration | Purpose |
|-----------|---------|-------|---------------|---------|
| **Session Duration** | 1h (3600s) | 60s-24h | Host UI | User session lifetime |
| **WAF Bypass Revalidation** | 15min (900s) | 60s-1h | Host UI | Security cookie refresh |
| **Setup Token Validity** | 24h | 1h-168h | UI/CLI | Passkey registration window |
| **Webhook Token Expiration** | Never | Any date | Token UI | API token lifetime |
| **Session Expiration** | Auto | - | Calculated | Absolute session cutoff |
| **Audit Log Retention** | 90 days | - | Hardcoded | Log cleanup period |
| **Cache Refresh Notification** | 60s | - | Hardcoded | Admin feedback delay |
| **Config Change Window** | 5min | - | Hardcoded | Recent user inclusion |
| **Default API Session** | 8h (28800s) | - | Hardcoded | Worker API default |
| **HTTP Request Timeout** | 5s | - | Hardcoded | Cache invalidation timeout |
| **CLI Time Parsing** | - | h/d/m | CLI | Flexible time formats |

## 🎯 Configuration Categories

### 🔒 Security Timeouts
Parameters that directly impact system security by controlling authentication windows and token lifetimes.

### 👤 Session Management  
Settings that control user session behavior and lifetime management.

### 🔧 System Maintenance
Automated cleanup and maintenance timing parameters.

### ⚡ Performance Tuning
Timeouts and refresh intervals that affect system performance and responsiveness.

## 🔧 System Parameters

Sunray uses system parameters to control maximum allowed values for timing configurations:

### `sunray.max_session_duration_s`
- **Default**: 86400 (24 hours)
- **Purpose**: Maximum allowed session duration for any host
- **Configuration**: System Parameters (Admin → Settings → Parameters)
- **Impact**: Prevents administrators from setting excessively long session durations

### `sunray.max_waf_bypass_revalidation_s`
- **Default**: 3600 (1 hour) 
- **Purpose**: Maximum allowed WAF bypass revalidation period
- **Configuration**: System Parameters (Admin → Settings → Parameters)
- **Impact**: Enforces security constraints on WAF cookie lifetimes

These parameters ensure system-wide security policies while allowing per-host customization within safe limits.

---

## 📖 Detailed Parameter Reference

### 1. Session Duration (`session_duration_s`)

**Location**: `sunray_host.py:66-73`  
**Model**: `sunray.host`  
**Field**: `session_duration_s`

**Purpose**: Controls how long user sessions remain valid after successful authentication. This is the primary user experience parameter - longer sessions reduce re-authentication frequency but may increase security risk.

**Configuration**:
- **Admin UI**: Host Settings → Session Duration (seconds)
- **CLI**: Not directly configurable (set via UI)
- **API**: Inherited by worker from host configuration

**Values**:
- **Default**: 3600 seconds (1 hour)
- **Range**: 60 seconds minimum to system parameter maximum (default 86400 seconds)
- **Common Values**:
  - 1 hour = 3600 seconds (default, balanced security)
  - 4 hours = 14400 seconds (longer work sessions)
  - 8 hours = 28800 seconds (full work day)
  - 24 hours = 86400 seconds (convenience, maximum default)

**Impact**: Shorter durations increase security but require more frequent user authentication. Longer durations improve user experience but extend potential exposure time.

---

### 2. WAF Bypass Revalidation Period (`waf_bypass_revalidation_s`)

**Location**: `sunray_host.py:87-94`  
**Model**: `sunray.host`  
**Field**: `waf_bypass_revalidation_s`

**Purpose**: Forces sublimation cookie refresh after this period to maintain security binding between user, IP address, and User-Agent. This prevents cookie theft and session hijacking.

**Configuration**:
- **Admin UI**: Host Settings → WAF Bypass Revalidation Period (seconds)
- **Default**: 900 seconds (15 minutes)
- **Range**: 60 seconds minimum to system parameter maximum (default 3600 seconds)

**Security Considerations**:
- **Shorter periods** (300-600s / 5-10 minutes): Higher security, more frequent validation
- **Standard periods** (900-1800s / 15-30 minutes): Balanced security and user experience
- **Longer periods** (>1800s / >30 minutes): Less secure but fewer interruptions

**Use Cases**:
- **High-security environments**: 300-600 seconds (5-10 minutes)
- **Standard environments**: 900 seconds (15 minutes, default)
- **Development/testing**: 1800+ seconds (30+ minutes) for convenience

---

## 🚨 Security Re-authentication Scenarios

### When Users Must Re-authenticate Within a Valid Session

Even with a valid session (e.g., 8 hours remaining), users must re-authenticate with their Passkey when:

1. **IP Address Changes**: Moving between networks (WiFi to cellular, office to home, roaming)
2. **User-Agent Changes**: Switching browsers or major browser updates  
3. **WAF Bypass Cookie Expires**: After the revalidation period (default 15 minutes)

### Why This Security Feature Exists

The WAF bypass cookie (`sunray_sublimation`) includes security bindings to prevent session hijacking:
- **IP address binding**: Prevents stolen cookies from being used elsewhere
- **User-Agent fingerprinting**: Detects browser changes that could indicate compromise
- **Short expiration**: Limits exposure window if cookie is compromised

### Common User Experience Examples

**🏠 Working from Office, Then Commuting Home:**
- Session: Still valid (within 8-hour window)
- WAF Cookie: Invalid (IP address changed from office to home network)
- **Result**: Must authenticate with Passkey at home location

**🌐 Switching from Chrome to Firefox:**
- Session: Still valid 
- WAF Cookie: Invalid (User-Agent changed)
- **Result**: Must authenticate in new browser

**📱 Moving from WiFi to Cellular:**
- Session: Still valid
- WAF Cookie: Invalid (IP address changed from WiFi to cellular)
- **Result**: Must authenticate on cellular network

### Security Benefits

- **Immediate hijacking detection**: If someone steals your cookie, they can't use it from a different IP
- **Comprehensive audit trail**: All location/browser changes are logged as security events
- **Defense in depth**: Additional security layer beyond basic session management
- **Attack prevention**: Makes session theft attacks significantly more difficult

**Important**: This is intentional security protection, not a bug. Re-authentication on IP/UA changes indicates the system is working correctly.

---

### 3. Setup Token Validity (`validity_hours`)

**Location**: `sunray_setup_token.py:47-58`, `setup_token_wizard.py:12-18`  
**Models**: `sunray.setup.token`, Setup Token Wizard  
**Field**: `validity_hours`

**Purpose**: Controls the time window users have to complete passkey registration using a setup token. Balances security (shorter window) with user convenience (longer window).

**Configuration**:
- **Admin UI**: Setup Token Wizard → Valid for (hours)
- **CLI**: `bin/sunray-srvr srctl setuptoken create --sr-hours N`
- **Default**: 24 hours

**Common Scenarios**:
- **Internal users**: 24-48 hours (standard)
- **External users**: 4-8 hours (security-focused)
- **Emergency access**: 1-2 hours (minimal window)
- **Bulk provisioning**: 168 hours (1 week for large deployments)

**Audit Trail**: Token usage and expiration are logged in audit logs for compliance tracking.

---

### 4. Webhook Token Expiration (`expires_at`)

**Location**: `sunray_webhook_token.py:41-48`  
**Model**: `sunray.webhook.token`  
**Field**: `expires_at`

**Purpose**: Optional expiration date for API/webhook tokens. Supports token rotation security practices by forcing periodic renewal.

**Configuration**:
- **Admin UI**: Webhook Token → Expiration Date (optional)
- **Default**: Never expires (None)

**Best Practices**:
- **Production APIs**: 90-365 days with rotation schedule
- **Development tokens**: 30-90 days for regular cleanup
- **Temporary access**: 1-7 days for short-term integrations
- **Long-term services**: Never expires with monitoring

**Security Notes**: Expired tokens are automatically rejected by the system. Audit logs track token usage and expiration events.

---

### 5. Session Expiration (`expires_at`)

**Location**: `sunray_session.py:20-24`, `rest_api.py:618-620`  
**Model**: `sunray.session`  
**Field**: `expires_at`

**Purpose**: Absolute expiration timestamp for user sessions, calculated as authentication time + session_duration_s. Cannot be manually configured.

**Calculation**: `expires_at = authentication_time + host.session_duration_s`

**Behavior**:
- Sessions are automatically invalidated when `expires_at < current_time`
- Cleanup processes remove expired sessions from database
- Workers check expiration on each request for security

---

### 6. Audit Log Retention

**Location**: `sunray_audit_log.py:77-80`  
**Model**: `sunray.audit.log`  
**Method**: `_cleanup_old_logs()`

**Purpose**: Automatically purges audit logs older than 90 days to prevent unbounded database growth while maintaining compliance history.

**Configuration**: Hardcoded (90 days)

**Impact**: 
- **Storage**: Prevents audit log table from growing indefinitely
- **Performance**: Keeps queries fast by limiting table size
- **Compliance**: Retains 90 days of security events for most compliance frameworks

**Customization**: Modify `timedelta(days=90)` in code if different retention needed.

---

### 7. Cache Refresh Notification Period

**Location**: `sunray_host.py:292`, `sunray_user.py:200`  
**Models**: Host and User force cache refresh methods

**Purpose**: Informs administrators that worker caches will refresh "within 60 seconds" when cache invalidation is triggered.

**Configuration**: Hardcoded (60 seconds)

**Usage**: Provides user feedback on timing expectations for cache invalidation operations.

---

### 8. Configuration Change Detection Window

**Location**: `rest_api.py:148-151`  
**Controller**: Config API endpoint

**Purpose**: Includes users modified within the last 5 minutes in configuration responses to ensure workers quickly receive updated user configurations.

**Configuration**: Hardcoded (5 minutes)

**Impact**: Balances freshness of configuration data with API response size and performance.

---

### 9. Default API Session Duration

**Location**: `rest_api.py:617`  
**Controller**: Session creation endpoint  
**Default**: 8 hours (28800 seconds)

**Purpose**: Fallback session duration when creating sessions via Worker API if no host-specific duration is configured.

**Configuration**: Hardcoded in REST API

---

### 10. HTTP Request Timeout

**Location**: Multiple cache invalidation calls (`sunray_host.py:295`, `sunray_user.py:203`, `sunray_cli.py:683`)  
**Purpose**: Prevents hanging requests when calling worker cache invalidation APIs.

**Configuration**: Hardcoded (5 seconds)

**Rationale**: Cache invalidation should be fast; longer timeouts could block server operations.

---

### 11. CLI Time Duration Parsing

**Location**: `sunray_cli.py:746-758`  
**CLI**: Sunray CLI time parsing  
**Method**: `_parse_time_duration()`

**Purpose**: Allows flexible time specification in CLI commands using human-readable formats.

**Supported Formats**:
- `1h`, `24h` = hours
- `1d`, `7d` = days  
- `5m`, `30m` = minutes

**Usage Examples**:
```bash
# View audit logs from last hour
bin/sunray-srvr srctl auditlog get --since 1h

# View audit logs from last day  
bin/sunray-srvr srctl auditlog get --since 24h

# View audit logs from last week
bin/sunray-srvr srctl auditlog get --since 7d
```

---

## ⚙️ Configuration Examples

### High-Security Environment
```
Session Duration: 3600s (1 hour)
WAF Bypass Revalidation: 5 minutes
Setup Token Validity: 2 hours
Webhook Token Expiration: 30 days
```

### User-Friendly Environment  
```
Session Duration: 86400s (24 hours)
WAF Bypass Revalidation: 30 minutes
Setup Token Validity: 48 hours  
Webhook Token Expiration: 365 days
```

### API-Heavy Environment
```
Session Duration: 28800s (8 hours) 
WAF Bypass Revalidation: 15 minutes
Setup Token Validity: 24 hours
Webhook Token Expiration: 90 days (with rotation)
```

---

## 🔧 Troubleshooting Common Timing Issues

### Users Frequently Re-authenticate
- **Cause**: Session duration too short (default changed from 8h to 1h)
- **Solution**: Increase `session_duration_s` in Host settings (now shows actual values, not 0)
- **Check**: Review audit logs for session expiration patterns
- **Note**: New default is 1 hour for better security; adjust based on your needs

### WAF Bypass Cookie Issues
- **Cause**: Revalidation period too short for user workflow
- **Solution**: Increase `waf_bypass_revalidation_s` (now in seconds, not minutes)
- **Check**: Monitor sublimation audit events
- **Note**: Field renamed from minutes to seconds for consistency

### Users Re-authenticating Despite Valid Session
- **Cause**: IP address or User-Agent changed (security feature, not a bug)
- **Understanding**: This protects against session hijacking attacks
- **Solution**: Educate users this is intentional security protection
- **Alternative**: For trusted environments, consider disabling WAF bypass entirely
- **Check**: Review audit logs for `waf_bypass.tamper.ip_change` and `waf_bypass.tamper.ua_change` events
- **Commands**: 
  ```bash
  # View IP/UA change events
  bin/sunray-srvr srctl auditlog get --event-type "waf_bypass.tamper.*" --since 24h
  
  # Monitor location changes for specific user
  bin/sunray-srvr srctl auditlog get --username "user@example.com" --sublimation-only
  ```

### Setup Tokens Expiring
- **Cause**: Users can't complete registration in time
- **Solution**: Increase `validity_hours` in Setup Token Wizard
- **Check**: Review setup token usage patterns in audit logs

### Cache Not Refreshing
- **Cause**: HTTP timeout or worker unreachable
- **Solution**: Check worker URLs and network connectivity
- **Check**: Cache invalidation audit logs for errors

### API Integration Failures
- **Cause**: Webhook tokens expired
- **Solution**: Check token expiration dates, renew if needed
- **Check**: API call audit logs for authentication failures

---

## 📊 Performance Impact

### Short Timeouts (High Security)
- **Benefits**: Reduced security exposure, frequent validation
- **Costs**: More authentication requests, higher CPU usage
- **Use Case**: Financial services, healthcare, government

### Long Timeouts (User Convenience)
- **Benefits**: Better user experience, fewer interruptions
- **Costs**: Extended exposure window, potential security risk
- **Use Case**: Internal tools, development environments

### Roaming and Mobile Users
- **Challenge**: More frequent re-authentication when changing networks/locations
- **Impact**: Users may need to authenticate multiple times during travel/commute
- **Mitigation**: Consider longer revalidation periods (30-60 minutes) for mobile workforce
- **Trade-off**: User convenience vs. security for network-changing scenarios
- **Alternative**: Educate users that re-authentication on IP changes is a security feature
- **Monitoring**: Track `waf_bypass.tamper.ip_change` events to understand roaming patterns

### Balanced Configuration
- **Session Duration**: 8 hours (full work day)
- **WAF Revalidation**: 15 minutes (security/UX balance)
- **Setup Tokens**: 24 hours (reasonable completion window)
- **Use Case**: Most production environments

---

## 🔍 Monitoring and Observability

### Key Metrics to Monitor
- Session creation/expiration rates
- Setup token usage patterns  
- Cache invalidation frequency
- Authentication failure rates
- Token expiration events

### Audit Log Queries
```bash
# Monitor session patterns
bin/sunray-srvr srctl auditlog get --event-type "session.*" --since 24h

# Check authentication events
bin/sunray-srvr srctl auditlog get --event-type "auth.*" --since 1h

# Review cache operations
bin/sunray-srvr srctl auditlog get --event-type "cache_invalidation" --since 24h
```

### Performance Optimization
- Monitor session duration vs re-authentication frequency
- Track cache hit rates and invalidation patterns
- Analyze user workflow vs revalidation periods
- Review token rotation vs API error rates

---

*This document covers Sunray Core v1.0+ timing parameters. For advanced timing features, see Sunray Advanced documentation.*