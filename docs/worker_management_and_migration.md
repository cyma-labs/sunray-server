
# Sunray Worker Management and Migration Guide

## 🤖 Overview

**Sunray** is a comprehensive and affordable Web/HTTP Zero Trust access solution. This guide covers Sunray's Worker Management system, which provides a sophisticated approach to deploying, monitoring, and migrating edge workers that enforce access control for your protected applications.

The system supports zero-downtime worker replacement, automatic registration, comprehensive health monitoring, and complete audit trails for continuous access protection.

This guide covers the complete worker lifecycle from initial deployment through controlled migration and decommissioning.

## 🏗️ Worker Architecture

### Core Concepts

**Worker Object**: A server-side representation of an edge worker that handles request interception and access control enforcement.

**Host-Worker Binding**: The relationship between a protected host and its assigned worker. One worker can protect multiple hosts, but each host can only be protected by one worker.

**Auto-Registration**: Workers automatically register themselves with the server on their first API call, eliminating manual setup steps.

**Migration System**: Controlled replacement of workers without service interruption through a pending worker mechanism.

### Worker Types

- **Cloudflare Workers**: Serverless edge functions on Cloudflare's global network
- **Kubernetes ForwardAuth**: Access control middleware for Kubernetes clusters (future)
- **NGINX auth_request**: Access control module for NGINX (future)
- **Traefik ForwardAuth**: Access control middleware for Traefik (future)

## 📋 Worker Lifecycle

### 1. Worker Creation and Deployment

**Step 1: Create API Key for Worker**
```bash
# Create a worker-specific API key
bin/sunray-srvr srctl apikey create worker-api-key-001 \
  --sr-worker \
  --sr-description "API key for production worker"
```

**Step 2: Deploy Worker with Configuration**
Workers auto-register using the `X-Worker-ID` header during their first API call. The worker name should be unique and descriptive.

**Example Worker Configuration**:
```toml
# wrangler.toml for Cloudflare Worker
name = "sunray-worker-prod-001"
worker_id = "sunray-worker-prod-001"
sunray_server_url = "https://sunray.example.com"
sunray_api_key = "your_worker_api_key_here"
```

**Step 3: Initial Registration**
On first API call, the worker automatically creates its server-side record with:
- Worker name (from `X-Worker-ID` header)
- Worker type (detected from request characteristics)
- API key association
- First seen timestamp
- Worker version (if provided in headers)

### 2. Host-Worker Binding

**Automatic Binding on Registration**
```bash
# Worker registers to protect a specific host
POST /sunray-srvr/v1/config/register
{
  "hostname": "app.example.com"
}
```

**Binding Logic**:
- **Unbound Host**: Worker binds immediately
- **Same Worker**: Idempotent operation (returns configuration)
- **Different Worker**: Registration blocked (requires migration setup)

**Manual Binding Management**
```bash
# View host binding status
bin/sunray-srvr srctl host get app.example.com

# List unbound hosts
bin/sunray-srvr srctl host list --unbound

# List workers and their assignments
bin/sunray-srvr srctl worker list
```

### 3. Worker Monitoring

**Health Status Indicators**:
- **Active**: Worker making regular API calls
- **Idle**: No recent API activity (configurable threshold)
- **Offline**: Extended period without contact
- **Error**: Recent API errors or failures

**Monitoring Commands**:
```bash
# List all workers with status
bin/sunray-srvr srctl worker list

# Get detailed worker information
bin/sunray-srvr srctl worker get worker-name-001

# Monitor worker health
bin/sunray-srvr srctl worker list --status active
bin/sunray-srvr srctl worker list --last-seen 1h

# View worker audit events
bin/sunray-srvr srctl auditlog get --worker worker-name-001 --since 24h
```

**Worker Metrics**:
- Last seen timestamp
- Total API calls
- Error rate
- Configuration version
- Host assignments
- Geographic distribution (for Cloudflare workers)

### 4. Worker Configuration Updates

**Automatic Updates**
Workers periodically fetch configuration updates using:
```bash
# Recommended approach for updates
GET /sunray-srvr/v1/config/{hostname}
```

**Force Configuration Refresh**
```bash
# Force worker to refresh configuration
bin/sunray-srvr srctl host force-cache-refresh app.example.com

# Refresh all hosts protected by a worker
bin/sunray-srvr srctl worker force-refresh worker-name-001
```

## 🔄 Worker Migration System

### Migration Overview

**Purpose**: Enable controlled replacement of workers without service interruption.

**Key Benefits**:
- **Zero Downtime**: Users experience no service interruption
- **Controlled Process**: Admin approval required for all migrations
- **Complete Audit Trail**: All migration events logged
- **Safety Mechanisms**: No accidental worker replacements
- **Rollback Capability**: Easy reversal if issues occur

