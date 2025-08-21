#!/bin/bash
# Sunray REST API Test Suite
# External API testing for Worker-Server communication
# Tests the server's REST API from an external perspective (as a worker would)

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
LOG_DIR="${PROJECT_ROOT}/test_logs_and_coverage"

# Create log directory if it doesn't exist
mkdir -p "${LOG_DIR}"

# Default values - can be overridden by environment variables or CLI args
API_URL="${SUNRAY_API_URL:-}"
API_KEY="${SUNRAY_API_KEY:-}"
WORKER_ID="${SUNRAY_WORKER_ID:-sunray-worker-001}"
TEST_USERNAME="${SUNRAY_TEST_USERNAME:-testuser}"

# Test options
VERBOSE=false
SPECIFIC_TEST=""
SKIP_AUTH=false
JSON_OUTPUT=false
LOG_FILE="${LOG_DIR}/rest_api_test_$(date +%Y%m%d_%H%M%S).log"

# Test counters
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

# Usage function
usage() {
    echo -e "${BLUE}Sunray REST API Test Suite${NC}"
    echo ""
    echo "Tests the Sunray Server REST API from an external perspective."
    echo "This simulates how a Worker communicates with the Server."
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -h, --help              Show this help message"
    echo "  -u, --url URL           API URL (or set SUNRAY_API_URL env var)"
    echo "  -k, --key KEY           API key (or set SUNRAY_API_KEY env var)"
    echo "  -w, --worker ID         Worker ID (default: sunray-worker-001)"
    echo "  -t, --test TEST         Run specific test (status|config|user|token|session|revoke)"
    echo "  -v, --verbose           Enable verbose output with detailed responses"
    echo "  --skip-auth             Skip tests that require authentication"
    echo "  --json                  Output results in JSON format"
    echo "  --username USERNAME     Test username (default: testuser)"
    echo "  --list-tests            List all available tests"
    echo ""
    echo "Environment Variables:"
    echo "  SUNRAY_API_URL          Server API URL"
    echo "  SUNRAY_API_KEY          API authentication key"
    echo "  SUNRAY_WORKER_ID        Worker identifier"
    echo "  SUNRAY_TEST_USERNAME    Username for testing"
    echo ""
    echo "Examples:"
    echo "  # Run all tests with environment variables"
    echo "  export SUNRAY_API_URL=\"https://sunray.example.com\""
    echo "  export SUNRAY_API_KEY=\"your-api-key-here\""
    echo "  $0"
    echo ""
    echo "  # Run specific test with CLI arguments"
    echo "  $0 --url https://sunray.example.com --key YOUR_KEY --test config"
    echo ""
    echo "  # Run without auth tests"
    echo "  $0 --url https://sunray.example.com --skip-auth"
    echo ""
    echo "  # Verbose mode with specific user"
    echo "  $0 -v --username admin"
    echo ""
}

# Print colored message
print_msg() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}" | tee -a "$LOG_FILE"
}

# Print section header
print_header() {
    echo "" | tee -a "$LOG_FILE"
    echo -e "${CYAN}================================================${NC}" | tee -a "$LOG_FILE"
    echo -e "${CYAN} $1${NC}" | tee -a "$LOG_FILE"
    echo -e "${CYAN}================================================${NC}" | tee -a "$LOG_FILE"
    echo "" | tee -a "$LOG_FILE"
}

# List available tests
list_tests() {
    print_header "Available Tests"
    echo "  status   - Test /status endpoint (no auth required)"
    echo "  config   - Test /config endpoint (auth required)"
    echo "  user     - Test /users/check endpoint (auth required)"
    echo "  token    - Test /setup-tokens/validate endpoint (auth required)"
    echo "  session  - Test /sessions creation endpoint (auth required)"
    echo "  revoke   - Test /sessions/{id}/revoke endpoint (auth required)"
    echo ""
    echo "Run all tests by not specifying --test option"
    echo "Run specific test with: $0 --test <test-name>"
}

# Check prerequisites
check_prerequisites() {
    print_header "Checking Prerequisites"
    
    # Check for required tools
    if ! command -v curl &> /dev/null; then
        print_msg $RED "✗ curl is not installed"
        exit 1
    fi
    
    if ! command -v jq &> /dev/null; then
        print_msg $YELLOW "⚠ jq is not installed (JSON parsing will be limited)"
    fi
    
    # Check API URL
    if [[ -z "$API_URL" ]]; then
        print_msg $RED "✗ API URL not specified. Use --url or set SUNRAY_API_URL"
        echo ""
        usage
        exit 1
    fi
    
    # Check API key for auth tests
    if [[ "$SKIP_AUTH" == "false" && -z "$API_KEY" ]]; then
        print_msg $YELLOW "⚠ API key not specified. Auth tests will be skipped."
        print_msg $YELLOW "  Use --key or set SUNRAY_API_KEY to run all tests"
        SKIP_AUTH=true
    fi
    
    print_msg $GREEN "✓ Prerequisites check passed"
    print_msg $BLUE "  API URL: $API_URL"
    print_msg $BLUE "  Worker ID: $WORKER_ID"
    if [[ -n "$API_KEY" ]]; then
        print_msg $BLUE "  API Key: ***${API_KEY: -8}"  # Show only last 8 chars
    fi
}

