# Sunray WAF Bypass Guide

## 🛡️ Overview

**Sunray** is a comprehensive and affordable Web/HTTP Zero Trust access solution. This guide covers Sunray's WAF Bypass feature, which allows users who have passed access control to bypass Cloudflare's Web Application Firewall (WAF) rules, significantly improving the user experience while maintaining enterprise-grade security. 

This sophisticated system uses a security-hardened cookie mechanism called "sublimation" that provides seamless access for legitimate users while maintaining complete audit trails and tamper detection.

### Why WAF Bypass Matters

Traditional WAF configurations can create friction for users who have already passed access control:
- **False Positives**: Legitimate user actions blocked by overly aggressive WAF rules
- **Performance Impact**: Every request subjected to full WAF inspection even for users who've proven access rights
- **User Frustration**: Users encountering security blocks despite having valid access
- **Admin Overhead**: Constant WAF rule tuning to balance security and usability

Sunray's WAF Bypass solves these challenges by creating a secure "trust lane" for users who have passed access control while preserving all security benefits for unverified traffic.

## 🏗️ How It Works

### Architecture Overview

```
1. User passes Sunray access control (WebAuthn/Passkeys)
2. Sunray Worker creates sublimation cookie with security bindings
3. Subsequent requests include sublimation cookie
4. Cloudflare WAF detects cookie and skips inspection
5. Request processed with minimal latency
6. All events comprehensively audit logged
```

### The Sublimation Cookie

The "sublimation" cookie is a sophisticated security token that contains:

- **Session Binding**: Links to active Sunray session
- **IP Address Binding**: Prevents cookie theft/replay attacks
- **User-Agent Fingerprinting**: Detects browser/device changes
- **HMAC Signature**: Cryptographically signed to prevent tampering
- **Time-based Expiry**: Configurable revalidation periods (default: 15 minutes)
- **Hidden Cookie Name**: Uses `sunray_sublimation` to reduce discoverability

## 🔐 Security Architecture

### Multi-Layer Protection

1. **Cryptographic Integrity**: HMAC-SHA256 signatures prevent cookie forgery
2. **Network Binding**: IP address validation prevents cross-network attacks
3. **Device Binding**: User-Agent fingerprinting detects device changes
4. **Temporal Security**: Regular revalidation ensures fresh authentication
5. **Session Correlation**: Links to active Sunray session for validity
6. **Comprehensive Auditing**: All manipulation attempts logged and alerted

### Tamper Detection Events

Sunray monitors and logs all manipulation attempts:

| Event Type | Description | Security Response |
|------------|-------------|------------------|
| `waf_bypass.tamper.format` | Invalid cookie structure | Cookie rejected, event logged |
| `waf_bypass.tamper.hmac` | Signature verification failed | Forgery attempt logged |
| `waf_bypass.tamper.session` | Session ID mismatch | Session correlation failure logged |
| `waf_bypass.tamper.ip_change` | IP address changed | Geographic/network change logged |
| `waf_bypass.tamper.ua_change` | User-Agent changed | Device/browser change logged |

### Performance Impact

- **Cookie Generation**: ~5ms on authentication (one-time cost)
- **Cookie Validation**: <2ms per request (negligible overhead)
- **Cookie Size**: ~200 bytes (minimal bandwidth impact)
- **Overall Latency**: <0.1% increase for authenticated users
- **WAF Bypass**: Significant performance improvement for complex requests

## ⚙️ Configuration Guide

### Server-Side Setup

1. **Enable WAF Bypass for Host**
   ```bash
   # Via CLI
   bin/sunray-srvr srctl host get example.com
   # Enable bypass_waf_for_authenticated field in Admin UI
   ```

2. **Configure Revalidation Period**
   ```bash
   # Set custom revalidation period (in seconds)
   # Default: 900 seconds (15 minutes)
   # Range: 60-3600 seconds
   ```

3. **Set Environment Variables**
   ```bash
   # Option 1: Dedicated WAF bypass secret
   export WAF_BYPASS_SECRET="your-strong-random-secret"
   
   # Option 2: Uses existing SESSION_SECRET if WAF_BYPASS_SECRET not set
   export SESSION_SECRET="your-session-secret"
   ```

### Cloudflare Configuration

1. **Create WAF Firewall Rule**
   - **Rule Name**: `Sunray Authenticated Bypass`
   - **Expression**: `(http.cookie contains "sunray_sublimation")`
   - **Action**: `Skip` → `All remaining custom rules`
   - **Priority**: `Very High` (must execute before OWASP rules)

2. **Rule Placement Considerations**
   - Place before all other custom rules
   - Place before OWASP Core Ruleset
   - Keep after DDoS protection rules
   - Keep after Bot Management rules

### Host Configuration Fields

In the Sunray Admin interface, each host has:

- **`bypass_waf_for_authenticated`** (Boolean): Enable/disable WAF bypass
- **`waf_bypass_revalidation_s`** (Integer): Revalidation period in seconds

## 📊 Monitoring & Audit

### Real-time Monitoring

