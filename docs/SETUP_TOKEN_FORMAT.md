# Setup Token Format Specification

## Overview

Setup tokens have evolved from urlsafe base64 to human-readable formats. All tokens must be normalized before validation to ensure compatibility across both old and new format generations.

## Token Formats

### New Format (Readable)
- **Pattern**: `XXXXX-XXXXX-XXXXX-XXXXX-XXXXX` (25 characters with dashes, 20 without)
- **Character Set**: Uppercase alphanumeric excluding confusable characters (O, I, L, 1, 0)
- **Example**: `A2B3C-4D5E6-F7G8H-9J2K3-M4N5P`
- **Benefits**: Human-readable, easier to type and verify, reduced transcription errors

### Old Format (URLSafe)
- **Pattern**: Base64 URL-safe encoded string
- **Example**: `abc123def456ghi789`
- **Legacy**: Supported for backward compatibility only

## Normalization Algorithm

All tokens MUST be normalized before hashing for server validation:

1. **Remove all dashes** (`-`)
2. **Remove all spaces** (` `)
3. **Convert to uppercase**

### Implementation Examples

#### JavaScript/TypeScript (Cloudflare Workers)
```javascript
function normalizeSetupToken(token) {
    // Remove dashes, spaces, and convert to uppercase
    return token.replace(/-/g, '').replace(/ /g, '').toUpperCase();
}

// Usage example
const userToken = "a2b3c-4d5e6-f7g8h-9j2k3-m4n5p";
const normalized = normalizeSetupToken(userToken);
// Result: "A2B3C4D5E6F7G8H9J2K3M4N5P"

// Then hash for API call
const crypto = require('crypto');
const tokenHash = "sha512:" + crypto.createHash('sha512').update(normalized).digest('hex');
```

#### Python (Server-side)
```python
def normalize_setup_token(token):
    """Normalize token for hashing by removing dashes and converting to uppercase."""
    return token.replace('-', '').replace(' ', '').upper()

# Usage example  
user_token = "A2B3C-4D5E6-F7G8H-9J2K3-M4N5P"
normalized = normalize_setup_token(user_token)
# Result: "A2B3C4D5E6F7G8H9J2K3M4N5P"

# Hash for validation
import hashlib
token_hash = f"sha512:{hashlib.sha512(normalized.encode()).hexdigest()}"
```

#### Go (Future Kubernetes Worker)
```go
import (
    "strings"
    "crypto/sha512"
    "fmt"
)

func normalizeSetupToken(token string) string {
    // Remove dashes and spaces, convert to uppercase
    token = strings.ReplaceAll(token, "-", "")
    token = strings.ReplaceAll(token, " ", "")
    return strings.ToUpper(token)
}

// Usage example
userToken := "A2B3C-4D5E6-F7G8H-9J2K3-M4N5P"
normalized := normalizeSetupToken(userToken)
// Result: "A2B3C4D5E6F7G8H9J2K3M4N5P"

// Hash for API call
hasher := sha512.New()
hasher.Write([]byte(normalized))
tokenHash := fmt.Sprintf("sha512:%x", hasher.Sum(nil))
```

## Test Vectors

Use these test cases to validate your normalization implementation:

| Input Token | Normalized Output |
|-------------|------------------|
| `A2B3C-4D5E6-F7G8H-9J2K3-M4N5P` | `A2B3C4D5E6F7G8H9J2K3M4N5P` |
| `a2b3c-4d5e6-f7g8h-9j2k3-m4n5p` | `A2B3C4D5E6F7G8H9J2K3M4N5P` |
| `A2B3C 4D5E6 F7G8H 9J2K3 M4N5P` | `A2B3C4D5E6F7G8H9J2K3M4N5P` |
| `  A2B3C-4D5E6-F7G8H-9J2K3-M4N5P  ` | `A2B3C4D5E6F7G8H9J2K3M4N5P` |
| `A2B3C-4D5E6` | `A2B3C4D5E6` |
| `abc123def456ghi789` | `ABC123DEF456GHI789` |

## Security Requirements

### Hashing Process
1. **Always normalize BEFORE hashing**
2. **Use SHA-512** for cryptographic security
3. **Prefix with "sha512:"** for algorithm identification
4. **Never log or store plain tokens** in application logs

