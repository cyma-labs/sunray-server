# Sunray Web Zero Trust

**Sunray** is a comprehensive and affordable Web/HTTP Zero Trust access solution that combines enterprise-grade security with unprecedented deployment flexibility and ease of use. 

Designed to protect web applications and APIs from all types of attacks—especially zero-day exploits—Sunray implements a unique distributed architecture where a secure, self-hosted server manages all access policies while lightweight edge workers enforce protection at the network edge. 

This approach delivers passwordless access control via WebAuthn, requires zero modification to existing applications, remains accessible to small teams, and offers complete sovereignty over your security infrastructure—all while maintaining the transparency of open source software.

---

### Why Choose Sunray?

• **Security-first protection** is at the heart of Sunray's design. The system has been specifically engineered to defend web sites and applications from all kinds of attacks, with particular strength against zero-day exploits and emerging threats. By integrating multiple layers of security controls and real-time threat detection, Sunray provides robust protection that adapts to the evolving threat landscape.

• **API and webhook compatibility** makes Sunray an ideal solution for modern, automated environments. Whether you're protecting human-accessible web applications or machine-to-machine communications, Sunray seamlessly handles API calls, webhooks, and automated services while maintaining the same high security standards across all types of traffic.

• **WebAuthn and Passkeys integration** delivers both exceptional security and outstanding user experience. Users must prove their identity using biometric data (fingerprint, face recognition, etc.) or hardware security keys to reach protected applications, eliminating passwords while providing stronger access control than traditional methods. This modern approach reduces the risk of credential-based attacks while making access faster and more convenient for legitimate users.

• **Zero modification deployment** means Sunray protects your existing applications without requiring any code changes, configuration updates, or architectural modifications to your hosts or web applications. Your applications continue to operate exactly as they always have, while Sunray transparently provides comprehensive security at the network edge.

• **Small team friendly** architecture ensures that organizations with limited IT resources can deploy and maintain enterprise-grade security. Sunray's intuitive management interface, automated security policies, and straightforward deployment process make it accessible to teams that need powerful protection without complex administration overhead.

• **Open source transparency** gives you complete visibility into how your security system works, enabling security audits, custom modifications, and community-driven enhancements. The open source model also ensures you're never locked into a proprietary solution and can adapt the system to meet your specific requirements.

• **Distributed architecture** separates management from enforcement for maximum security and flexibility. The Sunray Server handles all management, policy decisions, and audit functions while remaining safely isolated from the public internet. Sunray Workers, deployed at network edges, enforce access decisions and handle the direct interaction with users and potential threats, creating a secure and scalable protection system.

• **Complete sovereignty and deployment flexibility** ensures you maintain total control over your security infrastructure while choosing the optimal deployment strategy for your needs. The Sunray Server remains entirely under your control, never exposed to the internet, giving you complete data sovereignty and compliance capability. For the worker layer, you can choose the deployment that best matches your requirements:
  - **Maximum performance and security**: Deploy the Sunray Worker for Cloudflare to leverage global edge infrastructure, DDoS protection, and minimal latency
  - **Total sovereignty**: Deploy the Sunray Worker for Kubernetes to maintain complete control over every component while still benefiting from enterprise-grade security

This dual approach means you never have to compromise between sovereignty, performance, and security - you can optimize for your specific regulatory, compliance, and operational requirements.

## ✨ Key Features

- 🛡️ **Zero Trust Architecture**: Default deny with granular access control - no user or system is trusted by default
- 🚫 **Advanced Attack Protection**: Guards against zero-day exploits, injection attacks, and emerging web threats
- 🔐 **WebAuthn/Passkeys**: Passwordless biometric authentication for maximum security and user convenience
- 📱 **Remote Authentication**: Authenticate from any device using mobile passkey - perfect for shared computers (Advanced feature)
- 🔌 **API & Webhook Ready**: Seamless protection for automated systems, microservices, and machine-to-machine communications
- 📦 **Zero Modification Required**: Protect existing applications without any code changes or architectural modifications
- 👥 **Small Team Friendly**: Intuitive management interface designed for teams with limited IT resources
- 🔍 **Comprehensive Audit Trail**: Complete visibility into access attempts, security events, and user activities
- 🌐 **Multi-Platform Workers**: Support for Cloudflare, Kubernetes, and future edge computing platforms
- 🎛️ **Centralized Management**: Odoo 18-based admin interface for unified user, policy, and host management
- ⚡ **High Performance**: Lightweight workers with minimal latency impact on protected applications
- 🤖 **Intelligent Worker Management**: Auto-registration, health monitoring, and zero-downtime migration
- 🔄 **Zero-Downtime Migration**: Controlled worker replacement without service interruption
- 🛡️ **WAF Bypass for Authenticated Users**: Reduced friction for legitimate users while maintaining security

## 🏗️ Architecture

### Security-First Design
Sunray's architecture prioritizes security through complete separation of concerns and network isolation:

