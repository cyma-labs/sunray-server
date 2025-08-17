# Muppy Sunray

**Muppy Sunray** is a lightweight, secure, self-hosted solution for authorizing HTTP access to private cloud services without VPN or fixed IPs. The project integrates with Cloudflare's infrastructure to provide enterprise-grade security at a fraction of traditional costs.

## ✨ Key Features

- 🔐 **WebAuthn/Passkeys**: Passwordless authentication using biometrics
- 🌐 **Cloudflare Worker**: Edge authentication and request routing
- 🎛️ **Odoo 18 Admin Interface**: Centralized user and host management
- 🔒 **Zero Trust Security**: Default deny, whitelist exceptions only
- 📊 **Audit Logging**: Complete authentication and access trails

## 📂 Project Structure

```
.
├── sunray_worker/             # Cloudflare Worker
│   ├── src/                   # Worker source code
│   └── wrangler.toml          # Cloudflare configuration
├── sunray_server/             # Odoo 18 addons
│   └── sunray_core/           # Core authentication addon
├── demo-app/                  # Demo protected application
├── docs/                      # Documentation
├── config/                    # Configuration examples
├── schema/                    # JSON Schema validation
└── README.md
```

## 🚀 Quick Start

### Prerequisites

- Node.js 20.x and npm 10.x
- Python 3.10+
- PostgreSQL 14+
- Cloudflare account
- Domain managed by Cloudflare

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd appserver-sunray18
   ```

2. **Install dependencies**
   ```bash
   # Node.js dependencies for Worker
   cd sunray_worker && npm install
   
   # Python dependencies for Sunray Server
   ikb install  # Processes buildit.json and requirements.txt
   ```

3. **Configure Sunray Server**
   ```bash
   # Install sunray_core addon
   bin/sunray-srvr -i sunray_core
   
   # Generate API key for Worker
   bin/sunray-srvr srctl apikey create Worker_API_Key --sr-worker
   ```

4. **Deploy Worker to Cloudflare**
   ```bash
   cd sunray_worker
   wrangler deploy
   ```

## 🔧 Cloudflared Tunnel Setup

Cloudflared tunnels provide secure access to your Sunray Server without exposing it to the public internet.

### Installation

```bash
# Download and install cloudflared
curl -L --output cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared.deb

# Verify installation
cloudflared --version
```

### Authentication

```bash
# Login to Cloudflare (one-time setup)
cloudflared tunnel login
...
Leave cloudflared running to download the cert automatically.
2025-08-11T13:18:31Z INF You have successfully logged in.
If you wish to copy your credentials to a server, they have been saved to:
/home/muppy/.cloudflared/cert.pem
```

### Create and Configure Tunnel

```bash
# Create a named tunnel
cloudflared tunnel create sunray-server-dev-cyril

# Create configuration file
cat > ~/.cloudflared/config.yml << EOF
tunnel: sunray-server
credentials-file: /home/$USER/.cloudflared/<tunnel-id>.json

ingress:
  - hostname: sr-srvr-dev-cyril.pack8s.com
    service: http://localhost:8069
    originRequest:
      noTLSVerify: true
  - service: http_status:404
EOF
```

### Run the Tunnel

```bash
# Test the tunnel
cloudflared tunnel run sunray-server

# Or run with quick tunnel (for testing)
cloudflared tunnel --url http://localhost:8069

# Run as a service (production)
sudo cloudflared service install
sudo systemctl start cloudflared
sudo systemctl enable cloudflared
```

### Configure DNS

In Cloudflare Dashboard:
1. Go to DNS settings for your domain
2. Add CNAME record:
   - Name: `sr-srvr-dev-cyril`
   - Target: `<tunnel-id>.cfargotunnel.com`
   - Proxy: Enabled (orange cloud)

### Security Configuration

Apply WAF rules in Cloudflare Dashboard to restrict access:

```
# Example: Block all traffic except from trusted IPs
(http.host eq "sunray-servrr-dev-cyril.pack8s.com" 
 and not ip.src in { 
   178.170.1.44 
   147.79.118.98 
   5.135.178.38 
   5.250.182.225 
   162.19.69.75 
 })
Action: Block
```

### Monitoring

```bash
# View tunnel status
cloudflared tunnel list

# View tunnel info
cloudflared tunnel info sunray-server

