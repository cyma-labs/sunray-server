# Sunray Worker

Cloudflare Worker for Sunray authentication system using WebAuthn/Passkeys.

## Features

- WebAuthn/Passkey authentication
- JWT-based session management
- CIDR-based IP whitelisting
- Public URL pattern matching
- Webhook token authentication
- CSRF protection
- Device fingerprinting

## Setup

### 1. Install Dependencies

```bash
npm install
```

### 2. Configure Wrangler

Edit `wrangler.toml` and set your Cloudflare account ID and zone ID:

```toml
account_id = "your-account-id"
route = { pattern = "*.yourdomain.com/*", zone_id = "your-zone-id" }
```

### 3. Create KV Namespaces

```bash
# Create production namespaces
wrangler kv:namespace create "SESSIONS"
wrangler kv:namespace create "CHALLENGES"
wrangler kv:namespace create "CONFIG_CACHE"

# Create preview namespaces for development
wrangler kv:namespace create "SESSIONS" --preview
wrangler kv:namespace create "CHALLENGES" --preview
wrangler kv:namespace create "CONFIG_CACHE" --preview
```

Update the IDs in `wrangler.toml` with the output from these commands.

### 4. Set Secrets

```bash
# Generate session secret
openssl rand -base64 32

# Set secrets
wrangler secret put SESSION_SECRET
wrangler secret put ADMIN_API_KEY
```

### 5. Deploy

```bash
# Development
npm run dev

# Production
npm run deploy
```

## Environment Variables

### Required Secrets
- `SESSION_SECRET`: Secret key for signing JWT sessions
- `ADMIN_API_KEY`: API key for communicating with Sunray Server

### Configuration Variables
- `ADMIN_API_ENDPOINT`: URL of the Sunray Server
- `RP_ID`: Relying Party ID for WebAuthn (usually your domain)
- `RP_NAME`: Display name for WebAuthn prompts
- `WORKER_ID`: Unique identifier for this worker instance
- `SESSION_TTL`: Session lifetime in seconds (default: 86400)
- `CHALLENGE_TTL`: Challenge lifetime in seconds (default: 300)

## API Endpoints

### Public Endpoints

#### GET /sunray-wrkr/v1/setup
Display passkey registration page for new users.

#### POST /sunray-wrkr/v1/setup/validate
Validate setup token before passkey registration.

#### POST /sunray-wrkr/v1/setup/register
Complete passkey registration process.

#### GET /sunray-wrkr/v1/auth
Display authentication page.

#### POST /sunray-wrkr/v1/auth/challenge
Get WebAuthn authentication challenge.

#### POST /sunray-wrkr/v1/auth/verify
Verify passkey and create session.

#### GET /sunray-wrkr/v1/auth/logout
Terminate session and clear cookies.

### Protected Resources

All other URLs are protected and require:
1. Valid session cookie, OR
2. IP address in CIDR whitelist, OR
3. URL matching public patterns, OR
4. Valid webhook token

## Development

### Local Testing

```bash
# Run development server
npm run dev

# The worker will be available at http://localhost:8787
```

### Running Tests

```bash
npm test
```

### Debugging

```bash
# View live logs
wrangler tail

# View KV storage
wrangler kv:key list --namespace-id=<namespace-id>
```

## Security Considerations

1. **Session Security**: Sessions are signed JWTs with HMAC-SHA256
2. **CSRF Protection**: Double-submit cookie pattern
3. **Device Binding**: Optional device fingerprinting
4. **Challenge Expiry**: Short-lived challenges (5 minutes)
5. **Session Expiry**: Configurable session lifetime
6. **Secure Cookies**: HttpOnly, Secure, SameSite=Strict

## Integration with Sunray Server

The Worker communicates with Sunray Server (Odoo) for:
- Configuration synchronization
- Token validation
- Passkey registration
- Session reporting
- Audit logging

## Troubleshooting

### Worker not intercepting requests
- Check route configuration in `wrangler.toml`
- Verify DNS is proxied through Cloudflare
- Check Worker is deployed and active

### Authentication failures
- Verify `ADMIN_API_KEY` is correct
- Check `ADMIN_API_ENDPOINT` is accessible
- Review Worker logs with `wrangler tail`

### Session issues
- Verify `SESSION_SECRET` is set
- Check KV namespace bindings
- Review cookie settings for domain

## License

LGPL-3.0