**🔒 Sunray Server (Never Internet-Exposed)**
- **Complete network isolation**: Server never directly faces the public internet, eliminating entire classes of attacks
- **Centralized management**: User administration, policy configuration, and audit reporting through secure Odoo 18 interface
- **Policy evaluation engine**: All access control decisions, WebAuthn/Passkeys validation, and security rule processing
- **Audit and compliance**: Comprehensive logging and monitoring of all access attempts and security events
- **Session orchestration**: Secure session management and token validation for authenticated users

**🛡️ Sunray Workers (Edge Protection)**
- **Frontline defense**: Deployed at network edges to intercept and evaluate all incoming requests
- **Attack mitigation**: First line of defense against malicious traffic, DDoS attacks, and exploit attempts
- **Platform adaptation**: Translate platform-specific requests (Cloudflare, Kubernetes, etc.) to universal server API calls
- **Real-time enforcement**: Execute access control decisions with minimal latency impact
- **Threat intelligence**: Continuous monitoring and reporting of attack patterns to the server
- **Intelligent management**: Auto-registration, health monitoring, and zero-downtime replacement capabilities

### Communication Flow
```
Internet Traffic → Worker (Edge) → Server API (Internal) → Policy Decision → Worker → Protected App
```

- **Unidirectional communication**: Workers always initiate communication with the server, never the reverse
- **API-driven**: All interactions use well-defined REST APIs with comprehensive validation
- **Stateless workers**: Workers maintain no sensitive state, relying entirely on server-side policy decisions
- **Encrypted channels**: All worker-server communications use secure, authenticated connections

