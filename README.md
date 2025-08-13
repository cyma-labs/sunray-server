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

```bash
# Run Worker tests locally
cd sunray_worker
npm test

# Test with local Odoo server
bin/sunray-srvr --test-enable -u sunray_core

# End-to-end testing
npm run test:e2e
```

## 🛟 Support

- Check [CLAUDE.md](CLAUDE.md) for development guidelines
- Report issues at GitHub Issues
- See `.claude.local.md` for environment-specific configuration (not in repo)

## 📄 License

MIT - Designed to be forked, adapted, and improved.

---

**Note**: This is the transition from ED25519 signatures to WebAuthn/Passkeys. The Chrome Extension mentioned in old docs has been replaced by native passkey support.