# Test result tracking
record_test_result() {
    local test_name=$1
    local success=$2
    local message=$3
    
    TESTS_RUN=$((TESTS_RUN + 1))
    
    if [[ "$success" == "true" ]]; then
        TESTS_PASSED=$((TESTS_PASSED + 1))
        print_msg $GREEN "✓ $test_name: $message"
    else
        TESTS_FAILED=$((TESTS_FAILED + 1))
        print_msg $RED "✗ $test_name: $message"
    fi
}

# Test 1: Status endpoint
test_status() {
    print_msg $BLUE "Testing /status endpoint (no auth)..."
    
    local response=$(curl -s -w "\n%{http_code}" "$API_URL/sunray-srvr/v1/status" 2>/dev/null || echo "CURL_ERROR")
    
    if [[ "$response" == "CURL_ERROR" ]]; then
        record_test_result "Status" "false" "Connection failed"
        return 1
    fi
    
    local http_code=$(echo "$response" | tail -n1)
    local body=$(echo "$response" | head -n-1)
    
    if [[ "$VERBOSE" == "true" ]]; then
        print_msg $YELLOW "Response code: $http_code"
        print_msg $YELLOW "Response body: $body"
    fi
    
    if [[ "$http_code" == "200" ]]; then
        if command -v jq &> /dev/null && echo "$body" | jq -e '.status' > /dev/null 2>&1; then
            local status=$(echo "$body" | jq -r '.status')
            record_test_result "Status" "true" "Server status: $status"
        else
            record_test_result "Status" "true" "Endpoint accessible (HTTP 200)"
        fi
    else
        record_test_result "Status" "false" "HTTP $http_code"
    fi
}

# Test 2: Config endpoint
test_config() {
    if [[ "$SKIP_AUTH" == "true" ]]; then
        print_msg $YELLOW "⚠ Skipping /config test (auth required)"
        return
    fi
    
    print_msg $BLUE "Testing /config endpoint..."
    
    local response=$(curl -s -w "\n%{http_code}" \
        -H "Authorization: Bearer $API_KEY" \
        -H "X-Worker-ID: $WORKER_ID" \
        "$API_URL/sunray-srvr/v1/config" 2>/dev/null || echo "CURL_ERROR")
    
    local http_code=$(echo "$response" | tail -n1)
    local body=$(echo "$response" | head -n-1)
    
    if [[ "$VERBOSE" == "true" ]]; then
        print_msg $YELLOW "Response code: $http_code"
        if command -v jq &> /dev/null; then
            echo "$body" | jq '.' 2>/dev/null || print_msg $YELLOW "Response: $body"
        fi
    fi
    
    if [[ "$http_code" == "200" ]]; then
        if command -v jq &> /dev/null && echo "$body" | jq -e '.version' > /dev/null 2>&1; then
            local version=$(echo "$body" | jq -r '.version')
            local user_count=$(echo "$body" | jq -r '.users | keys | length' 2>/dev/null || echo "?")
            local host_count=$(echo "$body" | jq -r '.hosts | length' 2>/dev/null || echo "?")
            record_test_result "Config" "true" "v$version, $user_count users, $host_count hosts"
        else
            record_test_result "Config" "true" "Retrieved successfully"
        fi
    else
        record_test_result "Config" "false" "HTTP $http_code"
    fi
}

# Test 3: User check
test_user() {
    if [[ "$SKIP_AUTH" == "true" ]]; then
        print_msg $YELLOW "⚠ Skipping /users/check test (auth required)"
        return
    fi
    
    print_msg $BLUE "Testing /users/check endpoint..."
    
    local response=$(curl -s -w "\n%{http_code}" -X POST \
        -H "Authorization: Bearer $API_KEY" \
        -H "X-Worker-ID: $WORKER_ID" \
        -H "Content-Type: application/json" \
        -d "{\"username\": \"$TEST_USERNAME\"}" \
        "$API_URL/sunray-srvr/v1/users/check" 2>/dev/null || echo "CURL_ERROR")
    
    local http_code=$(echo "$response" | tail -n1)
    local body=$(echo "$response" | head -n-1)
    
    if [[ "$VERBOSE" == "true" ]]; then
        print_msg $YELLOW "Response code: $http_code"
        print_msg $YELLOW "Response: $body"
    fi
    
    if [[ "$http_code" == "200" ]]; then
        if command -v jq &> /dev/null && echo "$body" | jq -e '.exists' > /dev/null 2>&1; then
            local exists=$(echo "$body" | jq -r '.exists')
            record_test_result "User Check" "true" "User '$TEST_USERNAME' exists: $exists"
        else
            record_test_result "User Check" "true" "Endpoint working"
        fi
    else
        record_test_result "User Check" "false" "HTTP $http_code"
    fi
}

