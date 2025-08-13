/**
 * Configuration management
 * Fetches and caches configuration from admin server
 */

export async function getConfig(env, forceRefresh = false) {
  const cacheKey = `config:${env.WORKER_ID}`;
  
  // Check cache first (unless forced refresh)
  if (!forceRefresh) {
    const cached = await env.CONFIG_CACHE.get(cacheKey, { type: 'json' });
    if (cached) {
      // Check if cache is still valid
      const cacheAge = Date.now() - (cached.timestamp || 0);
      const maxAge = parseInt(env.CACHE_TTL || '300') * 1000; // Convert to ms
      
      if (cacheAge < maxAge) {
        return cached.data;
      }
    }
  }
  
  // Fetch fresh configuration from admin server
  try {
    const response = await fetch(`${env.ADMIN_API_ENDPOINT}/sunray-srvr/v1/config`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${env.ADMIN_API_KEY}`,
        'X-Worker-ID': env.WORKER_ID,
        'Content-Type': 'application/json'
      }
    });
    
    if (!response.ok) {
      console.error(`Failed to fetch config: ${response.status} ${response.statusText}`);
      
      // Try to use stale cache if available
      const staleCache = await env.CONFIG_CACHE.get(cacheKey, { type: 'json' });
      if (staleCache && staleCache.data) {
        console.log('Using stale cache due to fetch failure');
        return staleCache.data;
      }
      
      return null;
    }
    
    const config = await response.json();
    
    // Cache the configuration
    const cacheData = {
      timestamp: Date.now(),
      data: config
    };
    
    // Store with TTL
    const ttl = parseInt(env.CACHE_TTL || '300');
    await env.CONFIG_CACHE.put(cacheKey, JSON.stringify(cacheData), {
      expirationTtl: ttl
    });
    
    return config;
    
  } catch (error) {
    console.error('Error fetching config:', error);
    
    // Try to use stale cache if available
    const staleCache = await env.CONFIG_CACHE.get(cacheKey, { type: 'json' });
    if (staleCache && staleCache.data) {
      console.log('Using stale cache due to error');
      return staleCache.data;
    }
    
    return null;
  }
}

/**
 * Clear configuration cache
 */
export async function clearConfigCache(env) {
  const cacheKey = `config:${env.WORKER_ID}`;
  await env.CONFIG_CACHE.delete(cacheKey);
  console.log('Configuration cache cleared');
}

/**
 * Get user configuration from admin server
 */
export async function getUserConfig(username, env) {
  try {
    const response = await fetch(`${env.ADMIN_API_ENDPOINT}/sunray-srvr/v1/users/${username}`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${env.ADMIN_API_KEY}`,
        'X-Worker-ID': env.WORKER_ID,
        'Content-Type': 'application/json'
      }
    });
    
    if (!response.ok) {
      if (response.status === 404) {
        return null; // User not found
      }
      console.error(`Failed to fetch user config: ${response.status}`);
      return null;
    }
    
    return await response.json();
    
  } catch (error) {
    console.error('Error fetching user config:', error);
    return null;
  }
}

/**
 * Check if user exists
 */
export async function checkUserExists(username, env) {
  try {
    const response = await fetch(`${env.ADMIN_API_ENDPOINT}/sunray-srvr/v1/users/check`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${env.ADMIN_API_KEY}`,
        'X-Worker-ID': env.WORKER_ID,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ username })
    });
    
    if (!response.ok) {
      console.error(`Failed to check user: ${response.status}`);
      return false;
    }
    
    const result = await response.json();
    return result.exists === true;
    
  } catch (error) {
    console.error('Error checking user:', error);
    return false;
  }
}