### Deployment Flexibility
**Current Implementations:**
- [inouk-sunray-worker-cloudflare](https://gitlab.com/cmorisse/inouk-sunray-worker-cloudflare) - Cloudflare Workers (Production Ready)
- [inouk-sunray-worker-k8s](https://gitlab.com/cmorisse/inouk-sunray-worker-k8s) - Kubernetes / Traefik ForwardAuth (Coming Soon)

**Future Platforms:**
- Traefik ForwardAuth middleware  
- NGINX auth_request module
- Istio service mesh integration
- AWS Lambda@Edge functions
- Azure Front Door integration

## 📂 Project Structure

```
inouk-sunray-server/
├── project_addons/            # Odoo 18 addons (ikb standard)
│   └── sunray_core/           # Core authentication addon
├── docs/                      # Documentation and specifications
├── config/                    # Configuration examples
├── schema/                    # JSON Schema validation
├── bin/                       # Executable scripts
│   ├── sunray-srvr            # Odoo launcher script
│   ├── test_server.sh         # Internal Odoo test runner
│   └── test_rest_api.sh       # External REST API tester
└── etc/                       # Configuration files
```

## 🚀 Quick Start

### Prerequisites

- Node.js 20.x and npm 10.x
- Python 3.10+
- PostgreSQL 14+
- Domain for protected services

### Installation

1. **Clone the repository**
   ```bash
   git clone https://gitlab.com/cmorisse/inouk-sunray-server.git
   cd inouk-sunray-server
   ```

2. **Install system dependencies**
   ```bash
   # Install Odoo 18 system dependencies (requires sudo)
   sudo ./.muppy/scripts/mpy_install_500_odoo18_deps.sh

   # Install ikb (inouk buildit) - run WITHOUT sudo
   ./.muppy/scripts/mpy_install_510_ikb.sh
   ```

   See [.muppy/scripts/README.md](.muppy/scripts/README.md) for detailed installation documentation.

3. **Install Python dependencies**
   ```bash
   # Python dependencies for Sunray Server
   ikb install  # Processes buildit.json and requirements.txt
   ```

4. **Start Sunray Server**
   ```bash
   # Install sunray_core addon
   bin/sunray-srvr -i sunray_core

   # Start server
   bin/sunray-srvr
   ```

5. **Generate API key for workers**
   ```bash
   bin/sunray-srvr srctl apikey create Worker_API_Key --sr-worker
   ```

6. **Deploy a worker**
   Choose and deploy a worker implementation:
   - [Cloudflare Workers Setup](https://gitlab.com/cmorisse/inouk-sunray-worker-cloudflare)
   - Kubernetes ForwardAuth (coming soon)

## 🔧 Development

The Sunray Server is built as an Odoo 18 addon, leveraging the robust framework capabilities of Odoo for user management, API development, and administrative interfaces. This means developing for Sunray Server follows standard Odoo development practices and workflows.

### Sunray Server Development

```bash
# Start server in development mode
bin/sunray-srvr --dev=all

# Update modules
bin/sunray-srvr -u sunray_core

# Run server tests
bin/test_server.sh
bin/test_server.sh --test TestAccessRules  # Specific test class
bin/test_server.sh --coverage --verbose    # With coverage
```

### Sunray CLI (srctl)

Manage Sunray objects via command line:

```bash
# Core object management
bin/sunray-srvr srctl apikey list
bin/sunray-srvr srctl user create "username" --sr-email "user@example.com"
bin/sunray-srvr srctl setuptoken create "username" --sr-device "laptop" --sr-hours 24

# Worker management
bin/sunray-srvr srctl worker list                    # List all workers
bin/sunray-srvr srctl worker get worker-name         # Get worker details

# Host-worker binding and migration
bin/sunray-srvr srctl host set-pending-worker app.example.com new-worker-001
bin/sunray-srvr srctl host migration-status app.example.com
bin/sunray-srvr srctl host list-pending-migrations
bin/sunray-srvr srctl host clear-pending-worker app.example.com
```

## 🔐 Security Model

- **Default Locked**: All resources protected by default
- **Access Rules System**: Priority-based rule evaluation
  - **Public Access**: No authentication required
  - **CIDR Access**: IP address/range whitelist
  - **Token Access**: API/webhook token authentication
- **WebAuthn/Passkeys**: Primary authentication method
- **Remote Authentication**: Mobile device authentication for shared/untrusted computers (Advanced)
- **Session Management**: Secure cookies with configurable TTL
  - Normal sessions: Standard TTL (default 8h)
  - Remote sessions: Shorter TTL for untrusted devices (default 1h)
- **WAF Bypass**: Authenticated users can bypass WAF rules for improved performance
- **Worker Security**: Auto-registration with comprehensive audit trails

## 📡 API Documentation

The server provides a comprehensive REST API at `/sunray-srvr/v1/*`:

See [API_CONTRACT.md](./docs/API_CONTRACT.md) for complete API specification.

## 🧪 Testing

### Internal Tests (Unit/Integration)
```bash
# Run all server tests with comprehensive reporting
bin/test_server.sh

# Run specific test class
bin/test_server.sh --test TestAccessRules

# Full test run with coverage
bin/test_server.sh --coverage --verbose

# List all available test classes
bin/test_server.sh --list-tests
```

### External API Tests
```bash
# Test REST API endpoints (simulates Worker-Server communication)
export SUNRAY_API_URL="https://sunray.example.com"
export SUNRAY_API_KEY="your-api-key-here"
bin/test_rest_api.sh

# Run specific endpoint test
bin/test_rest_api.sh --url https://sunray.example.com --key YOUR_KEY --test config

# List all available API tests
bin/test_rest_api.sh --list-tests
```

## 🐳 Docker

```bash
# Build server image
bin/docker-build-srvr.sh

# Run server in container
docker run -e IKB_ODOO_ADMIN_PASSWORD="admin" -it sunray-srvr18:latest
```
## 

## 📚 Documentation

### Core Documentation
- [CLAUDE.md](./CLAUDE.md) - Complete development guide
- [API_CONTRACT.md](./docs/API_CONTRACT.md) - API specification for workers
- [Sunray Introduction](./docs/sunray_introduction.md) - System overview and concepts

### Deployment & Security
- [Sunray Deployment Security](./docs/sunray_deployment_security.md) - Production security hardening guide

### Feature Guides
- [Worker Management and Migration](./docs/worker_management_and_migration.md) - Complete worker lifecycle guide
- [WAF Bypass Guide](./docs/waf_bypass_guide.md) - Enhanced security for authenticated users


## 🤝 Contributing

1. Ensure server API changes are backward compatible
2. Update docs/API_CONTRACT.md for any API changes
3. Test with multiple worker implementations
4. Run comprehensive test suite before submitting

## 📄 License

Sunray Server is **dual-licensed** :

| Addon | Tier | License |
|-------|------|---------|
| `project_addons/sunray_core/` | Free | **FSL-1.1-Apache-2.0** (Functional Source License v1.1, converts to Apache 2.0 on the 2nd anniversary of each release) |
| `project_addons_advanced/sunray_advanced_core/` | Sunray Enterprise (paid) | **Elastic License 2.0** (perpetual source-available) |

Both licenses **forbid third parties from offering Sunray as a hosted or managed service** without a commercial agreement with oursbl.eu. Sunray Enterprise additionally requires an active commercial subscription (9€/month for 20 users + 1€/user above) — billing is currently inactive during beta.

See [LICENSE](LICENSE), [LICENSES/FSL-1.1-Apache-2.0.txt](LICENSES/FSL-1.1-Apache-2.0.txt), [LICENSES/ELv2.txt](LICENSES/ELv2.txt), and [docs/licensing_decision.md](docs/licensing_decision.md) for full terms and context.

**IP:** Cyril MORISSE · **Distribution:** oursbl.eu · **Partner model:** no white-label, partners purchase licenses at standard rates and resell their own hosting service with their own margin.

> ⚠️ This README still contains pre-2026-05-08 commercial wording (e.g. "Open Source"). The repository's source of truth is now [`sunray_ssot.md`](../sunray_ssot.md) ; this README will be regenerated from the SSOT.

---

**Note**: This is the server component of the Sunray ecosystem. For edge workers, see the respective worker repositories listed above.