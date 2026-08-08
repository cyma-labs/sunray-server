#!/bin/bash
# Sunray Server Test Runner
# Pure launcher - no wrapping, direct Odoo test execution

set -e  # Exit on error

# Colors for tool messages
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
LOG_DIR="${PROJECT_ROOT}/test_logs_and_coverage"
DEFAULT_MODULE="sunray_core"

# Default options
VERBOSE=false
ALL_MODULES=false
TEST_CLASS=""
TEST_METHOD=""
LOG_FILE=""

# Create log directory
mkdir -p "${LOG_DIR}"

# Print colored message
print_msg() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

# Print section header
print_header() {
    echo ""
    print_msg $CYAN "================================================"
    print_msg $CYAN " $1"
    print_msg $CYAN "================================================"
    echo ""
}

# Usage function
usage() {
    print_header "Sunray Server Test Runner"
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    print_msg $GREEN "  -h, --help              Show this help message"
    print_msg $GREEN "  --test CLASS            Run specific test class (case-sensitive!)"
    print_msg $GREEN "  --method METHOD         Run specific test method (requires --test)"
    print_msg $GREEN "  --verbose               Enable verbose output with debug logging"
    print_msg $GREEN "  --log [FILE]            Save output to log file (optional filename)"
    print_msg $GREEN "  --list-tests            List all available test classes"
    print_msg $GREEN "  --module MODULE         Test specific module (default: sunray_core)"
    print_msg $GREEN "  --all                   Run tests for all modules"
    echo ""
    print_msg $YELLOW "Examples:"
    echo "  $0                      # Run all tests"
    echo "  $0 --list-tests         # See available test classes"
    echo "  $0 --test TestClassName # Run specific test class"
    echo "  $0 --test TestClassName --method test_method_name"
    echo "  $0 --test TestClassName --log"
    echo "  $0 --verbose            # Debug output"
    echo ""
    print_msg $CYAN "Note:"
    echo "  - Test class names are case-sensitive"
    echo "  - Use --list-tests to see exact class names"
    echo "  - Odoo test output is shown directly in real-time"
}

# List available tests
list_tests() {
    print_header "Available Test Classes"
    
    # Both addon roots are scanned: sunray_advanced_core (and any other advanced addon) ships
    # tests too, and they used to be invisible here because only project_addons/ was searched.
    print_msg $CYAN "Discovering test classes in project_addons/ and project_addons_advanced/"
    echo ""

    # Find all test files and extract class names
    local test_files=($(find project_addons project_addons_advanced -path "*/tests/test_*.py" -type f 2>/dev/null | sort))

    if [[ ${#test_files[@]} -eq 0 ]]; then
        print_msg $RED "No test files found under project_addons/ or project_addons_advanced/"
        return 1
    fi
    
    print_msg $GREEN "Run ALL tests:"
    echo "  $0"
    echo ""
    
    print_msg $GREEN "Run specific test class:"
    
    for file in "${test_files[@]}"; do
        # Extract test class names from the file
        local classes=$(grep -oP '^class (Test[A-Za-z0-9_]+)' "$file" | sed 's/class //' | sort -u)

        if [[ -n "$classes" ]]; then
            local basename=$(basename "$file" .py)
            # <root>/<module>/tests/<file>.py -> the module is the 2nd path component. It must
            # be shown: a class name alone is ambiguous now that two roots are scanned.
            local module=$(echo "$file" | cut -d/ -f2)
            print_msg $YELLOW "From $module/$basename:"

            while IFS= read -r class; do
                print_msg $BLUE "  $class"
                print_msg $GREEN "    $0 --module $module --test $class"
                print_msg $GREEN "    make test ADDONS=$module TAGS=/$module:$class"
                echo ""
            done <<< "$classes"
        fi
    done

    print_msg $CYAN "Note: Test class names are case-sensitive!"
}

# Check prerequisites
check_prerequisites() {
    # Change to project root for all operations
    cd "${PROJECT_ROOT}"
    
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
    
    print_msg $GREEN "✓ Prerequisites check passed"
}

# Build test command
build_test_command() {
    local cmd="bin/sunray-srvr --test-enable --stop-after-init --workers=0"
    
    # Module selection
    if [[ "$ALL_MODULES" == "true" ]]; then
        cmd="$cmd -u all"
    else
        cmd="$cmd -u $DEFAULT_MODULE"
    fi
    
    # Test tags for specific tests
    if [[ -n "$TEST_METHOD" && -n "$TEST_CLASS" ]]; then
        cmd="$cmd --test-tags=/$DEFAULT_MODULE:$TEST_CLASS.$TEST_METHOD"
    elif [[ -n "$TEST_CLASS" ]]; then
        cmd="$cmd --test-tags=/$DEFAULT_MODULE:$TEST_CLASS"
    fi
    
    # Verbose logging
    if [[ "$VERBOSE" == "true" ]]; then
        cmd="$cmd --log-level=debug"
    fi
    
    echo "$cmd"
}

# Main execution
main() {
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                usage
                exit 0
                ;;
            --test)
                TEST_CLASS="$2"
                shift 2
                ;;
            --method)
                TEST_METHOD="$2"
                shift 2
                ;;
            --verbose)
                VERBOSE=true
                shift
                ;;
            --log)
                if [[ -n "$2" && ! "$2" =~ ^-- ]]; then
                    LOG_FILE="$2"
                    shift 2
                else
                    LOG_FILE="${LOG_DIR}/test_$(date +%Y%m%d_%H%M%S).log"
                    shift
                fi
                ;;
            --list-tests)
                list_tests
                exit 0
                ;;
            --module)
                DEFAULT_MODULE="$2"
                shift 2
                ;;
            --all)
                ALL_MODULES=true
                shift
                ;;
            *)
                print_msg $RED "Error: Unknown option: $1"
                echo ""
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
    
    # Show header
    print_header "Sunray Server Test Runner"
    
    # Check prerequisites
    check_prerequisites
    echo ""
    
    # Build command
    local cmd=$(build_test_command)
    
    # Show what we're running
    if [[ -n "$TEST_CLASS" ]]; then
        if [[ -n "$TEST_METHOD" ]]; then
            print_msg $BLUE "Running specific test: $TEST_CLASS.$TEST_METHOD"
        else
            print_msg $BLUE "Running test class: $TEST_CLASS"
        fi
    elif [[ "$ALL_MODULES" == "true" ]]; then
        print_msg $BLUE "Running tests for ALL modules"
    else
        print_msg $BLUE "Running tests for $DEFAULT_MODULE module"
    fi
    
    print_msg $YELLOW "Command: $cmd"
    
    if [[ -n "$LOG_FILE" ]]; then
        print_msg $CYAN "Log file: $LOG_FILE"
    fi
    
    echo ""
    
    # Execute command directly
    if [[ -n "$LOG_FILE" ]]; then
        exec $cmd 2>&1 | tee "$LOG_FILE"
    else
        exec $cmd
    fi
}

# Run main function
main "$@"