# Test 4: Token validation
test_token() {
    if [[ "$SKIP_AUTH" == "true" ]]; then
        print_msg $YELLOW "⚠ Skipping token validation test (auth required)"
        return
    fi
    
    print_msg $BLUE "Testing /setup-tokens/validate endpoint..."
    
    # Generate hash for invalid token
    local token_hash=$(echo -n "invalid-test-token-$(date +%s)" | sha256sum | cut -d' ' -f1)
    
    local response=$(curl -s -w "\n%{http_code}" -X POST \
        -H "Authorization: Bearer $API_KEY" \
        -H "X-Worker-ID: $WORKER_ID" \
        -H "Content-Type: application/json" \
        -d "{\"username\": \"$TEST_USERNAME\", \"token_hash\": \"$token_hash\", \"client_ip\": \"127.0.0.1\"}" \
        "$API_URL/sunray-srvr/v1/setup-tokens/validate" 2>/dev/null || echo "CURL_ERROR")
    
    local http_code=$(echo "$response" | tail -n1)
    local body=$(echo "$response" | head -n-1)
    
    if [[ "$VERBOSE" == "true" ]]; then
        print_msg $YELLOW "Response code: $http_code"
        print_msg $YELLOW "Response: $body"
    fi
    
    if [[ "$http_code" == "200" ]]; then
        if command -v jq &> /dev/null && echo "$body" | jq -e '.valid' > /dev/null 2>&1; then
            local valid=$(echo "$body" | jq -r '.valid')
            if [[ "$valid" == "false" ]]; then
                record_test_result "Token Validation" "true" "Correctly rejected invalid token"
            else
                record_test_result "Token Validation" "false" "Should have rejected invalid token"
            fi
        else
            record_test_result "Token Validation" "true" "Endpoint working"
        fi
    else
        record_test_result "Token Validation" "false" "HTTP $http_code"
    fi
}

# Test 5 & 6: Session creation and revocation
test_session() {
    if [[ "$SKIP_AUTH" == "true" ]]; then
        print_msg $YELLOW "⚠ Skipping session tests (auth required)"
        return
    fi
    
    print_msg $BLUE "Testing /sessions endpoint..."
    
    local session_id="test-$(date +%s)-$$"
    
    # Create session
    local response=$(curl -s -w "\n%{http_code}" -X POST \
        -H "Authorization: Bearer $API_KEY" \
        -H "X-Worker-ID: $WORKER_ID" \
        -H "Content-Type: application/json" \
        -d "{
            \"session_id\": \"$session_id\",
            \"username\": \"$TEST_USERNAME\",
            \"credential_id\": \"test-cred-$(date +%s)\",
            \"host_domain\": \"test.example.com\",
            \"created_ip\": \"127.0.0.1\",
            \"device_fingerprint\": \"test-device\",
            \"user_agent\": \"REST API Test Suite\",
            \"csrf_token\": \"test-csrf-$(date +%s)\",
            \"duration\": 3600
        }" \
        "$API_URL/sunray-srvr/v1/sessions" 2>/dev/null || echo "CURL_ERROR")
    
    local http_code=$(echo "$response" | tail -n1)
    local body=$(echo "$response" | head -n-1)
    
    if [[ "$VERBOSE" == "true" ]]; then
        print_msg $YELLOW "Create response code: $http_code"
        print_msg $YELLOW "Create response: $body"
    fi
    
    if [[ "$http_code" == "200" ]] || [[ "$http_code" == "201" ]]; then
        record_test_result "Session Create" "true" "Session ID: $session_id"
        
        # Now test revocation if creation succeeded
        test_revoke "$session_id"
    else
        record_test_result "Session Create" "false" "HTTP $http_code"
    fi
}

