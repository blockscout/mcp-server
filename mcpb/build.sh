#!/bin/bash

# Build script for Blockscout MCP Server MCP Bundle (Development Only)
# This script can be run inside the Docker container to build the bundle automatically
#
# Usage: ./build.sh
#
# Note: This bundle is for development/testing purposes only.
# For production use, install from the Anthropic Connectors Directory:
# https://claude.com/connectors/blockscout

set -e  # Exit on any error

MCPB_FILENAME="blockscout-mcp-dev.mcpb"

echo "🚀 Building Blockscout MCP Server MCP Bundle (development)..."

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

# Step 4: Copy required files
echo "📋 Copying manifest and assets..."
cp manifest.json _build/
cp blockscout.png _build/

# Step 5: Change to build directory and install dependencies
echo "📦 Installing mcp-remote dependency..."
cd _build
npm install mcp-remote@0.1.37

# Step 6: Package the bundle
echo "📦 Packaging bundle..."
mcpb pack . "$MCPB_FILENAME"

# Step 7: Verify the bundle
echo "✅ Verifying bundle..."
if mcpb verify "$MCPB_FILENAME"; then
    echo "   ✅ Bundle verified successfully"
else
    echo "   ⚠️  Bundle verification failed"
fi
echo ""
echo "ℹ️  Bundle info:"
mcpb info "$MCPB_FILENAME"

echo ""
echo "🎉 Bundle built successfully!"
echo "📄 Output: mcpb/_build/$MCPB_FILENAME"
echo ""
echo "⚙️  Note: This is a development bundle. Configure the Blockscout MCP server URL"
echo "   during installation in Claude Desktop (default: http://127.0.0.1:8000/mcp)"
echo ""
echo "To use this bundle:"
echo "1. Copy the .mcpb file from the container to your host system"
echo "2. Install it in Claude Desktop"
echo "3. Configure the MCP server URL when prompted"
