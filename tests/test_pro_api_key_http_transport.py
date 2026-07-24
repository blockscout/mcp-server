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
from blockscout_mcp_server.pro_api_key_context import pro_api_key_scope, require_pro_api_key, resolve_pro_api_key

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


@pytest.fixture(autouse=True)
def disable_telemetry(monkeypatch):
    """Disable community telemetry for all tests in this module.

    The real @log_tool_invocation decorator schedules
    telemetry.send_community_usage_report(...) via asyncio.create_task in its
    finally block — even when the tool body raises. Setting
    config.disable_community_telemetry = True triggers the real gate in the
    production code and avoids flaky real network calls, following the
    established fixture in tests/api/test_routes_pro_api_key.py:88-100.
    """
    monkeypatch.setattr(server_config, "disable_community_telemetry", True, raising=False)


@pytest.fixture()
def unlock_app(monkeypatch):
    """A throwaway FastMCP instance carrying the real, fully local, keyless
    ``__unlock_blockchain_analysis__`` tool, registered exactly the way
    production registers it (blockscout_mcp_server/server.py:235-240):
    ``mcp.tool(structured_output=True, ...)`` wrapping
    ``_wrap_tool_for_structured_output``. Registering the raw function would
    fall back to the SDK's auto-serialization instead of the wrapper that
    actually builds ``structuredContent`` in production, silently bypassing
    the very serialization boundary these notice tests exist to cover.
    """
    from blockscout_mcp_server.server import _wrap_tool_for_structured_output
    from blockscout_mcp_server.tools.initialization.unlock_blockchain_analysis import (
        __unlock_blockchain_analysis__,
    )

    monkeypatch.setattr(server_config, "pro_api_key_header", "Blockscout-MCP-Pro-Api-Key", raising=False)

    mcp = FastMCP(
        name="test-notice-transport",
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )
    mcp.settings.stateless_http = True
    mcp.settings.json_response = True

    mcp.tool(structured_output=True)(_wrap_tool_for_structured_output(__unlock_blockchain_analysis__))

    return mcp.streamable_http_app()


_NOTICE_TEXT = "PRO API keys will soon be required for every request; see https://dev.blockscout.com."


def test_notice_present_in_structured_content_without_key_header(unlock_app, monkeypatch):
    """Notice configured, no key header → structuredContent.notes ends with the notice."""
    monkeypatch.setattr(server_config, "pro_api_key_required_notice", _NOTICE_TEXT)

    with TestClient(unlock_app) as client:
        response = client.post(
            "/mcp",
            json=_build_tools_call_body("__unlock_blockchain_analysis__"),
            headers=_MCP_HEADERS,
        )

    assert response.status_code == 200, f"Unexpected status: {response.status_code}, body: {response.text}"
    data = json.loads(response.text)
    structured = data["result"]["structuredContent"]
    assert structured["notes"][-1] == _NOTICE_TEXT


def test_notice_absent_in_structured_content_with_well_formed_key_header(unlock_app, monkeypatch):
    """Notice configured, well-formed key header → no notice in structuredContent.notes."""
    monkeypatch.setattr(server_config, "pro_api_key_required_notice", _NOTICE_TEXT)

    with TestClient(unlock_app) as client:
        response = client.post(
            "/mcp",
            json=_build_tools_call_body("__unlock_blockchain_analysis__"),
            headers={**_MCP_HEADERS, "Blockscout-MCP-Pro-Api-Key": "client-key-456"},
        )

    assert response.status_code == 200, f"Unexpected status: {response.status_code}, body: {response.text}"
    data = json.loads(response.text)
    structured = data["result"]["structuredContent"]
    notes = structured.get("notes")
    assert notes is None or _NOTICE_TEXT not in notes


def test_not_configured_error_terse_contract_over_http(monkeypatch):
    """The model-facing JSON-RPC error text carries the new terse not-configured contract.

    Proves the transport layer preserves the minimal message: the chokepoint tests in
    test_require_pro_api_key.py pin the source string, but they do not exercise the
    FastMCP wrapping path. This test is the literal #404 failure boundary.
    """
    monkeypatch.setattr(server_config, "pro_api_key_header", "Blockscout-MCP-Pro-Api-Key", raising=False)
    monkeypatch.setattr(server_config, "pro_api_key", "", raising=False)

    mcp = FastMCP(
        name="test-not-configured-transport",
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )
    mcp.settings.stateless_http = True
    mcp.settings.json_response = True

    @mcp.tool()
    @pro_api_key_scope
    async def needs_pro_key(ctx: Context) -> str:
        """Tool that requires a PRO API key for data access."""
        return require_pro_api_key("data access")

    app = mcp.streamable_http_app()

    with TestClient(app) as client:
        response = client.post(
            "/mcp",
            json=_build_tools_call_body("needs_pro_key"),
            headers=_MCP_HEADERS,
        )

    assert response.status_code == 200, f"Unexpected status: {response.status_code}, body: {response.text}"
    data = json.loads(response.text)
    assert data["result"]["isError"] is True
    error_text = data["result"]["content"][0]["text"]
    assert "PRO API key required" in error_text
    assert "data access" in error_text
    assert "BLOCKSCOUT_PRO_API_KEY" not in error_text
    assert "on the server" not in error_text
    assert "Blockscout-MCP-Pro-Api-Key" not in error_text
