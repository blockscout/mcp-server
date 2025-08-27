#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[ -f "${SCRIPT_DIR}/.env" ] || {
  echo "ERROR: ${SCRIPT_DIR}/.env not found" >&2
  exit 1
}
source "${SCRIPT_DIR}/.env"

if [ -z "${CODEALIVE_API_KEY:-}" ]; then
  echo "WARNING: CODEALIVE_API_KEY is not set. The CodeAlive MCP server will not be available." >&2
  CODEALIVE_API_KEY=""
fi

# Root dir for Gemini CLI
WORKSPACE_DIR="/workspace/bs-mcp-server"

CURRENT_DIR="$(pwd)"

GEMINI_CLI_SANDBOX_IMAGE="us-docker.pkg.dev/gemini-code-dev/gemini-cli/sandbox"
GEMINI_CLI_SANDBOX_VERSION=${GEMINI_CLI_VERSION}
GEMINI_CLI_SANDBOX=${GEMINI_CLI_SANDBOX_IMAGE}:${GEMINI_CLI_SANDBOX_VERSION}

docker run --rm -it \
  -e CODEALIVE_API_KEY="${CODEALIVE_API_KEY}" \
  -v "${HOME}/.gemini":/home/node/.gemini \
  -v "${CURRENT_DIR}":"${WORKSPACE_DIR}" -w "${WORKSPACE_DIR}" \
  -v "${CURRENT_DIR}"/temp:/workspace/temp \
  ${GEMINI_CLI_SANDBOX}
