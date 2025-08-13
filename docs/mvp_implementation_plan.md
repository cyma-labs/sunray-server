# Sunray MVP Implementation Plan

## 🎯 MVP Scope Definition

### **Core MVP Goal**
Build a working demonstration of Sunray that shows:
- A user can protect a website with passkey authentication
- Admin can manage users and configure access via Odoo interface  
- System works end-to-end with real WebAuthn passkeys
- Basic security exceptions (CIDR, public URLs, token auth) function

### **MVP Features (In Scope)**

#### **Sunray Worker (Free Edition Only)**
✅ **Authentication Core:**
- WebAuthn passkey registration and authentication
- Session management with secure cookies
- Basic request proxying to backend

✅ **Access Control Core:**
- CIDR bypass (office networks)
- Public URL patterns (static content)
- Token URL patterns (webhooks)
- Default passkey requirement

✅ **User Journey Core:**
- Setup page for new users
- Login page for existing users  
- Basic error handling and user feedback

#### **Admin Server Core**
✅ **User Management:**
- User CRUD operations
- Passkey registration tracking
- Setup token generation (manual)

✅ **Host Configuration:**
- Domain configuration with backend URLs
- Access control pattern configuration
- Basic webhook token management

✅ **API Endpoints:**
- Worker configuration retrieval
- User existence checks
- Passkey registration/validation
- Emergency cache invalidation

✅ **Security Incident Response:**
- Emergency user deactivation
- Session invalidation for compromised users
- Cache reset triggers (global and per-user)
- Audit logging for security events

#### **MVP Demo Environment**
✅ **Protected Application:**
- Simple demo web app (HTML/JS)
- Mix of public and protected pages
- API endpoints for webhook testing

✅ **Infrastructure:**
- Single Cloudflare Worker deployment
- Single Odoo instance with addon
- Basic monitoring and logs

### **MVP Features (Out of Scope)**
❌ **Advanced Edition Features:**
- Rate limiting
- Advanced session policies  
- MFA requirements
- Security alerts
- Advanced monitoring

❌ **Production Features:**
- Automated deployment
- Backup/recovery
- High availability
- Performance optimization

❌ **Business Features:**
- Billing integration
- Usage tracking
- Customer onboarding automation
- Support ticketing

## 🏗️ MVP Technical Architecture

### **Component Dependencies**
```
Admin Server (Odoo) → Worker → Demo App
     ↓                 ↓
   Database         Cloudflare KV
```

### **MVP API Contracts**

#### **Worker Internal Endpoints (Browser → Worker)**
```
POST /sunray-wrkr/v1/setup/validate
- Body: {username, token}
- Returns: {valid: boolean}
- Purpose: Validate setup token from browser

POST /sunray-wrkr/v1/setup/register
- Body: {username, step: 'options'|'verify', credential?}
- Returns: WebAuthn options or success status
- Purpose: WebAuthn registration flow

POST /sunray-wrkr/v1/auth/challenge
- Body: {}
- Returns: WebAuthn authentication options
- Purpose: Start passkey authentication

POST /sunray-wrkr/v1/auth/verify
- Body: {credential}
- Returns: {success: boolean}
- Purpose: Verify passkey and create session

POST /sunray-wrkr/v1/auth/logout
- Body: {}
- Returns: {success: boolean}
- Purpose: Clear session cookie

POST /sunray-wrkr/v1/admin/cache/invalidate
- Body: {scope, target?}
- Returns: {success: boolean}
- Auth: Admin API key required
- Purpose: Force cache refresh from admin

GET /sunray-wrkr/v1/admin/health
- Returns: {status: 'ok', version, cache_age}
- Purpose: Health check endpoint
```

#### **Admin Server APIs (Worker → Admin Server)**
```
GET /sunray-srvr/v1/config
- Returns: hosts[], users[], webhook_tokens[]
- Auth: Bearer token
- Called by: Worker to fetch configuration

POST /sunray-srvr/v1/users/check  
- Body: {username}
- Returns: {exists: boolean}
- Called by: Worker to check if user exists

POST /sunray-srvr/v1/setup-tokens/validate
- Body: {username, token_hash, client_ip}
- Returns: {valid: boolean, user_id?}
- Called by: Worker to validate setup token

POST /sunray-srvr/v1/users/{username}/passkeys
- Body: {credential_id, public_key, name, client_ip}
- Returns: {success: boolean}
- Called by: Worker to store new passkey

POST /sunray-srvr/v1/cache/invalidate
- Body: {scope: 'global'|'user', username?, reason}
- Returns: {success: boolean, invalidated_count}
- Auth: Bearer token (admin required)
- Called by: Admin UI for emergency reset

POST /sunray-srvr/v1/users/{username}/revoke
- Body: {reason, revoke_sessions: boolean}
- Returns: {success: boolean, sessions_revoked}
- Auth: Bearer token (admin required)
- Called by: Admin UI for user deactivation

POST /sunray-srvr/v1/webhooks/track-usage
- Body: {token, client_ip, timestamp}
- Returns: {success: boolean}
- Called by: Worker to track webhook usage
```

