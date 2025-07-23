#!/bin/bash
set -euo pipefail

source .gemini/.env

# Root dir for Gemini CLI
WORKSPACE_DIR="/workspace/bs-mcp-server"

CURRENT_DIR="$(pwd)"

GEMINI_CLI_SANDBOX_IMAGE="us-docker.pkg.dev/gemini-code-dev/gemini-cli/sandbox"
GEMINI_CLI_SANDBOX_VERSION=${GEMINI_CLI_VERSION}
GEMINI_CLI_SANDBOX=${GEMINI_CLI_SANDBOX_IMAGE}:${GEMINI_CLI_SANDBOX_VERSION}

docker run --rm -it \
  -v "${HOME}/.gemini":/home/node/.gemini \
  -v "${CURRENT_DIR}":"${WORKSPACE_DIR}" -w "${WORKSPACE_DIR}" \
  -v "${CURRENT_DIR}"/temp:/workspace/temp \
  ${GEMINI_CLI_SANDBOX}

