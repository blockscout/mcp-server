#!/usr/bin/env bash
#
# Evaluation Runner Script for Blockscout MCP Server
#
# Usage:
#   ./run.sh              - Run interactive Gemini session
#   ./run.sh 4            - Run test at index 4 (0-indexed, runs eval-004)
#   ./run.sh eval-004     - Run test by ID
#   ./run.sh --dry 4      - Show command without executing (dry run)
#   ./run.sh list         - List all available tests
#   ./run.sh print 4      - Print details of test at index 4
#   ./run.sh print eval-004 - Print details of test by ID
#   ./run.sh clean        - Stop and remove containers
#
set -euo pipefail

# =============================================================================
# Configurable Variables (can be overridden via environment)
# =============================================================================
SANITY_CHECK_TIMEOUT="${SANITY_CHECK_TIMEOUT:-2}"  # Max seconds for external server check
SKIP_SANITY_CHECK="${SKIP_SANITY_CHECK:-false}"    # Set to "true" to disable external URL check
LIST_TRUNCATE_LENGTH="${LIST_TRUNCATE_LENGTH:-70}" # Max chars for question in 'list' output

# =============================================================================
# Constants
# =============================================================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EVAL_SET_FILE="${SCRIPT_DIR}/eval-set.json"
RESULTS_DIR="${SCRIPT_DIR}/results"
DEFAULT_MCP_URL="http://mcp-server:8080"
GEMINI_IMAGE_REGISTRY="us-docker.pkg.dev/gemini-code-dev/gemini-cli/sandbox"
MCP_SERVER_IMAGE="ghcr.io/blockscout/mcp-server:latest"

# Global state (set during validation/argument parsing)
USE_INTERNAL_SERVER="false"
DRY_RUN="false"

# =============================================================================
# Helper Functions
# =============================================================================

error() {
    echo "ERROR: $1" >&2
    exit 1
}

warn() {
    echo "WARNING: $1" >&2
}

info() {
    echo "INFO: $1"
}

# Check if a Docker image exists locally
image_exists() {
    local image="$1"
    docker image inspect "$image" >/dev/null 2>&1
}

# Get docker compose run flags based on server mode
# When using external server, includes --no-deps to skip starting mcp-server
docker_compose_run_flags() {
    if [[ "$USE_INTERNAL_SERVER" == "true" ]]; then
        echo "--rm -i"
    else
        echo "--rm -i --no-deps"
    fi
}

# Sanity check for external server availability using HTTP HEAD
check_external_server() {
    local url="$1"
    local status_code
    
    status_code=$(curl --head \
        --connect-timeout "$SANITY_CHECK_TIMEOUT" \
        --max-time "$SANITY_CHECK_TIMEOUT" \
        --silent \
        --output /dev/null \
        --write-out "%{http_code}" \
        "$url" 2>/dev/null) || true
    
    # Accept 2xx and 3xx status codes
    [[ "$status_code" =~ ^[23] ]]
}

# Load environment from .env file if it exists
load_env() {
    local env_file="${SCRIPT_DIR}/.env"
    if [[ -f "$env_file" ]]; then
        # Export variables from .env, ignoring comments and empty lines
        set -a
        # shellcheck source=/dev/null
        source "$env_file"
        set +a
    fi
}

# Get test data by index (0-indexed)
get_test_by_index() {
    local index="$1"
    jq -e ".[$index]" "$EVAL_SET_FILE" 2>/dev/null
}

# Get test data by ID
get_test_by_id() {
    local id="$1"
    jq -e ".[] | select(.id == \"$id\")" "$EVAL_SET_FILE" 2>/dev/null
}

# Extract field from test JSON
get_field() {
    local json="$1"
    local field="$2"
    echo "$json" | jq -r ".$field // empty"
}

# Get the index of a test by ID
get_index_by_id() {
    local id="$1"
    jq -e "to_entries[] | select(.value.id == \"$id\") | .key" "$EVAL_SET_FILE" 2>/dev/null
}

# Get total number of tests
get_test_count() {
    jq -e "length" "$EVAL_SET_FILE" 2>/dev/null
}

# =============================================================================
# Validation Functions
# =============================================================================

validate_gemini_version() {
    if [[ -z "${GEMINI_CLI_DOCKER_IMAGE_VERSION:-}" ]]; then
        error "GEMINI_CLI_DOCKER_IMAGE_VERSION is not set.
Please configure it in ${SCRIPT_DIR}/.env file:
  echo 'GEMINI_CLI_DOCKER_IMAGE_VERSION=0.2.0' >> ${SCRIPT_DIR}/.env"
    fi
}

validate_gemini_image() {
    # Skip image check in dry run mode
    if [[ "$DRY_RUN" == "true" ]]; then
        return 0
    fi
    
    local image="${GEMINI_IMAGE_REGISTRY}:${GEMINI_CLI_DOCKER_IMAGE_VERSION}"
    if ! image_exists "$image"; then
        error "Gemini CLI image not found locally: $image
Please pull the image first:
  docker pull $image"
    fi
}

