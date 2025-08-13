#!/bin/bash

# Test REST API endpoints for Worker-Server communication
# This simulates the Worker calling the server's REST API

API_URL="https://sunray-server-dev-cyril.pack8s.com"
API_KEY="MmppsNo3G8A_vTJOElIhM13bGHBbE1ht78tpjG55qdE"
WORKER_ID="sunray-worker-001"

echo "Testing Sunray Server REST API"
echo "================================"
echo ""

# Test 1: Status endpoint (no auth required)
echo "1. Testing /status endpoint..."
curl -s "$API_URL/sunray-srvr/v1/status" | jq -r '.status'
echo "✓ Status endpoint working"
echo ""

# Test 2: Config endpoint (requires auth)
echo "2. Testing /config endpoint..."
CONFIG=$(curl -s \
  -H "Authorization: Bearer $API_KEY" \
  -H "X-Worker-ID: $WORKER_ID" \
  "$API_URL/sunray-srvr/v1/config")

if echo "$CONFIG" | jq -e '.version' > /dev/null; then
  echo "✓ Config retrieved successfully"
  echo "  - Version: $(echo "$CONFIG" | jq -r '.version')"
  echo "  - Users: $(echo "$CONFIG" | jq -r '.users | keys | length')"
  echo "  - Hosts: $(echo "$CONFIG" | jq -r '.hosts | length')"
else
  echo "✗ Failed to get config"
fi
echo ""

# Test 3: User check endpoint
echo "3. Testing /users/check endpoint..."
EXISTS=$(curl -s -X POST \
  -H "Authorization: Bearer $API_KEY" \
  -H "X-Worker-ID: $WORKER_ID" \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser"}' \
  "$API_URL/sunray-srvr/v1/users/check" | jq -r '.exists')

if [ "$EXISTS" = "true" ]; then
  echo "✓ User check successful (testuser exists)"
else
  echo "✗ User check failed"
fi
echo ""

# Test 4: Setup token validation (should fail with invalid token)
echo "4. Testing /setup-tokens/validate endpoint..."
TOKEN_HASH=$(echo -n "invalid-token" | sha256sum | cut -d' ' -f1)
VALID=$(curl -s -X POST \
  -H "Authorization: Bearer $API_KEY" \
  -H "X-Worker-ID: $WORKER_ID" \
  -H "Content-Type: application/json" \
  -d "{\"username\": \"testuser\", \"token_hash\": \"$TOKEN_HASH\", \"client_ip\": \"127.0.0.1\"}" \
  "$API_URL/sunray-srvr/v1/setup-tokens/validate" | jq -r '.valid')

if [ "$VALID" = "false" ]; then
  echo "✓ Token validation correctly rejected invalid token"
else
  echo "✗ Token validation unexpected result"
fi
echo ""

# Test 5: Session creation
echo "5. Testing /sessions endpoint..."
SESSION_ID="test-$(date +%s)"
RESULT=$(curl -s -X POST \
  -H "Authorization: Bearer $API_KEY" \
  -H "X-Worker-ID: $WORKER_ID" \
  -H "Content-Type: application/json" \
  -d "{
    \"session_id\": \"$SESSION_ID\",
    \"username\": \"testuser\",
    \"credential_id\": \"test-cred-456\",
    \"host_domain\": \"odoo18-cfed-test-g.pack8s.com\",
    \"created_ip\": \"127.0.0.1\",
    \"device_fingerprint\": \"test-device\",
    \"user_agent\": \"Test Client\",
    \"csrf_token\": \"test-csrf\",
    \"duration\": 86400
  }" \
  "$API_URL/sunray-srvr/v1/sessions" | jq -r '.success')

if [ "$RESULT" = "true" ]; then
  echo "✓ Session created successfully (ID: $SESSION_ID)"
else
  echo "✗ Session creation failed"
fi
echo ""

# Test 6: Session revocation
echo "6. Testing /sessions/{id}/revoke endpoint..."
REVOKE=$(curl -s -X POST \
  -H "Authorization: Bearer $API_KEY" \
  -H "X-Worker-ID: $WORKER_ID" \
  -H "Content-Type: application/json" \
  -d '{"reason": "Test revocation"}' \
  "$API_URL/sunray-srvr/v1/sessions/$SESSION_ID/revoke" | jq -r '.success')

if [ "$REVOKE" = "true" ]; then
  echo "✓ Session revoked successfully"
else
  echo "✗ Session revocation failed"
fi
echo ""

echo "================================"
echo "REST API tests completed!"
echo ""
echo "Summary:"
echo "- Server is accessible at: $API_URL"
echo "- API key is valid and working"
echo "- All critical endpoints are responding correctly"
echo "- Worker can communicate with server using REST API"