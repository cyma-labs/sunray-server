# Sunray Deployment Security Guide

## Overview

This guide covers the security configuration of a production Sunray deployment: how the Sunray Server is reached, how protected hosts are exposed, and what to check after each change.

Two principles drive everything below:

- **The Sunray Server is never exposed to the open internet.** Only two kinds of clients may reach it: administrators, from known office IPs, and Sunray Workers, which only ever call the REST API under `/sunray-srvr/`.
- **A worker API key must never open more than the REST API.** Odoo authenticates the API itself; the filters in front of it exist to keep everything else, `/web/login`, `/jsonrpc`, `/xmlrpc/2/*`, `/web/database/manager`, out of reach of anyone holding a key.

## Sunray Server Access Control

Workers can reach the server two ways. Both are supported and can coexist on the same server.

| Path | Who uses it | Filtered by |
|------|-------------|-------------|
| **A. Public FQDN through Cloudflare** | Cloudflare Workers, and self-hosted workers that resolve the public name | Cloudflare WAF custom rule, then the host firewall (Cloudflare IP ranges only) |
| **B. Direct IP of the server** | Self-hosted workers (FastAPI) with a fixed egress IP | Host firewall (worker IPs only, port 443), then the reverse proxy in front of Odoo |

Path B is preferred for self-hosted workers: the worker's outbound traffic targets a single address, which keeps the worker's own egress policy precise, and no worker key ever transits Cloudflare.

### Path A: Cloudflare WAF rule

Create a custom rule on the zone hosting the server FQDN. It blocks everything except administrators by IP, and workers on the REST API prefix only:

```
(
    http.host in {"sunray.example.com"}
    and not (
        ip.src in $my_offices_list
        or (
            starts_with(http.request.uri.path, "/sunray-srvr/")
            and (
                any(http.request.headers["authorization"][*] contains "<fragment of worker key 1>")
                or any(http.request.headers["authorization"][*] contains "<fragment of worker key 2>")
            )
        )
    )
)
Action: Block
```

Rules for this expression:

- **Keep the `starts_with` on the path.** Without it, a matching `Authorization` header opens the whole Odoo surface, not only the API. Workers never call anything outside `/sunray-srvr/`.
- **Use a fragment of each key, not the full key.** A full `eq "Bearer …"` would put every worker key in the Cloudflare dashboard, readable by any member of the account. Because Odoo still validates the full key on the API, the WAF only needs to filter noise, and a contiguous fragment of twelve characters or more is enough.
- **Take fragments from the middle of the key.** The Sunray admin masks keys as `first 8…last 4`; those characters are visible to every admin user. Never use them as a fragment.
- **One block per server when several servers share the rule**, so that a key for server A does not pass the WAF of server B: `http.host eq "…" and starts_with(…) and (fragments of that server)`.
- No regular expressions are needed, so the rule works on the Pro plan.

The host firewall must still only accept port 443 from Cloudflare IP ranges on this path, otherwise the rule is bypassed by connecting to the origin directly.

### Path B: direct IP with host firewall and reverse proxy

1. **Host firewall.** Allow inbound `443/tcp` only from: each worker's egress IP, the Cloudflare IP ranges if path A is also used, and office IPs if administrators connect directly. Nothing else inbound. Do not open port 80 for workers. With Muppy, declare these as firewall rules on the host, or as a CIDR Dynamic Range dedicated to your workers attached to the `Open HTTPS 443/TCP` rule, so that they survive a firewall reconfiguration and stay auditable; a rule added by hand with `ufw` is lost the next time Muppy resets the firewall.
2. **Reverse proxy path restriction.** The firewall opens port 443 to the worker IP, and port 443 serves all of Odoo. The reverse proxy in front of Odoo must therefore apply the same restriction as the WAF rule: requests that are not from an office IP may only reach `/sunray-srvr/`. Traefik example, dynamic configuration:

```yaml
http:
  routers:
    sunray-api:
      rule: "Host(`sunray.example.com`) && PathPrefix(`/sunray-srvr/`)"
      entryPoints: [web-secure]
      service: sunray-odoo
      tls: {}
      # No IP allow-list: Odoo authenticates the API with the worker key.
    sunray-admin:
      rule: "Host(`sunray.example.com`)"
      entryPoints: [web-secure]
      service: sunray-odoo
      middlewares: [offices-only]
      tls: {}
  middlewares:
    offices-only:
      ipAllowList:
        sourceRange:
          - "203.0.113.0/24"      # office
          # Cloudflare ranges only if administrators also come through path A
```

   Traefik picks the longer rule first, so the API router wins on `/sunray-srvr/` and everything else falls to the admin router and its allow-list.
3. **TLS verification stays on in the worker.** The FastAPI worker verifies certificates by default; do not disable it. The certificate served on the direct IP must be publicly valid for the name the worker uses: a Let's Encrypt certificate obtained by DNS challenge, or by HTTP challenge through Cloudflare. A Cloudflare Origin CA certificate is not trusted by workers.
4. **Name resolution.** Either a DNS-only record (grey cloud) pointing at the direct IP, which reveals the origin address but is acceptable with the firewall above, or an `/etc/hosts` entry in the worker for the public FQDN. In both cases the worker keeps using the FQDN in `SUNRAY_SERVER_URL`.

### Odoo hardening, both paths

- `list_db = False` and a strict `dbfilter`, so the database manager does not exist even for office IPs.
- `proxy_mode = True`, so Odoo logs the real client IP behind the reverse proxy.
- One API key per worker, so a key can be rotated or disabled without touching the others. The server's audit log records the source IP of every key use; review it for unknown addresses.

## Protected Host Security

Protected hosts follow the standard Cloudflare origin rules:

- Origin traffic restricted to Cloudflare IP ranges only.
- Direct origin access blocked, possibly except for office IPs.

To protect a protected host with a Cloudflare WAF custom rule:

```
(
    http.host in { "xxx.domain.app" "thing.domain2.net" }
    and not ip.src in $my_offices_list
)
Action: Block
```

### What Muppy automates

Muppy maintains the **origin side** of this protection: its CIDR Dynamic Ranges load the Cloudflare IP ranges from the official source and apply them as host firewall rules and, optionally, as Traefik `ipAllowList` middlewares, so that origins only accept traffic from Cloudflare edge servers. Muppy does not create or manage rules on the Cloudflare side; WAF custom rules such as the ones above are configured in the Cloudflare dashboard.

## Security Checklist

- [ ] Sunray Server: port 443 accepts only office IPs, worker IPs, and Cloudflare ranges when path A is used
- [ ] Path A: WAF rule restricts worker keys to `/sunray-srvr/`, with key fragments taken from the middle of the key
- [ ] Path B: reverse proxy restricts non-office sources to `/sunray-srvr/`
- [ ] Workers verify TLS; the certificate on the direct IP is publicly valid
- [ ] `list_db = False` and `dbfilter` set on the server
- [ ] One API key per worker; audit log reviewed for unknown source IPs
- [ ] Protected hosts restricted to Cloudflare IP ranges; direct origin access blocked
- [ ] Firewall rules declared in Muppy, not added by hand
