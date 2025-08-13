/**
 * Setup page HTML template
 */

export function getSetupHTML(rpName) {
  return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Setup - ${rpName}</title>
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
        
        .success {
            background: #efe;
            color: #363;
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
        
        <h1>Account Setup</h1>
        <p class="subtitle">Register your passkey to secure your account</p>
        
        <div class="error" id="error"></div>
        <div class="success" id="success"></div>
        <div class="spinner" id="spinner"></div>
        
        <form id="setupForm">
            <div class="form-group">
                <label for="username">Username</label>
                <input type="text" id="username" name="username" required autocomplete="username">
            </div>
            
            <div class="form-group">
                <label for="token">Setup Token</label>
                <input type="text" id="token" name="token" required>
            </div>
            
            <button type="submit" id="submitBtn">Create Passkey</button>
        </form>
    </div>
    
    <script>
        const form = document.getElementById('setupForm');
        const errorDiv = document.getElementById('error');
        const successDiv = document.getElementById('success');
        const spinner = document.getElementById('spinner');
        const submitBtn = document.getElementById('submitBtn');
        
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const username = document.getElementById('username').value;
            const token = document.getElementById('token').value;
            
            // Reset UI
            errorDiv.style.display = 'none';
            successDiv.style.display = 'none';
            spinner.style.display = 'block';
            submitBtn.disabled = true;
            
            try {
                // Validate token
                const validateResponse = await fetch('/sunray-wrkr/v1/setup/validate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username, token })
                });
                
                const validateResult = await validateResponse.json();
                
                if (!validateResult.success) {
                    throw new Error(validateResult.error || 'Token validation failed');
                }
                
                // Create passkey
                console.log('Creating credential with options:', validateResult.options);
                
                // Convert string fields to ArrayBuffer as required by WebAuthn
                // Helper function to convert base64 to Uint8Array
                function base64ToUint8Array(base64) {
                    const padding = '='.repeat((4 - base64.length % 4) % 4);
                    const base64Padded = (base64 + padding)
                        .replace(/\-/g, '+')
                        .replace(/_/g, '/');
                    const rawData = window.atob(base64Padded);
                    const outputArray = new Uint8Array(rawData.length);
                    for (let i = 0; i < rawData.length; ++i) {
                        outputArray[i] = rawData.charCodeAt(i);
                    }
                    return outputArray;
                }
                
                // Convert challenge from UUID string to Uint8Array
                const challengeBuffer = new TextEncoder().encode(validateResult.options.challenge);
                
                // Convert user.id from base64url to Uint8Array
                const userIdBuffer = base64ToUint8Array(validateResult.options.user.id);
                
                const publicKeyOptions = {
                    ...validateResult.options,
                    challenge: challengeBuffer,
                    user: {
                        ...validateResult.options.user,
                        id: userIdBuffer
                    }
                };
                
                console.log('Converted options:', publicKeyOptions);
                
                let credential;
                try {
                    credential = await navigator.credentials.create({
                        publicKey: publicKeyOptions
                    });
                    console.log('Credential created successfully:', credential);
                } catch (credError) {
                    console.error('Failed to create credential:', credError);
                    throw new Error('Passkey creation failed: ' + (credError.message || credError));
                }
                
                // Register with server
                const registerResponse = await fetch('/sunray-wrkr/v1/setup/register', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        username,
                        challenge: validateResult.options.challenge,
                        credential: {
                            id: credential.id,
                            rawId: btoa(String.fromCharCode(...new Uint8Array(credential.rawId))),
                            type: credential.type,
                            response: {
                                clientDataJSON: btoa(String.fromCharCode(...new Uint8Array(credential.response.clientDataJSON))),
                                attestationObject: btoa(String.fromCharCode(...new Uint8Array(credential.response.attestationObject)))
                            }
                        }
                    })
                });
                
                const registerResult = await registerResponse.json();
                
                if (!registerResult.success) {
                    throw new Error(registerResult.error || 'Registration failed');
                }
                
                successDiv.textContent = registerResult.message;
                successDiv.style.display = 'block';
                
                // Redirect after success
                setTimeout(() => {
                    window.location.href = '/sunray-wrkr/v1/auth';
                }, 2000);
                
            } catch (error) {
                errorDiv.textContent = error.message;
                errorDiv.style.display = 'block';
            } finally {
                spinner.style.display = 'none';
                submitBtn.disabled = false;
            }
        });
    </script>
</body>
</html>`;
}