#!/bin/bash

# =============================================================================
# NDN Transmission Test Script
# =============================================================================
# Description: Automated testing script for NDN producer-consumer transmission
# Author: NDN Development Team
# Date: $(date +%Y-%m-%d)
# =============================================================================


# Save original terminal settings for restoration
orig_stty=$(stty -g 2>/dev/null || echo "")

set -e  # Exit on any error
set -u  # Exit on undefined variables

# =============================================================================
# CONFIGURATION AND CONSTANTS
# =============================================================================

# Colors for output formatting
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly PURPLE='\033[0;35m'
readonly CYAN='\033[0;36m'
readonly NC='\033[0m' # No Color

# Directory paths
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_DIR="$SCRIPT_DIR"
readonly PRODUCER_DIR="$PROJECT_DIR/producer"
readonly CONSUMER_DIR="$PROJECT_DIR/consumer"
readonly EXPERIMENTS_DIR="$PROJECT_DIR/experiments"
readonly NFD_CONFIG="$PROJECT_DIR/nfd.conf"

# Test configuration
TEST_DATASET_ID=1
TEST_PREFIX="/test/data"

VERBOSE=false
QUIET=false

# Process IDs for cleanup
NFD_PID=""
PRODUCER_PID=""

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

# Function to print colored output with timestamps
print_status() {
    if [ "$QUIET" = true ]; then return; fi
    echo -e "${BLUE}[$(date '+%H:%M:%S')] [INFO]${NC} $1"
}

print_success() {
    if [ "$QUIET" = true ]; then return; fi
    echo -e "${GREEN}[$(date '+%H:%M:%S')] [SUCCESS]${NC} $1"
}

print_error() {
    if [ "$QUIET" = true ]; then return; fi
    echo -e "${RED}[$(date '+%H:%M:%S')] [ERROR]${NC} $1"
}

print_warning() {
    if [ "$QUIET" = true ]; then return; fi
    echo -e "${YELLOW}[$(date '+%H:%M:%S')] [WARNING]${NC} $1"
}

print_debug() {
    if [ "$VERBOSE" = true ] && [ "$QUIET" != true ]; then
        echo -e "${CYAN}[$(date '+%H:%M:%S')] [DEBUG]${NC} $1"
    fi
}