validate_mcp_server() {
    local mcp_url="${MCP_SERVER_URL:-$DEFAULT_MCP_URL}"
    
    # Check if using internal server (default or explicitly set to default)
    if [[ -z "${MCP_SERVER_URL:-}" ]] || [[ "$mcp_url" == "$DEFAULT_MCP_URL" ]]; then
        # Using internal server
        USE_INTERNAL_SERVER="true"
        
        # Skip image check in dry run mode
        if [[ "$DRY_RUN" == "true" ]]; then
            info "Using internal MCP server (dry run - image check skipped)"
            return 0
        fi
        
        if ! image_exists "$MCP_SERVER_IMAGE"; then
            error "MCP server image not found locally.
Please choose one of the following options:
  1. Pull the image:      docker pull $MCP_SERVER_IMAGE
  2. Build locally:       docker build -t $MCP_SERVER_IMAGE .
  3. Use external server: Set MCP_SERVER_URL in ${SCRIPT_DIR}/.env
     Example: echo 'MCP_SERVER_URL=https://your-server.com' >> ${SCRIPT_DIR}/.env"
        fi
        info "Using internal MCP server (image: $MCP_SERVER_IMAGE)"
    else
        # Using external server
        USE_INTERNAL_SERVER="false"
        
        # Skip sanity check in dry run mode
        if [[ "$DRY_RUN" == "true" ]]; then
            info "Using external MCP server: $mcp_url (dry run - sanity check skipped)"
            return 0
        fi
        
        if [[ "$SKIP_SANITY_CHECK" != "true" ]]; then
            info "Checking external MCP server availability: $mcp_url"
            if ! check_external_server "$mcp_url"; then
                error "External MCP server is not reachable: $mcp_url
The server did not respond within ${SANITY_CHECK_TIMEOUT} seconds.
Please verify:
  1. The server URL is correct
  2. The server is running and accessible
  3. Network connectivity is available

To skip this check, set SKIP_SANITY_CHECK=true"
            fi
            info "External MCP server is reachable"
        else
            warn "Sanity check skipped (SKIP_SANITY_CHECK=true)"
        fi
    fi
}

# =============================================================================
# Command Execution Functions
# =============================================================================

run_clean() {
    info "Stopping and removing containers..."
    cd "$SCRIPT_DIR"
    docker compose down
    info "Cleanup complete"
}

