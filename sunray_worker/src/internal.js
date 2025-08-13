/**
 * Internal Sunray endpoints handler
 * Handles authentication UI and WebAuthn flows
 */

import { handleSetup } from './endpoints/setup.js';
import { handleAuth } from './endpoints/auth.js';
import { handleLogout } from './endpoints/logout.js';

export async function handleInternalRequest(request, env, ctx) {
  const url = new URL(request.url);
  const path = url.pathname;
  
  // Route to appropriate handler
  if (path.startsWith('/sunray-wrkr/v1/setup')) {
    return handleSetup(request, env, ctx);
  }
  
  if (path.startsWith('/sunray-wrkr/v1/auth')) {
    return handleAuth(request, env, ctx);
  }
  
  if (path === '/sunray-wrkr/v1/logout') {
    return handleLogout(request, env, ctx);
  }
  
  // Health check endpoint
  if (path === '/sunray-wrkr/v1/health') {
    // Only allow GET requests
    if (request.method !== 'GET' && request.method !== 'HEAD') {
      return new Response('Method Not Allowed', { 
        status: 405,
        headers: { 
          'Content-Type': 'text/plain',
          'Allow': 'GET, HEAD'
        }
      });
    }
    
    return new Response(JSON.stringify({
      status: 'healthy',
      worker_id: env.WORKER_ID,
      timestamp: new Date().toISOString()
    }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' }
    });
  }
  
  // Cache invalidation endpoint (called by admin server)
  if (path === '/sunray-wrkr/v1/cache/invalidate' && request.method === 'POST') {
    // Verify admin API key
    const authHeader = request.headers.get('Authorization');
    if (authHeader !== `Bearer ${env.ADMIN_API_KEY}`) {
      return new Response('Unauthorized', { status: 401 });
    }
    
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
    
    const { clearConfig } = await import('./config.js');
    await clearConfig(env);
    
    const body = await request.json().catch(() => ({}));
    if (body.user_id) {
      // Revoke user sessions
      const { revokeUserSessions } = await import('./auth/session.js');
      await revokeUserSessions(body.user_id, env);
    }
    
    return new Response(JSON.stringify({ success: true }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' }
    });
  }
  
  return new Response('Not Found', { status: 404 });
}