# View tunnel metrics
cloudflared tunnel metrics sunray-server
```

## 🔐 Security Considerations

### Change Default Credentials

**CRITICAL**: Before exposing any service, change default admin credentials:

```bash
# Via Odoo CLI
bin/sunray-srvr shell
>>> admin = env['res.users'].search([('login', '=', 'admin')])
>>> admin.password = 'your-secure-password-here'
>>> env.cr.commit()
```

### Firewall Rules

1. **API Access**: Restrict `/sunray-srvr/v1/*` endpoints to Cloudflare Workers only
2. **Admin Access**: Use internal URLs or restrict to trusted IPs
3. **Protected Hosts**: All traffic must go through Worker authentication

## 📚 Documentation

- [Architecture Overview](docs/architecture.md)
- [API Documentation](docs/api.md)
- [Security Model](docs/security.md)
- [Deployment Guide](docs/deployment.md)

## 🧪 Testing

Sunray includes comprehensive test suites for both server (Odoo) and worker (Cloudflare) components with dedicated test scripts for easy execution.

### Prerequisites

- **Database**: PostgreSQL with test database access
- **Node.js**: Version 20.x for worker tests  
- **Environment**: All required environment variables configured
- **Dependencies**: `npm install` completed in `sunray_worker/`

### Quick Start

```bash
# Run server tests (Odoo/Python)
./test_server.sh

# Run worker tests (Vitest/Node.js)
./test_worker.sh

# Run both with coverage
./test_server.sh --coverage && ./test_worker.sh --coverage
```

### Server Tests (Odoo)

The `test_server.sh` script provides comprehensive testing for the Sunray Server (Odoo addon):

#### Basic Usage
```bash
# Run sunray_core tests (default)
./test_server.sh

# Run with verbose debug output
./test_server.sh --verbose

# Run all module tests
./test_server.sh --full

# Generate coverage report  
./test_server.sh --coverage
```

#### Advanced Options
```bash
# Clean database before testing
./test_server.sh --clean

# Run specific test class
./test_server.sh --test TestCacheInvalidation

# Run specific test method
./test_server.sh --test TestWebhookToken --method test_token_creation

# Stop on first failure
./test_server.sh --stop-on-fail

# List available tests
./test_server.sh --list-tests
```

#### Test Categories
- **Multi-provider webhook tokens**: Authentication for Shopify, Stripe, GitHub webhooks
- **Cache invalidation**: Version tracking and worker synchronization
- **User management**: WebAuthn passkey registration and validation
- **Host configuration**: Protected resource management
- **Audit logging**: Security event tracking and compliance

### Worker Tests (Vitest)

The `test_worker.sh` script provides testing for the Cloudflare Worker components:

#### Basic Usage
```bash
# Run all tests once
./test_worker.sh

# Development watch mode (auto-rerun on changes)
./test_worker.sh --watch

# Generate coverage report
./test_worker.sh --coverage

# Run with visual UI
./test_worker.sh --ui
```

#### Advanced Options
```bash
# Run specific test file
./test_worker.sh cache.test.js

# Verbose output with debug info
./test_worker.sh --verbose

# Stop on first failure
./test_worker.sh --bail

# Environment validation only
./test_worker.sh --check-env

# List available tests
./test_worker.sh --list-tests
```

#### Test Categories
- **Cache management**: Configuration caching and invalidation
- **Token extraction**: Multi-provider webhook authentication
- **Session handling**: WebAuthn session management
- **Request routing**: Protected resource access control

### Test Output and Logs

Both scripts generate detailed logs and reports:

```bash
# Logs are saved to
./test_logs/
├── server_test_20250817_094512.log
├── worker_test_20250817_094630.log
└── ...

# Coverage reports in  
./coverage/
├── server_coverage_20250817_094512.html
├── worker_coverage_20250817_094630/
└── ...
```

### Continuous Integration

For CI/CD pipelines, use the scripts with appropriate flags:

```yaml
# GitHub Actions example
- name: Test Server
  run: ./test_server.sh --coverage --stop-on-fail

- name: Test Worker  
  run: ./test_worker.sh --coverage --bail
```

### Troubleshooting

#### Common Issues

**Server Tests Failing**:
```bash
# Check database connection
bin/sunray-srvr --help

# Verify addon installation
bin/sunray-srvr -i sunray_core --stop-after-init

# Clean test with fresh database
./test_server.sh --clean --verbose
```

**Worker Tests Failing**:
```bash
# Verify Node.js version
node --version  # Should be 20.x

# Check dependencies
./test_worker.sh --check-env

# Reinstall dependencies
cd sunray_worker && rm -rf node_modules && npm install
```

**Database Constraint Errors**:
These are often expected validation tests. Look for:
- `ERREUR: la nouvelle ligne de la relation « sunray_webhook_token » viole la contrainte`
- These prove our validation logic is working correctly

### Performance Benchmarks

Test execution times on typical development machine:
- **Server tests**: ~10 seconds (32 tests)
- **Worker tests**: ~2 seconds (15+ tests)  
- **Coverage generation**: Additional ~5 seconds each

### Test Development

When adding new tests:

**Server (Python/Odoo)**:
- Place in `sunray_server/sunray_core/tests/`
- Follow pattern: `test_feature_name.py`
- Extend `TransactionCase` for database tests
- Import in `tests/__init__.py`

**Worker (JavaScript/Vitest)**:
- Place in `sunray_worker/src/`
- Follow pattern: `feature.test.js`
- Use Vitest API: `describe()`, `test()`, `expect()`
- Mock Cloudflare Worker APIs as needed

## 🛟 Support

- Check [CLAUDE.md](CLAUDE.md) for development guidelines
- Report issues at GitHub Issues
- See `.claude.local.md` for environment-specific configuration (not in repo)

## 🚧 TODOs

### KV Namespace Creation Documentation
The following Cloudflare KV namespaces need to be created for the Worker:
- `SESSIONS` - Store user session data
- `CHALLENGES` - Store WebAuthn challenges
- `CONFIG_CACHE` - Cache configuration from server
- `CONTROL_SIGNALS` - Cache invalidation signals

Use `./sunray_worker/deploy.sh` option 3 to create all namespaces automatically.

**Note**: KV cache refresh delays are defined by Cloudflare (60s all Tiers)

## 📄 License

MIT - Designed to be forked, adapted, and improved.

---

**Note**: This is the transition from ED25519 signatures to WebAuthn/Passkeys. The Chrome Extension mentioned in old docs has been replaced by native passkey support.