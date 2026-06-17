#!/bin/bash

# Build script for Blockscout MCP Server MCP Bundle
# This script can be run inside the Docker container to build the bundle automatically
#
# Usage: ./build.sh [mode]
#   mode: "prod" (default) or "dev"

set -e  # Exit on any error

# Parse arguments
MODE="${1:-prod}"

if [[ "$MODE" != "prod" && "$MODE" != "dev" ]]; then
    echo "❌ Error: Mode must be 'prod' or 'dev'"
    echo "Usage: $0 [prod|dev]"
    exit 1
fi

echo "🚀 Building Blockscout MCP Server MCP Bundle (${MODE} mode)..."

# Step 1: Install system dependencies
echo "📦 Installing system dependencies..."
apt-get update -qq
apt-get install -y openssl

# Step 2: Install MCPB CLI
echo "🔧 Installing MCPB CLI..."
npm install -g @anthropic-ai/mcpb

# Step 3: Prepare build directory
echo "📂 Preparing build directory..."
if [ -d "_build" ]; then
    echo "   Cleaning existing _build directory..."
    rm -rf _build
fi

mkdir _build

# Step 4: Copy required files based on mode
echo "📋 Copying manifest and assets..."
if [[ "$MODE" == "dev" ]]; then
    echo "   Using development manifest (manifest-dev.json)"
    cp manifest-dev.json _build/manifest.json
else
    echo "   Using production manifest (manifest.json)"
    cp manifest.json _build/
fi
cp blockscout.png _build/

# Step 5: Change to build directory and install dependencies
echo "📦 Installing mcp-remote dependency..."
cd _build
npm install mcp-remote@0.1.37

# Step 6: Package the bundle
echo "📦 Packaging bundle..."
if [[ "$MODE" == "dev" ]]; then
    MCPB_FILENAME="blockscout-mcp-dev.mcpb"
else
    MCPB_FILENAME="blockscout-mcp.mcpb"
fi
mcpb pack . "$MCPB_FILENAME"

# Step 7: Verify the bundle
# Verification could fail since we intentionally don't sign the bundle
echo "✅ Verifying bundle..."
if mcpb verify "$MCPB_FILENAME"; then
    echo "   ✅ Bundle verified successfully"
else
    echo "   ⚠️  Bundle verification failed (expected for non-signed bundles)"
    echo "   ℹ️  This is normal when using self-signed certificates and won't affect functionality"
fi
echo ""
echo "ℹ️  Bundle info:"
mcpb info "$MCPB_FILENAME"

echo ""
echo "🎉 Bundle built successfully!"
echo "📄 Output: mcpb/_build/$MCPB_FILENAME"
echo "🔧 Mode: $MODE"
if [[ "$MODE" == "dev" ]]; then
    echo "⚙️  Note: Dev mode requires manual configuration of both Blockscout MCP server URL and Blockscout PRO API Key"
fi
echo ""
echo "To use this bundle:"
echo "1. Copy the .mcpb file from the container to your host system"
echo "2. Install it in Claude Desktop"
echo "3. Configure the Blockscout PRO API Key when prompted"
