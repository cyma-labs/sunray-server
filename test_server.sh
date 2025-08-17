#!/bin/bash
# Sunray Server Test Runner
# Comprehensive test script for Odoo-based Sunray Server components

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
LOG_DIR="${SCRIPT_DIR}/test_logs"
COVERAGE_DIR="${SCRIPT_DIR}/coverage"
DEFAULT_MODULE="sunray_core"

# Default options
VERBOSE=false
FULL_TEST=false
CLEAN_DB=false
COVERAGE=false
TEST_CLASS=""
TEST_METHOD=""
STOP_ON_FAIL=false
PARALLEL=true

# Create directories
mkdir -p "${LOG_DIR}" "${COVERAGE_DIR}"

# Usage function
usage() {
    echo -e "${BLUE}Sunray Server Test Runner${NC}"
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -h, --help              Show this help message"
    echo "  -v, --verbose           Enable verbose output with debug logging"
    echo "  -f, --full              Run tests for all modules (not just sunray_core)"
    echo "  -c, --clean             Reset test database before running tests"
    echo "  --coverage              Generate test coverage report"
    echo "  -t, --test CLASS        Run specific test class (e.g., TestCacheInvalidation)"
    echo "  -m, --method METHOD     Run specific test method (requires --test)"
    echo "  -s, --stop-on-fail      Stop on first test failure"
    echo "  --no-parallel           Disable parallel test execution"
    echo "  --list-tests            List all available test classes"
    echo ""
    echo "Examples:"
    echo "  $0                                    # Run sunray_core tests"
    echo "  $0 --full --verbose                  # Run all tests with debug output"
    echo "  $0 --test TestWebhookToken           # Run specific test class"
    echo "  $0 --clean --coverage                # Clean run with coverage"
    echo "  $0 --test TestCacheInvalidation --method test_version_field_initialization"
    echo ""
}

# Print colored message
print_msg() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

# Print section header
print_header() {
    echo ""
    echo -e "${CYAN}================================================${NC}"
    echo -e "${CYAN} $1${NC}"
    echo -e "${CYAN}================================================${NC}"
    echo ""
}

# Check prerequisites
check_prerequisites() {
    print_header "Checking Prerequisites"
    
    # Check if we're in the right directory
    if [[ ! -f "bin/sunray-srvr" ]]; then
        print_msg $RED "Error: bin/sunray-srvr not found. Are you in the correct directory?"
        exit 1
    fi
    
    # Check database connection
    if ! bin/sunray-srvr --help > /dev/null 2>&1; then
        print_msg $RED "Error: Cannot execute bin/sunray-srvr. Check your setup."
        exit 1
    fi
    
    # Check Python environment
    if ! python3 -c "import odoo" 2>/dev/null; then
        print_msg $YELLOW "Warning: Odoo not found in Python path. Continuing anyway..."
    fi
    
    print_msg $GREEN "✓ Prerequisites check passed"
}

# Clean test database
clean_database() {
    if [[ "$CLEAN_DB" == "true" ]]; then
        print_header "Cleaning Test Database"
        
        local test_db="sunray_test_$(date +%s)"
        print_msg $YELLOW "Creating fresh test database: $test_db"
        
        # Create clean database
        dropdb "${test_db}" 2>/dev/null || true
        createdb "${test_db}"
        
        # Initialize base
        bin/sunray-srvr --database="${test_db}" --init=base --without-demo=all --stop-after-init
        
        # Install sunray_core
        bin/sunray-srvr --database="${test_db}" -i sunray_core --stop-after-init
        
        export PGDATABASE="${test_db}"
        print_msg $GREEN "✓ Clean database created: $test_db"
    fi
}

