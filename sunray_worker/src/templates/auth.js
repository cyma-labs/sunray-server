/**
 * Authentication page HTML template
 */

export function getAuthHTML(rpName, returnTo = '/') {
  return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sign In - ${rpName}</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        
        .container {
            background: white;
            border-radius: 12px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            padding: 40px;
            width: 100%;
            max-width: 400px;
        }
        
        .logo {
            text-align: center;
            margin-bottom: 30px;
        }
        
        .logo svg {
            width: 60px;
            height: 60px;
        }
        
        h1 {
            color: #333;
            font-size: 24px;
            margin-bottom: 10px;
            text-align: center;
        }
        
        .subtitle {
            color: #666;
            text-align: center;
            margin-bottom: 30px;
        }
        
        .form-group {
            margin-bottom: 20px;
        }
        
        label {
            display: block;
            color: #555;
            font-size: 14px;
            margin-bottom: 5px;
        }
        
        input {
            width: 100%;
            padding: 12px;
            border: 1px solid #ddd;
            border-radius: 6px;
            font-size: 16px;
            transition: border-color 0.3s;
        }
        
        input:focus {
            outline: none;
            border-color: #667eea;
        }
        
        button {
            width: 100%;
            padding: 12px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 6px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s;
        }
        
        button:hover {
            transform: translateY(-1px);
        }
        
        button:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        
        .error {
            background: #fee;
            color: #c33;
            padding: 10px;
            border-radius: 6px;
            margin-bottom: 20px;
            display: none;
        }
        
        .info {
            background: #e7f3ff;
            color: #0051cc;
            padding: 10px;
            border-radius: 6px;
            margin-bottom: 20px;
            display: none;
        }
        
        .spinner {
            display: none;
            width: 20px;
            height: 20px;
            border: 2px solid #f3f3f3;
            border-top: 2px solid #667eea;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin: 0 auto 20px;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        .setup-link {
            text-align: center;
            margin-top: 20px;
            font-size: 14px;
        }
        
        .setup-link a {
            color: #667eea;
            text-decoration: none;
        }
        
        .setup-link a:hover {
            text-decoration: underline;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="logo">
            <svg viewBox="0 0 60 60" xmlns="http://www.w3.org/2000/svg">
                <circle cx="30" cy="30" r="28" fill="#667eea" opacity="0.1"/>
                <path d="M30 10 L30 20 M30 40 L30 50 M10 30 L20 30 M40 30 L50 30" 
                      stroke="#667eea" stroke-width="3" stroke-linecap="round"/>
                <circle cx="30" cy="30" r="8" fill="#764ba2"/>
            </svg>
        </div>
        
        <h1>Sign In</h1>
        <p class="subtitle">Use your passkey to authenticate</p>
        
        <div class="error" id="error"></div>
        <div class="info" id="info"></div>
        <div class="spinner" id="spinner"></div>
        
        <form id="authForm">
            <div class="form-group">
                <label for="username">Username</label>
                <input type="text" id="username" name="username" required autocomplete="username webauthn">
            </div>
            
            <button type="submit" id="submitBtn">Sign In with Passkey</button>
        </form>
        
        <div class="setup-link">
            <a href="/sunray-wrkr/v1/setup">Need to register? Set up your account</a>
        </div>
    </div>
    
    <script>
        const form = document.getElementById('authForm');
        const errorDiv = document.getElementById('error');
        const infoDiv = document.getElementById('info');
        const spinner = document.getElementById('spinner');
        const submitBtn = document.getElementById('submitBtn');
        const returnTo = '${returnTo.replace(/'/g, "\\'")}';
        
        // Check for WebAuthn support
        if (!window.PublicKeyCredential) {
            errorDiv.textContent = 'Your browser does not support passkeys. Please use a modern browser.';
            errorDiv.style.display = 'block';
            submitBtn.disabled = true;
        }
        
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const username = document.getElementById('username').value;
            
            // Reset UI
            errorDiv.style.display = 'none';
            infoDiv.style.display = 'none';
            spinner.style.display = 'block';
            submitBtn.disabled = true;
            
            try {
                // Get authentication challenge
                infoDiv.textContent = 'Getting authentication challenge...';
                infoDiv.style.display = 'block';
                
                const challengeResponse = await fetch('/sunray-wrkr/v1/auth/challenge', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username })
                });
                
                const challengeResult = await challengeResponse.json();
                
                if (!challengeResult.success) {
                    throw new Error(challengeResult.error || 'Failed to get challenge');
                }
                
                infoDiv.textContent = 'Authenticating with passkey...';
                
                // Authenticate with passkey
                const credential = await navigator.credentials.get({
                    publicKey: {
                        challenge: new TextEncoder().encode(challengeResult.options.challenge),
                        rpId: challengeResult.options.rpId,
                        userVerification: challengeResult.options.userVerification,
                        timeout: challengeResult.options.timeout
                    }
                });
                
                infoDiv.textContent = 'Verifying authentication...';
                
                // Verify with server
                const verifyResponse = await fetch('/sunray-wrkr/v1/auth/verify', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        username,
                        challenge: challengeResult.options.challenge,
                        credential: {
                            id: credential.id,
                            rawId: btoa(String.fromCharCode(...new Uint8Array(credential.rawId))),
                            type: credential.type,
                            response: {
                                clientDataJSON: btoa(String.fromCharCode(...new Uint8Array(credential.response.clientDataJSON))),
                                authenticatorData: btoa(String.fromCharCode(...new Uint8Array(credential.response.authenticatorData))),
                                signature: btoa(String.fromCharCode(...new Uint8Array(credential.response.signature))),
                                userHandle: credential.response.userHandle ? 
                                    btoa(String.fromCharCode(...new Uint8Array(credential.response.userHandle))) : null
                            }
                        },
                        returnTo
                    })
                });
                
                const verifyResult = await verifyResponse.json();
                
                if (!verifyResult.success) {
                    throw new Error(verifyResult.error || 'Authentication failed');
                }
                
                infoDiv.textContent = 'Success! Redirecting...';
                
                // Redirect to completion endpoint to set cookie
                window.location.href = '/sunray-wrkr/v1/auth/complete?sid=' + verifyResult.sessionId;
                
            } catch (error) {
                console.error('Authentication error:', error);
                errorDiv.textContent = error.message || 'Authentication failed';
                errorDiv.style.display = 'block';
                infoDiv.style.display = 'none';
            } finally {
                spinner.style.display = 'none';
                submitBtn.disabled = false;
            }
        });
        
        // Auto-fill username if available
        if (window.PublicKeyCredential && 
            window.PublicKeyCredential.isConditionalMediationAvailable) {
            window.PublicKeyCredential.isConditionalMediationAvailable().then(available => {
                if (available) {
                    // Enable conditional UI
                    console.log('Conditional mediation available');
                }
            });
        }
    </script>
</body>
</html>`;
}