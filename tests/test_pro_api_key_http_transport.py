# SPDX-License-Identifier: LicenseRef-Blockscout
"""Transport-level tests that prove the real FastMCP streamable-HTTP transport delivers
a client-supplied request header into the tool's ctx in the shape that
extract_client_pro_api_key_from_ctx reads.
"""

import json

import pytest
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.testclient import TestClient

from blockscout_mcp_server.config import config as server_config
from blockscout_mcp_server.pro_api_key_context import pro_api_key_scope, resolve_pro_api_key

_MCP_HEADERS = {
    "Accept": "application/json, text/event-stream",
    "Content-Type": "application/json",
}


def _build_tools_call_body(tool_name: str, arguments: dict | None = None) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments or {}},
    }


@pytest.fixture()
def mcp_app(monkeypatch):
    """A throwaway FastMCP instance with a single key-echo tool and streamable-HTTP app."""
    monkeypatch.setattr(server_config, "pro_api_key_header", "Blockscout-MCP-Pro-Api-Key", raising=False)
    monkeypatch.setattr(server_config, "pro_api_key", "server-key", raising=False)

    mcp = FastMCP(
        name="test-key-transport",
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )
    mcp.settings.stateless_http = True
    mcp.settings.json_response = True

    @mcp.tool()
    @pro_api_key_scope
    async def echo_resolved_key(ctx: Context) -> str:
        """Return the resolved PRO API key for the current request."""
        return resolve_pro_api_key()

    return mcp.streamable_http_app()


def _extract_text_result(response_body: str) -> str:
    """Parse the JSON-RPC result and return the first content text value."""
    data = json.loads(response_body)
    return data["result"]["content"][0]["text"]


def test_client_key_header_reaches_tool_body(mcp_app):
    """When the configured header is sent with a non-canonical casing, the tool resolves
    the client-supplied key rather than the server key."""
    with TestClient(mcp_app) as client:
        response = client.post(
            "/mcp",
            json=_build_tools_call_body("echo_resolved_key"),
            headers={
                **_MCP_HEADERS,
                # Non-canonical casing — exercises case-insensitive extraction
                "BLOCKSCOUT-MCP-PRO-API-KEY": "my-client-key",
            },
        )
    assert response.status_code == 200, f"Unexpected status: {response.status_code}, body: {response.text}"
    assert _extract_text_result(response.text) == "my-client-key"


def test_missing_client_header_falls_back_to_server_key(mcp_app):
    """When the client key header is absent the tool resolves the server key."""
    with TestClient(mcp_app) as client:
        response = client.post(
            "/mcp",
            json=_build_tools_call_body("echo_resolved_key"),
            headers=_MCP_HEADERS,
        )
    assert response.status_code == 200, f"Unexpected status: {response.status_code}, body: {response.text}"
    assert _extract_text_result(response.text) == "server-key"
