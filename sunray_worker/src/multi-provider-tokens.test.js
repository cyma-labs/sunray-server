import { describe, it, expect, beforeEach } from 'vitest';

// Mock the handler functions
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

describe('Multi-Provider Webhook Token Authentication', () => {
  let mockLogger;
  let hostConfig;

  beforeEach(() => {
    mockLogger = {
      debug: () => {}
    };

    // Sample host configuration with multiple webhook providers
    hostConfig = {
      domain: 'api.example.com',
      webhook_tokens: [
        {
          name: 'Shopify Webhook',
          token: 'shopify_secret_123',
          header_name: 'X-Shopify-Hmac-Sha256',
          param_name: null,
          token_source: 'header',
          is_active: true,
          expires_at: null
        },
        {
          name: 'Mirakl API',
          token: 'mirakl_key_456',
          header_name: 'Authorization',
          param_name: null,
          token_source: 'header',
          is_active: true,
          expires_at: null
        },
        {
          name: 'Legacy System',
          token: 'legacy_789',
          header_name: null,
          param_name: 'api_key',
          token_source: 'param',
          is_active: true,
          expires_at: null
        },
        {
          name: 'Flexible API',
          token: 'flex_abc',
          header_name: 'X-API-Key',
          param_name: 'key',
          token_source: 'both',
          is_active: true,
          expires_at: null
        }
      ]
    };
  });

  describe('Header-based token extraction', () => {
    it('should extract Shopify webhook token from X-Shopify-Hmac-Sha256 header', () => {
      const request = new Request('https://api.example.com/webhook/shopify', {
        headers: {
          'X-Shopify-Hmac-Sha256': 'shopify_secret_123',
          'Content-Type': 'application/json'
        }
      });

      const result = extractAndValidateTokens(request, hostConfig, mockLogger);
      
      expect(result).toBeTruthy();
      expect(result.name).toBe('Shopify Webhook');
    });

    it('should extract Mirakl API token from Authorization header', () => {
      const request = new Request('https://api.example.com/api/mirakl', {
        headers: {
          'Authorization': 'mirakl_key_456',
          'Content-Type': 'application/json'
        }
      });

      const result = extractAndValidateTokens(request, hostConfig, mockLogger);
      
      expect(result).toBeTruthy();
      expect(result.name).toBe('Mirakl API');
    });
  });

  describe('Parameter-based token extraction', () => {
    it('should extract legacy system token from URL parameter', () => {
      const request = new Request('https://api.example.com/legacy?api_key=legacy_789');

      const result = extractAndValidateTokens(request, hostConfig, mockLogger);
      
      expect(result).toBeTruthy();
      expect(result.name).toBe('Legacy System');
    });
  });

  describe('Both header and parameter support', () => {
    it('should prioritize header over parameter for "both" mode', () => {
      const request = new Request('https://api.example.com/flexible?key=wrong_token', {
        headers: {
          'X-API-Key': 'flex_abc'
        }
      });

      const result = extractAndValidateTokens(request, hostConfig, mockLogger);
      
      expect(result).toBeTruthy();
      expect(result.name).toBe('Flexible API');
    });

    it('should fall back to parameter if header is not present in "both" mode', () => {
      const request = new Request('https://api.example.com/flexible?key=flex_abc');

      const result = extractAndValidateTokens(request, hostConfig, mockLogger);
      
      expect(result).toBeTruthy();
      expect(result.name).toBe('Flexible API');
    });
  });

  describe('Token validation', () => {
    it('should reject inactive tokens', () => {
      const inactiveConfig = {
        ...hostConfig,
        webhook_tokens: [
          {
            name: 'Inactive Token',
            token: 'inactive_123',
            header_name: 'X-Inactive-Token',
            token_source: 'header',
            is_active: false,
            expires_at: null
          }
        ]
      };

      const request = new Request('https://api.example.com/test', {
        headers: {
          'X-Inactive-Token': 'inactive_123'
        }
      });

      const result = extractAndValidateTokens(request, inactiveConfig, mockLogger);
      
      expect(result).toBeNull();
    });

    it('should reject expired tokens', () => {
      const expiredConfig = {
        ...hostConfig,
        webhook_tokens: [
          {
            name: 'Expired Token',
            token: 'expired_123',
            header_name: 'X-Expired-Token',
            token_source: 'header',
            is_active: true,
            expires_at: '2023-01-01T00:00:00Z' // Past date
          }
        ]
      };

      const request = new Request('https://api.example.com/test', {
        headers: {
          'X-Expired-Token': 'expired_123'
        }
      });

      const result = extractAndValidateTokens(request, expiredConfig, mockLogger);
      
      expect(result).toBeNull();
    });

    it('should reject mismatched tokens', () => {
      const request = new Request('https://api.example.com/webhook/shopify', {
        headers: {
          'X-Shopify-Hmac-Sha256': 'wrong_token_value'
        }
      });

      const result = extractAndValidateTokens(request, hostConfig, mockLogger);
      
      expect(result).toBeNull();
    });
  });

  describe('Multiple provider scenarios', () => {
    it('should correctly identify different providers on same host', () => {
      // Test Shopify webhook
      const shopifyRequest = new Request('https://api.example.com/webhook/shopify', {
        headers: {
          'X-Shopify-Hmac-Sha256': 'shopify_secret_123'
        }
      });

      const shopifyResult = extractAndValidateTokens(shopifyRequest, hostConfig, mockLogger);
      expect(shopifyResult.name).toBe('Shopify Webhook');

      // Test Mirakl API
      const miraklRequest = new Request('https://api.example.com/api/mirakl', {
        headers: {
          'Authorization': 'mirakl_key_456'
        }
      });

      const miraklResult = extractAndValidateTokens(miraklRequest, hostConfig, mockLogger);
      expect(miraklResult.name).toBe('Mirakl API');

      // Test Legacy system
      const legacyRequest = new Request('https://api.example.com/legacy?api_key=legacy_789');

      const legacyResult = extractAndValidateTokens(legacyRequest, hostConfig, mockLogger);
      expect(legacyResult.name).toBe('Legacy System');
    });

    it('should handle requests with multiple headers but match correct token', () => {
      const request = new Request('https://api.example.com/webhook', {
        headers: {
          'X-Shopify-Hmac-Sha256': 'shopify_secret_123',
          'Authorization': 'Bearer wrong_token',
          'X-Custom-Header': 'some_value'
        }
      });

      const result = extractAndValidateTokens(request, hostConfig, mockLogger);
      
      expect(result).toBeTruthy();
      expect(result.name).toBe('Shopify Webhook');
    });
  });

  describe('Edge cases', () => {
    it('should handle empty webhook_tokens array', () => {
      const emptyConfig = {
        ...hostConfig,
        webhook_tokens: []
      };

      const request = new Request('https://api.example.com/test', {
        headers: {
          'X-Any-Header': 'any_value'
        }
      });

      const result = extractAndValidateTokens(request, emptyConfig, mockLogger);
      
      expect(result).toBeNull();
    });

    it('should handle missing webhook_tokens property', () => {
      const noTokensConfig = {
        domain: 'api.example.com'
      };

      const request = new Request('https://api.example.com/test');

      const result = extractAndValidateTokens(request, noTokensConfig, mockLogger);
      
      expect(result).toBeNull();
    });

    it('should handle requests with no headers or parameters', () => {
      const request = new Request('https://api.example.com/test');

      const result = extractAndValidateTokens(request, hostConfig, mockLogger);
      
      expect(result).toBeNull();
    });
  });
});