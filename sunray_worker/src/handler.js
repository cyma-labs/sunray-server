/**
 * Main request handler
 * Handles authentication checks and request proxying
 */

import { checkCIDRBypass } from './utils/cidr.js';
import { checkPublicURL, checkTokenURL } from './utils/patterns.js';
import { validateSession } from './auth/session.js';
import { getConfig } from './config.js';

export async function handleRequest(request, env, ctx) {
  const url = new URL(request.url);
  const clientIP = request.headers.get('CF-Connecting-IP') || '127.0.0.1';
  
  // Get configuration (with caching)
  const config = await getConfig(env);
  if (!config) {
    return new Response('Service temporarily unavailable', { status: 503 });
  }
  
  // Find matching host configuration
  const hostname = url.hostname;
  const hostConfig = config.hosts.find(h => h.domain === hostname);
  
  if (!hostConfig) {
    // No configuration for this domain, pass through
    return fetch(request);
  }
  
  // Check bypass conditions in order
  
  // 1. Check CIDR bypass (office networks, etc.)
  if (hostConfig.allowed_cidrs && hostConfig.allowed_cidrs.length > 0) {
    for (const cidr of hostConfig.allowed_cidrs) {
      if (checkCIDRBypass(clientIP, cidr)) {
        console.log(`CIDR bypass granted for ${clientIP} matching ${cidr}`);
        return fetch(request);  // Pass through to origin
      }
    }
  }
  
  // 2. Check public URL patterns
  if (hostConfig.public_url_patterns && hostConfig.public_url_patterns.length > 0) {
    for (const pattern of hostConfig.public_url_patterns) {
      if (checkPublicURL(url.pathname, pattern)) {
        console.log(`Public URL access granted for ${url.pathname}`);
        return fetch(request);  // Pass through to origin
      }
    }
  }
  
  // 3. Check token authentication for webhooks
  if (hostConfig.token_url_patterns && hostConfig.token_url_patterns.length > 0) {
    for (const pattern of hostConfig.token_url_patterns) {
      if (checkTokenURL(url.pathname, pattern)) {
        const token = extractToken(request, hostConfig);
        if (token && validateWebhookToken(token, hostConfig.webhook_tokens)) {
          console.log(`Token auth granted for ${url.pathname}`);
          return fetch(request);  // Pass through to origin
        }
      }
    }
  }
  
  // 4. Check session authentication
  console.log(`[Session Check] Looking for session cookie on ${hostname}`);
  const sessionCookie = getCookie(request, 'sunray_session');
  console.log(`[Session Check] Cookie found: ${sessionCookie ? 'YES (length: ' + sessionCookie.length + ')' : 'NO'}`);
  
  if (sessionCookie) {
    console.log(`[Session Check] Validating session...`);
    const session = await validateSession(sessionCookie, env);
    console.log(`[Session Check] Validation result:`, session ? JSON.stringify({
      has_user_id: !!session.user_id,
      username: session.username,
      host_id: session.host_id,
      expires_at: session.expires_at,
      is_active: session.is_active
    }) : 'NULL');
    
    // Check if session is valid and matches the current host
    if (session && session.user_id) {
      // Session host_id might be hostname or 'default'
      const sessionHostMatches = session.host_id === hostConfig.domain || 
                                 session.host_id === 'default' ||
                                 !session.host_id;
      
      console.log(`[Session Check] Host match check: session.host_id='${session.host_id}' vs hostConfig.domain='${hostConfig.domain}' = ${sessionHostMatches}`);
      
      if (sessionHostMatches) {
        console.log(`[Session Check] ✓ Session auth granted for user ${session.username} on host ${hostConfig.domain}`);
        
        // Add user info headers for backend
        const headers = new Headers(request.headers);
        headers.set('X-Sunray-User', session.username);
        headers.set('X-Sunray-User-ID', session.user_id);
        
        // Pass through to origin with user info headers
        const modifiedRequest = new Request(request, { headers });
        console.log(`[Session Check] Passing through to origin for ${url.pathname}`);
        return fetch(modifiedRequest);
      } else {
        console.log(`[Session Check] ✗ Session host mismatch`);
      }
    } else {
      console.log(`[Session Check] ✗ Session invalid or missing user_id`);
    }
  } else {
    console.log(`[Session Check] No session cookie found`);
  }
  
  // No valid authentication found, redirect to login
  const loginUrl = new URL('/sunray-wrkr/v1/auth', url);
  loginUrl.searchParams.set('return_to', url.pathname + url.search);
  
  return Response.redirect(loginUrl.toString(), 302);
}

// Removed proxyRequest function - we now pass through directly to origin

/**
 * Extract token from request (header or query param)
 */
function extractToken(request, hostConfig) {
  // Check header first
  if (hostConfig.webhook_header_name) {
    const headerToken = request.headers.get(hostConfig.webhook_header_name);
    if (headerToken) return headerToken;
  }
  
  // Check query parameter
  if (hostConfig.webhook_param_name) {
    const url = new URL(request.url);
    const paramToken = url.searchParams.get(hostConfig.webhook_param_name);
    if (paramToken) return paramToken;
  }
  
  // Check Authorization header
  const authHeader = request.headers.get('Authorization');
  if (authHeader && authHeader.startsWith('Bearer ')) {
    return authHeader.substring(7);
  }
  
  return null;
}

/**
 * Validate webhook token
 */
function validateWebhookToken(token, validTokens) {
  if (!validTokens || validTokens.length === 0) return false;
  
  for (const validToken of validTokens) {
    if (validToken.token === token && validToken.is_active) {
      // Check if token has expired
      if (validToken.expires_at) {
        const expiresAt = new Date(validToken.expires_at);
        if (expiresAt < new Date()) {
          continue;
        }
      }
      return true;
    }
  }
  
  return false;
}

/**
 * Get cookie value
 */
function getCookie(request, name) {
  const cookieHeader = request.headers.get('Cookie');
  console.log(`[getCookie] Cookie header present: ${cookieHeader ? 'YES' : 'NO'}`);
  if (!cookieHeader) return null;
  
  console.log(`[getCookie] Full cookie header: ${cookieHeader.substring(0, 100)}...`);
  const cookies = cookieHeader.split(';').map(c => c.trim());
  console.log(`[getCookie] Found ${cookies.length} cookies`);
  
  for (const cookie of cookies) {
    const [key, value] = cookie.split('=');
    console.log(`[getCookie] Checking cookie: ${key} = ${value ? value.substring(0, 20) + '...' : 'undefined'}`);
    if (key === name) {
      const decoded = decodeURIComponent(value);
      console.log(`[getCookie] Found ${name} cookie, length: ${decoded.length}`);
      return decoded;
    }
  }
  
  console.log(`[getCookie] Cookie '${name}' not found`);
  return null;
}