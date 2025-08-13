# Sunray Worker Deployment Guide

## Overview

The Sunray Worker is a Cloudflare Worker that acts as an **authenticating proxy** for protected web applications. It intercepts all incoming requests to protected domains, validates authentication according to configured rules, and either proxies the request to the backend or redirects to authentication.

### Architecture

```
User Request → Cloudflare Worker → Authentication Check → Backend Server
                     ↓                      ↓
              Auth Required?         Proxy Request
                     ↓
              Redirect to Login
```

### How It Works

1. **Intercepts ALL requests** to protected domains (e.g., `odoo18-cfed-test-g.pack8s.com/*`)
2. **Reserved paths** (`/sunray-wrkr/v1/*`) handle authentication operations:
   - `/sunray-wrkr/v1/auth` - Login page
   - `/sunray-wrkr/v1/setup` - Passkey registration
   - `/sunray-wrkr/v1/health` - Health check
3. **All other paths** are checked for authentication then proxied to the backend
4. **Authentication methods** (checked in order):
   - CIDR whitelist (office IPs)
   - Public URL patterns
   - Webhook tokens
   - Session cookies (WebAuthn/Passkeys)

## Prerequisites

### Required Tools

- **Node.js** 20.x and npm (already installed)
- **Wrangler CLI** (Cloudflare's deployment tool)
  ```bash
  npm install -g wrangler
  ```
- **jq** (for JSON parsing in scripts)
  ```bash
  apt-get install jq  # or appropriate for your system
  ```

### Required Access

- Cloudflare account with access to the target zone
- Permission to create Workers and KV namespaces
- Access to the Sunray Server API key

### Remote Development Environment Authentication

When working in a remote development environment (SSH, VS Code Web, cloud IDE), the standard `wrangler login` won't work because the OAuth callback goes to `localhost:8976` which isn't accessible from your local machine.

#### Solution 1: Use API Token (Recommended in General)

1. **Generate an API token** in Cloudflare Dashboard:
   - Go to https://dash.cloudflare.com/profile/api-tokens
   - Click "Create Token"
   - Use template "Edit Cloudflare Workers" or create custom token with:
     - Account: `Cloudflare Workers Scripts:Edit`
     - Zone: `Workers Routes:Edit` (for your domain)
   - Copy the generated token

2. **Set the token in your environment**:
   ```bash
   # Option A: Export for current session
   export CLOUDFLARE_API_TOKEN="your-api-token-here"
   
   # Option B: Create .env file (add to .gitignore!)
   echo "CLOUDFLARE_API_TOKEN=your-api-token-here" > .env
   
   # Option C: Use wrangler config
   wrangler config
   # Choose "API Token" and paste your token
   ```

3. **Verify authentication**:
   ```bash
   wrangler whoami
   # Should show your account details
   ```

#### Solution 2: SSH Tunnel for OAuth Flow (Recommended for Muppy Dev Servers)

If you prefer OAuth login over API tokens:

1. **From your local machine**, create an SSH tunnel:
   ```bash
   # Standard SSH port (22)
   ssh -L 8976:localhost:8976 user@your-dev-server
   
   # Non-standard SSH port (example: port 2222)
   ssh -p 2222 -L 8976:localhost:8976 user@your-dev-server
   
   # For your specific setup (example with custom port)
   ssh -p RemoteServerPort -L 8976:localhost:8976 RemoteServerUsername@RemoteServerIP
   
   # eg.
   ssh -p 40010 -L 8976:localhost:8976 muppy@100.65.185.8
   ```

2. **In the remote environment**, run:
   ```bash
   wrangler login
   ```

3. **On your local machine**, open the browser URL shown
4. Complete authentication in your local browser
5. The callback will work through the SSH tunnel

#### Solution 3: Use Wrangler's Remote URL

For some environments, you can specify a custom callback URL:

```bash
# Generate auth URL without starting local server
wrangler login --browser=false

# This will output a URL like:
# https://dash.cloudflare.com/oauth2/auth?response_type=code&...

# Open this URL in your browser manually
# After auth, you'll get a code - paste it back in terminal
```

## Step-by-Step Deployment

### 1. Prepare Environment

```bash
cd /opt/muppy/appserver-sunray18/sunray_worker

# Ensure dependencies are installed
npm install

# Authenticate with Cloudflare
# For remote environments, use API token method above
# For local development:
wrangler login
```

### 2. Create KV Namespaces

KV namespaces are Cloudflare's key-value storage used for sessions, challenges, and config caching.

```bash
# Use the deployment script
./deploy.sh

# Select option 3: Create KV namespaces only
# This will:
# - Create production and preview namespaces
# - Update wrangler.toml with the namespace IDs
```

Alternatively, create manually:
```bash
# Create production namespaces
wrangler kv:namespace create "SESSIONS"
wrangler kv:namespace create "CHALLENGES"  
wrangler kv:namespace create "CONFIG_CACHE"

# Create preview namespaces (for wrangler dev)
wrangler kv:namespace create "SESSIONS" --preview
wrangler kv:namespace create "CHALLENGES" --preview
wrangler kv:namespace create "CONFIG_CACHE" --preview
```

### 3. Configure Secrets

Secrets are sensitive values that shouldn't be in code.

```bash
# Set the Admin API key (get from Sunray Server)
echo "YOUR_ADMIN_API_KEY" | wrangler secret put ADMIN_API_KEY

# Generate and set a session secret
openssl rand -base64 32 | wrangler secret put SESSION_SECRET
```

### 4. Update Production Configuration

Edit `wrangler.toml` for your production environment:

```toml
name = "sunray-worker"
main = "src/index.js"
compatibility_date = "2024-11-01"
workers_dev = false  # Change to false for production

# KV Namespaces (IDs will be updated by deploy.sh)
[[kv_namespaces]]
binding = "CONFIG_CACHE"
id = "YOUR_CONFIG_CACHE_ID"
preview_id = "YOUR_CONFIG_CACHE_PREVIEW_ID"

[[kv_namespaces]]
binding = "SESSIONS"
id = "YOUR_SESSIONS_ID"
preview_id = "YOUR_SESSIONS_PREVIEW_ID"

[[kv_namespaces]]
binding = "CHALLENGES"
id = "YOUR_CHALLENGES_ID"
preview_id = "YOUR_CHALLENGES_PREVIEW_ID"

# Environment variables
[vars]
ADMIN_API_ENDPOINT = "https://sunray-server-dev-cyril.pack8s.com"  # Your Sunray Server
RP_ID = "odoo18-cfed-test-g.pack8s.com"  # The protected domain
RP_NAME = "Sunray Authentication"
CACHE_TTL = "300"
SESSION_TTL = "86400"
CHALLENGE_TTL = "300"
WORKER_ID = "sunray-worker-001"

# Routes - CRITICAL: This makes the Worker intercept ALL requests
# IMPORTANT: Pattern must include leading asterisk (*subdomain.domain.com/*)
routes = [
  { pattern = "*odoo18-cfed-test-g.pack8s.com/*", zone_name = "pack8s.com" }
]
```

### 5. Deploy to Cloudflare

```bash
# Deploy the Worker
wrangler deploy

# Output will show:
# - Worker URL
# - Routes configured
# - KV namespaces bound
```

### 6. Configure Worker Route Manually (if needed)

If the route isn't automatically applied or the Worker isn't intercepting requests, configure it manually in the Cloudflare dashboard:

#### Via Cloudflare Dashboard:

1. **Log into Cloudflare Dashboard**
   - Go to https://dash.cloudflare.com
   - Select the account: `oursbleu`

2. **Navigate to the Zone**
   - Select the `pack8s.com` zone

3. **Configure Worker Route**
   - Go to **Workers Routes** (in the left sidebar)
   - Click **Add route**
   - Configure:
     - **Route**: `*odoo18-cfed-test-g.pack8s.com/*` (⚠️ Leading asterisk is REQUIRED)
     - **Worker**: Select `sunray-worker` from dropdown
     - **Zone**: `pack8s.com`
   - Click **Save**
   
   **Note about the leading asterisk**: 
   - `*odoo18-cfed-test-g.pack8s.com/*` = Protects the domain AND any subdomain variations (e.g., `admin-odoo18-cfed-test-g.pack8s.com`)
   - `odoo18-cfed-test-g.pack8s.com/*` = Protects ONLY the exact domain
   - Choose based on whether you want to protect subdomain variations

4. **Verify DNS Settings**
   - Go to **DNS** section
   - Ensure `odoo18-cfed-test-g` subdomain is:
     - Proxied (orange cloud icon)
     - Pointing to the correct origin server

### 7. Verify Deployment

```bash
# Monitor logs in real-time
wrangler tail --format pretty

# In another terminal, test the endpoints:

# Health check (should return JSON status)
curl https://odoo18-cfed-test-g.pack8s.com/sunray-wrkr/v1/health

# Setup page (should return HTML)
curl https://odoo18-cfed-test-g.pack8s.com/sunray-wrkr/v1/setup

# Protected path (should redirect to auth)
curl -I https://odoo18-cfed-test-g.pack8s.com/web
# Expected: 302 redirect to /sunray-wrkr/v1/auth?return_to=/web
```

## Configuration Reference

### Environment Variables (wrangler.toml)

| Variable | Description | Example |
|----------|-------------|---------|
| `ADMIN_API_ENDPOINT` | Sunray Server URL | `https://sunray-server.example.com` |
| `RP_ID` | Relying Party ID (domain) | `app.example.com` |
| `RP_NAME` | Display name for auth | `My App Authentication` |
| `CACHE_TTL` | Config cache TTL (seconds) | `300` |
| `SESSION_TTL` | Session duration (seconds) | `86400` (24 hours) |
| `CHALLENGE_TTL` | Auth challenge TTL (seconds) | `300` |
| `WORKER_ID` | Unique Worker identifier | `worker-prod-001` |

### Secrets (via wrangler secret)

| Secret | Description | How to Generate |
|--------|-------------|-----------------|
| `ADMIN_API_KEY` | API key for Sunray Server | Generate in Sunray Server UI |
| `SESSION_SECRET` | Cookie signing secret | `openssl rand -base64 32` |

### Route Patterns

Routes determine which requests the Worker intercepts:

```toml
# Single domain (CORRECT - with leading asterisk)
routes = [
  { pattern = "*app.example.com/*", zone_name = "example.com" }
]

# Multiple subdomains  
routes = [
  { pattern = "*.example.com/*", zone_name = "example.com" }
]

# Specific paths only
routes = [
  { pattern = "*example.com/protected/*", zone_name = "example.com" }
]
```

**Understanding Route Patterns**:

The leading asterisk (*) is a wildcard for subdomain variations:
- `subdomain.domain.com/*` = Protects ONLY `subdomain.domain.com`
- `*subdomain.domain.com/*` = Protects `subdomain.domain.com` AND variations like `admin-subdomain.domain.com`, `api-subdomain.domain.com`, etc.
- `*.domain.com/*` = Protects ALL subdomains of domain.com

Choose your pattern based on your security needs:
- Use exact domain (no leading *) if you want to protect only one specific domain
- Use wildcard (with leading *) if you want to protect multiple related subdomains

## Testing Guide

### 1. Test Authentication Flow

```bash
# 1. Generate a setup token in Sunray Server
bin/sunray-srvr cli sunray.user.create_setup_token \
  --username testuser \
  --email test@example.com \
  --host_id 1

# 2. Visit setup page in browser
https://odoo18-cfed-test-g.pack8s.com/sunray-wrkr/v1/setup

# 3. Enter username and token
# 4. Register passkey
# 5. Test login at /sunray-wrkr/v1/auth
```

### 2. Test Access Control

```bash
# Test CIDR bypass (if configured)
curl -H "CF-Connecting-IP: 10.0.0.1" https://protected.example.com/

# Test public URL pattern
curl https://protected.example.com/public/health

# Test webhook token
curl -H "X-Webhook-Token: YOUR_TOKEN" https://protected.example.com/webhook/
```

### 3. Monitor Worker

```bash
# Real-time logs
wrangler tail --format pretty

# Check KV storage
wrangler kv:key list --binding SESSIONS
wrangler kv:key list --binding CONFIG_CACHE
```

## Troubleshooting

### Common Issues

#### Worker Not Intercepting Requests

**Symptom**: Requests go directly to origin, bypassing Worker

**Solution**: 
- Verify route pattern in wrangler.toml
- Check Cloudflare dashboard → Workers → Routes
- Ensure domain is proxied (orange cloud) in DNS

#### Authentication Redirect Loop

**Symptom**: Continuous redirects between app and auth page

**Solution**:
- Check session cookie domain/path settings
- Verify RP_ID matches the domain
- Check browser console for cookie errors

#### Config Not Loading

**Symptom**: Worker returns 503 Service Unavailable

**Solution**:
- Verify ADMIN_API_KEY is correct
- Check ADMIN_API_ENDPOINT is accessible
- Look for errors in `wrangler tail`
- Test API directly: `curl -H "Authorization: Bearer API_KEY" ENDPOINT/sunray-srvr/v1/config`

#### Session Not Persisting

**Symptom**: User must re-authenticate frequently

**Solution**:
- Check SESSION_TTL value
- Verify SESSION_SECRET is set
- Check KV namespace bindings
- Look for session errors in logs

### Debug Commands

```bash
# View Worker configuration
wrangler whoami
wrangler deployments list

# Check KV namespaces
wrangler kv:namespace list

# View specific KV keys
wrangler kv:key get --binding SESSIONS "session_id"

# View secrets (names only, not values)
wrangler secret list

# Test from command line with specific IP
curl -H "CF-Connecting-IP: 192.168.1.1" https://protected.example.com/

# Force config refresh
curl -X POST https://protected.example.com/sunray-wrkr/v1/cache/invalidate \
  -H "Authorization: Bearer ADMIN_API_KEY"
```

## Production Checklist

### Before Deployment

- [ ] Cloudflare account has access to target zone
- [ ] Admin API key generated in Sunray Server
- [ ] Target domain is proxied through Cloudflare (orange cloud)
- [ ] Backend server URL configured in Sunray Server
- [ ] Test environment working with local wrangler dev

### During Deployment

- [ ] KV namespaces created and IDs in wrangler.toml
- [ ] Secrets configured (ADMIN_API_KEY, SESSION_SECRET)
- [ ] Route pattern correctly targets protected domain(s)
- [ ] RP_ID matches the protected domain
- [ ] ADMIN_API_ENDPOINT points to Sunray Server

### After Deployment

- [ ] Health endpoint responding: `/sunray-wrkr/v1/health`
- [ ] Setup page loads: `/sunray-wrkr/v1/setup`
- [ ] Protected paths redirect to auth when not authenticated
- [ ] Config loads from Sunray Server (check logs)
- [ ] Test user can register passkey and authenticate
- [ ] Session persists across requests
- [ ] Monitoring enabled with `wrangler tail`

## Security Considerations

1. **Always use HTTPS** for ADMIN_API_ENDPOINT
2. **Rotate secrets regularly** (SESSION_SECRET, ADMIN_API_KEY)
3. **Monitor logs** for suspicious authentication attempts
4. **Configure rate limiting** in Cloudflare if needed
5. **Keep Worker code updated** with security patches
6. **Review access logs** in Sunray Server regularly
7. **Test bypass rules** carefully (CIDR, public URLs)

## Support

For issues or questions:
1. Check Worker logs: `wrangler tail`
2. Review Sunray Server logs
3. Consult main documentation in project root
4. Check Cloudflare Worker documentation