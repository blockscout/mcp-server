#!/bin/bash

# Build script for Blockscout MCP Server Desktop Extension
# This script can be run inside the Docker container to build the extension automatically
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

echo "🚀 Building Blockscout MCP Server Desktop Extension (${MODE} mode)..."

# Step 1: Install system dependencies
echo "📦 Installing system dependencies..."
apt-get update -qq
apt-get install -y openssl

# Step 2: Install DXT CLI
echo "🔧 Installing DXT CLI..."
npm install -g @anthropic-ai/dxt

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
npm install mcp-remote@0.1.18

# Step 6: Package the extension
echo "📦 Packaging extension..."
if [[ "$MODE" == "dev" ]]; then
    DXT_FILENAME="blockscout-mcp-dev.dxt"
else
    DXT_FILENAME="blockscout-mcp.dxt"
fi
dxt pack . "$DXT_FILENAME"

# Step 7: Sign the extension
echo "✍️  Signing extension..."
dxt sign "$DXT_FILENAME" --self-signed

# Step 8: Verify the extension
echo "✅ Verifying extension..."
if dxt verify "$DXT_FILENAME"; then
    echo "   ✅ Extension signature verified successfully"
else
    echo "   ⚠️  Extension verification failed (expected for self-signed certificates)"
    echo "   ℹ️  This is normal when using self-signed certificates and won't affect functionality"
fi
echo ""
echo "ℹ️  Extension info:"
dxt info "$DXT_FILENAME"

echo ""
echo "🎉 Extension built successfully!"
echo "📄 Output: dxt/_build/$DXT_FILENAME"
echo "🔧 Mode: $MODE"
if [[ "$MODE" == "dev" ]]; then
    echo "⚙️  Note: Dev mode requires manual configuration of Blockscout MCP server URL"
fi
echo ""
echo "To use this extension:"
echo "1. Copy the .dxt file from the container to your host system"
echo "2. Install it in Claude Desktop"
