/**
 * Session management
 */

import { SignJWT, jwtVerify } from 'jose';
import { createLogger } from '../utils/logger.js';

/**
 * Create a new session
 */
export async function createSession(user, hostId, env) {
  const logger = createLogger(env);
  const sessionId = crypto.randomUUID();
  const now = Date.now();
  const ttl = parseInt(env.SESSION_TTL || '86400') * 1000; // Convert to ms
  const expiresAt = now + ttl;
  
  logger.info(`[createSession] Creating session for user ${user.username} on host ${hostId}`);
  
  const sessionData = {
    session_id: sessionId,
    user_id: user.id,
    username: user.username,
    host_id: hostId,
    created_at: now,
    expires_at: expiresAt,
    is_active: true
  };
  
  logger.debug(`[createSession] Session data:`, JSON.stringify(sessionData));
  
  // Store in KV
  const sessionKey = `session:${sessionId}`;
  logger.debug(`[createSession] Storing in KV with key: ${sessionKey}`);
  
  await env.SESSIONS.put(
    sessionKey,
    JSON.stringify(sessionData),
    { expirationTtl: parseInt(env.SESSION_TTL || '86400') }
  );
  
  logger.debug(`[createSession] Session stored successfully`);
  
  // Create JWT for cookie
  const secret = new TextEncoder().encode(env.SESSION_SECRET || 'default-secret-change-me');
  const jwt = await new SignJWT({
    sid: sessionId,
    uid: user.id,
    usr: user.username,
    hid: hostId
  })
    .setProtectedHeader({ alg: 'HS256' })
    .setIssuedAt()
    .setExpirationTime(expiresAt / 1000)
    .sign(secret);
  
  // Report session creation to admin server
  try {
    await fetch(`${env.ADMIN_API_ENDPOINT}/sunray-srvr/v1/sessions`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${env.ADMIN_API_KEY}`,
        'X-Worker-ID': env.WORKER_ID,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        session_id: sessionId,
        username: user.username,
        credential_id: user.credential_id || 'unknown',
        host_domain: hostId,
        created_ip: '127.0.0.1', // TODO: Get from request
        device_fingerprint: 'worker-session',
        user_agent: 'Cloudflare Worker',
        csrf_token: crypto.randomUUID(),
        duration: ttl / 1000 // Convert to seconds
      })
    });
  } catch (error) {
    console.error('Failed to report session to admin:', error);
  }
  
  return {
    sessionId,
    jwt,
    expiresAt
  };
}

/**
 * Validate a session
 */
export async function validateSession(sessionCookie, env) {
  console.log(`[validateSession] Starting validation, cookie length: ${sessionCookie.length}`);
  
  try {
    // Verify JWT
    const secret = new TextEncoder().encode(env.SESSION_SECRET || 'default-secret-change-me');
    console.log(`[validateSession] Using secret: ${env.SESSION_SECRET ? 'custom' : 'default'}`);
    
    const { payload } = await jwtVerify(sessionCookie, secret);
    console.log(`[validateSession] JWT verified successfully, payload:`, JSON.stringify(payload));
    
    if (!payload.sid) {
      console.log(`[validateSession] ✗ No session ID in JWT payload`);
      return null;
    }
    
    // Check session in KV
    const sessionKey = `session:${payload.sid}`;
    console.log(`[validateSession] Looking up KV key: ${sessionKey}`);
    
    const sessionData = await env.SESSIONS.get(sessionKey, { type: 'json' });
    console.log(`[validateSession] KV lookup result:`, sessionData ? 'FOUND' : 'NOT FOUND');
    
    if (!sessionData) {
      console.log(`[validateSession] ✗ Session not found in KV`);
      return null;
    }
    
    console.log(`[validateSession] Session data:`, JSON.stringify({
      session_id: sessionData.session_id,
      username: sessionData.username,
      host_id: sessionData.host_id,
      is_active: sessionData.is_active,
      expires_at: sessionData.expires_at,
      created_at: sessionData.created_at
    }));
    
    // Check if session is active and not expired
    if (!sessionData.is_active) {
      console.log(`[validateSession] ✗ Session is not active`);
      return null;
    }
    
    const now = Date.now();
    if (sessionData.expires_at < now) {
      console.log(`[validateSession] ✗ Session expired (expires_at: ${sessionData.expires_at}, now: ${now})`);
      // Session expired, clean up
      await env.SESSIONS.delete(sessionKey);
      return null;
    }
    
    // Check revocation list
    const revoked = await env.SESSIONS.get(`revoked:${sessionData.user_id}`);
    if (revoked) {
      const revokedTime = parseInt(revoked);
      if (sessionData.created_at < revokedTime) {
        // Session was created before revocation
        await env.SESSIONS.delete(`session:${payload.sid}`);
        return null;
      }
    }
    
    console.log(`[validateSession] ✓ Session is valid and active`);
    return sessionData;
    
  } catch (error) {
    console.error('[validateSession] Error during validation:', error.message);
    console.error('[validateSession] Error stack:', error.stack);
    return null;
  }
}

/**
 * Revoke a session
 */
export async function revokeSession(sessionId, env) {
  await env.SESSIONS.delete(`session:${sessionId}`);
  
  // Report to admin server
  try {
    await fetch(`${env.ADMIN_API_ENDPOINT}/sunray-srvr/v1/sessions/${sessionId}/revoke`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${env.ADMIN_API_KEY}`,
        'X-Worker-ID': env.WORKER_ID,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        reason: 'User logout'
      })
    });
  } catch (error) {
    console.error('Failed to report session revocation:', error);
  }
}

/**
 * Revoke all sessions for a user
 */
export async function revokeUserSessions(userId, env) {
  // Add to revocation list with current timestamp
  await env.SESSIONS.put(
    `revoked:${userId}`,
    Date.now().toString(),
    { expirationTtl: parseInt(env.SESSION_TTL || '86400') }
  );
  
  // Note: Actual session cleanup happens during validation
}

/**
 * Create session cookie
 */
export function createSessionCookie(jwt, expiresAt, domain) {
  const expires = new Date(expiresAt).toUTCString();
  const secure = domain !== 'localhost';
  
  const cookieParts = [
    `sunray_session=${jwt}`,
    `Domain=${domain}`,
    `Path=/`,
    `Expires=${expires}`,
    'HttpOnly',
    secure ? 'Secure' : '',
    'SameSite=Lax'
  ].filter(Boolean);
  
  const cookie = cookieParts.join('; ');
  
  console.log(`[createSessionCookie] Created cookie:`, {
    domain,
    expires,
    secure,
    jwtLength: jwt.length,
    cookieLength: cookie.length,
    preview: cookie.substring(0, 100) + '...'
  });
  
  return cookie;
}

/**
 * Create logout cookie (clears session)
 */
export function createLogoutCookie(domain) {
  const secure = domain !== 'localhost';
  
  return [
    'sunray_session=',
    `Domain=${domain}`,
    'Path=/',
    'Expires=Thu, 01 Jan 1970 00:00:00 GMT',
    'HttpOnly',
    secure ? 'Secure' : '',
    'SameSite=Lax'
  ].filter(Boolean).join('; ');
}