#### **MVP Data Models**
```python
# Minimum viable models
class SunrayUser(Model):
    username, email, active, created_date
    
class SunrayPasskey(Model):  
    user_id, credential_id, public_key, name, created_date
    
class SunraySetupToken(Model):
    user_id, token_hash, expires_at, used

class SunrayHost(Model):
    domain, backend_url, allowed_cidrs, 
    public_url_patterns, token_url_patterns

class SunrayWebhookToken(Model):
    host_id, token, name, active

class SunraySecurityEvent(Model):
    event_type, user_id, username, ip_address, 
    user_agent, details, timestamp
```

## 🛠️ Development Environment Setup

### **Prerequisites**
```bash
# Required tools
node >= 18.0.0
python >= 3.8  
docker & docker-compose
git

# Cloudflare CLI
npm install -g wrangler

# Odoo development (if needed)
# Will use Docker for MVP
```

### **Project Structure**
```
sunray/
├── sunray_worker/          # Cloudflare Worker
│   ├── src/
│   │   ├── index.js       # Main handler
│   │   ├── auth.js        # Authentication logic  
│   │   ├── config.js      # Admin server integration
│   │   └── templates.js   # HTML templates
│   ├── wrangler.toml      # Worker configuration
│   └── package.json
├── sunray_server/          # Odoo addons (prepare enterprise extension addon)
│   ├── sunray_core/        # Free edition core addon
│   │   ├── __manifest__.py
│   │   ├── models/
│   │   ├── controllers/
│   │   ├── views/
│   │   └── security/
│   └── sunray_enterprise/  # Advanced edition addon (extends core)
│       ├── __manifest__.py # Depends on sunray_core
│       ├── models/         # Extended models
│       ├── controllers/    # Advanced API endpoints
│       ├── views/          # Enhanced UI
│       ├── wizards/        # Automation wizards
│       └── data/           # Enterprise data
├── demo-app/             # Protected demo application
│   ├── public/           # Public pages
│   ├── protected/        # Protected pages  
│   └── api/              # Webhook endpoints
├── docker-compose.yml    # Local development
└── docs/
```

### **Local Development Setup**

#### **1. Admin Server (Odoo)**
```bash
# Use Docker for MVP simplicity
docker-compose up -d postgres
docker-compose up -d odoo

# Access: http://localhost:8069
# Install Sunray addon
```

#### **2. Demo Application**  
```bash
# Simple static server for MVP
cd demo-app
python -m http.server 3000

# Serves public and protected content
# Protected URLs: /admin/*, /dashboard/*  
# Public URLs: /, /about, /products/*
# API URLs: /api/webhooks/*
```

#### **3. Cloudflare Worker (Local)**
```bash
cd worker
npm install
wrangler dev --port 8787

# Local development server
# Proxies to demo-app on localhost:3000
```

### **MVP Configuration**
```yaml
# Environment variables for MVP
ADMIN_API_ENDPOINT=http://localhost:8069
ADMIN_API_KEY=mvp_test_key_123
RP_ID=localhost
RP_NAME=Sunray MVP Demo
CACHE_TTL=300  # 5 minutes for MVP (shorter for testing)
```

### **Emergency Cache Reset Implementation**

