# Sunray Web/HTTP Zero Trust Access Solution - Introduction

## 🌞 Overview

**Sunray** is a comprehensive and affordable Web/HTTP Zero Trust access solution that protects web applications using `WebAuthn Passkeys` with intelligent edge workers for enterprise-grade security. The system consists of two main components: edge `Workers` for access control enforcement (supporting multiple platforms) and the `Admin Server` (Odoo addon) for centralized policy management and worker orchestration.

**Important**: Sunray is not an authentication system. It's an access control layer that decides who can reach your protected applications. Users still authenticate with the actual application after passing through Sunray's access control.

## 📦 Editions

Sunray is available in two technical editions:

### **Sunray Core** (Free/Open Source)
- Full passkey authentication system
- CIDR bypass, public URLs, webhook tokens
- Session management
- User and host configuration
- Basic monitoring dashboard
- Community support

### **Sunray Advanced** (Paid License)
- All Core features plus:
- TOTP (two-factor authentication)
- Advanced session policies
- Rate limiting
- Security alerts and monitoring
- Compliance reporting
- Emergency access
- SAML/OIDC integration
- Premium support

### **Sunray Enterprise** (Commercial Package)
A complete solution combining:
- Sunray Advanced license
- Professional services (installation, configuration)
- Training and onboarding
- SLA with guaranteed response times
- Custom integrations
- Dedicated support team

*Note: "Enterprise" is a commercial offering, not a separate technical product. The technical implementation consists of `sunray_core` and `sunray_advanced` addons.*

## 🔄 Access Control Flow

When a `User` visits a protected website, the `Worker` intercepts the request and applies security-first Zero Trust access control. By default, everything is locked and requires `Passkey Verification`, but administrators can configure three types of exceptions: `CIDR Bypass` for office networks, `Public URL Patterns` for unrestricted access to specific pages, and `Token URL Patterns` for API webhooks. If no exception applies, the `Worker` checks for a valid `Session Cookie` - if present, the request is proxied to the `Backend Service`; if not, the `Worker` queries the `Admin Server` to determine if the user exists and serves either a `Setup Page` (new users with `Setup Tokens`) or `Login Page` (existing users). After successful `Passkey` verification, a `Session Cookie` is established and the original request is completed, with all access control state managed through the `Admin Server's` configuration. The `Worker` auto-registers with the `Admin Server` and supports zero-downtime migration for continuous service availability.

## 📚 Lexicon

### **Admin Server**
Odoo 18 addon that provides centralized configuration management, user administration, and `Setup Token` generation. Stores `Passkey` credentials, manages `Webhook Tokens`, and defines access control rules for protected domains.

### **Backend Service** 
The original web application being protected by Sunray. Receives proxied requests from the `Cloudflare Worker` with authentication headers indicating how the user was authenticated.

### **CIDR Bypass**
Network-based exception that allows requests from specific IP ranges (e.g., `192.168.1.0/24`) to bypass all authentication. Typically used for office networks where physical access provides sufficient security.

### **CIDR Blocks**
IP address ranges specified in CIDR notation (e.g., `10.0.0.0/16`) that define which networks are allowed to bypass authentication entirely.

### **Cloudflare Worker**
Serverless JavaScript code that runs at Cloudflare's edge locations, intercepting all requests to protected domains. Handles authentication logic, session validation, and request proxying while leveraging Cloudflare's built-in WAF, DDoS protection, and bot management. Auto-registers with Admin Server and supports zero-downtime migration.

### **Login Page**
HTML page served by the `Cloudflare Worker` to existing users who need to authenticate. Prompts for `Passkey` authentication using WebAuthn browser APIs.

### **Passkey**
WebAuthn credential that provides passwordless, phishing-resistant authentication. Stored securely on the user's device and used for cryptographic proof of identity without transmitting secrets.

### **Passkey Verification**
The default security mechanism requiring users to verify their identity using their WebAuthn `Passkey` to gain access to protected applications. Provides strong cryptographic verification with biometric or PIN confirmation.

### **Public URL Patterns**
Regular expression patterns (e.g., `^/products/.*`) that define which URLs should be accessible without authentication. Used for public content like marketing pages, product catalogs, or static assets.

### **Session Cookie**
HTTP cookie (`sunray_session`) that maintains authenticated state after successful `Passkey` verification. Contains encrypted session data and has configurable expiration times.

### **Setup Page**
HTML page served by the `Cloudflare Worker` to new users during their first visit. Collects username and `Setup Token`, then guides through `Passkey` registration process.

### **Setup Token**
One-time authentication token generated by administrators in the `Admin Server` and provided to new users. Required for initial account setup and `Passkey` registration. Expires after use or configurable time period.

### **Token URL Patterns**
Regular expression patterns (e.g., `^/webhooks/.*`) that define which URLs accept token-based access instead of `Passkey Verification`. Used for API endpoints, webhooks, and automated integrations.

### **User**
End user accessing the protected web application. Can gain access through `Passkey Verification`, `CIDR Bypass`, or accessing `Public URL Patterns`.

### **WebAuthn**
W3C standard for passwordless authentication that enables secure, phishing-resistant user verification using public-key cryptography. Foundation technology for `Passkeys`.

### **Webhook Tokens**
Authentication tokens (e.g., `wh_live_abc123`) used by external services to authenticate API requests to URLs matching `Token URL Patterns`. Can include IP restrictions and expiration dates for enhanced security.

### **Worker**
Edge protection component that implements access control logic and request interception. Can be deployed on various platforms (Cloudflare, Kubernetes, etc.). Auto-registers with Admin Server, supports zero-downtime migration, and maintains comprehensive audit trails.

### **Worker Migration**
Controlled process for replacing workers without service interruption. Admin sets pending worker, new worker auto-migrates upon registration, old worker receives error and stops serving traffic.

---

## 📋 Component Specifications

This introduction covers the core concepts used in the detailed specifications:

- **[Muppy Sunray Worker v3 Specification](specs/muppy_sunray_worker_spec_v3.md)** - Complete technical specification for the Cloudflare Worker implementation
- **[Sunray Admin Server v3 Specification](specs/sunray_admin_server_spec_v3.md)** - Complete technical specification for the Odoo 18 addon implementation