# List available tests
list_tests() {
    print_header "Available Test Classes"
    
    local test_files=($(find sunray_server/sunray_core/tests -name "test_*.py" -type f))
    
    for file in "${test_files[@]}"; do
        local basename=$(basename "$file" .py)
        local classes=$(grep -o "class Test[A-Za-z]*" "$file" | sed 's/class //' || true)
        
        if [[ -n "$classes" ]]; then
            echo -e "${BLUE}File: ${basename}.py${NC}"
            while IFS= read -r class; do
                echo -e "  ${GREEN}• $class${NC}"
                
                # List methods for this class
                local methods=$(grep -A 50 "class $class" "$file" | grep -o "def test_[a-zA-Z_]*" | sed 's/def //' || true)
                if [[ -n "$methods" ]]; then
                    while IFS= read -r method; do
                        echo -e "    ${CYAN}→ $method${NC}"
                    done <<< "$methods"
                fi
            done <<< "$classes"
            echo ""
        fi
    done
}

# Build test command
build_test_command() {
    local cmd="bin/sunray-srvr --test-enable --stop-after-init"
    
    # Database workers
    if [[ "$PARALLEL" == "true" ]]; then
        cmd="$cmd --workers=0"  # Disable workers for testing
    fi
    
    # Module selection
    if [[ "$FULL_TEST" == "true" ]]; then
        cmd="$cmd -u all"
    else
        cmd="$cmd -u $DEFAULT_MODULE"
    fi
    
    # Verbose logging
    if [[ "$VERBOSE" == "true" ]]; then
        cmd="$cmd --log-level=debug"
    fi
    
    # Stop on fail
    if [[ "$STOP_ON_FAIL" == "true" ]]; then
        cmd="$cmd --stop-after-init"
    fi
    
    echo "$cmd"
}

# Run specific test class/method
run_specific_test() {
    local cmd=$(build_test_command)
    local log_file="${LOG_DIR}/specific_test_$(date +%Y%m%d_%H%M%S).log"
    
    if [[ -n "$TEST_METHOD" && -n "$TEST_CLASS" ]]; then
        print_msg $BLUE "Running specific test: $TEST_CLASS.$TEST_METHOD"
        cmd="$cmd --test-tags=$TEST_CLASS.$TEST_METHOD"
    elif [[ -n "$TEST_CLASS" ]]; then
        print_msg $BLUE "Running test class: $TEST_CLASS"
        cmd="$cmd --test-tags=$TEST_CLASS"
    fi
    
    print_msg $YELLOW "Command: $cmd"
    echo "Log file: $log_file"
    echo ""
    
    if [[ "$VERBOSE" == "true" ]]; then
        eval "$cmd" 2>&1 | tee "$log_file"
    else
        eval "$cmd" > "$log_file" 2>&1
    fi
}

# Run all tests
run_all_tests() {
    local cmd=$(build_test_command)
    local log_file="${LOG_DIR}/full_test_$(date +%Y%m%d_%H%M%S).log"
    
    if [[ "$FULL_TEST" == "true" ]]; then
        print_msg $BLUE "Running tests for ALL modules"
    else
        print_msg $BLUE "Running tests for $DEFAULT_MODULE module"
    fi
    
    print_msg $YELLOW "Command: $cmd"
    echo "Log file: $log_file"
    echo ""
    
    local start_time=$(date +%s)
    
    if [[ "$VERBOSE" == "true" ]]; then
        eval "$cmd" 2>&1 | tee "$log_file"
    else
        eval "$cmd" > "$log_file" 2>&1
    fi
    
    local exit_code=$?
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    echo ""
    print_header "Test Results Summary"
    
    # Parse results from log
    local total_tests=$(grep -o "[0-9]* tests" "$log_file" | tail -1 | grep -o "[0-9]*" || echo "0")
    local failures=$(grep -o "[0-9]* failures" "$log_file" | tail -1 | grep -o "[0-9]*" || echo "0")
    local errors=$(grep -o "[0-9]* errors" "$log_file" | tail -1 | grep -o "[0-9]*" || echo "0")
    
    echo "Total tests: $total_tests"
    echo "Duration: ${duration}s"
    
    if [[ "$exit_code" -eq 0 ]]; then
        print_msg $GREEN "✓ All tests passed!"
    else
        print_msg $RED "✗ Tests failed!"
        echo "Failures: $failures"
        echo "Errors: $errors"
        
        # Show last few lines of failures
        echo ""
        print_msg $YELLOW "Last few lines from log:"
        tail -20 "$log_file"
    fi
    
    return $exit_code
}

