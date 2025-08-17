#!/bin/bash
# Sunray Worker Test Runner
# Comprehensive test script for Cloudflare Worker components using Vitest

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
WORKER_DIR="${SCRIPT_DIR}/sunray_worker"
LOG_DIR="${SCRIPT_DIR}/test_logs"
COVERAGE_DIR="${SCRIPT_DIR}/coverage"

# Default options
WATCH_MODE=false
COVERAGE=false
VERBOSE=false
CHECK_ENV=false
SPECIFIC_TEST=""
UI_MODE=false
BAIL=false
PARALLEL=true

# Create directories
mkdir -p "${LOG_DIR}" "${COVERAGE_DIR}"

# Usage function
usage() {
    echo -e "${BLUE}Sunray Worker Test Runner${NC}"
    echo ""
    echo "Usage: $0 [OPTIONS] [TEST_FILE]"
    echo ""
    echo "Options:"
    echo "  -h, --help              Show this help message"
    echo "  -w, --watch             Run tests in watch mode (auto-rerun on changes)"
    echo "  -c, --coverage          Generate test coverage report"
    echo "  -v, --verbose           Enable verbose output"
    echo "  --check-env             Validate environment variables and setup"
    echo "  --ui                    Run tests with Vitest UI interface"
    echo "  --bail                  Stop on first test failure"
    echo "  --no-parallel           Run tests sequentially"
    echo "  --list-tests            List all available test files"
    echo ""
    echo "Arguments:"
    echo "  TEST_FILE               Run specific test file (e.g., cache.test.js)"
    echo ""
    echo "Examples:"
    echo "  $0                                    # Run all tests once"
    echo "  $0 --watch                           # Run in watch mode for development"
    echo "  $0 --coverage                        # Generate coverage report"
    echo "  $0 cache.test.js                     # Run specific test file"
    echo "  $0 --ui --verbose                    # Run with UI and verbose output"
    echo "  $0 --check-env                       # Only validate environment"
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

# Check if we're in the right directory
check_directory() {
    if [[ ! -d "$WORKER_DIR" ]]; then
        print_msg $RED "Error: sunray_worker directory not found. Are you in the correct project root?"
        exit 1
    fi
    
    if [[ ! -f "$WORKER_DIR/package.json" ]]; then
        print_msg $RED "Error: package.json not found in sunray_worker directory."
        exit 1
    fi
}

# Check Node.js and npm versions
check_nodejs() {
    print_header "Checking Node.js Environment"
    
    # Check Node.js
    if ! command -v node &> /dev/null; then
        print_msg $RED "Error: Node.js is not installed."
        exit 1
    fi
    
    local node_version=$(node --version)
    print_msg $GREEN "✓ Node.js version: $node_version"
    
    # Check if version is 20.x
    if [[ ! "$node_version" =~ ^v20\. ]]; then
        print_msg $YELLOW "Warning: Recommended Node.js version is 20.x, found $node_version"
    fi
    
    # Check npm
    if ! command -v npm &> /dev/null; then
        print_msg $RED "Error: npm is not installed."
        exit 1
    fi
    
    local npm_version=$(npm --version)
    print_msg $GREEN "✓ npm version: $npm_version"
}

# Check dependencies
check_dependencies() {
    print_header "Checking Dependencies"
    
    cd "$WORKER_DIR"
    
    # Check if node_modules exists
    if [[ ! -d "node_modules" ]]; then
        print_msg $YELLOW "node_modules not found. Installing dependencies..."
        npm install
    fi
    
    # Check key dependencies
    local deps=("vitest" "wrangler" "@vitest/ui")
    for dep in "${deps[@]}"; do
        if npm list "$dep" &> /dev/null; then
            local version=$(npm list "$dep" --depth=0 2>/dev/null | grep "$dep" | head -1 | sed 's/.*@//' || echo "unknown")
            print_msg $GREEN "✓ $dep@$version"
        else
            print_msg $RED "✗ $dep not found"
        fi
    done
    
    cd - > /dev/null
}

# Validate environment variables
check_environment() {
    print_header "Validating Environment Variables"
    
    # Required for testing
    local required_vars=()
    local optional_vars=("WORKER_URL" "ADMIN_API_ENDPOINT" "ADMIN_API_KEY" "SESSION_SECRET")
    
    # Check optional but useful variables
    for var in "${optional_vars[@]}"; do
        if [[ -n "${!var}" ]]; then
            # Mask sensitive values
            if [[ "$var" == *"KEY"* || "$var" == *"SECRET"* ]]; then
                local masked_value="${!var:0:8}..."
                print_msg $GREEN "✓ $var: $masked_value"
            else
                print_msg $GREEN "✓ $var: ${!var}"
            fi
        else
            print_msg $YELLOW "○ $var: not set (optional for tests)"
        fi
    done
    
    # Check if we have wrangler auth
    if command -v wrangler &> /dev/null; then
        cd "$WORKER_DIR"
        if wrangler whoami &> /dev/null; then
            local whoami_output=$(wrangler whoami 2>/dev/null | head -1 || echo "unknown")
            print_msg $GREEN "✓ Wrangler authenticated: $whoami_output"
        else
            print_msg $YELLOW "○ Wrangler not authenticated (optional for unit tests)"
        fi
        cd - > /dev/null
    else
        print_msg $YELLOW "○ Wrangler not installed (optional for unit tests)"
    fi
}

# List available test files
list_tests() {
    print_header "Available Test Files"
    
    cd "$WORKER_DIR"
    
    local test_files=($(find src -name "*.test.js" -type f | sort))
    
    if [[ ${#test_files[@]} -eq 0 ]]; then
        print_msg $YELLOW "No test files found in src directory"
        return
    fi
    
    for file in "${test_files[@]}"; do
        local basename=$(basename "$file")
        local filesize=$(du -h "$file" | cut -f1)
        
        echo -e "${BLUE}$file${NC} ${CYAN}($filesize)${NC}"
        
        # Try to extract test descriptions
        local descriptions=$(grep -o "describe\|test\|it.*['\"].*['\"]" "$file" | head -5 | sed "s/.*['\"]\\(.*\\)['\"].*/  • \\1/" || true)
        if [[ -n "$descriptions" ]]; then
            echo -e "${GREEN}$descriptions${NC}"
        fi
        echo ""
    done
    
    cd - > /dev/null
}

# Build vitest command
build_test_command() {
    local cmd="npx vitest"
    
    # Specific test file
    if [[ -n "$SPECIFIC_TEST" ]]; then
        cmd="$cmd $SPECIFIC_TEST"
    fi
    
    # Watch mode
    if [[ "$WATCH_MODE" == "true" ]]; then
        cmd="$cmd --watch"
    else
        cmd="$cmd --run"  # Single run
    fi
    
    # Coverage
    if [[ "$COVERAGE" == "true" ]]; then
        cmd="$cmd --coverage"
    fi
    
    # Verbose output
    if [[ "$VERBOSE" == "true" ]]; then
        cmd="$cmd --verbose"
    fi
    
    # UI mode
    if [[ "$UI_MODE" == "true" ]]; then
        cmd="$cmd --ui"
    fi
    
    # Bail on first failure
    if [[ "$BAIL" == "true" ]]; then
        cmd="$cmd --bail"
    fi
    
    # Parallel execution
    if [[ "$PARALLEL" == "false" ]]; then
        cmd="$cmd --no-parallelism"
    fi
    
    echo "$cmd"
}

# Run tests
run_tests() {
    local cmd=$(build_test_command)
    local log_file="${LOG_DIR}/worker_test_$(date +%Y%m%d_%H%M%S).log"
    
    print_header "Running Worker Tests"
    
    cd "$WORKER_DIR"
    
    if [[ -n "$SPECIFIC_TEST" ]]; then
        print_msg $BLUE "Running specific test: $SPECIFIC_TEST"
    else
        print_msg $BLUE "Running all worker tests"
    fi
    
    if [[ "$WATCH_MODE" == "true" ]]; then
        print_msg $YELLOW "Starting in watch mode (press 'q' to quit)"
    fi
    
    print_msg $YELLOW "Command: $cmd"
    echo "Working directory: $WORKER_DIR"
    if [[ "$WATCH_MODE" == "false" ]]; then
        echo "Log file: $log_file"
    fi
    echo ""
    
    local start_time=$(date +%s)
    local exit_code=0
    
    if [[ "$WATCH_MODE" == "true" || "$UI_MODE" == "true" ]]; then
        # Interactive modes - no logging
        eval "$cmd"
        exit_code=$?
    else
        # Non-interactive mode - with logging
        if [[ "$VERBOSE" == "true" ]]; then
            eval "$cmd" 2>&1 | tee "$log_file"
            exit_code=${PIPESTATUS[0]}
        else
            eval "$cmd" > "$log_file" 2>&1
            exit_code=$?
        fi
    fi
    
    if [[ "$WATCH_MODE" == "false" && "$UI_MODE" == "false" ]]; then
        local end_time=$(date +%s)
        local duration=$((end_time - start_time))
        
        echo ""
        print_header "Test Results Summary"
        
        # Parse results from log if available
        if [[ -f "$log_file" ]]; then
            # Extract test summary from vitest output
            local test_summary=$(grep -E "(Test Files|Tests|Pass|Fail|Skipped)" "$log_file" | tail -5 || true)
            if [[ -n "$test_summary" ]]; then
                echo "$test_summary"
            fi
        fi
        
        echo "Duration: ${duration}s"
        
        if [[ $exit_code -eq 0 ]]; then
            print_msg $GREEN "✓ All tests passed!"
        else
            print_msg $RED "✗ Tests failed!"
            
            # Show last few lines of failures
            if [[ -f "$log_file" ]]; then
                echo ""
                print_msg $YELLOW "Last few lines from log:"
                tail -15 "$log_file"
            fi
        fi
    fi
    
    cd - > /dev/null
    return $exit_code
}

# Generate coverage report
generate_coverage_report() {
    if [[ "$COVERAGE" == "true" ]]; then
        print_header "Coverage Report Generated"
        
        local coverage_dir="$WORKER_DIR/coverage"
        if [[ -d "$coverage_dir" ]]; then
            # Copy coverage to our coverage directory
            cp -r "$coverage_dir" "$COVERAGE_DIR/worker_coverage_$(date +%Y%m%d_%H%M%S)"
            
            print_msg $GREEN "✓ Coverage report available:"
            print_msg $CYAN "  HTML: $COVERAGE_DIR/worker_coverage_*/index.html"
            
            # Look for coverage summary
            local summary_file="$coverage_dir/coverage-summary.json"
            if [[ -f "$summary_file" ]]; then
                print_msg $BLUE "Coverage Summary:"
                # Extract key metrics if jq is available
                if command -v jq &> /dev/null; then
                    local lines=$(jq -r '.total.lines.pct' "$summary_file" 2>/dev/null || echo "N/A")
                    local functions=$(jq -r '.total.functions.pct' "$summary_file" 2>/dev/null || echo "N/A")
                    local branches=$(jq -r '.total.branches.pct' "$summary_file" 2>/dev/null || echo "N/A")
                    echo "  Lines: ${lines}%"
                    echo "  Functions: ${functions}%"
                    echo "  Branches: ${branches}%"
                fi
            fi
        else
            print_msg $YELLOW "Coverage directory not found. Make sure @vitest/coverage-v8 is installed."
        fi
    fi
}

# Main execution
main() {
    print_header "Sunray Worker Test Runner"
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                usage
                exit 0
                ;;
            -w|--watch)
                WATCH_MODE=true
                shift
                ;;
            -c|--coverage)
                COVERAGE=true
                shift
                ;;
            -v|--verbose)
                VERBOSE=true
                shift
                ;;
            --check-env)
                CHECK_ENV=true
                shift
                ;;
            --ui)
                UI_MODE=true
                shift
                ;;
            --bail)
                BAIL=true
                shift
                ;;
            --no-parallel)
                PARALLEL=false
                shift
                ;;
            --list-tests)
                check_directory
                list_tests
                exit 0
                ;;
            -*)
                print_msg $RED "Unknown option: $1"
                usage
                exit 1
                ;;
            *)
                # Assume it's a test file
                SPECIFIC_TEST="$1"
                shift
                ;;
        esac
    done
    
    # Validate test file if specified
    if [[ -n "$SPECIFIC_TEST" ]]; then
        if [[ ! "$SPECIFIC_TEST" =~ \.test\.js$ ]]; then
            print_msg $YELLOW "Warning: Test file should end with .test.js"
        fi
        
        if [[ ! -f "$WORKER_DIR/src/$SPECIFIC_TEST" && ! -f "$WORKER_DIR/$SPECIFIC_TEST" ]]; then
            print_msg $RED "Error: Test file not found: $SPECIFIC_TEST"
            print_msg $CYAN "Available tests:"
            list_tests
            exit 1
        fi
    fi
    
    # Run the test suite
    check_directory
    check_nodejs
    check_dependencies
    
    if [[ "$CHECK_ENV" == "true" ]]; then
        check_environment
        print_msg $GREEN "✓ Environment validation complete"
        exit 0
    fi
    
    local exit_code=0
    run_tests
    exit_code=$?
    
    generate_coverage_report
    
    # Final summary
    if [[ "$WATCH_MODE" == "false" && "$UI_MODE" == "false" ]]; then
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
    fi
    
    exit $exit_code
}

# Run main function
main "$@"