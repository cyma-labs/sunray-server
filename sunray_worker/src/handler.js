/**
 * Main request handler
 * Handles authentication checks and request proxying
 */

import { checkCIDRBypass } from './utils/cidr.js';
import { checkPublicURL, checkTokenURL } from './utils/patterns.js';
import { validateSession, validateWAFBypassCookie, createSublimationClearCookie } from './auth/session.js';
import { getConfig } from './config.js';
import { createLogger } from './utils/logger.js';

export async function handleRequest(request, env, ctx) {
  const logger = createLogger(env);
  const url = new URL(request.url);
  const clientIP = request.headers.get('CF-Connecting-IP') || '127.0.0.1';
  
  logger.info(`[Request] ${request.method} ${url.pathname} from IP: ${clientIP}`);
  
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
  
  // 1. Check CIDR bypass (office networks, single IPs with /32, etc.)
  if (hostConfig.allowed_cidrs && hostConfig.allowed_cidrs.length > 0) {
    for (const cidr of hostConfig.allowed_cidrs) {
      if (checkCIDRBypass(clientIP, cidr)) {
        logger.info(`CIDR bypass granted for ${clientIP} matching ${cidr}`);
        return fetch(request);  // Pass through to origin
      }
    }
  }
  
  // 2. Check public URL patterns
  if (hostConfig.public_url_patterns && hostConfig.public_url_patterns.length > 0) {
    for (const pattern of hostConfig.public_url_patterns) {
      if (checkPublicURL(url.pathname, pattern)) {
        logger.info(`Public URL access granted for ${url.pathname}`);
        return fetch(request);  // Pass through to origin
      }
    }
  }
  
  // 3. Check token authentication for webhooks
  if (hostConfig.token_url_patterns && hostConfig.token_url_patterns.length > 0) {
    for (const pattern of hostConfig.token_url_patterns) {
      if (checkTokenURL(url.pathname, pattern)) {
        const validatedToken = extractAndValidateTokens(request, hostConfig, logger);
        if (validatedToken) {
          logger.info(`Token auth granted for ${url.pathname} using token '${validatedToken.name}'`);
          return fetch(request);  // Pass through to origin
        }
      }
    }
  }
  
  // 4. Check session authentication
  logger.debug(`[Session Check] Looking for session cookie on ${hostname}`);
  const sessionCookie = getCookie(request, 'sunray_session', logger);
  logger.debug(`[Session Check] Cookie found: ${sessionCookie ? 'YES (length: ' + sessionCookie.length + ')' : 'NO'}`);
  
  if (sessionCookie) {
    logger.debug(`[Session Check] Validating session...`);
    const session = await validateSession(sessionCookie, env, logger);
    logger.debug(`[Session Check] Validation result:`, session ? JSON.stringify({
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
      
      logger.debug(`[Session Check] Host match check: session.host_id='${session.host_id}' vs hostConfig.domain='${hostConfig.domain}' = ${sessionHostMatches}`);
      
      if (sessionHostMatches) {
        logger.info(`[Session Check] ✓ Session auth granted for user ${session.username} on host ${hostConfig.domain}`);
        
        // Check WAF bypass cookie if enabled for this host
        if (hostConfig.bypass_waf_for_authenticated) {
          const sublimationCookie = getCookie(request, 'sunray_sublimation', logger);
          
          if (sublimationCookie) {
            const clientIP = request.headers.get('CF-Connecting-IP') || '127.0.0.1';
            const userAgent = request.headers.get('User-Agent') || '';
            const maxAge = (hostConfig.waf_bypass_revalidation_minutes || 15) * 60;
            
            const isWAFBypassValid = await validateWAFBypassCookie(
              sublimationCookie,
              session.session_id,
              clientIP,
              userAgent,
              maxAge,
              env,
              session.username
            );
            
            if (!isWAFBypassValid) {
              // Sublimation cookie invalid, clear it and force re-authentication
              logger.warn(`[WAF Bypass] Invalid sublimation cookie for user ${session.username} from IP ${clientIP} - forcing re-auth`);
              
              const response = Response.redirect(loginUrl.toString(), 302);
              response.headers.set('Set-Cookie', createSublimationClearCookie(hostConfig.domain));
              return response;
            } else {
              logger.debug(`[WAF Bypass] Sublimation cookie validated for user ${session.username}`);
            }
          } else {
            // Session exists but no sublimation cookie - could be old session from before feature was enabled
            // Check if session was created recently (last 30 seconds) - if so, it might need a refresh
            const sessionAge = Date.now() - (session.created_at || 0);
            if (sessionAge < 30000) {
              logger.debug(`[WAF Bypass] Recent session without sublimation cookie for ${session.username} (feature may be newly enabled)`);
            }
          }
        }
        
        // Add user info headers for backend
        const headers = new Headers(request.headers);
        headers.set('X-Sunray-User', session.username);
        headers.set('X-Sunray-User-ID', session.user_id);
        
        // Pass through to origin with user info headers
        const modifiedRequest = new Request(request, { headers });
        logger.debug(`[Session Check] Passing through to origin for ${url.pathname}`);
        return fetch(modifiedRequest);
      } else {
        logger.debug(`[Session Check] ✗ Session host mismatch`);
      }
    } else {
      logger.debug(`[Session Check] ✗ Session invalid or missing user_id`);
    }
  } else {
    logger.debug(`[Session Check] No session cookie found`);
  }
  
  // No valid authentication found, redirect to login
  const loginUrl = new URL('/sunray-wrkr/v1/auth', url);
  loginUrl.searchParams.set('return_to', url.pathname + url.search);
  
  return Response.redirect(loginUrl.toString(), 302);
}

// Removed proxyRequest function - we now pass through directly to origin

/**
 * Extract and validate tokens using per-token configuration
 */
function extractAndValidateTokens(request, hostConfig, logger) {
  if (!hostConfig.webhook_tokens || hostConfig.webhook_tokens.length === 0) {
    return null;
  }

  const url = new URL(request.url);
  
  // Try each configured token
  for (const tokenConfig of hostConfig.webhook_tokens) {
    const extractedToken = extractTokenByConfig(request, tokenConfig, url, logger);
    
    if (extractedToken && isTokenValid(extractedToken, tokenConfig, logger)) {
      logger.debug(`Token validation successful for '${tokenConfig.name}'`);
      return tokenConfig;
    }
  }
  
  logger.debug('No valid tokens found');
  return null;
}

/**
 * Extract token based on individual token configuration
 */
function extractTokenByConfig(request, tokenConfig, url, logger) {
  const { header_name, param_name, token_source } = tokenConfig;
  
  logger.debug(`Extracting token for '${tokenConfig.name}' with source '${token_source}'`);
  
  switch (token_source) {
    case 'header':
      if (header_name) {
        const headerValue = request.headers.get(header_name);
        if (headerValue) {
          logger.debug(`Found token in header '${header_name}'`);
          return headerValue;
        }
      }
      break;
      
    case 'param':
      if (param_name) {
        const paramValue = url.searchParams.get(param_name);
        if (paramValue) {
          logger.debug(`Found token in parameter '${param_name}'`);
          return paramValue;
        }
      }
      break;
      
    case 'both':
      // Try header first, then parameter
      if (header_name) {
        const headerValue = request.headers.get(header_name);
        if (headerValue) {
          logger.debug(`Found token in header '${header_name}' (both mode)`);
          return headerValue;
        }
      }
      if (param_name) {
        const paramValue = url.searchParams.get(param_name);
        if (paramValue) {
          logger.debug(`Found token in parameter '${param_name}' (both mode)`);
          return paramValue;
        }
      }
      break;
  }
  
  logger.debug(`No token found for '${tokenConfig.name}'`);
  return null;
}

/**
 * Validate if extracted token matches the configured token
 */
function isTokenValid(extractedToken, tokenConfig, logger) {
  // Check if token matches
  if (extractedToken !== tokenConfig.token) {
    logger.debug(`Token mismatch for '${tokenConfig.name}'`);
    return false;
  }
  
  // Check if token is active
  if (!tokenConfig.is_active) {
    logger.debug(`Token '${tokenConfig.name}' is inactive`);
    return false;
  }
  
  // Check expiration
  if (tokenConfig.expires_at) {
    const expiresAt = new Date(tokenConfig.expires_at);
    if (expiresAt < new Date()) {
      logger.debug(`Token '${tokenConfig.name}' has expired`);
      return false;
    }
  }
  
  return true;
}

/**
 * Legacy: Extract token from request (kept for backward compatibility)
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
 * Legacy: Validate webhook token (kept for backward compatibility)
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
function getCookie(request, name, logger) {
  const cookieHeader = request.headers.get('Cookie');
  logger.debug(`[getCookie] Cookie header present: ${cookieHeader ? 'YES' : 'NO'}`);
  if (!cookieHeader) return null;
  
  logger.debug(`[getCookie] Full cookie header: ${cookieHeader.substring(0, 100)}...`);
  const cookies = cookieHeader.split(';').map(c => c.trim());
  logger.debug(`[getCookie] Found ${cookies.length} cookies`);
  
  for (const cookie of cookies) {
    const [key, value] = cookie.split('=');
    logger.debug(`[getCookie] Checking cookie: ${key} = ${value ? value.substring(0, 20) + '...' : 'undefined'}`);
    if (key === name) {
      const decoded = decodeURIComponent(value);
      logger.debug(`[getCookie] Found ${name} cookie, length: ${decoded.length}`);
      return decoded;
    }
  }
  
  logger.debug(`[getCookie] Cookie '${name}' not found`);
  return null;
}