# Generate coverage report
generate_coverage() {
    if [[ "$COVERAGE" == "true" ]]; then
        print_header "Generating Coverage Report"
        
        # Python coverage for server code
        local coverage_file="${COVERAGE_DIR}/server_coverage_$(date +%Y%m%d_%H%M%S).html"
        
        print_msg $YELLOW "Generating Python coverage report..."
        print_msg $YELLOW "Note: Coverage requires additional setup with coverage.py"
        
        # For now, just create a placeholder
        cat > "$coverage_file" << EOF
<!DOCTYPE html>
<html>
<head>
    <title>Sunray Server Test Coverage</title>
</head>
<body>
    <h1>Sunray Server Test Coverage</h1>
    <p>Coverage report generated on: $(date)</p>
    <p>To enable detailed coverage reporting, install coverage.py and configure it for Odoo testing.</p>
    
    <h2>Quick Setup:</h2>
    <pre>
pip install coverage
# Run tests with coverage
coverage run --source=sunray_server bin/sunray-srvr --test-enable --stop-after-init -u sunray_core
coverage html -d ${COVERAGE_DIR}/htmlcov
    </pre>
</body>
</html>
EOF
        
        print_msg $GREEN "✓ Coverage placeholder created: $coverage_file"
        print_msg $CYAN "For detailed coverage, run: coverage run --source=sunray_server bin/sunray-srvr --test-enable --stop-after-init -u sunray_core && coverage html"
    fi
}

# Main execution
main() {
    print_header "Sunray Server Test Runner"
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                usage
                exit 0
                ;;
            -v|--verbose)
                VERBOSE=true
                shift
                ;;
            -f|--full)
                FULL_TEST=true
                shift
                ;;
            -c|--clean)
                CLEAN_DB=true
                shift
                ;;
            --coverage)
                COVERAGE=true
                shift
                ;;
            -t|--test)
                TEST_CLASS="$2"
                shift 2
                ;;
            -m|--method)
                TEST_METHOD="$2"
                shift 2
                ;;
            -s|--stop-on-fail)
                STOP_ON_FAIL=true
                shift
                ;;
            --no-parallel)
                PARALLEL=false
                shift
                ;;
            --list-tests)
                list_tests
                exit 0
                ;;
            *)
                print_msg $RED "Unknown option: $1"
                usage
                exit 1
                ;;
        esac
    done
    
    # Validate method requires class
    if [[ -n "$TEST_METHOD" && -z "$TEST_CLASS" ]]; then
        print_msg $RED "Error: --method requires --test to specify the class"
        exit 1
    fi
    
    # Run the test suite
    check_prerequisites
    clean_database
    
    local exit_code=0
    
    if [[ -n "$TEST_CLASS" ]]; then
        run_specific_test
        exit_code=$?
    else
        run_all_tests
        exit_code=$?
    fi
    
    generate_coverage
    
    # Final summary
    echo ""
    print_header "Test Session Complete"
    echo "Logs directory: $LOG_DIR"
    if [[ "$COVERAGE" == "true" ]]; then
        echo "Coverage directory: $COVERAGE_DIR"
    fi
    
    if [[ $exit_code -eq 0 ]]; then
        print_msg $GREEN "🎉 Test session completed successfully!"
    else
        print_msg $RED "❌ Test session failed!"
    fi
    
    exit $exit_code
}

# Run main function
main "$@"