#### **Worker Cache Strategy**
```javascript
// Cache with version tracking for instant invalidation
async function getConfig(forceRefresh = false) {
  const cacheVersion = await env.CONFIG_CACHE.get('version');
  const serverVersion = await checkServerVersion();
  
  if (!forceRefresh && cacheVersion === serverVersion) {
    const cached = await env.CONFIG_CACHE.get('config');
    if (cached) return JSON.parse(cached);
  }
  
  // Fetch fresh config
  const response = await fetch(`${env.ADMIN_API_ENDPOINT}/sunray-srvr/v1/config`, {
    headers: { 'Authorization': `Bearer ${env.ADMIN_API_KEY}` }
  });
  const config = await response.json();
  await env.CONFIG_CACHE.put('config', JSON.stringify(config));
  await env.CONFIG_CACHE.put('version', serverVersion);
  return config;
}

// Session invalidation check
async function validateSession(sessionId) {
  const revocationList = await env.SESSIONS.get('revoked_users');
  const session = await env.SESSIONS.get(`session:${sessionId}`);
  
  if (!session) return false;
  
  const sessionData = JSON.parse(session);
  const revokedUsers = JSON.parse(revocationList || '[]');
  
  // Check if user has been revoked
  if (revokedUsers.includes(sessionData.username)) {
    await env.SESSIONS.delete(`session:${sessionId}`);
    return false;
  }
  
  return sessionData;
}
```

#### **Admin Server Revocation Flow**
```python
def revoke_user(self, username, reason, revoke_sessions=True):
    # 1. Deactivate user
    user = self.env['sunray.user'].search([('username', '=', username)])
    user.active = False
    
    # 2. Log security event
    self.env['sunray.security.event'].create({
        'event_type': 'user.revoked',
        'username': username,
        'details': json.dumps({'reason': reason})
    })
    
    # 3. Increment cache version to force refresh
    self.env['ir.config_parameter'].set_param(
        'sunray.cache_version', 
        str(int(time.time()))
    )
    
    # 4. Add to revocation list for immediate effect
    if revoke_sessions:
        self._add_to_revocation_list(username)
    
    return {'success': True}
```

## 📅 MVP Implementation Timeline

### **Phase 1: Foundation (Week 1-2)**

#### **Week 1: Admin Server MVP**
**Day 1-2: Odoo Addon Basic Structure**
- [ ] Create addon manifest and basic structure
- [ ] Implement core data models (User, Passkey, Host, SetupToken)
- [ ] Create basic forms and list views

**Day 3-4: Core API Endpoints**  
- [ ] POST /sunray-srvr/v1/users/check (user existence)
- [ ] GET /sunray-srvr/v1/config (configuration for worker)
- [ ] POST /sunray-srvr/v1/setup-tokens/validate (token validation)
- [ ] POST /sunray-srvr/v1/cache/invalidate (emergency cache reset)
- [ ] POST /sunray-srvr/v1/users/{username}/revoke (user deactivation)

**Day 5: Integration Testing**
- [ ] Test API endpoints with Postman/curl
- [ ] Verify data model relationships work
- [ ] Basic error handling

#### **Week 2: Worker MVP**
**Day 1-2: Request Handling Core**
- [ ] Main request handler with routing
- [ ] CIDR check implementation  
- [ ] URL pattern matching (public/token)
- [ ] Basic request proxying