```bash
# View all WAF bypass events
bin/sunray-srvr srctl auditlog get --sublimation-only

# Monitor manipulation attempts
bin/sunray-srvr srctl auditlog get --event-type "waf_bypass.tamper.*"

# Real-time monitoring
bin/sunray-srvr srctl auditlog get --since 1m --sublimation-only --follow

# View events for specific host
bin/sunray-srvr srctl auditlog get --host example.com --sublimation-only
```

### Audit Event Types

**Normal Operations**:
- `waf_bypass.created` - Sublimation cookie created after authentication
- `waf_bypass.validated` - Successful cookie validation
- `waf_bypass.expired` - Cookie expired naturally (time-based)
- `waf_bypass.cleared` - Cookie cleared on logout

**Security Events**:
- `waf_bypass.tamper.*` - Various tampering attempts detected
- `waf_bypass.error` - General validation errors

### Monitoring Best Practices

1. **Set up alerting** for tamper events (`waf_bypass.tamper.*`)
2. **Monitor IP changes** - may indicate account compromise or legitimate travel
3. **Track User-Agent changes** - may indicate device switching or browser updates
4. **Review expiry patterns** - understand user session behavior
5. **Correlate with session events** - ensure proper session management

## 🚨 Security Considerations

### Deployment Requirements

1. **HTTPS Only**: WAF bypass only functions over secure connections
2. **Secure Environment Variables**: Protect WAF_BYPASS_SECRET like passwords
3. **Regular Secret Rotation**: Rotate bypass secrets according to security policy
4. **Audit Log Protection**: Ensure audit logs are tamper-proof and backed up

### Risk Assessment

**Low Risk Scenarios**:
- Internal corporate networks with controlled access
- Applications with additional authentication layers
- Environments with comprehensive network monitoring

**Higher Risk Scenarios**:
- Public-facing applications with sensitive data
- Regulatory compliance environments (PCI, HIPAA, SOX)
- Applications without additional security controls

### Compliance Considerations

- **Audit Requirements**: Ensure audit logging meets regulatory standards
- **Data Classification**: Consider data sensitivity when enabling bypass
- **Change Management**: Document all bypass configuration changes
- **Security Reviews**: Regular security assessments of bypass usage

## 🔧 Troubleshooting

### Common Issues

**Cookie Not Working**:
- Verify Cloudflare rule expression and priority
- Check `bypass_waf_for_authenticated` is enabled on host
- Ensure HTTPS is used (cookies require secure connection)
- Confirm WAF_BYPASS_SECRET is set correctly

**Frequent Revalidation**:
- Check `waf_bypass_revalidation_s` setting
- Monitor for IP address changes
- Review User-Agent consistency
- Verify session stability

**Performance Issues**:
- Monitor cookie generation overhead
- Check HMAC validation performance
- Review Cloudflare rule placement
- Verify network latency impacts

### Diagnostic Commands

```bash
# Check host configuration
bin/sunray-srvr srctl host get example.com

# View recent bypass events
bin/sunray-srvr srctl auditlog get --since 1h --sublimation-only

# Monitor for errors
bin/sunray-srvr srctl auditlog get --event-type "waf_bypass.error" --since 24h

# Check session correlation
bin/sunray-srvr srctl session list --active --host example.com
```

## 🛑 Emergency Rollback Procedures

### Immediate Rollback

1. **Disable WAF Bypass on Host**
   ```bash
   # Disable via CLI or Admin UI
   # Set bypass_waf_for_authenticated = False
   ```

2. **Remove Cloudflare Rule**
   - Delete or disable "Sunray Authenticated Bypass" rule
   - Changes take effect within 30 seconds globally

3. **Monitor Impact**
   ```bash
   # Check for exploitation attempts
   bin/sunray-srvr srctl auditlog get --event-type "waf_bypass.tamper.*" --since 24h
   
   # Monitor user experience
   bin/sunray-srvr srctl auditlog get --event-type "auth.*" --since 1h
   ```

### Post-Incident Analysis

1. **Audit Log Review**: Analyze all WAF bypass events before/during incident
2. **Security Assessment**: Evaluate if bypass was exploited
3. **Configuration Review**: Verify all settings and secrets
4. **User Impact**: Assess any service disruption
5. **Lessons Learned**: Document findings and improve procedures

### Graceful Degradation

- **No Data Migration Required**: Rollback affects only future requests
- **Session Continuity**: Existing sessions remain valid
- **User Experience**: Users may face additional WAF challenges
- **Automatic Fallback**: System continues functioning without bypass

## 📚 Related Documentation

- [API Contract - WAF Bypass Fields](../docs/API_CONTRACT.md#waf-bypass-cookie-management)
- [Worker Management Guide](../docs/worker_management_and_migration.md)
- [Session Management](../docs/API_CONTRACT.md#session-management-instructions-for-worker-implementers)
- [Audit Logging](../docs/API_CONTRACT.md#audit-endpoint)

## 🆘 Support and Escalation

For WAF bypass issues:

1. **Check audit logs first** - most issues visible in logs
2. **Verify Cloudflare configuration** - common source of problems  
3. **Review environment variables** - ensure secrets are correctly set
4. **Monitor user reports** - correlation with security events
5. **Escalate security concerns** - any suspected tampering or exploitation

---

**⚠️ Security Notice**: WAF bypass affects your application's security posture. Ensure thorough testing, monitoring, and regular security reviews when this feature is enabled.