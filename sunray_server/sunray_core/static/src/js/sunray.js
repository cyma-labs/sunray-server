/** @odoo-module */

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component } from "@odoo/owl";

/**
 * Sunray Dashboard Component
 * Shows real-time statistics for authentication system
 */
export class SunrayDashboard extends Component {
    static template = "sunray_core.Dashboard";
    
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
    }
    
    async refreshStats() {
        try {
            const stats = await this.orm.call(
                "sunray.user",
                "get_dashboard_stats",
                []
            );
            this.state.stats = stats;
        } catch (error) {
            this.notification.add("Failed to refresh statistics", {
                type: "danger",
            });
        }
    }
    
    async revokeSession(sessionId) {
        try {
            await this.orm.call(
                "sunray.session",
                "revoke",
                [sessionId]
            );
            this.notification.add("Session revoked successfully", {
                type: "success",
            });
            await this.refreshStats();
        } catch (error) {
            this.notification.add("Failed to revoke session", {
                type: "danger",
            });
        }
    }
}

/**
 * Setup Token Copy Widget
 * Provides one-click copy functionality for setup tokens
 */
export class SetupTokenCopyWidget extends Component {
    static template = "sunray_core.SetupTokenCopy";
    
    setup() {
        this.notification = useService("notification");
    }
    
    async copyToClipboard() {
        const token = this.props.value;
        try {
            await navigator.clipboard.writeText(token);
            this.notification.add("Token copied to clipboard", {
                type: "success",
            });
        } catch (error) {
            this.notification.add("Failed to copy token", {
                type: "danger",
            });
        }
    }
}

/**
 * Passkey Registration Handler
 * Manages WebAuthn registration flow
 */
export class PasskeyRegistration {
    constructor(notification) {
        this.notification = notification;
    }
    
    async startRegistration(username, challenge) {
        if (!window.PublicKeyCredential) {
            this.notification.add("WebAuthn is not supported in this browser", {
                type: "danger",
            });
            return null;
        }
        
        try {
            const credential = await navigator.credentials.create({
                publicKey: {
                    challenge: Uint8Array.from(challenge, c => c.charCodeAt(0)),
                    rp: {
                        name: "Sunray Authentication",
                        id: window.location.hostname,
                    },
                    user: {
                        id: Uint8Array.from(username, c => c.charCodeAt(0)),
                        name: username,
                        displayName: username,
                    },
                    pubKeyCredParams: [
                        { alg: -7, type: "public-key" },  // ES256
                        { alg: -257, type: "public-key" }, // RS256
                    ],
                    authenticatorSelection: {
                        authenticatorAttachment: "platform",
                        userVerification: "required",
                    },
                    timeout: 60000,
                    attestation: "none",
                },
            });
            
            return credential;
        } catch (error) {
            this.notification.add(`Registration failed: ${error.message}`, {
                type: "danger",
            });
            return null;
        }
    }
}

// Register components
registry.category("actions").add("sunray.dashboard", SunrayDashboard);
registry.category("fields").add("setup_token_copy", SetupTokenCopyWidget);