**Day 3-4: WebAuthn Implementation**
- [ ] Registration flow (setup page)
- [ ] Authentication flow (login page)
- [ ] Session cookie management
- [ ] Admin server integration
- [ ] Cache invalidation handling
- [ ] Session revocation mechanism
- [ ] Worker internal endpoints (/sunray/v1/*)

**Day 5: End-to-End Testing**
- [ ] Complete user registration flow
- [ ] Complete authentication flow
- [ ] Test all access control patterns
- [ ] Basic error scenarios

### **Phase 2: Integration (Week 3)**

#### **Week 3: Demo Application & Polish** 
**Day 1-2: Demo Application**
- [ ] Create demo pages (public, protected, API)
- [ ] Add realistic content and navigation
- [ ] Webhook endpoints for testing token auth

**Day 3-4: Integration Testing**
- [ ] End-to-end user flows
- [ ] Cross-browser WebAuthn testing
- [ ] Performance basic testing
- [ ] Error handling refinement

**Day 5: Demo Preparation**
- [ ] Demo script and scenarios
- [ ] Known issues documentation
- [ ] Basic deployment documentation

### **Phase 3: Demo Ready (Week 4)**

#### **Week 4: Refinement & Documentation**
**Day 1-2: Bug Fixes & Polish**
- [ ] Fix critical issues from integration testing
- [ ] UI/UX improvements for demo
- [ ] Logging and debugging improvements

**Day 3-4: Demo Environment**
- [ ] Deploy to staging environment
- [ ] Test with real domain and SSL
- [ ] Performance verification

**Day 5: Demo Readiness**
- [ ] Final testing and verification
- [ ] Demo walkthrough preparation
- [ ] Stakeholder demo session

## 🧪 MVP Testing Strategy

### **Unit Testing (Minimal for MVP)**
- **Worker**: Test core functions (CIDR check, URL matching, session validation)
- **Admin Server**: Test API endpoints and data model methods
- **Tools**: Jest for Worker, Python unittest for Admin Server

### **Integration Testing (Focus Area)**  
- **User Registration Flow**: Setup token → WebAuthn registration → Session creation
- **Authentication Flow**: WebAuthn authentication → Session validation → Request proxy
- **Access Control**: CIDR bypass, public URLs, token authentication, passkey requirement
- **Error Scenarios**: Invalid tokens, expired sessions, network failures

### **Manual Testing Scenarios**
```
Scenario 1: New User Registration
1. Visit protected page
2. Enter username and setup token
3. Create passkey (browser prompt)
4. Verify access to original page

Scenario 2: Returning User Login  
1. Visit protected page (no session)
2. Authenticate with existing passkey
3. Verify session persistence
4. Test session across different protected pages

Scenario 3: Access Control Patterns
1. Test public URL access (no auth required)
2. Test CIDR bypass from office network
3. Test token authentication for webhook
4. Test default passkey requirement

Scenario 4: Error Handling
1. Invalid setup token
2. WebAuthn registration failure  
3. Expired session
4. Network disconnection scenarios

Scenario 5: Security Incident Response
1. Compromise detected - user account
2. Admin revokes user access
3. Cache invalidation triggers
4. User sessions terminated immediately
5. User cannot authenticate anymore
6. Audit log shows security events
```

### **Browser Compatibility (MVP)**
- **Primary**: Chrome, Firefox, Safari (latest versions)
- **WebAuthn**: Test with platform authenticators (Touch ID, Windows Hello)
- **Secondary**: Edge, mobile browsers

## 🚀 MVP Success Criteria

### **Functional Requirements**
✅ **Core Authentication:**
- User can register with passkey and access protected content
- User can authenticate with existing passkey
- Session persists across page navigation
- Logout functionality works

✅ **Access Control:**
- Public URLs accessible without authentication
- CIDR bypass works for office networks  
- Token authentication works for webhooks
- Default passkey requirement enforced

✅ **Admin Management:**
- Admin can create users and setup tokens
- Admin can configure host access patterns
- Admin can manage webhook tokens
- Configuration changes reflect in worker
- Emergency actions: revoke user, invalidate cache
- Security event audit log viewing

### **Technical Requirements**
✅ **Performance:**
- Authentication flow completes in <3 seconds
- Request proxying adds <100ms latency
- WebAuthn registration works in <10 seconds

✅ **Security:**
- Passkeys stored securely in browser
- Sessions use secure, httpOnly cookies
- API endpoints require authentication
- No secrets exposed in client-side code

✅ **Reliability:**
- Handles network failures gracefully
- Provides clear error messages
- Recovers from temporary outages
- Logs sufficient debugging information

## 🔧 MVP Development Guidelines

### **Code Quality (Minimal for MVP)**
- ESLint for JavaScript (Worker)
- Python formatting with Black (Admin Server)
- Basic error handling and logging
- Clear variable and function names

### **Security Practices**
- No secrets in code or configuration files
- HTTPS only (even in development)
- Input validation on all API endpoints
- Secure cookie configuration

### **Documentation (Essential Only)**
- Setup instructions for development environment
- API endpoint documentation
- Demo scenario instructions
- Known issues and limitations

## 📋 MVP Deliverables

### **Week 4 Deliverables:**
1. **Working Software:**
   - Deployed Cloudflare Worker
   - Configured Odoo instance with addon
   - Demo application with realistic content

2. **Documentation:**
   - Development setup instructions
   - Demo walkthrough script
   - Known limitations document
   - Next phase planning outline

3. **Demo Materials:**
   - Live demo environment
   - Demo scenarios and script
   - Technical architecture overview
   - User journey documentation

This MVP plan prioritizes getting a working demonstration quickly while maintaining quality for the core authentication flow. After demo validation, we can iterate and add advanced features based on feedback.

---

**Next Steps:**
1. Review and approve this MVP scope
2. Set up development environment  
3. Begin Phase 1 implementation
4. Weekly progress reviews and adjustments