run_list() {
    local count
    count=$(get_test_count)
    
    if [[ -z "$count" ]] || [[ "$count" -eq 0 ]]; then
        echo "No tests found in $EVAL_SET_FILE"
        return 0
    fi
    
    # Calculate padding width based on max index
    local max_index=$((count - 1))
    local pad_width=${#max_index}
    
    # Iterate through all tests
    for ((i=0; i<count; i++)); do
        local test_json
        test_json=$(get_test_by_index "$i")
        
        local id
        local question
        id=$(get_field "$test_json" "id")
        question=$(get_field "$test_json" "question")
        
        # Truncate question to configured length
        local truncated_question="${question:0:$LIST_TRUNCATE_LENGTH}"
        if [[ ${#question} -gt $LIST_TRUNCATE_LENGTH ]]; then
            truncated_question="${truncated_question}..."
        fi
        
        # Print with proper padding
        printf "%${pad_width}d: %s: %s\n" "$i" "$id" "$truncated_question"
    done
}

run_print() {
    local arg="$1"
    local test_json=""
    local index=""
    
    if [[ "$arg" =~ ^[0-9]+$ ]]; then
        # Numeric argument - treat as 0-indexed position
        index="$arg"
        test_json=$(get_test_by_index "$arg")
        if [[ -z "$test_json" ]]; then
            error "No test found at index $arg (0-indexed)"
        fi
    elif [[ "$arg" =~ ^eval-[0-9]+$ ]]; then
        # ID format - lookup by ID
        test_json=$(get_test_by_id "$arg")
        if [[ -z "$test_json" ]]; then
            error "No test found with ID: $arg"
        fi
        index=$(get_index_by_id "$arg")
    else
        error "Invalid test identifier: $arg
Usage:
  ./run.sh print 4        - Print test at index 4
  ./run.sh print eval-004 - Print test by ID"
    fi
    
    # Extract fields
    local id
    local question
    local expected_format
    local ground_truth
    
    id=$(get_field "$test_json" "id")
    question=$(get_field "$test_json" "question")
    expected_format=$(get_field "$test_json" "expected_result_format")
    ground_truth=$(echo "$test_json" | jq -r '.ground_truth // {}')
    
    # Check if ground_truth is empty
    local ground_truth_display="N/A"
    if [[ "$ground_truth" != "{}" ]] && [[ -n "$ground_truth" ]]; then
        ground_truth_display="$ground_truth"
    fi
    
    echo "index: $index"
    echo "id: $id"
    echo "question: \"$question\""
    echo "format_instructions: \"${expected_format:-}\""
    echo "ground_truth: $ground_truth_display"
}

run_interactive() {
    info "Starting interactive Gemini session..."
    cd "$SCRIPT_DIR"
    # shellcheck disable=SC2046
    docker compose run $(docker_compose_run_flags) evaluation gemini -y -e none
}

run_test() {
    local test_json="$1"
    
    # Extract test fields
    local id
    local model
    local question
    local expected_format
    
    id=$(get_field "$test_json" "id")
    model=$(get_field "$test_json" "model")
    question=$(get_field "$test_json" "question")
    expected_format=$(get_field "$test_json" "expected_result_format")
    
    if [[ -z "$id" ]]; then
        error "Test ID is missing from test data"
    fi
    
    if [[ -z "$question" ]]; then
        error "Question is missing from test data for $id"
    fi
    
    # Ensure results directory exists
    mkdir -p "$RESULTS_DIR"
    
    # Generate timestamp for file names
    local timestamp
    timestamp=$(date +"%Y-%m-%d-%H-%M-%S")
    
    local record_file="results/${id}-${timestamp}.json"
    local output_file="results/${id}-output-${timestamp}.json"
    
    # Build the prompt
    local prompt="${question}"
    if [[ -n "$expected_format" ]]; then
        prompt="${question} ${expected_format}"
    fi
    
    # Build the docker command with appropriate flags
    local cmd
    # shellcheck disable=SC2046
    cmd=(docker compose run $(docker_compose_run_flags) evaluation gemini -y -e none)
    
    # Add model flag if specified
    if [[ -n "$model" ]]; then
        cmd+=(-m "$model")
    fi
    
    cmd+=(--output-format json)
    cmd+=(-p "$prompt")
    cmd+=(--record-responses "$record_file")
    
    info "Running evaluation: $id"
    info "Model: ${model:-<default>}"
    info "Question: $question"
    info "Expected format: ${expected_format:-<none>}"
    echo ""
    
    cd "$SCRIPT_DIR"
    
    # Dry run mode - just print the command
    if [[ "$DRY_RUN" == "true" ]]; then
        echo "Command to execute:"
        echo "  ${cmd[*]} | tee $output_file"
        echo ""
        echo "Output files would be:"
        echo "  Record: ${SCRIPT_DIR}/${record_file}"
        echo "  Output: ${SCRIPT_DIR}/${output_file}"
        return 0
    fi
    
    # Execute the command with tee
    "${cmd[@]}" | tee "$output_file"
    local exit_code=${PIPESTATUS[0]}
    
    echo ""
    echo "========================================"
    echo "Evaluation complete. Output files:"
    echo "  Record: ${SCRIPT_DIR}/${record_file}"
    echo "  Output: ${SCRIPT_DIR}/${output_file}"
    echo "========================================"
    
    return $exit_code
}

# =============================================================================
# Main Entry Point
# =============================================================================

main() {
    # Parse --dry flag from any position
    local args=()
    for arg in "$@"; do
        if [[ "$arg" == "--dry" ]]; then
            DRY_RUN="true"
        else
            args+=("$arg")
        fi
    done
    
    local arg="${args[0]:-}"
    
    # Check for jq dependency (needed for most commands)
    if ! command -v jq &>/dev/null; then
        error "jq is required but not installed. Please install jq first."
    fi
    
    # Handle 'clean' command without loading env or validating
    if [[ "$arg" == "clean" ]]; then
        run_clean
        exit 0
    fi
    
    # Handle 'list' command without loading env or validating
    if [[ "$arg" == "list" ]]; then
        run_list
        exit 0
    fi
    
    # Handle 'print' command without loading env or validating
    if [[ "$arg" == "print" ]]; then
        local test_arg="${args[1]:-}"
        if [[ -z "$test_arg" ]]; then
            error "Missing test identifier for 'print' command.
Usage:
  ./run.sh print 4        - Print test at index 4
  ./run.sh print eval-004 - Print test by ID"
        fi
        run_print "$test_arg"
        exit 0
    fi
    
    # Load environment variables
    load_env
    
    # Validate required configurations and images
    validate_gemini_version
    validate_gemini_image
    validate_mcp_server
    
    # Handle no argument - interactive mode
    if [[ -z "$arg" ]]; then
        run_interactive
        exit 0
    fi
    
    # Handle test selection
    local test_json=""
    
    if [[ "$arg" =~ ^[0-9]+$ ]]; then
        # Numeric argument - treat as 0-indexed position
        test_json=$(get_test_by_index "$arg")
        if [[ -z "$test_json" ]]; then
            error "No test found at index $arg (0-indexed)"
        fi
    elif [[ "$arg" =~ ^eval-[0-9]+$ ]]; then
        # ID format - lookup by ID
        test_json=$(get_test_by_id "$arg")
        if [[ -z "$test_json" ]]; then
            error "No test found with ID: $arg"
        fi
    else
        error "Invalid argument: $arg
Usage:
  ./run.sh              - Run interactive Gemini session
  ./run.sh 4            - Run test at index 4 (0-indexed, runs eval-004)
  ./run.sh eval-004     - Run test by ID
  ./run.sh --dry 4      - Show command without executing (dry run)
  ./run.sh list         - List all available tests
  ./run.sh print 4      - Print details of test at index 4
  ./run.sh print eval-004 - Print details of test by ID
  ./run.sh clean        - Stop and remove containers"
    fi
    
    run_test "$test_json"
}

main "$@"