### Migration Workflow

#### Phase 1: Migration Preparation

1. **Assess Migration Need**
   - Scaling requirements
   - Version upgrades
   - Geographic relocation
   - Disaster recovery
   - Performance optimization

2. **Deploy New Worker**
   ```bash
   # Deploy new worker with unique identifier
   # Do NOT use the same name as existing worker
   # Example: upgrade from "prod-worker-001" to "prod-worker-002"
   ```

3. **Verify New Worker Health**
   ```bash
   # Worker should auto-register on first API call
   # But will NOT bind to hosts (existing worker present)
   bin/sunray-srvr srctl worker get prod-worker-002
   ```

#### Phase 2: Migration Authorization

4. **Set Pending Worker**
   ```bash
   # Authorize migration by setting pending worker
   bin/sunray-srvr srctl host set-pending-worker app.example.com prod-worker-002
   
   # Verify pending status
   bin/sunray-srvr srctl host migration-status app.example.com
   ```

5. **Monitor Migration Readiness**
   ```bash
   # List all pending migrations
   bin/sunray-srvr srctl host list-pending-migrations
   
   # Check new worker is healthy and ready
   bin/sunray-srvr srctl worker get prod-worker-002
   ```

#### Phase 3: Migration Execution

6. **Automatic Migration Trigger**
   - New worker attempts registration to host
   - Migration occurs automatically when pending worker matches
   - Old worker receives error response on next API call
   - Old worker stops serving traffic

7. **Migration Completion**
   ```bash
   # Verify migration completed
   bin/sunray-srvr srctl host get app.example.com
   # Should show new worker as bound
   
   # Check migration timing and success
   bin/sunray-srvr srctl host migration-status app.example.com
   ```

#### Phase 4: Migration Verification

8. **Post-Migration Testing**
   - Verify protected application accessibility
   - Test authentication flows
   - Monitor error rates and performance
   - Validate all protected endpoints

9. **Audit Review**
   ```bash
   # Review migration events
   bin/sunray-srvr srctl auditlog get --event-type "worker.migration_*" --since 1h
   
   # Monitor new worker performance
   bin/sunray-srvr srctl auditlog get --worker prod-worker-002 --since 1h
   ```

### Migration Scenarios

#### Scenario 1: Version Upgrade
```bash
# 1. Deploy new worker version
# 2. Set pending worker
bin/sunray-srvr srctl host set-pending-worker app.example.com app-worker-v2

# 3. New worker automatically migrates on registration
# 4. Verify and cleanup old worker
```

#### Scenario 2: Scaling (Additional Workers)
```bash
# 1. Deploy additional worker for different host
# 2. Bind directly (no existing worker)
bin/sunray-srvr srctl host create new-app.example.com --worker new-worker-001
```

#### Scenario 3: Geographic Migration
```bash
# 1. Deploy worker in new region
# 2. Migrate hosts in planned sequence
# 3. Monitor performance improvements
```

#### Scenario 4: Emergency Replacement
```bash
# 1. Deploy emergency worker quickly
# 2. Fast migration with minimal testing
bin/sunray-srvr srctl host set-pending-worker app.example.com emergency-worker
```

### Migration CLI Commands Reference

```bash
# Migration Planning
bin/sunray-srvr srctl host list                    # View all hosts
bin/sunray-srvr srctl worker list                  # View all workers
bin/sunray-srvr srctl host list --unbound          # Find unbound hosts

# Migration Setup
bin/sunray-srvr srctl host set-pending-worker <host> <worker>
bin/sunray-srvr srctl host migration-status <host>
bin/sunray-srvr srctl host list-pending-migrations

# Migration Management
bin/sunray-srvr srctl host clear-pending-worker <host>  # Cancel migration
bin/sunray-srvr srctl worker force-refresh <worker>     # Force config update

# Post-Migration
bin/sunray-srvr srctl auditlog get --event-type "worker.*" --since 1h
bin/sunray-srvr srctl worker get <worker>               # Verify status
```

### Migration Audit Events

| Event Type | Description | Timing |
|------------|-------------|---------|
| `worker.migration_requested` | Admin sets pending worker | Pre-migration |
| `worker.migration_started` | New worker begins registration | During migration |
| `worker.migration_completed` | Successful worker replacement | Post-migration |
| `worker.migration_cancelled` | Admin cancels pending migration | Any time |
| `worker.re_registered` | Same worker re-registers (normal) | Ongoing |
| `worker.registration_blocked` | Unauthorized registration attempt | When blocked |

## 🎛️ Administrative Interface

### Sunray Admin UI Features

**Worker List View**:
- Worker name and type
- Health status indicators
- Last seen timestamp
- Number of protected hosts
- Migration status

**Worker Detail View**:
- Complete worker configuration
- Recent activity timeline
- Performance metrics
- Associated hosts list
- Audit log summary

