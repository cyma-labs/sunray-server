# Cloudflared Setup Instructions

## Step 1: Authenticate with Cloudflare

Run this command and open the URL in your browser:
```bash
cloudflared tunnel login
```

This will:
1. Open a browser authentication page
2. You log in with your Cloudflare account
3. Select the domain (pack8s.com)
4. A certificate will be downloaded to `~/.cloudflared/cert.pem`

## Step 2: Create Named Tunnel

Once authenticated, create the tunnel:
```bash
cloudflared tunnel create sunray-srvr-dev-cyril
```

This creates:
- Tunnel ID (UUID)
- Credentials file: `~/.cloudflared/<tunnel-id>.json`

## Step 3: Configure Tunnel

Create configuration file:
```bash
cat > ~/.cloudflared/config.yml << EOF
tunnel: sunray-srvr-dev-cyril
credentials-file: /home/$USER/.cloudflared/<tunnel-id>.json

ingress:
  - hostname: sr-srvr-dev-cyril.pack8s.com
    service: http://localhost:8069
    originRequest:
      noTLSVerify: true
  - service: http_status:404
EOF
```

## Step 4: Configure DNS

Add DNS record in Cloudflare Dashboard:
- Type: CNAME
- Name: sr-srvr-dev-cyril
- Target: <tunnel-id>.cfargotunnel.com
- Proxy: Enabled (orange cloud)

Or via API:
```bash
cloudflared tunnel route dns sunray-srvr-dev-cyril sr-srvr-dev-cyril.pack8s.com
```

## Step 5: Run Tunnel

```bash
# Test run
cloudflared tunnel run sunray-srvr-dev-cyril

# Run as service (production)
sudo cloudflared service install
sudo systemctl start cloudflared
sudo systemctl enable cloudflared
```

## Step 6: Apply WAF Rules

In Cloudflare Dashboard, create WAF rule:
```
(http.host eq "sr-srvr-dev-cyril.pack8s.com" 
 and not ip.src in { 
   178.170.1.44 
   147.79.118.98 
   5.135.178.38 
   5.250.182.225 
   162.19.69.75 
 })
Action: Block
```

## Current Status

- [x] Cloudflared installed
- [ ] Authenticated with Cloudflare (need browser access)
- [ ] Named tunnel created
- [ ] DNS configured
- [ ] Tunnel running
- [ ] WAF rules applied