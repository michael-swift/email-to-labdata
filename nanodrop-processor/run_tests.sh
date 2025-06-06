#!/bin/bash

# Nanodrop Testing Framework Runner
# This script provides a simple interface to run various test configurations

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default values
TEST_TYPE="all"
VERBOSE=false
COVERAGE=false
FAIL_FAST=false

# Function to print colored output
print_color() {
    color=$1
    message=$2
    echo -e "${color}${message}${NC}"
}

# Function to show usage
usage() {
    echo "Nanodrop Testing Framework Runner"
    echo ""
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  -t, --type TYPE       Test type: all, unit, integration, image, llm, validation"
    echo "  -v, --verbose         Verbose output"
    echo "  -c, --coverage        Run with coverage report"
    echo "  -f, --fail-fast       Stop on first failure"
    echo "  -h, --help            Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                    # Run all tests"
    echo "  $0 -t unit -v         # Run unit tests with verbose output"
    echo "  $0 -t image -c        # Run image tests with coverage"
    echo "  $0 -f                 # Run all tests, stop on first failure"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -t|--type)
            TEST_TYPE="$2"
            shift 2
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -c|--coverage)
            COVERAGE=true
            shift
            ;;
        -f|--fail-fast)
            FAIL_FAST=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    print_color $YELLOW "Activating virtual environment..."
    source venv/bin/activate
fi

# Build pytest command
PYTEST_CMD="pytest"

# Add test selection
case $TEST_TYPE in
    all)
        PYTEST_CMD="$PYTEST_CMD tests/"
        ;;
    unit)
        PYTEST_CMD="$PYTEST_CMD tests/unit/ -m unit"
        ;;
    integration)
        PYTEST_CMD="$PYTEST_CMD tests/integration/ -m integration"
        ;;
    image)
        PYTEST_CMD="$PYTEST_CMD tests/unit/test_image_processing.py"
        ;;
    llm)
        PYTEST_CMD="$PYTEST_CMD tests/unit/test_mock_llm.py"
        ;;
    validation)
        PYTEST_CMD="$PYTEST_CMD tests/unit/test_data_validation.py"
        ;;
    *)
        print_color $RED "Unknown test type: $TEST_TYPE"
        usage
        exit 1
        ;;
esac

# Add options
if [ "$VERBOSE" = true ]; then
    PYTEST_CMD="$PYTEST_CMD -v"
fi

if [ "$COVERAGE" = true ]; then
    PYTEST_CMD="$PYTEST_CMD --cov=src --cov-report=html --cov-report=term-missing"
fi

if [ "$FAIL_FAST" = true ]; then
    PYTEST_CMD="$PYTEST_CMD -x"
fi

# Always add short traceback
PYTEST_CMD="$PYTEST_CMD --tb=short"

# Run tests
print_color $GREEN "Running tests: $TEST_TYPE"
print_color $YELLOW "Command: $PYTEST_CMD"
echo ""

$PYTEST_CMD

# Check exit code
if [ $? -eq 0 ]; then
    print_color $GREEN "\n✓ All tests passed!"
    if [ "$COVERAGE" = true ]; then
        print_color $YELLOW "\nCoverage report generated in htmlcov/index.html"
    fi
else
    print_color $RED "\n✗ Tests failed!"
    exit 1
fi