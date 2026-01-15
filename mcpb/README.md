# Blockscout MCP Server MCP Bundle (Development Only)

> **Important:** This bundle is intended for **development and testing purposes only**. For production use with Claude, install the official Blockscout connector from the [Anthropic Connectors Directory](https://claude.com/connectors/blockscout).

## General MCPB Specification

An MCP Bundle (.mcpb file) bundles an entire MCP server — including all dependencies — into a single package that can be effortlessly installed in the Claude Desktop.

- [MCPB architecture overview, capabilities, and integration patterns](https://github.com/modelcontextprotocol/mcpb/blob/main/README.md)
- [Complete bundle manifest structure and field definitions](https://github.com/modelcontextprotocol/mcpb/blob/main/MANIFEST.md)
- [Reference implementations including a "Hello World" example](https://github.com/modelcontextprotocol/mcpb/tree/main/examples)

## Purpose

This development bundle allows developers to test local or custom instances of the Blockscout MCP Server with Claude Desktop. It uses [mcp-remote](https://github.com/geelen/mcp-remote) to proxy requests to a configurable MCP server URL.

**Use cases:**

- Testing local MCP server changes before deployment
- Connecting to custom/self-hosted Blockscout MCP instances
- Development and debugging workflows

## Technical Details

The bundle doesn't include the original Python package. Instead, it uses `mcp-remote` to proxy all requests to a user-configured Blockscout MCP Server URL (default: `http://127.0.0.1:8000/mcp`).

The reasons for this approach:

- **Simplify the distribution**: Node.js (required for `mcp-remote`) is shipped with Claude Desktop, whereas Python is not.
- **Configurable endpoint**: Users can specify any MCP server URL during installation.
- **Open source in action**: Uses community-tested and trusted `mcp-remote` for proxy functionality.

## Building the Bundle

### Automated Build (Recommended)

For automated building using the provided build script:

```shell
docker run --rm -it -v "$(pwd)"/mcpb:/workspace -w /workspace node:20-slim bash -c "./build.sh"
```

This will create the bundle at `mcpb/_build/blockscout-mcp-dev.mcpb`.

### Manual Build

For manual building or if you prefer step-by-step control:

1. This step is optional and required only if there is no local Node.js installation.

    For the project directory run:

    ```shell
    docker run --rm -it -v "$(pwd)"/mcpb:/workspace -w /workspace node:20-slim bash
    ```

    In the interactive session then execute the following steps:

    ```shell
    apt-get update
    apt-get install -y openssl
    ```

2. Install the MCPB CLI:

    ```shell
    npm install -g @anthropic-ai/mcpb
    ```

3. Package the bundle:

    ```shell
    mkdir _build
    cp manifest.json blockscout.png _build/
    cd _build
    npm install mcp-remote@0.1.18
    mcpb pack . blockscout-mcp-dev.mcpb
    ```

4. Verify the bundle:

    ```shell
    mcpb verify blockscout-mcp-dev.mcpb 
    mcpb info blockscout-mcp-dev.mcpb
    ```

Finally the built bundle will be in `mcpb/_build/blockscout-mcp-dev.mcpb`.

## Installation

After building, install the bundle in Claude Desktop:

1. Copy the `.mcpb` file from the container to your host system
2. Double-click the file or drag it into Claude Desktop's Extensions window
3. Configure the Blockscout MCP Server URL when prompted (default: `http://127.0.0.1:8000/mcp`)
