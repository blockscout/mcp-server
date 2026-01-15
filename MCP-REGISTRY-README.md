# MCP Registry for Blockscout MCP Server

This document explains the purpose of the MCP Registry, the role of `server.json`, and provides instructions for publishing the Blockscout MCP Server to the registry.

## Why is the MCP Registry Needed?

The Model Context Protocol (MCP) Registry serves as a crucial component for the discoverability and management of MCP servers. It provides:

* **Centralized Metadata Repository:** A single, official source for server creators to publish metadata about their publicly-accessible MCP servers.
* **Server Discovery:** A REST API that allows MCP clients and aggregators to programmatically discover available servers.
* **Standardization:** Standardized installation and configuration information for MCP servers, ensuring consistency across different deployments.
* **Namespace Management:** A mechanism for managing server namespaces through DNS verification, which helps ensure ownership and authenticity.

## What is `server.json`?

The `server.json` file is the core configuration file for publishing your MCP server to the registry. It contains essential metadata about your server, including:

* **Schema reference:** A link to the JSON schema for validation.
* **Name:** A unique identifier for your server, typically in reverse-DNS format (e.g., `com.blockscout/mcp-server`).
* **Description:** A brief explanation of what your server does.

* **Version:** The current version of your server, aligning with your project's version.
    *Note: Ensure this version matches the `version` specified in `pyproject.toml` and `blockscout_mcp_server/__init__.py` to maintain consistency across the project and the registry.*
* **Website URL:** The official website for your project.
* **Repository:** Information about your project's source code repository.
* **Remotes:** Details about how to connect to your server, including the transport type and URL.

For the Blockscout MCP Server, the `server.json` is configured to point to the official remote Blockscout server (`https://mcp.blockscout.com/mcp`) using `streamable-http` transport, and does not support local deployments from the registry.

## Original Publishing Instructions

For the most up-to-date and comprehensive instructions on publishing an MCP server, please refer to the official MCP Registry documentation:

[Quickstart: Publish an MCP Server](https://github.com/modelcontextprotocol/registry/blob/main/docs/modelcontextprotocol-io/quickstart.mdx)

## Verifying DNS Configuration

Before publishing, you can verify that the DNS TXT record for `blockscout.com` contains the MCP authentication public key:

```bash
curl -s "https://dns.google/resolve?name=blockscout.com&type=TXT" | jq '.Answer[] | select(.data | contains("MCPv1"))'
```

The output should show a record like:

```json
{
  "name": "blockscout.com.",
  "type": 16,
  "TTL": 300,
  "data": "v=MCPv1; k=ed25519; p=<PUBLIC_KEY>"
}
```

## Manual Publishing Steps

While the primary method for publishing new server versions is through GitHub Actions (as described below), you can manually publish the Blockscout MCP Server to the registry using the `mcp-publisher` CLI tool. These steps assume that your `key.pem` file for DNS authorization is located in the project root directory.

1. **Install `mcp-publisher` CLI:**

    ```bash
    curl -L "https://github.com/modelcontextprotocol/registry/releases/latest/download/mcp-publisher_$(uname -s | tr '[:upper:]' '[:lower:]')_$(uname -m | sed 's/x86_64/amd64/;s/aarch64/arm64/').tar.gz" | tar xz mcp-publisher && sudo mv mcp-publisher /usr/local/bin/
    ```

2. **Login to the Registry with DNS Ownership Proof:**
    This command uses the `key.pem` file to authenticate your domain ownership (`blockscout.com`).

    ```bash
    mcp-publisher login dns --domain blockscout.com --private-key "$(openssl pkey -in key.pem -noout -text | grep -A3 "priv:" | tail -n +2 | tr -d ' :\n')"
    ```

    *Note: The `openssl` command extracts the private key content from `key.pem` and passes it to `mcp-publisher`.*

3. **Publish the Server:**
    Once logged in, navigate to the directory containing your `server.json` file (the project root) and run the publish command:

    ```bash
    mcp-publisher publish
    ```

## Publishing New Server Versions via GitHub Actions

The primary method for publishing new server versions for the Blockscout MCP Server is through **GitHub Actions**. This automates the publishing process, ensuring consistency and reducing manual effort.

For details on the automated publishing workflow, please refer to the GitHub Actions workflow file: `.github/workflows/mcp-registry.yml`.
