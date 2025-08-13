/**
 * Authentication endpoint - handles user login
 */

import { getAuthHTML } from '../templates/auth.js';
import { verifyPasskey } from '../auth/webauthn.js';
import { createSession, createSessionCookie } from '../auth/session.js';
import { checkUserExists } from '../config.js';

export async function handleAuth(request, env, ctx) {
  const url = new URL(request.url);
  const path = url.pathname;
  
  // GET /sunray-wrkr/v1/auth - Show login form
  if (request.method === 'GET' && path === '/sunray-wrkr/v1/auth') {
    const returnTo = url.searchParams.get('return_to') || '/';
    const html = getAuthHTML(env.RP_NAME, returnTo);
    return new Response(html, {
      status: 200,
      headers: { 'Content-Type': 'text/html; charset=utf-8' }
    });
  }
  
  // POST /sunray-wrkr/v1/auth/challenge - Get authentication challenge
  if (request.method === 'POST' && path === '/sunray-wrkr/v1/auth/challenge') {
    // Validate Content-Type
    const contentType = request.headers.get('Content-Type');
    if (!contentType || !contentType.includes('application/json')) {
      return new Response(JSON.stringify({
        success: false,
        error: 'Content-Type must be application/json'
      }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' }
      });
    }
    
    const body = await request.json();
    const { username } = body;
    
    if (!username) {
      return new Response(JSON.stringify({
        success: false,
        error: 'Username is required'
      }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' }
      });
    }
    
    // Check if user exists
    const userExists = await checkUserExists(username, env);
    
    if (!userExists) {
      // Don't reveal whether user exists or not
      return new Response(JSON.stringify({
        success: false,
        error: 'Invalid username or password'
      }), {
        status: 401,
        headers: { 'Content-Type': 'application/json' }
      });
    }
    
    // Generate authentication challenge
    const challenge = crypto.randomUUID();
    
    // Store challenge temporarily
    await env.CHALLENGES.put(
      `auth:${username}:${challenge}`,
      JSON.stringify({
        username,
        timestamp: Date.now()
      }),
      { expirationTtl: parseInt(env.CHALLENGE_TTL || '300') }
    );
    
    // Return WebAuthn authentication options
    return new Response(JSON.stringify({
      success: true,
      options: {
        challenge,
        rpId: env.RP_ID,
        userVerification: 'required',
        timeout: 60000
      }
    }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' }
    });
  }
  
  // POST /sunray-wrkr/v1/auth/verify - Verify authentication
  if (request.method === 'POST' && path === '/sunray-wrkr/v1/auth/verify') {
    // Validate Content-Type
    const contentType = request.headers.get('Content-Type');
    if (!contentType || !contentType.includes('application/json')) {
      return new Response(JSON.stringify({
        success: false,
        error: 'Content-Type must be application/json'
      }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' }
      });
    }
    
    const body = await request.json();
    const { username, challenge, credential, returnTo } = body;
    
    if (!username || !challenge || !credential) {
      return new Response(JSON.stringify({
        success: false,
        error: 'Missing required parameters'
      }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' }
      });
    }
    
    // Verify challenge
    const challengeData = await env.CHALLENGES.get(
      `auth:${username}:${challenge}`,
      { type: 'json' }
    );
    
    if (!challengeData) {
      return new Response(JSON.stringify({
        success: false,
        error: 'Invalid or expired challenge'
      }), {
        status: 401,
        headers: { 'Content-Type': 'application/json' }
      });
    }
    
    // Clean up challenge
    await env.CHALLENGES.delete(`auth:${username}:${challenge}`);
    
    // Verify passkey with admin server
    const user = await verifyPasskey(username, credential, challenge, env);
    
    if (!user) {
      return new Response(JSON.stringify({
        success: false,
        error: 'Authentication failed'
      }), {
        status: 401,
        headers: { 'Content-Type': 'application/json' }
      });
    }
    
    // Get host domain from return URL
    const returnUrl = new URL(returnTo || '/', url);
    const hostDomain = returnUrl.hostname;
    
    // Create session with the host domain
    const session = await createSession(user, hostDomain, env);
    
    // Create session cookie
    const cookie = createSessionCookie(
      session.jwt,
      session.expiresAt,
      env.RP_ID
    );
    
    // Store session info temporarily for cookie setting
    await env.SESSIONS.put(
      `pending:${session.sessionId}`,
      JSON.stringify({
        cookie,
        redirectTo: returnTo || '/'
      }),
      { expirationTtl: 60 } // 1 minute TTL
    );
    
    console.log(`Session created: ${session.sessionId}, pending redirect to: ${returnTo || '/'}`);
    
    // Return success with session ID for redirect
    return new Response(JSON.stringify({
      success: true,
      sessionId: session.sessionId
    }), {
      status: 200,
      headers: {
        'Content-Type': 'application/json'
      }
    });
  }
  
  // GET /sunray-wrkr/v1/auth/complete - Complete auth and set cookie
  if (request.method === 'GET' && path === '/sunray-wrkr/v1/auth/complete') {
    const sessionId = url.searchParams.get('sid');
    
    console.log(`[auth/complete] Completing authentication for session: ${sessionId}`);
    
    if (!sessionId) {
      console.log(`[auth/complete] ✗ No session ID provided`);
      return Response.redirect('/sunray-wrkr/v1/auth', 302);
    }
    
    // Get pending session
    const pendingKey = `pending:${sessionId}`;
    console.log(`[auth/complete] Looking up pending session: ${pendingKey}`);
    
    const pending = await env.SESSIONS.get(pendingKey, { type: 'json' });
    if (!pending) {
      console.log(`[auth/complete] ✗ Pending session not found`);
      return Response.redirect('/sunray-wrkr/v1/auth', 302);
    }
    
    console.log(`[auth/complete] Found pending session:`, {
      redirectTo: pending.redirectTo,
      cookieLength: pending.cookie ? pending.cookie.length : 0,
      cookiePreview: pending.cookie ? pending.cookie.substring(0, 100) + '...' : 'none'
    });
    
    // Clean up pending session
    await env.SESSIONS.delete(pendingKey);
    console.log(`[auth/complete] Cleaned up pending session`);
    
    // Redirect with cookie
    console.log(`[auth/complete] ✓ Redirecting to ${pending.redirectTo} with session cookie`);
    
    return new Response(null, {
      status: 302,
      headers: {
        'Location': pending.redirectTo,
        'Set-Cookie': pending.cookie
      }
    });
  }
  
  return new Response('Not Found', { status: 404 });
}

/**
 * Get host ID for a domain
 */
async function getHostIdForDomain(domain, env) {
  const { getConfig } = await import('../config.js');
  const config = await getConfig(env);
  
  if (!config || !config.hosts) {
    return null;
  }
  
  const host = config.hosts.find(h => h.domain === domain);
  return host ? host.id : null;
}