# Test session revocation
test_revoke() {
    local session_id=${1:-""}
    
    if [[ -z "$session_id" ]]; then
        print_msg $YELLOW "⚠ No session ID provided for revocation test"
        return
    fi
    
    print_msg $BLUE "Testing /sessions/{id}/revoke endpoint..."
    
    local response=$(curl -s -w "\n%{http_code}" -X POST \
        -H "Authorization: Bearer $API_KEY" \
        -H "X-Worker-ID: $WORKER_ID" \
        -H "Content-Type: application/json" \
        -d '{"reason": "REST API test suite"}' \
        "$API_URL/sunray-srvr/v1/sessions/$session_id/revoke" 2>/dev/null || echo "CURL_ERROR")
    
    local http_code=$(echo "$response" | tail -n1)
    local body=$(echo "$response" | head -n-1)
    
    if [[ "$VERBOSE" == "true" ]]; then
        print_msg $YELLOW "Revoke response code: $http_code"
        print_msg $YELLOW "Revoke response: $body"
    fi
    
    if [[ "$http_code" == "200" ]]; then
        record_test_result "Session Revoke" "true" "Revoked: $session_id"
    else
        record_test_result "Session Revoke" "false" "HTTP $http_code"
    fi
}

# Run all tests
run_all_tests() {
    print_header "Running All Tests"
    
    test_status
    test_config
    test_user
    test_token
    test_session
}

# Run specific test
run_specific_test() {
    local test_name=$1
    
    print_header "Running Test: $test_name"
    
    case $test_name in
        status)
            test_status
            ;;
        config)
            test_config
            ;;
        user)
            test_user
            ;;
        token)
            test_token
            ;;
        session)
            test_session
            ;;
        revoke)
            print_msg $YELLOW "Note: Revoke test requires a session ID"
            print_msg $YELLOW "Run 'session' test instead to test both create and revoke"
            ;;
        *)
            print_msg $RED "Unknown test: $test_name"
            echo ""
            list_tests
            exit 1
            ;;
    esac
}

# Print summary
print_summary() {
    print_header "Test Results Summary"
    
    local duration=$(($(date +%s) - START_TIME))
    
    if [[ "$JSON_OUTPUT" == "true" ]]; then
        cat > "${LOG_DIR}/rest_api_results.json" <<EOF
{
    "timestamp": "$(date -Iseconds)",
    "api_url": "$API_URL",
    "worker_id": "$WORKER_ID",
    "tests_run": $TESTS_RUN,
    "tests_passed": $TESTS_PASSED,
    "tests_failed": $TESTS_FAILED,
    "duration_seconds": $duration,
    "log_file": "$LOG_FILE"
}
EOF
        cat "${LOG_DIR}/rest_api_results.json"
    else
        echo "Tests run: $TESTS_RUN"
        echo "Tests passed: $TESTS_PASSED"
        echo "Tests failed: $TESTS_FAILED"
        echo "Duration: ${duration}s"
        echo ""
        echo "Log file: $LOG_FILE"
        
        if [[ $TESTS_FAILED -eq 0 && $TESTS_RUN -gt 0 ]]; then
            print_msg $GREEN "🎉 All tests passed!"
        elif [[ $TESTS_RUN -eq 0 ]]; then
            print_msg $YELLOW "⚠ No tests were run"
        else
            print_msg $RED "❌ Some tests failed"
        fi
    fi
}

# Main execution
main() {
    START_TIME=$(date +%s)
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                usage
                exit 0
                ;;
            -u|--url)
                API_URL="$2"
                shift 2
                ;;
            -k|--key)
                API_KEY="$2"
                shift 2
                ;;
            -w|--worker)
                WORKER_ID="$2"
                shift 2
                ;;
            -t|--test)
                SPECIFIC_TEST="$2"
                shift 2
                ;;
            -v|--verbose)
                VERBOSE=true
                shift
                ;;
            --skip-auth)
                SKIP_AUTH=true
                shift
                ;;
            --json)
                JSON_OUTPUT=true
                shift
                ;;
            --username)
                TEST_USERNAME="$2"
                shift 2
                ;;
            --list-tests)
                list_tests
                exit 0
                ;;
            *)
                print_msg $RED "Unknown option: $1"
                echo ""
                usage
                exit 1
                ;;
        esac
    done
    
    # Start logging
    echo "Sunray REST API Test Suite - $(date)" > "$LOG_FILE"
    echo "==========================================" >> "$LOG_FILE"
    
    if [[ "$JSON_OUTPUT" != "true" ]]; then
        print_header "Sunray REST API Test Suite"
    fi
    
    # Check prerequisites
    check_prerequisites
    
    # Run tests
    if [[ -n "$SPECIFIC_TEST" ]]; then
        run_specific_test "$SPECIFIC_TEST"
    else
        run_all_tests
    fi
    
    # Print summary
    print_summary
    
    # Exit with appropriate code
    if [[ $TESTS_FAILED -gt 0 ]]; then
        exit 1
    else
        exit 0
    fi
}

# Run main function
main "$@"