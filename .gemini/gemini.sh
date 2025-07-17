#!/bin/bash

# Root dir for Gemini CLI
WORKSPACE_DIR="/workspace/bs-mcp-server"

PWD="$(pwd)"

# Could be used for additional mount points
EXTRA_ARGS="-v ${PWD}/temp:/workspace/temp"

GEMINI_CLI_SANDBOX_IMAGE="us-docker.pkg.dev/gemini-code-dev/gemini-cli/sandbox"
GEMINI_CLI_SANDBOX_VERSION="0.1.12"
GEMINI_CLI_SANDBOX=${GEMINI_CLI_SANDBOX_IMAGE}:${GEMINI_CLI_SANDBOX_VERSION}

docker run --rm -it \
  -v "$(echo ~)/.gemini":/home/node/.gemini \
  -v ${PWD}:${WORKSPACE_DIR} -w ${WORKSPACE_DIR} \
  ${EXTRA_ARGS} \
  ${GEMINI_CLI_SANDBOX}

