/**
 * Sunray Authentication Worker
 * Main entry point for Cloudflare Worker
 */

import { handleRequest } from './handler.js';
import { handleInternalRequest } from './internal.js';

// CORS configuration
const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type, Authorization, X-Sunray-Token',
  'Access-Control-Max-Age': '86400',
};

/**
 * Add CORS headers to response
 */
function addCorsHeaders(response) {
  const newHeaders = new Headers(response.headers);
  Object.entries(corsHeaders).forEach(([key, value]) => {
    newHeaders.set(key, value);
  });
  
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers: newHeaders,
  });
}

export default {
  async fetch(request, env, ctx) {
    try {
      const url = new URL(request.url);
      
      // Handle CORS preflight requests
      if (request.method === 'OPTIONS') {
        return new Response(null, {
          status: 204,
          headers: corsHeaders,
        });
      }
      
      let response;
      
      // Handle internal Sunray endpoints
      if (url.pathname.startsWith('/sunray-wrkr/v1/')) {
        response = await handleInternalRequest(request, env, ctx);
      } else {
        // Handle all other requests (proxy with auth check)
        response = await handleRequest(request, env, ctx);
      }
      
      // Add CORS headers to all responses
      return addCorsHeaders(response);
      
    } catch (error) {
      console.error('Worker error:', error);
      return addCorsHeaders(new Response('Internal Server Error', { 
        status: 500,
        headers: { 'Content-Type': 'text/plain' }
      }));
    }
  }
};