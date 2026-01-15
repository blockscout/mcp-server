# Blockscout MCP Server MCP Bundle

## General MCPB Specification

An MCP Bundle (.mcpb file) bundles an entire MCP server — including all dependencies — into a single package that can be effortlessly installed in the Claude Desktop.

- [MCPB architecture overview, capabilities, and integration patterns](https://github.com/modelcontextprotocol/mcpb/blob/main/README.md)
- [Complete bundle manifest structure and field definitions](https://github.com/modelcontextprotocol/mcpb/blob/main/MANIFEST.md)
- [Reference implementations including a "Hello World" example](https://github.com/modelcontextprotocol/mcpb/tree/main/examples)

## Technical Details

The blockscout MCP Server MCP Bundle doesn't include the original Python package. Instead, it uses [mcp-remote](https://github.com/geelen/mcp-remote) to proxy all requests to [the official Blockscout MCP Server](http://mcp.blockscout.com/) (see configuration details in the `server` section of the [manifest.json](manifest.json) file).

The reasons for this are:

- **Upgradeless improvements**: the stable version of the Blockscout MCP Server with the newest functionality is always deployed on `http://mcp.blockscout.com/mcp`, therefore users don't need to upgrade the bundle to get access to the newest features.
- **Simplify the distribution**: while Claude Desktop supports installing Python-based bundles, Python is not shipped with the application whereas Node.js (which is required for `mcp-remote`) is. Reducing assumptions about the software stack makes the bundle more accessible to a wider range of users. If a user is experienced enough to install Python/Docker, they can easily install the original MCP server on the local machine by themselves.
- **Simplify the development**: there is no need to adapt the MCP server to comply with the MCPB specification.
- **Open source in action**: the Blockscout MCP server code does not need to implement its own proxy functionality; instead, community-tested and trusted `mcp-remote` is used.

## Packaging instructions

### Automated Build (Recommended)

For automated building using the provided build script:

**Production mode (default):**

```shell
docker run --rm -it -v "$(pwd)"/mcpb:/workspace -w /workspace node:20-slim bash -c "./build.sh"
# or explicitly:
docker run --rm -it -v "$(pwd)"/mcpb:/workspace -w /workspace node:20-slim bash -c "./build.sh prod"
```

**Development mode:**

```shell
docker run --rm -it -v "$(pwd)"/mcpb:/workspace -w /workspace node:20-slim bash -c "./build.sh dev"
```

#### Build Modes

- **Production (`prod`)**: Uses `manifest.json` and connects to the official `https://mcp.blockscout.com/mcp` server. Creates `blockscout-mcp.mcpb`.
- **Development (`dev`)**: Uses `manifest-dev.json` with configurable URL and creates `blockscout-mcp-dev.mcpb`. Users can configure the Blockscout MCP server URL during installation in Claude Desktop.

This will automatically handle all the steps below and create the bundle at `mcpb/_build/blockscout-mcp[--dev].mcpb`.

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
    mcpb pack . blockscout-mcp.mcpb
    ```

4. Verify the bundle:

    ```shell
    mcpb verify blockscout-mcp.mcpb 
    mcpb info blockscout-mcp.mcpb
    ```

Finally the built bundle will be in `mcpb/_build/blockscout-mcp.mcpb`.
