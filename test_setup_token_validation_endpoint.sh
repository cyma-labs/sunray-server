#!/bin/bash
# Simple test script for the /setup-tokens/validate endpoint

set -e

API_URL="${APP_PRIMARY_URL}/sunray-srvr/v1/setup-tokens/validate"
API_KEY="your-api-key-here"  # Replace with actual API key
WORKER_ID="test-worker-001"

echo "========================================"
echo "Testing Setup Token Validation Endpoint"
echo "========================================"
echo "API URL: $API_URL"
echo

# Test 1: Missing API key (should fail)
echo "Test 1: Missing Authentication"
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -H "X-Worker-ID: $WORKER_ID" \
  -d '{
    "username": "test@example.com",
    "token_hash": "sha512:invalid_hash",
    "client_ip": "192.168.1.100",
    "host_domain": "test.example.com"
  }' | jq .
echo

# Test 2: Missing required fields (should fail)
echo "Test 2: Missing Required Fields"
curl -s -X POST "$API_URL" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -H "X-Worker-ID: $WORKER_ID" \
  -d '{
    "username": "test@example.com"
  }' | jq .
echo

# Test 3: Invalid token hash (should return valid: false)
echo "Test 3: Invalid Token Hash"
curl -s -X POST "$API_URL" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -H "X-Worker-ID: $WORKER_ID" \
  -d '{
    "username": "nonexistent@example.com",
    "token_hash": "sha512:invalid_hash_value",
    "client_ip": "192.168.1.100",
    "host_domain": "test.example.com"
  }' | jq .
echo

echo "========================================"
echo "Test completed!"
echo
echo "To test with a real token:"
echo "1. Create a user and setup token via admin interface"
echo "2. Get the actual API key from admin interface"
echo "3. Update API_KEY in this script"
echo "4. Replace token_hash with actual SHA-512 hash"
echo "========================================"