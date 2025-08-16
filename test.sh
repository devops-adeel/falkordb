#!/bin/bash

# Unified test runner for FalkorDB-Graphiti test suite
# Usage: ./test.sh [OPTIONS]

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
TEST_SUITE="all"
VERBOSE=false
COVERAGE=false
MARKERS=""
REPORT_DIR="tests/test_results"

# Help message
show_help() {
    cat << EOF
Usage: ./test.sh [OPTIONS]

Test Suites:
  -q, --quick           Run quick smoke tests
  -i, --integration     Run integration tests only
  -r, --regression      Run regression tests for version issues
  -c, --custom          Run custom entity tests
  -b, --basic           Run basic connectivity tests
  -a, --all             Run all tests (default)

Options:
  -v, --verbose         Verbose output
  --coverage            Generate coverage report
  -m, --markers MARKER  Run tests with specific markers
  -k, --keyword EXPR    Run tests matching expression
  -h, --help            Show this help message

Examples:
  ./test.sh                   # Run all tests
  ./test.sh -q                # Run quick smoke tests
  ./test.sh -i -v             # Run integration tests with verbose output
  ./test.sh -k "test_add"     # Run tests matching "test_add"
  ./test.sh -m "slow"         # Run tests marked as slow
  ./test.sh --coverage        # Run with coverage report

EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -q|--quick)
            TEST_SUITE="quick"
            shift
            ;;
        -i|--integration)
            TEST_SUITE="integration"
            shift
            ;;
        -r|--regression)
            TEST_SUITE="regression"
            shift
            ;;
        -c|--custom)
            TEST_SUITE="custom"
            shift
            ;;
        -b|--basic)
            TEST_SUITE="basic"
            shift
            ;;
        -a|--all)
            TEST_SUITE="all"
            shift
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        --coverage)
            COVERAGE=true
            shift
            ;;
        -m|--markers)
            MARKERS="$2"
            shift 2
            ;;
        -k|--keyword)
            KEYWORD="$2"
            shift 2
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            show_help
            exit 1
            ;;
    esac
done

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}⚠️  Virtual environment not found. Creating one...${NC}"
    python3 -m venv venv
    source venv/bin/activate
    pip install -r tests/requirements.txt
else
    source venv/bin/activate
fi

# Export environment variables
if [ -f ~/.env ]; then
    export $(grep -v '^#' ~/.env | xargs) 2>/dev/null || true
fi

# Check FalkorDB status
check_falkordb() {
    echo -e "${BLUE}🔍 Checking FalkorDB status...${NC}"
    if docker exec falkordb redis-cli ping > /dev/null 2>&1; then
        echo -e "${GREEN}✅ FalkorDB is running${NC}"
        return 0
    else
        echo -e "${RED}❌ FalkorDB is not running${NC}"
        echo -e "${YELLOW}Start it with: docker compose up -d${NC}"
        return 1
    fi
}

# Build pytest command
build_pytest_cmd() {
    local cmd="pytest"
    
    # Add test path based on suite
    case $TEST_SUITE in
        quick)
            cmd="$cmd tests/test_basic_connection.py tests/test_graphiti_simple.py"
            ;;
        integration)
            cmd="$cmd tests/test_*_int.py"
            ;;
        regression)
            cmd="$cmd tests/test_v*.py tests/test_*regression*.py tests/test_group_id*.py"
            ;;
        custom)
            cmd="$cmd tests/test_custom_entities*.py tests/test_falkordb_gaps.py tests/test_workaround*.py"
            ;;
        basic)
            cmd="$cmd tests/test_basic_connection.py"
            ;;
        all)
            cmd="$cmd tests/"
            ;;
    esac
    
    # Add common options
    cmd="$cmd --asyncio-mode=auto"
    
    # Add verbose flag
    if [ "$VERBOSE" = true ]; then
        cmd="$cmd -v -s"
    else
        cmd="$cmd --tb=short"
    fi
    
    # Add coverage
    if [ "$COVERAGE" = true ]; then
        cmd="$cmd --cov=tests --cov-report=html --cov-report=term"
    fi
    
    # Add markers if specified
    if [ -n "$MARKERS" ]; then
        cmd="$cmd -m \"$MARKERS\""
    fi
    
    # Add keyword expression if specified
    if [ -n "$KEYWORD" ]; then
        cmd="$cmd -k \"$KEYWORD\""
    fi
    
    # Add duration report
    cmd="$cmd --durations=10"
    
    echo "$cmd"
}

# Main execution
main() {
    echo -e "${BLUE}============================================${NC}"
    echo -e "${BLUE}FalkorDB-Graphiti Test Suite${NC}"
    echo -e "${BLUE}============================================${NC}"
    echo ""
    
    # Check FalkorDB
    if ! check_falkordb; then
        exit 1
    fi
    
    echo ""
    echo -e "${BLUE}📊 Running test suite: ${YELLOW}$TEST_SUITE${NC}"
    echo -e "${BLUE}============================================${NC}"
    
    # Build and execute pytest command
    PYTEST_CMD=$(build_pytest_cmd)
    echo -e "${BLUE}Command: ${NC}$PYTEST_CMD"
    echo ""
    
    # Create results directory if needed
    if [ "$TEST_SUITE" = "custom" ] || [ "$COVERAGE" = true ]; then
        mkdir -p "$REPORT_DIR"
    fi
    
    # Run tests
    eval $PYTEST_CMD
    TEST_EXIT_CODE=$?
    
    # Show results
    echo ""
    echo -e "${BLUE}============================================${NC}"
    if [ $TEST_EXIT_CODE -eq 0 ]; then
        echo -e "${GREEN}✅ Tests passed successfully!${NC}"
    else
        echo -e "${RED}❌ Some tests failed${NC}"
    fi
    
    # Show coverage report location if generated
    if [ "$COVERAGE" = true ]; then
        echo ""
        echo -e "${BLUE}📈 Coverage report generated:${NC}"
        echo "   HTML: htmlcov/index.html"
        echo "   Open with: open htmlcov/index.html"
    fi
    
    # Show test suite specific notes
    case $TEST_SUITE in
        custom)
            echo ""
            echo -e "${YELLOW}📝 Note: Custom entity tests may fail due to known group_id issue${NC}"
            echo "   See tests/CUSTOM_ENTITIES_REPORT.md for details"
            ;;
        regression)
            echo ""
            echo -e "${YELLOW}📝 Note: Testing regression between v0.17.7 (working) and v0.18.x (broken)${NC}"
            echo "   GitHub issue: https://github.com/getzep/graphiti/issues/841"
            ;;
    esac
    
    exit $TEST_EXIT_CODE
}

# Run main function
main