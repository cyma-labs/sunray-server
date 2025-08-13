/**
 * Local testing script for Sunray Worker
 */

import { describe, it, expect } from 'vitest';
import { handleRequest } from '../src/handler.js';

// Mock environment
const mockEnv = {
  ADMIN_API_ENDPOINT: 'http://localhost:8069',
  ADMIN_API_KEY: 'test-api-key',
  SESSION_SECRET: 'test-secret',
  RP_ID: 'localhost',
  RP_NAME: 'Test Sunray',
  WORKER_ID: 'test-worker',
  SESSION_TTL: '3600',
  CHALLENGE_TTL: '300',
  CONFIG_CACHE: {
    get: async (key) => null,
    put: async (key, value, options) => {},
    delete: async (key) => {}
  },
  SESSIONS: {
    get: async (key) => null,
    put: async (key, value, options) => {},
    delete: async (key) => {}
  },
  CHALLENGES: {
    get: async (key) => null,
    put: async (key, value, options) => {},
    delete: async (key) => {}
  }
};

describe('Worker Request Handling', () => {
  it('should redirect unauthenticated requests to login', async () => {
    const request = new Request('https://localhost/protected');
    const response = await handleRequest(request, mockEnv, {});
    
    expect(response.status).toBe(302);
    expect(response.headers.get('location')).toContain('/sunray-wrkr/v1/auth');
  });
  
  it('should serve setup page', async () => {
    const request = new Request('https://localhost/sunray-wrkr/v1/setup');
    const response = await handleRequest(request, mockEnv, {});
    
    expect(response.status).toBe(200);
    expect(response.headers.get('content-type')).toContain('text/html');
  });
  
  it('should serve auth page', async () => {
    const request = new Request('https://localhost/sunray-wrkr/v1/auth');
    const response = await handleRequest(request, mockEnv, {});
    
    expect(response.status).toBe(200);
    expect(response.headers.get('content-type')).toContain('text/html');
  });
  
  it('should allow CIDR bypass', async () => {
    // Mock config with CIDR whitelist
    mockEnv.CONFIG_CACHE.get = async (key) => {
      if (key === 'config') {
        return JSON.stringify({
          cidr_whitelist: ['10.0.0.0/8'],
          public_url_patterns: [],
          hosts: []
        });
      }
      return null;
    };
    
    const request = new Request('https://localhost/protected', {
      headers: {
        'CF-Connecting-IP': '10.0.0.1'
      }
    });
    
    const response = await handleRequest(request, mockEnv, {});
    
    // Should pass through (would normally proxy to origin)
    expect(response.status).not.toBe(302);
  });
});

describe('WebAuthn Flow', () => {
  it('should validate setup token', async () => {
    const request = new Request('https://localhost/sunray-wrkr/v1/setup/validate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        username: 'testuser',
        token: 'test-token'
      })
    });
    
    // This would normally call the admin API
    // For testing, we'd need to mock the fetch calls
    const response = await handleRequest(request, mockEnv, {});
    
    expect(response.status).toBeLessThan(500); // Not a server error
  });
});

describe('Session Management', () => {
  it('should create session cookie', async () => {
    // Test session creation would go here
    // This requires mocking the WebAuthn flow
  });
  
  it('should validate session cookie', async () => {
    // Test session validation would go here
  });
  
  it('should handle logout', async () => {
    const request = new Request('https://localhost/sunray-wrkr/v1/auth/logout');
    const response = await handleRequest(request, mockEnv, {});
    
    expect(response.status).toBe(302);
    expect(response.headers.get('set-cookie')).toContain('Max-Age=0');
  });
});