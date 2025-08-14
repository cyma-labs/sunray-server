/**
 * WebAuthn/Passkey authentication functions
 */

/**
 * Validate setup token with admin server
 */
export async function validateSetupToken(username, token, clientIp, env) {
  try {
    // Hash the token for security (using SHA-512 to match server)
    const encoder = new TextEncoder();
    const data = encoder.encode(token);
    const hashBuffer = await crypto.subtle.digest('SHA-512', data);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    const hash = hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
    // Add sha512: prefix to match server storage format
    const token_hash = `sha512:${hash}`;
    
    // Get current host domain from environment (RP_ID is the domain we're protecting)
    const hostDomain = env.RP_ID;
    
    const response = await fetch(`${env.ADMIN_API_ENDPOINT}/sunray-srvr/v1/setup-tokens/validate`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${env.ADMIN_API_KEY}`,
        'X-Worker-ID': env.WORKER_ID,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ 
        username, 
        token_hash,
        client_ip: clientIp,
        host_domain: hostDomain  // Pass the domain this Worker is protecting
      })
    });
    
    if (!response.ok) {
      console.error(`Setup token validation failed: ${response.status}`);
      return false;
    }
    
    const result = await response.json();
    return result.valid === true;
    
  } catch (error) {
    console.error('Error validating setup token:', error);
    return false;
  }
}

/**
 * Register passkey with admin server
 */
export async function registerPasskey(username, credential, clientIp, userAgent, env) {
  try {
    // Log the credential structure for debugging
    console.log('Credential structure:', JSON.stringify({
      id: credential.id,
      type: credential.type,
      hasResponse: !!credential.response,
      responseKeys: credential.response ? Object.keys(credential.response) : []
    }));
    
    // Ensure we have the required attestationObject
    if (!credential || !credential.response || !credential.response.attestationObject) {
      console.error('Missing attestationObject in credential response');
      return false;
    }
    
    // Generate a device name based on user agent
    const deviceName = userAgent.includes('Chrome') ? 'Chrome' :
                      userAgent.includes('Firefox') ? 'Firefox' :
                      userAgent.includes('Safari') ? 'Safari' :
                      userAgent.includes('Edge') ? 'Edge' :
                      'Unknown Browser';
    const timestamp = new Date().toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    const name = `${deviceName} - ${timestamp}`;
    
    // Prepare the passkey data for the server
    const passkeyData = {
      credential_id: credential.id,
      public_key: credential.response.attestationObject, // This is already base64 encoded from frontend
      name: name,
      client_ip: clientIp,
      user_agent: userAgent,
      backup_eligible: false,
      backup_state: false
    };
    
    console.log('Sending passkey data to server:', JSON.stringify({
      ...passkeyData,
      public_key: passkeyData.public_key ? `[base64 ${passkeyData.public_key.length} chars]` : 'missing'
    }));
    
    const response = await fetch(`${env.ADMIN_API_ENDPOINT}/sunray-srvr/v1/users/${username}/passkeys`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${env.ADMIN_API_KEY}`,
        'X-Worker-ID': env.WORKER_ID,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(passkeyData)
    });
    
    const responseText = await response.text();
    console.log(`Server response: ${response.status} - ${responseText}`);
    
    if (!response.ok) {
      console.error(`Passkey registration failed: ${response.status} - ${responseText}`);
      return false;
    }
    
    return true;
    
  } catch (error) {
    console.error('Error registering passkey:', error);
    return false;
  }
}

/**
 * Verify passkey authentication with admin server
 */
export async function verifyPasskey(username, credential, challenge, env) {
  try {
    // Parse credential data
    const credentialData = {
      id: credential.id,
      rawId: credential.rawId,
      type: credential.type,
      response: {
        clientDataJSON: credential.response.clientDataJSON,
        authenticatorData: credential.response.authenticatorData,
        signature: credential.response.signature,
        userHandle: credential.response.userHandle
      },
      clientExtensionResults: credential.clientExtensionResults || {}
    };
    
    const response = await fetch(`${env.ADMIN_API_ENDPOINT}/sunray-srvr/v1/auth/verify`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${env.ADMIN_API_KEY}`,
        'X-Worker-ID': env.WORKER_ID,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        username,
        credential: credentialData,
        challenge
      })
    });
    
    if (!response.ok) {
      console.error(`Passkey verification failed: ${response.status}`);
      return null;
    }
    
    const result = await response.json();
    if (result.success && result.user) {
      return result.user;
    }
    
    return null;
    
  } catch (error) {
    console.error('Error verifying passkey:', error);
    return null;
  }
}