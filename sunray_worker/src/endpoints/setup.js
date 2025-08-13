/**
 * Setup endpoint - handles new user registration
 */

import { getSetupHTML } from '../templates/setup.js';
import { validateSetupToken, registerPasskey } from '../auth/webauthn.js';

export async function handleSetup(request, env, ctx) {
  const url = new URL(request.url);
  const path = url.pathname;
  
  // GET /sunray-wrkr/v1/setup - Show setup form
  if (request.method === 'GET' && path === '/sunray-wrkr/v1/setup') {
    const html = getSetupHTML(env.RP_NAME);
    return new Response(html, {
      status: 200,
      headers: { 'Content-Type': 'text/html; charset=utf-8' }
    });
  }
  
  // POST /sunray-wrkr/v1/setup/validate - Validate setup token
  if (request.method === 'POST' && path === '/sunray-wrkr/v1/setup/validate') {
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
    const { username, token } = body;
    
    if (!username || !token) {
      return new Response(JSON.stringify({
        success: false,
        error: 'Username and token are required'
      }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' }
      });
    }
    
    // Get client IP from request headers
    const clientIp = request.headers.get('CF-Connecting-IP') || 
                     request.headers.get('X-Forwarded-For') || 
                     '127.0.0.1';
    
    // Validate token with admin server
    const isValid = await validateSetupToken(username, token, clientIp, env);
    
    if (!isValid) {
      return new Response(JSON.stringify({
        success: false,
        error: 'Invalid or expired setup token'
      }), {
        status: 401,
        headers: { 'Content-Type': 'application/json' }
      });
    }
    
    // Generate registration challenge
    const challenge = crypto.randomUUID();
    
    // Store challenge temporarily
    await env.CHALLENGES.put(
      `setup:${username}:${challenge}`,
      JSON.stringify({
        username,
        token,
        timestamp: Date.now()
      }),
      { expirationTtl: parseInt(env.CHALLENGE_TTL || '300') }
    );
    
    // Return WebAuthn registration options
    return new Response(JSON.stringify({
      success: true,
      options: {
        challenge,
        rp: {
          name: env.RP_NAME,
          id: env.RP_ID
        },
        user: {
          // user.id must be a base64url encoded string for the browser API
          id: btoa(username).replace(/\+/g, '-').replace(/\//g, '_').replace(/=/g, ''),
          name: username,
          displayName: username
        },
        pubKeyCredParams: [
          { alg: -7, type: 'public-key' },   // ES256
          { alg: -257, type: 'public-key' }  // RS256
        ],
        authenticatorSelection: {
          authenticatorAttachment: 'platform',
          requireResidentKey: true,
          residentKey: 'required',
          userVerification: 'required'
        },
        timeout: 60000,
        attestation: 'none'
      }
    }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' }
    });
  }
  
  // POST /sunray-wrkr/v1/setup/register - Complete registration
  if (request.method === 'POST' && path === '/sunray-wrkr/v1/setup/register') {
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
    const { username, challenge, credential } = body;
    
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
      `setup:${username}:${challenge}`,
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
    await env.CHALLENGES.delete(`setup:${username}:${challenge}`);
    
    // Get client info from request
    const clientIp = request.headers.get('CF-Connecting-IP') || 
                     request.headers.get('X-Forwarded-For') || 
                     '127.0.0.1';
    const userAgent = request.headers.get('User-Agent') || 'Unknown';
    
    // Register passkey with admin server
    const registered = await registerPasskey(username, credential, clientIp, userAgent, env);
    
    if (!registered) {
      return new Response(JSON.stringify({
        success: false,
        error: 'Failed to register passkey'
      }), {
        status: 500,
        headers: { 'Content-Type': 'application/json' }
      });
    }
    
    // Consume the setup token
    try {
      await fetch(`${env.ADMIN_API_ENDPOINT}/sunray-srvr/v1/setup-tokens/consume`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${env.ADMIN_API_KEY}`,
          'X-Worker-ID': env.WORKER_ID,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          username,
          token: challengeData.token
        })
      });
    } catch (error) {
      console.error('Failed to consume setup token:', error);
    }
    
    return new Response(JSON.stringify({
      success: true,
      message: 'Registration successful! You can now sign in.'
    }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' }
    });
  }
  
  return new Response('Not Found', { status: 404 });
}