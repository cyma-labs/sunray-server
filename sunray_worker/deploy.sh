#!/bin/bash

# Sunray Worker Deployment Script

set -e

echo "🚀 Sunray Worker Deployment"
echo "=========================="

# Check if wrangler is installed
if ! command -v wrangler &> /dev/null; then
    echo "❌ Wrangler CLI not found. Installing..."
    npm install -g wrangler
fi

# Function to create KV namespaces
create_kv_namespaces() {
    echo "📦 Creating KV namespaces..."
    
    # Create production namespaces
    SESSIONS_ID=$(wrangler kv namespace create SESSIONS 2>&1 | grep -oP 'id = "\K[^"]+')
    CHALLENGES_ID=$(wrangler kv namespace create CHALLENGES 2>&1 | grep -oP 'id = "\K[^"]+')
    CONFIG_CACHE_ID=$(wrangler kv namespace create CONFIG_CACHE 2>&1 | grep -oP 'id = "\K[^"]+')
    
    # Create preview namespaces
    SESSIONS_PREVIEW_ID=$(wrangler kv namespace create SESSIONS --preview 2>&1 | grep -oP 'id = "\K[^"]+')
    CHALLENGES_PREVIEW_ID=$(wrangler kv namespace create CHALLENGES --preview 2>&1 | grep -oP 'id = "\K[^"]+')
    CONFIG_CACHE_PREVIEW_ID=$(wrangler kv namespace create CONFIG_CACHE --preview 2>&1 | grep -oP 'id = "\K[^"]+' )
    
    echo "✅ KV namespaces created:"
    echo "   SESSIONS: $SESSIONS_ID (preview: $SESSIONS_PREVIEW_ID)"
    echo "   CHALLENGES: $CHALLENGES_ID (preview: $CHALLENGES_PREVIEW_ID)"
    echo "   CONFIG_CACHE: $CONFIG_CACHE_ID (preview: $CONFIG_CACHE_PREVIEW_ID)"
    
    # Update wrangler.toml with the IDs
    sed -i.bak "s/id = \"sunray_sessions\"/id = \"$SESSIONS_ID\"/" wrangler.toml
    sed -i.bak "s/preview_id = \"sunray_sessions_preview\"/preview_id = \"$SESSIONS_PREVIEW_ID\"/" wrangler.toml
    sed -i.bak "s/id = \"sunray_challenges\"/id = \"$CHALLENGES_ID\"/" wrangler.toml
    sed -i.bak "s/preview_id = \"sunray_challenges_preview\"/preview_id = \"$CHALLENGES_PREVIEW_ID\"/" wrangler.toml
    sed -i.bak "s/id = \"sunray_config_cache\"/id = \"$CONFIG_CACHE_ID\"/" wrangler.toml
    sed -i.bak "s/preview_id = \"sunray_config_cache_preview\"/preview_id = \"$CONFIG_CACHE_PREVIEW_ID\"/" wrangler.toml
}

# Function to set secrets
set_secrets() {
    echo "🔐 Setting up secrets..."
    
    # Generate session secret if not provided
    if [ -z "$SESSION_SECRET" ]; then
        SESSION_SECRET=$(openssl rand -base64 32)
        echo "   Generated SESSION_SECRET: $SESSION_SECRET"
    fi
    
    # Prompt for API key if not provided
    if [ -z "$ADMIN_API_KEY" ]; then
        read -p "Enter ADMIN_API_KEY: " ADMIN_API_KEY
    fi
    
    # Set secrets
    echo "$SESSION_SECRET" | wrangler secret put SESSION_SECRET
    echo "$ADMIN_API_KEY" | wrangler secret put ADMIN_API_KEY
    
    echo "✅ Secrets configured"
}

# Function to deploy worker
deploy_worker() {
    echo "🚀 Deploying Worker..."
    
    # Install dependencies
    npm install
    
    # Deploy to Cloudflare
    if [ "$1" == "production" ]; then
        wrangler deploy --env production
    else
        wrangler deploy
    fi
    
    echo "✅ Worker deployed successfully"
}

# Main deployment flow
main() {
    echo ""
    echo "Select deployment option:"
    echo "1) Full setup (create KV, set secrets, deploy)"
    echo "2) Deploy only (update existing worker)"
    echo "3) Create KV namespaces only"
    echo "4) Set secrets only"
    echo "5) Production deployment"
    read -p "Option [1-5]: " option
    
    case $option in
        1)
            create_kv_namespaces
            set_secrets
            deploy_worker
            ;;
        2)
            deploy_worker
            ;;
        3)
            create_kv_namespaces
            ;;
        4)
            set_secrets
            ;;
        5)
            deploy_worker "production"
            ;;
        *)
            echo "❌ Invalid option"
            exit 1
            ;;
    esac
    
    echo ""
    echo "✨ Deployment complete!"
    echo ""
    echo "Next steps:"
    echo "1. Update ADMIN_API_KEY in Sunray Server"
    echo "2. Configure your domain's DNS to proxy through Cloudflare"
    echo "3. Test authentication at: https://your-domain/sunray-wrkr/v1/setup"
}

# Run main function
main