### Example Complete Flow
```javascript
// User input: "A2B3C-4D5E6-F7G8H-9J2K3-M4N5P"
const userInput = "A2B3C-4D5E6-F7G8H-9J2K3-M4N5P";

// Step 1: Normalize
const normalized = normalizeSetupToken(userInput);
// Result: "A2B3C4D5E6F7G8H9J2K3M4N5P"

// Step 2: Hash  
const crypto = require('crypto');
const hash = crypto.createHash('sha512').update(normalized).digest('hex');
const tokenHash = `sha512:${hash}`;

// Step 3: Send to server API
await fetch('/sunray-srvr/v1/setup-tokens/validate', {
    method: 'POST',
    headers: {
        'Authorization': `Bearer ${apiKey}`,
        'Content-Type': 'application/json'
    },
    body: JSON.stringify({
        username: 'user@example.com',
        token_hash: tokenHash,
        client_ip: '192.168.1.100',
        host_domain: 'app.example.com'
    })
});
```

## Implementation Testing

### Unit Tests
Workers should include unit tests for token normalization:

```javascript
// Example Vitest test for Cloudflare Workers
import { describe, it, expect } from 'vitest';

describe('Setup Token Normalization', () => {
    it('should normalize tokens correctly', () => {
        const testCases = [
            ['A2B3C-4D5E6-F7G8H-9J2K3-M4N5P', 'A2B3C4D5E6F7G8H9J2K3M4N5P'],
            ['a2b3c-4d5e6-f7g8h-9j2k3-m4n5p', 'A2B3C4D5E6F7G8H9J2K3M4N5P'],
            ['A2B3C 4D5E6 F7G8H 9J2K3 M4N5P', 'A2B3C4D5E6F7G8H9J2K3M4N5P'],
            ['  A2B3C-4D5E6  ', 'A2B3C4D5E6'],
        ];

        testCases.forEach(([input, expected]) => {
            expect(normalizeSetupToken(input)).toBe(expected);
        });
    });
});
```

### Integration Tests
Test end-to-end token validation with the server to ensure proper normalization:

```javascript
// Example integration test
it('should validate normalized tokens with server', async () => {
    const rawToken = "A2B3C-4D5E6-F7G8H-9J2K3-M4N5P";
    const normalized = normalizeSetupToken(rawToken);
    const tokenHash = `sha512:${crypto.createHash('sha512').update(normalized).digest('hex')}`;
    
    const response = await validateTokenWithServer({
        username: 'test@example.com',
        token_hash: tokenHash,
        client_ip: '127.0.0.1',
        host_domain: 'test.example.com'
    });
    
    expect(response.success).toBe(true);
});
```

## Common Implementation Errors

### ❌ Wrong: Hash First, Then Normalize
```javascript
// INCORRECT - Don't do this
const hash = crypto.createHash('sha512').update(token).digest('hex');
const normalized = hash.replace(/-/g, ''); // Too late!
```

### ❌ Wrong: Partial Normalization
```javascript
// INCORRECT - Missing uppercase conversion
const normalized = token.replace(/-/g, ''); // Missing .toUpperCase()
```

### ❌ Wrong: Server-Side Only Normalization
```javascript
// INCORRECT - Worker must normalize before sending
fetch('/api/validate', {
    body: JSON.stringify({ token_hash: rawToken }) // Should be normalized hash
});
```

### ✅ Correct: Normalize Before Hash
```javascript
// CORRECT
const normalized = token.replace(/-/g, '').replace(/ /g, '').toUpperCase();
const hash = crypto.createHash('sha512').update(normalized).digest('hex');
const tokenHash = `sha512:${hash}`;
```

## Migration Path

### For Existing Workers
1. **Add normalization function** to your codebase
2. **Update token hashing** to use normalization
3. **Add unit tests** for normalization logic
4. **Test with both old and new tokens** to ensure compatibility
5. **Deploy gradually** with monitoring

### Backward Compatibility
- Both old (urlsafe) and new (readable) tokens are supported
- Server handles normalization internally for validation
- Workers must normalize regardless of token format
- No breaking changes for existing integrations

## References

- **API Contract**: See `docs/API_CONTRACT.md` for complete API documentation
- **Server Implementation**: `project_addons/sunray_core/models/sunray_setup_token.py:173`
- **Test Suite**: `project_addons/sunray_core/tests/test_setup_token.py:704`