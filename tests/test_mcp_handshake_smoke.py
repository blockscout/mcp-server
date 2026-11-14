# SPDX-License-Identifier: LicenseRef-Blockscout
"""CI handshake smoke test for issue #458.

A raw MCP ``initialize`` request posted to the streamable-HTTP endpoint must
come back with a JSON-RPC result. A regression that returns an empty body or
error (observed as ``NO_RESPONSE`` by anonymous registry checks) fails here
before release.
"""

import json

import pytest
from mcp.server.transport_security import TransportSecuritySettings
from starlette.testclient import TestClient

from blockscout_mcp_server.config import config as server_config
from blockscout_mcp_server.server import mcp

_MCP_HEADERS = {
    "Accept": "application/json, text/event-stream",
    "Content-Type": "application/json",
}

_INITIALIZE_BODY = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "blockscout-mcp-ci-handshake", "version": "0.0.0"},
    },
}


@pytest.fixture(autouse=True)
def disable_telemetry(monkeypatch):
    """Disable community telemetry, mirroring test_pro_api_key_http_transport.py."""
    monkeypatch.setattr(server_config, "disable_community_telemetry", True, raising=False)


@pytest.fixture
def http_app(monkeypatch):
    """Build the streamable-HTTP app in CI mode without leaking settings to other tests."""
    monkeypatch.setattr(mcp.settings, "stateless_http", True, raising=False)
    monkeypatch.setattr(mcp.settings, "json_response", True, raising=False)
    monkeypatch.setattr(
        mcp.settings,
        "transport_security",
        TransportSecuritySettings(enable_dns_rebinding_protection=False),
        raising=False,
    )
    # The session manager is created lazily and cached on the module: if an earlier
    # test already built (or entered) one, the patched transport settings above never
    # reach it, and its lifespan cannot run a second time.
    monkeypatch.setattr(mcp, "_session_manager", None)
    return mcp.streamable_http_app()


def test_mcp_handshake_returns_result(http_app):
    """A raw initialize over the streamable-HTTP endpoint must yield a JSON-RPC result."""
    with TestClient(http_app) as client:
        response = client.post("/mcp", headers=_MCP_HEADERS, json=_INITIALIZE_BODY)

    assert response.status_code == 200, response.text
    assert response.text.strip(), (
        "MCP endpoint returned an empty body for a raw initialize request (observed externally as NO_RESPONSE)"
    )
    body = json.loads(response.text)
    assert "result" in body, f"initialize did not return a JSON-RPC result: {body}"
    assert body["result"].get("serverInfo"), body
