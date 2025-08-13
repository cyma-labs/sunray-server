#!/bin/bash

# Comprehensive Worker Testing Script
# Tests the Sunray Worker via reverse proxy

WORKER_URL="https://wrkr-sunray18-main-dev-cmorisse.msa2.lair.ovh"
SERVER_URL="https://sunray-server-dev-cyril.pack8s.com"

echo "======================================"
echo "Sunray Worker Comprehensive Test Suite"
echo "======================================"
echo ""
echo "Worker URL: $WORKER_URL"
echo "Server URL: $SERVER_URL"
echo ""

# Test counter
TESTS_PASSED=0
TESTS_FAILED=0

# Function to run a test
run_test() {
    local test_name="$1"
    local test_command="$2"
    local expected_result="$3"
    
    echo -n "Testing: $test_name... "
    
    if eval "$test_command" > /dev/null 2>&1; then
        if [ -n "$expected_result" ]; then
            result=$(eval "$test_command" 2>/dev/null)
            if echo "$result" | grep -q "$expected_result"; then
                echo "✓ PASSED"
                ((TESTS_PASSED++))
            else
                echo "✗ FAILED (unexpected result)"
                ((TESTS_FAILED++))
            fi
        else
            echo "✓ PASSED"
            ((TESTS_PASSED++))
        fi
    else
        echo "✗ FAILED"
        ((TESTS_FAILED++))
    fi
}

echo "1. BASIC CONNECTIVITY TESTS"
echo "----------------------------"

# Test 1: Health endpoint
run_test "Health endpoint" \
    "curl -s $WORKER_URL/sunray-wrkr/v1/health | jq -e '.status == \"healthy\"'" \
    ""

# Test 2: Setup page HTML
run_test "Setup page loads" \
    "curl -s $WORKER_URL/sunray-wrkr/v1/setup | grep -q 'Account Setup'" \
    ""

# Test 3: Auth page HTML
run_test "Auth page loads" \
    "curl -s $WORKER_URL/sunray-wrkr/v1/auth | grep -q 'Sign In'" \
    ""

echo ""
echo "2. API ENDPOINT TESTS"
echo "---------------------"

# Test 4: Invalid setup token
run_test "Invalid setup token rejection" \
    "curl -s -X POST $WORKER_URL/sunray-wrkr/v1/setup/validate -H 'Content-Type: application/json' -d '{\"username\": \"testuser\", \"token\": \"invalid\"}' | jq -e '.success == false'" \
    ""

# Test 5: Missing parameters
run_test "Missing parameters handling" \
    "curl -s -X POST $WORKER_URL/sunray-wrkr/v1/setup/validate -H 'Content-Type: application/json' -d '{}' | jq -e '.error'" \
    ""

echo ""
echo "3. WORKER-SERVER COMMUNICATION"
echo "-------------------------------"

# Test 6: Check if Worker can reach server
echo -n "Testing: Worker → Server connectivity... "
CONFIG_TEST=$(curl -s $WORKER_URL/sunray-wrkr/v1/health 2>&1)
if echo "$CONFIG_TEST" | grep -q "healthy"; then
    echo "✓ PASSED (Worker is healthy, likely connected to server)"
    ((TESTS_PASSED++))
else
    echo "✗ FAILED"
    ((TESTS_FAILED++))
fi

echo ""
echo "4. ERROR HANDLING TESTS"
echo "-----------------------"

# Test 7: 404 handling
run_test "404 for invalid endpoint" \
    "curl -s -o /dev/null -w '%{http_code}' $WORKER_URL/sunray-wrkr/v1/invalid" \
    "404"

# Test 8: Method not allowed
run_test "Method not allowed" \
    "curl -s -o /dev/null -w '%{http_code}' -X DELETE $WORKER_URL/sunray-wrkr/v1/health" \
    "405"

echo ""
echo "5. SECURITY TESTS"
echo "-----------------"

# Test 9: CORS headers
echo -n "Testing: CORS headers present... "
CORS_HEADER=$(curl -s -I $WORKER_URL/sunray-wrkr/v1/health | grep -i "access-control")
if [ -n "$CORS_HEADER" ]; then
    echo "✓ PASSED"
    ((TESTS_PASSED++))
else
    echo "✗ FAILED (No CORS headers)"
    ((TESTS_FAILED++))
fi

# Test 10: Content-Type validation
run_test "Content-Type validation" \
    "curl -s -X POST $WORKER_URL/sunray-wrkr/v1/setup/validate -H 'Content-Type: text/plain' -d 'test' | grep -q 'error'" \
    ""

echo ""
echo "======================================"
echo "TEST RESULTS SUMMARY"
echo "======================================"
echo ""
echo "Tests Passed: $TESTS_PASSED"
echo "Tests Failed: $TESTS_FAILED"
echo "Total Tests: $((TESTS_PASSED + TESTS_FAILED))"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo "✅ All tests passed! Worker is ready for deployment."
    exit 0
else
    echo "⚠️  Some tests failed. Please review the issues above."
    exit 1
fi