print_header() {
    if [ "$QUIET" = true ]; then return; fi
    echo -e "${PURPLE}==============================================================================${NC}"
    echo -e "${PURPLE} $1${NC}"
    echo -e "${PURPLE}==============================================================================${NC}"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to wait for process with timeout
wait_for_process() {
    local pid=$1
    local timeout=${2:-10}
    local count=0
    
    while [ $count -lt $timeout ]; do
        if kill -0 "$pid" 2>/dev/null; then
            return 0
        fi
        sleep 1
        count=$((count + 1))
    done
    return 1
}

# =============================================================================
# CLEANUP AND SIGNAL HANDLING
# =============================================================================


# Function to cleanup processes and temporary files
cleanup() {
    print_header "CLEANUP"
    print_status "Cleaning up processes and temporary files..."

    # Stop producer if running
    if [ -n "$PRODUCER_PID" ] && kill -0 "$PRODUCER_PID" 2>/dev/null; then
        print_status "Stopping producer (PID: $PRODUCER_PID)"
        kill "$PRODUCER_PID" 2>/dev/null || true
        wait "$PRODUCER_PID" 2>/dev/null || true
    fi

    # Stop NFD if running
    if [ -n "$NFD_PID" ] && sudo kill -0 "$NFD_PID" 2>/dev/null; then
        print_status "Stopping NFD (PID: $NFD_PID)"
        sudo kill "$NFD_PID" 2>/dev/null || true
    fi

    # Kill any remaining processes (fallback)
    pkill -f "ndnput" 2>/dev/null || true
    sudo pkill -f "nfd" 2>/dev/null || true

    # Clean up temporary files
    rm -f /tmp/ndn_test_output_* 2>/dev/null || true

    # Restore terminal settings if changed
    if [ -n "$orig_stty" ]; then
        stty "$orig_stty" 2>/dev/null || true
    else
        stty sane 2>/dev/null || true
    fi

    print_success "Cleanup completed"
}

# Set trap for cleanup on exit and signals
trap cleanup EXIT
trap 'print_error "Script interrupted"; exit 130' INT
trap 'print_error "Script terminated"; exit 143' TERM

# =============================================================================
# PREREQUISITE CHECKS
# =============================================================================

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check all prerequisites
check_prerequisites() {
    print_header "PREREQUISITE CHECKS"
    print_status "Checking system requirements..."
    
    local errors=0
    
    # Check if NFD is installed
    if ! command_exists nfd; then
        print_error "NFD (NDN Forwarding Daemon) is not installed or not in PATH"
        errors=$((errors + 1))
    else
        print_success "NFD found: $(which nfd)"
    fi
    
    # Check if producer binary exists
    if [ ! -f "$PRODUCER_DIR/bin/ndnput" ]; then
        print_error "Producer binary not found at $PRODUCER_DIR/bin/ndnput"
        print_error "Run 'make producer' in the project directory first"
        errors=$((errors + 1))
    else
        print_success "Producer binary found"
    fi
    
    # Check if consumer binary exists
    if [ ! -f "$CONSUMER_DIR/bin/ndnget" ]; then
        print_error "Consumer binary not found at $CONSUMER_DIR/bin/ndnget"
        print_error "Run 'make consumer' in the project directory first"
        errors=$((errors + 1))
    else
        print_success "Consumer binary found"
    fi
    
    # Check if NFD config exists
    if [ ! -f "$NFD_CONFIG" ]; then
        print_error "NFD configuration file not found at $NFD_CONFIG"
        errors=$((errors + 1))
    else
        print_success "NFD configuration found"
    fi
    
    # Check if producer config exists
    if [ ! -f "$PRODUCER_DIR/config.ini" ]; then
        print_error "Producer configuration file not found at $PRODUCER_DIR/config.ini"
        errors=$((errors + 1))
    else
        print_success "Producer configuration found"
    fi
    
    # Check permissions for creating directories
    if ! mkdir -p "$EXPERIMENTS_DIR" 2>/dev/null; then
        print_error "Cannot create experiments directory at $EXPERIMENTS_DIR"
        errors=$((errors + 1))
    else
        print_success "Experiments directory accessible"
    fi
    
    # Check sudo permissions for NFD
    if ! sudo -n true 2>/dev/null; then
        print_warning "Sudo access required for NFD. You may be prompted for password."
    fi
    
    if [ $errors -gt 0 ]; then
        print_error "Prerequisites check failed with $errors error(s)"
        exit 1
    fi
    
    print_success "All prerequisites satisfied"
}

# =============================================================================
# TEST DATA GENERATION
# =============================================================================

# Function to create test data files
create_test_data() {
    print_header "TEST DATA CREATION"
    print_status "Creating test data files..."
    
    # Create experiments directory structure
    local dataset_dir="$EXPERIMENTS_DIR/$TEST_DATASET_ID"
    mkdir -p "$dataset_dir"
    print_debug "Created directory: $dataset_dir"
    
    # Create small text file
    local small_file="$dataset_dir/test.txt"
    cat > "$small_file" << 'EOF'
Hello, this is a test file for NDN transmission!
This file contains multiple lines of text to test the segmentation functionality.
Line 3: Testing data transmission over NDN.
Line 4: This should be split into multiple segments if large enough.
Line 5: Each segment will be transmitted separately.
Line 6: The consumer should be able to retrieve all segments.
Line 7: And reassemble them into the original file.
Line 8: This completes our test data.
EOF
    print_success "Created small test file: $(basename "$small_file") ($(stat -c%s "$small_file") bytes)"
    
    # Create medium-sized text file
    local medium_file="$dataset_dir/medium_test.txt"
    {
        echo "Medium-sized test file for NDN transmission testing."
        echo "Testing multiple segments and performance characteristics."
        echo "========================================"
        for i in {1..50}; do
            echo "Line $i: Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat."
        done
        echo "========================================"
        echo "End of medium test file."
    } > "$medium_file"
    print_success "Created medium test file: $(basename "$medium_file") ($(stat -c%s "$medium_file") bytes)"
    
    # Create large text file
    local large_file="$dataset_dir/large_test.txt"
    {
        echo "Large test file for NDN transmission testing."
        echo "Testing segmentation with many segments."
        echo "========================================"
        for i in {1..20000}; do
            echo "Line $i: Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur."
        done
        echo "========================================"
        echo "End of large test file."
    } > "$large_file"
    print_success "Created large test file: $(basename "$large_file") ($(stat -c%s "$large_file") bytes)"
    
    # Create binary test file
    local binary_file="$dataset_dir/binary_test.dat"
    if command_exists dd; then
        dd if=/dev/urandom of="$binary_file" bs=1024 count=8 2>/dev/null
        print_success "Created binary test file: $(basename "$binary_file") ($(stat -c%s "$binary_file") bytes)"
    else
        print_warning "dd command not available, skipping binary file creation"
    fi
    
    # Create JSON test file
    local json_file="$dataset_dir/test.json"
    cat > "$json_file" << 'EOF'
{
  "name": "NDN Test Data",
  "version": "1.0",
  "description": "Test JSON file for NDN transmission",
  "data": {
    "numbers": [1, 2, 3, 4, 5],
    "strings": ["hello", "world", "ndn"],
    "nested": {
      "key1": "value1",
      "key2": "value2"
    }
  },
  "timestamp": "2025-01-01T00:00:00Z"
}
EOF
    print_success "Created JSON test file: $(basename "$json_file") ($(stat -c%s "$json_file") bytes)"
    
    print_success "Test data creation completed in $dataset_dir"
}

# =============================================================================
# NFD MANAGEMENT
# =============================================================================

# Function to start NFD daemon
start_nfd() {
    print_header "NFD STARTUP"
    print_status "Starting NDN Forwarding Daemon..."
    
    # Check if NFD is already running
    if pgrep -f "nfd" > /dev/null; then
        print_warning "NFD is already running"
        print_status "Stopping existing NFD instance..."
        sudo pkill -f "nfd" 2>/dev/null || true
        sleep 3
    fi
    
    # Create NFD socket directory with proper permissions
    print_status "Creating NFD socket directory..."
    sudo mkdir -p /run/nfd
    sudo chmod 755 /run/nfd
    
    # Check if NFD configuration file is readable
    print_status "Checking NFD configuration..."
    if ! sudo test -r "$NFD_CONFIG"; then
        print_error "NFD configuration file is not readable"
        return 1
    fi
    print_debug "NFD configuration file is accessible"
    
    # Start NFD in background
    print_status "Launching NFD daemon..."
    sudo nfd --config "$NFD_CONFIG" >/dev/null 2>&1 &
    NFD_PID=$!
    print_debug "NFD started with PID: $NFD_PID"
    
    # Wait for NFD to initialize
    print_status "Waiting for NFD to initialize..."
    local count=0
    local max_wait=15
    
    while [ $count -lt $max_wait ]; do
        if [ -S "/run/nfd/nfd.sock" ]; then
            print_success "NFD socket created successfully"
            break
        fi
        sleep 1
        count=$((count + 1))
        print_debug "Waiting for NFD socket... ($count/$max_wait)"
    done
    
    # Verify NFD is running
    if ! pgrep -f "nfd" > /dev/null; then
        print_error "Failed to start NFD - process not found"
        return 1
    fi
    
    if [ ! -S "/run/nfd/nfd.sock" ]; then
        print_error "Failed to start NFD - socket not created"
        return 1
    fi
    
    print_success "NFD started successfully (PID: $NFD_PID)\n"
    return 0
}

# =============================================================================
# PRODUCER MANAGEMENT
# =============================================================================

# Function to start producer
start_producer() {
    print_header "PRODUCER STARTUP"
    print_status "Starting NDN producer..."
    
    # Change to producer directory
    cd "$PRODUCER_DIR" || {
        print_error "Cannot change to producer directory: $PRODUCER_DIR"
        return 1
    }
    
    # Verify producer binary exists and is executable
    if [ ! -x "./bin/ndnput" ]; then
        print_error "Producer binary is not executable: $PRODUCER_DIR/bin/ndnput"
        return 1
    fi
    
    # Start producer in background
    print_status "Launching producer with prefix '$TEST_PREFIX' and dataset ID '$TEST_DATASET_ID'..."
    if [ "$VERBOSE" = true ]; then
        ./bin/ndnput --prefix "$TEST_PREFIX" --datasetId "$TEST_DATASET_ID" &
    else
        ./bin/ndnput --prefix "$TEST_PREFIX" --datasetId "$TEST_DATASET_ID" >/dev/null 2>&1 &
    fi
    PRODUCER_PID=$!
    print_debug "Producer started with PID: $PRODUCER_PID"
    
    # Wait for producer to initialize
    print_status "Waiting for producer to initialize..."
    sleep 3
    
    # Check if producer is still running
    if ! kill -0 "$PRODUCER_PID" 2>/dev/null; then
        print_error "Producer failed to start or crashed immediately"
        return 1
    fi
    
    # Give producer additional time to register with NFD
    print_status "Allowing time for prefix registration..."
    sleep 2
    
    print_success "Producer started successfully (PID: $PRODUCER_PID)"
    return 0
}

# =============================================================================
# TESTING FUNCTIONS
# =============================================================================

# Function to run individual consumer test
run_consumer_test() {
    local test_file="$1"
    local expected_file="$2"
    local test_name="$3"
    
    print_status "Running test: $test_name"
    print_debug "Test file: $test_file"
    print_debug "Expected file: $expected_file"
    
    # Change to consumer directory
    cd "$CONSUMER_DIR" || {
        print_error "Cannot change to consumer directory: $CONSUMER_DIR"
        return 1
    }
    
    # Create result directory if not exists
    local result_dir="$EXPERIMENTS_DIR/result"
    mkdir -p "$result_dir"
    # Create unique output file
    local timestamp=$(date +%s%N)
    local output_file="$result_dir/ndn_test_output_${timestamp}_$(basename "$test_file")"
    print_debug "Output file: $output_file"
    
    # Construct Interest name
    local interest_name="$TEST_PREFIX/$TEST_DATASET_ID/$test_file"
    print_debug "Interest name: $interest_name"
    
    # Run consumer with timeout
    print_status "Sending Interest: $interest_name"
    if timeout 30s ./bin/ndnget "$interest_name" --no-version-discovery > "$output_file" 2>/dev/null; then
        # Check if we got any output
        if [ ! -s "$output_file" ]; then
            print_error "Test '$test_name' failed - No data received"
            print_status "Output file saved for inspection: $output_file"
            return 1
        fi

        local received_size=$(stat -c%s "$output_file" 2>/dev/null || echo "0")
        print_debug "Received data size: $received_size bytes"

        # Compare files if expected file is provided
        if [ -n "$expected_file" ] && [ -f "$expected_file" ]; then
            if cmp -s "$output_file" "$expected_file"; then
                local expected_size=$(stat -c%s "$expected_file" 2>/dev/null || echo "0")
                print_success "Test '$test_name' PASSED - Files match ($expected_size bytes)"
                print_status "Output file saved for inspection: $output_file"
                return 0
            else
                print_error "Test '$test_name' FAILED - Files don't match"
                print_debug "Expected size: $(stat -c%s "$expected_file" 2>/dev/null || echo "unknown")"
                print_debug "Received size: $received_size"
                print_status "Output file saved for inspection: $output_file"
                return 1
            fi
        else
            print_success "Test '$test_name' PASSED - Data received ($received_size bytes)"
            print_status "Output file saved for inspection: $output_file"
            return 0
        fi
    else
        local exit_code=$?
        print_error "Test '$test_name' FAILED - Consumer error (exit code: $exit_code)"
        print_status "Output file saved for inspection: $output_file"
        return 1
    fi
}

# Function to run performance test with detailed metrics
run_performance_test() {
    local test_file="$1"
    local test_name="$2"
    
    print_status "Running performance test: $test_name"
    
    cd "$CONSUMER_DIR" || {
        print_error "Cannot change to consumer directory: $CONSUMER_DIR"
        return 1
    }
    
    local interest_name="$TEST_PREFIX/$TEST_DATASET_ID/$test_file"
    print_debug "Performance test Interest: $interest_name"
    
    # Run consumer with verbose output to capture statistics
    local temp_output="/tmp/ndn_perf_output_$(date +%s%N).txt"
    local temp_stats="/tmp/ndn_perf_stats_$(date +%s%N).txt"
    
    if timeout 60s ./bin/ndnget "$interest_name" --no-version-discovery --verbose > "$temp_output" 2> "$temp_stats"; then
        # Extract performance metrics from stderr
        local time_elapsed=$(grep "Time elapsed:" "$temp_stats" 2>/dev/null | awk '{print $3}' | head -1)
        local segments=$(grep "Segments received:" "$temp_stats" 2>/dev/null | awk '{print $3}' | head -1)
        local transferred_size=$(grep "Transferred size:" "$temp_stats" 2>/dev/null | awk '{print $3}' | head -1)
        local goodput=$(grep "Goodput:" "$temp_stats" 2>/dev/null | awk '{print $2}' | head -1)
        local rtt_stats=$(grep "RTT min/avg/max" "$temp_stats" 2>/dev/null | awk -F'= ' '{print $2}' | head -1)
        
        print_success "Performance test '$test_name' completed:"
        echo "    Time elapsed: ${time_elapsed:-unknown} seconds"
        echo "    Segments received: ${segments:-unknown}"
        echo "    Transferred size: ${transferred_size:-unknown}"
        echo "    Goodput: ${goodput:-unknown}"
        echo "    RTT (min/avg/max): ${rtt_stats:-unknown}"
        
        rm -f "$temp_output" "$temp_stats"
        return 0
    else
        print_error "Performance test '$test_name' failed"
        rm -f "$temp_output" "$temp_stats"
        return 1
    fi
}

# =============================================================================
# TEST SUITE EXECUTION
# =============================================================================

# Function to run all transmission tests
run_tests() {
    print_header "TEST EXECUTION"
    print_status "Running NDN transmission test suite..."
    
    local tests_passed=0
    local tests_total=0
    local dataset_dir="$EXPERIMENTS_DIR/$TEST_DATASET_ID"
    
    # Test 1: Small text file
    print_status "Test 1/5: Small text file transmission"
    tests_total=$((tests_total + 1))
    if run_consumer_test "test.txt" "$dataset_dir/test.txt" "Small text file"; then
        tests_passed=$((tests_passed + 1))
    fi
    echo ""
    
    # Test 2: Medium text file  
    print_status "Test 2/5: Medium text file transmission"
    tests_total=$((tests_total + 1))
    if run_consumer_test "medium_test.txt" "$dataset_dir/medium_test.txt" "Medium text file"; then
        tests_passed=$((tests_passed + 1))
    fi
    echo ""
    
    # Test 3: Large text file
    print_status "Test 3/5: Large text file transmission"
    tests_total=$((tests_total + 1))
    if run_consumer_test "large_test.txt" "$dataset_dir/large_test.txt" "Large text file"; then
        tests_passed=$((tests_passed + 1))
    fi
    echo ""
    
    # Test 4: JSON file
    print_status "Test 4/5: JSON file transmission"
    tests_total=$((tests_total + 1))
    if run_consumer_test "test.json" "$dataset_dir/test.json" "JSON file"; then
        tests_passed=$((tests_passed + 1))
    fi
    echo ""
    
    # Test 5: Binary file (if it exists)
    if [ -f "$dataset_dir/binary_test.dat" ]; then
        print_status "Test 5/5: Binary file transmission"
        tests_total=$((tests_total + 1))
        if run_consumer_test "binary_test.dat" "$dataset_dir/binary_test.dat" "Binary file"; then
            tests_passed=$((tests_passed + 1))
        fi
        echo ""
    else
        print_warning "Skipping binary file test (file not created)"
    fi
    
    # Performance tests
    print_header "PERFORMANCE TESTS"
    print_status "Running performance benchmarks..."
    
    run_performance_test "test.txt" "Small file performance" || true
    echo ""
    run_performance_test "medium_test.txt" "Medium file performance" || true  
    echo ""
    run_performance_test "large_test.txt" "Large file performance" || true
    echo ""
    
    # Test summary
    print_header "TEST RESULTS"
    print_status "Test execution completed"
    echo ""
    echo "  📊 Tests Summary:"
    echo "     Total tests: $tests_total"
    echo "     Passed: $tests_passed"
    echo "     Failed: $((tests_total - tests_passed))"
    echo "     Success rate: $(( tests_passed * 100 / tests_total ))%"
    echo ""
    
    if [ $tests_passed -eq $tests_total ]; then
        print_success "🎉 ALL TESTS PASSED!"
        return 0
    else
        print_error "❌ SOME TESTS FAILED!"
        return 1
    fi
}

# =============================================================================
# HELP AND ARGUMENT PARSING
# =============================================================================

# Function to display help information
show_help() {
    cat << EOF
=============================================================================
NDN Transmission Test Script
=============================================================================

DESCRIPTION:
    Automated testing script for NDN producer-consumer transmission.
    Tests various file types and sizes to verify NDN functionality.

USAGE:
    $0 [OPTIONS]

OPTIONS:
    -h, --help              Show this help message and exit
    -v, --verbose           Enable verbose output and debugging
    -d, --dataset ID        Set dataset ID (default: $TEST_DATASET_ID)
    -p, --prefix PREFIX     Set test prefix (default: $TEST_PREFIX)
    -q, --quiet             Suppress non-essential output
    
EXAMPLES:
    $0                      # Run with default settings
    $0 -v                   # Run with verbose output
    $0 -d 2 -p /mytest      # Use dataset ID 2 and prefix /mytest
    $0 -h                   # Show this help

TEST PROCESS:
    1. Check prerequisites (NFD, binaries, configs)
    2. Create test data files (various sizes and types)
    3. Start NFD (NDN Forwarding Daemon)
    4. Start NDN producer
    5. Run consumer tests with file verification
    6. Run performance benchmarks
    7. Clean up processes and temporary files

REQUIREMENTS:
    - NFD (NDN Forwarding Daemon) installed
    - Producer and consumer binaries built
    - Sudo access for NFD operations
    - Write permissions for test data creation

FILES CREATED:
    - experiments/\$DATASET_ID/test.txt (small text)
    - experiments/\$DATASET_ID/medium_test.txt (medium text)
    - experiments/\$DATASET_ID/large_test.txt (large text)
    - experiments/\$DATASET_ID/test.json (JSON data)
    - experiments/\$DATASET_ID/binary_test.dat (binary data)

=============================================================================
EOF
}

# Function to parse command line arguments
parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_help
                exit 0
                ;;
            -v|--verbose)
                VERBOSE=true
                set -x  # Enable bash debugging
                print_debug "Verbose mode enabled"
                shift
                ;;
            -d|--dataset)
                if [ -z "$2" ] || [[ $2 == -* ]]; then
                    print_error "Dataset ID requires a value"
                    exit 1
                fi
                TEST_DATASET_ID="$2"
                print_debug "Dataset ID set to: $TEST_DATASET_ID"
                shift 2
                ;;
            -p|--prefix)
                if [ -z "$2" ] || [[ $2 == -* ]]; then
                    print_error "Prefix requires a value"
                    exit 1
                fi
                TEST_PREFIX="$2"
                print_debug "Test prefix set to: $TEST_PREFIX"
                shift 2
                ;;
            -q|--quiet)
                QUIET=true
                shift
                ;;
            *)
                print_error "Unknown option: $1"
                echo "Use '$0 --help' for usage information."
                exit 1
                ;;
        esac
    done
}

