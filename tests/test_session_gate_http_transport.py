# SPDX-License-Identifier: LicenseRef-Blockscout
"""Transport-level tests that prove the session gate on the real FastMCP streamable-HTTP
transport: `SessionGateError` -> `isError=True` conversion, the request-header
exemption path, and composition with the production structured-output wrapper.

Fully local, no network — mirrors the pattern in `tests/test_pro_api_key_http_transport.py`.

Thread ownership (load-bearing): Starlette's `TestClient` executes the ASGI app in an
AnyIO portal thread, not the pytest thread, and the session store keeps
`check_same_thread=True`. A store initialized by the shared `enabled_session_gate`
fixture (on the pytest thread) would make every SQL-touching scenario here die with a
cross-thread `ProgrammingError`. So this file does NOT use that fixture: instead it
enters `TestClient(...)` as a context manager (one long-lived portal thread for the
whole `with` block) and initializes/closes the store *through that portal*
(`client.portal.call(initialize_store, path)` / `client.portal.call(close_store)`).
Minting and verifying tokens is store-I/O-free (it only reads the in-memory
`generation` attribute) and can run on any thread, including the pytest thread.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.testclient import TestClient

from blockscout_mcp_server import analytics
from blockscout_mcp_server.config import config as server_config
from blockscout_mcp_server.constants import SESSION_BUDGET_NOTE_TEMPLATE, SESSION_ID_REQUIRED_MESSAGE
from blockscout_mcp_server.models import ToolResponse
from blockscout_mcp_server.pro_api_key_context import pro_api_key_scope
from blockscout_mcp_server.server import _wrap_tool_for_structured_output
from blockscout_mcp_server.session_gate import mint_token, session_gate
from blockscout_mcp_server.session_store import close_store, initialize_store
from blockscout_mcp_server.tools.common import build_tool_response

_MCP_HEADERS = {
    "Accept": "application/json, text/event-stream",
    "Content-Type": "application/json",
}

_TOOL_NAME = "session_gated_dummy_tool"


def _build_tools_call_body(tool_name: str, arguments: dict | None = None) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments or {}},
    }


def _extract_result(response_body: str) -> dict:
    return json.loads(response_body)["result"]


@pytest.fixture(autouse=True)
def disable_telemetry(monkeypatch):
    """Disable community telemetry for every test in this module (see the identical
    fixture in tests/test_pro_api_key_http_transport.py for the rationale)."""
    monkeypatch.setattr(server_config, "disable_community_telemetry", True, raising=False)


@pytest.fixture(autouse=True)
def _reset_http_mode():
    analytics.set_http_mode(False)
    yield
    analytics.set_http_mode(False)


@pytest.fixture()
def gated_app(tmp_path, monkeypatch):
    """A throwaway FastMCP instance carrying one dummy tool, gated exactly the way
    production gates every real tool: `@pro_api_key_scope` then `@session_gate`,
    registered through the same `mcp.tool(structured_output=True)(...)` +
    `_wrap_tool_for_structured_output` wrapper production uses (see the `unlock_app`
    fixture in `tests/test_pro_api_key_http_transport.py` for why the raw decorated
    function must never be registered directly)."""
    db_path = tmp_path / "sessions.db"
    monkeypatch.setattr(server_config, "session_secret", "test-session-secret")
    monkeypatch.setattr(server_config, "session_db_path", str(db_path))
    monkeypatch.setattr(server_config, "pro_api_key_header", "Blockscout-MCP-Pro-Api-Key", raising=False)
    monkeypatch.setattr(server_config, "pro_api_key", "", raising=False)
    analytics.set_http_mode(True)

    mcp = FastMCP(
        name="test-session-gate-transport",
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )
    mcp.settings.stateless_http = True
    mcp.settings.json_response = True

    @pro_api_key_scope
    @session_gate
    async def session_gated_dummy_tool(ctx: Context, session_id: str | None = None) -> ToolResponse:
        """Dummy tool used only to exercise the session gate over the real transport.

        Goes through `build_tool_response` (not a bare `ToolResponse(...)` construction)
        so the Phase 5 budget-note branch — which reads the session-gate ContextVar —
        actually has a chance to fire, exactly as every real gated tool does.
        """
        return build_tool_response(data={"ok": True})

    mcp.tool(structured_output=True)(_wrap_tool_for_structured_output(session_gated_dummy_tool))

    return mcp.streamable_http_app(), str(db_path)


def test_missing_session_id_over_transport_is_error(gated_app):
    app, db_path = gated_app
    with TestClient(app) as client:
        client.portal.call(initialize_store, db_path)
        try:
            response = client.post(
                "/mcp",
                json=_build_tools_call_body(_TOOL_NAME),
                headers=_MCP_HEADERS,
            )
        finally:
            client.portal.call(close_store)

    assert response.status_code == 200, f"Unexpected status: {response.status_code}, body: {response.text}"
    result = _extract_result(response.text)
    assert result["isError"] is True
    expected_text = f"Error executing tool {_TOOL_NAME}: {SESSION_ID_REQUIRED_MESSAGE}"
    assert result["content"][0]["text"] == expected_text


def test_valid_token_over_transport_succeeds(gated_app):
    app, db_path = gated_app
    with TestClient(app) as client:
        client.portal.call(initialize_store, db_path)
        try:
            token = mint_token()
            response = client.post(
                "/mcp",
                json=_build_tools_call_body(_TOOL_NAME, {"session_id": token}),
                headers=_MCP_HEADERS,
            )
        finally:
            client.portal.call(close_store)

    assert response.status_code == 200, f"Unexpected status: {response.status_code}, body: {response.text}"
    result = _extract_result(response.text)
    assert result.get("isError") is not True
    assert result["structuredContent"]["data"] == {"ok": True}


def test_client_key_header_exempts_without_session_id(gated_app):
    app, db_path = gated_app
    with TestClient(app) as client:
        client.portal.call(initialize_store, db_path)
        try:
            response = client.post(
                "/mcp",
                json=_build_tools_call_body(_TOOL_NAME),
                headers={**_MCP_HEADERS, "Blockscout-MCP-Pro-Api-Key": "a-well-formed-client-key"},
            )
        finally:
            client.portal.call(close_store)

    assert response.status_code == 200, f"Unexpected status: {response.status_code}, body: {response.text}"
    result = _extract_result(response.text)
    assert result.get("isError") is not True
    assert result["structuredContent"]["data"] == {"ok": True}


def test_malformed_client_key_without_session_id_is_error(gated_app):
    app, db_path = gated_app
    malformed_key = "x" * 300  # exceeds the max accepted client-key length
    with TestClient(app) as client:
        client.portal.call(initialize_store, db_path)
        try:
            response = client.post(
                "/mcp",
                json=_build_tools_call_body(_TOOL_NAME),
                headers={**_MCP_HEADERS, "Blockscout-MCP-Pro-Api-Key": malformed_key},
            )
        finally:
            client.portal.call(close_store)

    assert response.status_code == 200, f"Unexpected status: {response.status_code}, body: {response.text}"
    result = _extract_result(response.text)
    assert result["isError"] is True
    expected_text = f"Error executing tool {_TOOL_NAME}: {SESSION_ID_REQUIRED_MESSAGE}"
    assert result["content"][0]["text"] == expected_text


def test_valid_token_over_transport_carries_budget_note(gated_app):
    """Gated `tools/call` with a valid token -> `structuredContent.notes` contains
    the exact formatted budget note (Phase 5), proving the note survives the
    production MCP serialization path through `_wrap_tool_for_structured_output`."""
    app, db_path = gated_app
    with TestClient(app) as client:
        client.portal.call(initialize_store, db_path)
        try:
            token = mint_token()
            response = client.post(
                "/mcp",
                json=_build_tools_call_body(_TOOL_NAME, {"session_id": token}),
                headers=_MCP_HEADERS,
            )
        finally:
            client.portal.call(close_store)

    assert response.status_code == 200, f"Unexpected status: {response.status_code}, body: {response.text}"
    result = _extract_result(response.text)
    assert result.get("isError") is not True
    expected_note = SESSION_BUDGET_NOTE_TEMPLATE.format(
        remaining=server_config.session_max_calls - 1, max_calls=server_config.session_max_calls
    )
    assert result["structuredContent"]["notes"] == [expected_note]


def _build_unlock_app(*, gated: bool) -> Any:
    """Construct a throwaway FastMCP instance carrying the real, fully local
    `__unlock_blockchain_analysis__` tool, registered exactly the way production
    registers it (mirrors the `unlock_app` fixture in
    `tests/test_pro_api_key_http_transport.py`): `mcp.tool(structured_output=True)`
    wrapping `_wrap_tool_for_structured_output`. Registering the raw function would
    fall back to the SDK's auto-serialization instead of the wrapper that actually
    builds `structuredContent` in production, bypassing the very serialization
    boundary these tests exist to cover."""
    from blockscout_mcp_server.tools.initialization.unlock_blockchain_analysis import (
        __unlock_blockchain_analysis__,
    )

    mcp = FastMCP(
        name="test-unlock-serialization-transport",
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )
    mcp.settings.stateless_http = True
    mcp.settings.json_response = True
    mcp.tool(structured_output=True)(_wrap_tool_for_structured_output(__unlock_blockchain_analysis__))
    analytics.set_http_mode(gated)

    return mcp.streamable_http_app()


def test_unlock_serialization_gated_includes_verifiable_session_id(tmp_path, monkeypatch):
    """Gated deployment: structuredContent.data carries a session_id that verify_token accepts."""
    db_path = tmp_path / "unlock-sessions.db"
    monkeypatch.setattr(server_config, "session_secret", "test-session-secret")
    monkeypatch.setattr(server_config, "session_db_path", str(db_path))

    app = _build_unlock_app(gated=True)
    with TestClient(app) as client:
        client.portal.call(initialize_store, str(db_path))
        try:
            response = client.post(
                "/mcp",
                json=_build_tools_call_body("__unlock_blockchain_analysis__"),
                headers=_MCP_HEADERS,
            )

            assert response.status_code == 200, f"Unexpected status: {response.status_code}, body: {response.text}"
            result = _extract_result(response.text)
            assert result.get("isError") is not True
            session_id = result["structuredContent"]["data"]["session_id"]
            assert session_id
            # verify_token is store-I/O-free (only reads the in-memory `generation` attribute set
            # by `initialize_store` above), so it is safe to call on the pytest thread — but it
            # must run before `close_store` tears down the module-level singleton it reads from.
            from blockscout_mcp_server.session_gate import verify_token

            verify_token(session_id)
        finally:
            client.portal.call(close_store)


def test_unlock_serialization_ungated_has_no_session_id_key():
    """Ungated deployment: structuredContent.data has no session_id key at all."""
    app = _build_unlock_app(gated=False)
    with TestClient(app) as client:
        response = client.post(
            "/mcp",
            json=_build_tools_call_body("__unlock_blockchain_analysis__"),
            headers=_MCP_HEADERS,
        )

    assert response.status_code == 200, f"Unexpected status: {response.status_code}, body: {response.text}"
    result = _extract_result(response.text)
    assert result.get("isError") is not True
    assert "session_id" not in result["structuredContent"]["data"]


def test_exempt_call_carries_no_budget_note(gated_app):
    """A client-supplied PRO API key exempts the call from the gate entirely, so no
    budget ContextVar is ever set and `structuredContent.notes` carries no budget note."""
    app, db_path = gated_app
    with TestClient(app) as client:
        client.portal.call(initialize_store, db_path)
        try:
            response = client.post(
                "/mcp",
                json=_build_tools_call_body(_TOOL_NAME),
                headers={**_MCP_HEADERS, "Blockscout-MCP-Pro-Api-Key": "a-well-formed-client-key"},
            )
        finally:
            client.portal.call(close_store)

    assert response.status_code == 200, f"Unexpected status: {response.status_code}, body: {response.text}"
    result = _extract_result(response.text)
    assert result.get("isError") is not True
    assert result["structuredContent"].get("notes") is None
