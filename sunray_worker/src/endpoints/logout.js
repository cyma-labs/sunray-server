/**
 * Logout endpoint - handles session termination
 */

import { revokeSession, createLogoutCookie } from '../auth/session.js';

export async function handleLogout(request, env, ctx) {
  const url = new URL(request.url);
  const returnTo = url.searchParams.get('return_to') || '/';
  
  // Get session cookie
  const cookieHeader = request.headers.get('Cookie');
  if (cookieHeader) {
    const cookies = cookieHeader.split(';').map(c => c.trim());
    for (const cookie of cookies) {
      const [key, value] = cookie.split('=');
      if (key === 'sunray_session' && value) {
        // Extract session ID from JWT (would need to decode)
        try {
          const { jwtVerify } = await import('jose');
          const secret = new TextEncoder().encode(env.SESSION_SECRET || 'default-secret-change-me');
          const { payload } = await jwtVerify(value, secret);
          
          if (payload.sid) {
            await revokeSession(payload.sid, env);
          }
        } catch (error) {
          console.error('Failed to revoke session:', error);
        }
      }
    }
  }
  
  // Clear session cookie
  const cookie = createLogoutCookie(env.RP_ID);
  
  // Redirect to return URL or home
  return Response.redirect(returnTo, 302, {
    headers: {
      'Set-Cookie': cookie
    }
  });
}