**Host Form View**:
- Current worker assignment
- Migration status banner (if pending)
- Pending worker field
- Clear pending migration button
- Force cache refresh action

### Search and Filtering

**Worker Filters**:
- By worker type (Cloudflare, Kubernetes, etc.)
- By health status (Active, Idle, Offline)
- By last seen period
- By number of hosts protected

**Host Filters**:
- By worker assignment status
- By pending migration status
- By migration duration
- By protection status

## 🚨 Troubleshooting

### Common Worker Issues

**Worker Not Auto-Registering**:
```bash
# Check API key configuration
bin/sunray-srvr srctl apikey list

# Verify worker is sending X-Worker-ID header
# Check worker logs for API call errors
# Confirm server accessibility from worker location
```

**Worker Registration Blocked**:
```bash
# Check if host is already bound to another worker
bin/sunray-srvr srctl host get app.example.com

# View registration attempt details
bin/sunray-srvr srctl auditlog get --event-type "worker.registration_blocked"
```

**Migration Not Proceeding**:
```bash
# Verify pending worker is set correctly
bin/sunray-srvr srctl host migration-status app.example.com

# Check if new worker is healthy and making requests
bin/sunray-srvr srctl worker get new-worker-name

# Review migration audit events
bin/sunray-srvr srctl auditlog get --event-type "worker.migration_*"
```

**Worker Performance Issues**:
```bash
# Check worker health status
bin/sunray-srvr srctl worker list --status error

# Review recent worker errors
bin/sunray-srvr srctl auditlog get --worker worker-name --event-type "*.error"

# Force configuration refresh
bin/sunray-srvr srctl host force-cache-refresh app.example.com
```

### Migration Rollback Procedures

**Emergency Rollback**:
```bash
# Cancel pending migration
bin/sunray-srvr srctl host clear-pending-worker app.example.com

# If migration completed, reverse the process:
# 1. Ensure old worker is still available
# 2. Set old worker as pending
# 3. Force old worker to re-register
bin/sunray-srvr srctl host set-pending-worker app.example.com old-worker-name
```

**Post-Rollback Verification**:
```bash
# Verify rollback completed
bin/sunray-srvr srctl host get app.example.com

# Test application accessibility
# Monitor for any service disruption
# Review audit logs for rollback events
```

## 📊 Best Practices

### Worker Naming Conventions

- **Environment Prefix**: `prod-`, `staging-`, `dev-`
- **Application Identifier**: `app-name-`
- **Version/Sequence**: `001`, `v2`, `202401`
- **Example**: `prod-ecommerce-worker-v2-001`

### Migration Planning

1. **Off-Peak Timing**: Schedule migrations during low traffic periods
2. **Gradual Rollout**: Migrate less critical hosts first
3. **Health Verification**: Ensure new workers are healthy before migration
4. **Rollback Readiness**: Keep old workers available for rollback
5. **Communication**: Notify stakeholders of planned migrations

### Security Considerations

1. **API Key Management**: Rotate worker API keys regularly
2. **Worker Authentication**: Verify worker identity through X-Worker-ID
3. **Audit Monitoring**: Alert on suspicious migration activity
4. **Access Control**: Limit migration permissions to authorized admins
5. **Network Security**: Ensure secure communication channels

### Performance Optimization

1. **Geographic Distribution**: Deploy workers close to users
2. **Load Balancing**: Use multiple workers for high-traffic applications
3. **Configuration Caching**: Optimize cache refresh intervals
4. **Monitoring**: Track worker response times and error rates
5. **Capacity Planning**: Monitor worker resource utilization

## 🔗 Related Documentation

- [WAF Bypass Guide](./waf_bypass_guide.md) - Enhanced security for authenticated users
- [API Contract](./API_CONTRACT.md) - Complete API specification
- [Sunray Introduction](./sunray_introduction.md) - System overview and concepts

## 🆘 Emergency Procedures

### Worker Down Emergency

1. **Assess Impact**: Identify affected hosts and users
2. **Deploy Emergency Worker**: Fast deployment with minimal configuration
3. **Emergency Migration**: Use `set-pending-worker` for rapid replacement
4. **User Communication**: Notify users of temporary service restoration
5. **Root Cause Analysis**: Investigate failure after service restoration

### Widespread Worker Failure

1. **Activate Incident Response**: Follow organization incident procedures  
2. **Assess Scope**: Identify all affected workers and hosts
3. **Priority Triage**: Restore most critical services first
4. **Parallel Recovery**: Deploy multiple replacement workers simultaneously
5. **Service Validation**: Verify all services restored before all-clear

---

**🔧 Technical Support**: For complex worker management issues, ensure you have recent audit logs, worker configurations, and detailed error descriptions when seeking support.