# =============================================================================
# MAIN EXECUTION
# =============================================================================

# Main function to orchestrate the entire test process
main() {
    # Print banner
    print_header "NDN TRANSMISSION AUTOMATIC TEST SCRIPT"
    echo "Starting automated NDN transmission testing..."
    echo "Dataset ID: $TEST_DATASET_ID"
    echo "Test Prefix: $TEST_PREFIX"
    echo "Verbose Mode: $VERBOSE"
    echo "Script Directory: $SCRIPT_DIR"
    echo ""
    
    # Record start time
    local start_time=$(date +%s)
    
    # Execute test phases
    if check_prerequisites && \
       create_test_data && \
       start_nfd && \
       start_producer; then
        
        # Give systems time to stabilize
        print_status "Allowing systems to stabilize..."
        sleep 5
        
        # Run the test suite
        if run_tests; then
            local end_time=$(date +%s)
            local duration=$((end_time - start_time))
            
            print_header "TEST COMPLETION"
            print_success "🎉 All tests completed successfully!"
            print_success "Total execution time: ${duration} seconds"
            exit 0
        else
            local end_time=$(date +%s)
            local duration=$((end_time - start_time))
            
            print_header "TEST COMPLETION"
            print_error "❌ Some tests failed!"
            print_status "Total execution time: ${duration} seconds"
            exit 1
        fi
    else
        print_header "SETUP FAILURE"
        print_error "❌ Failed to set up test environment!"
        exit 1
    fi
}

# =============================================================================
# SCRIPT ENTRY POINT
# =============================================================================

# Parse command line arguments first
parse_arguments "$@"

# Execute main function
main
