# SPDX-License-Identifier: LicenseRef-Blockscout
"""End-to-end proof of the shipped REST composition: wrapper -> real decorated
tool -> `handle_rest_errors`.

`tests/api/test_routes.py` (and the passthrough/status-mapping modules above)
patch the wrapped tool with an `AsyncMock`, which is correct for routing tests
but replaces the real `@session_gate`-decorated tool with a bare mock — the
gate never runs there. This module keeps the real decorated tool registered
and mocks one level deeper, at the upstream-HTTP seam, following the blessed
pattern documented in `tests/api/test_routes_pro_api_key.py` (its rationale
header explains why the tool is not mocked there either).

Uses the shared `enabled_session_gate` fixture (see `tests/conftest.py`),
which is safe here because `httpx.AsyncClient(ASGITransport)` runs the ASGI
app on the pytest thread's own event loop — the store's
`check_same_thread=True` connection is never touched from another thread.
"""

from unittest.mock import AsyncMock, patch

import httpx
import pytest
from httpx import ASGITransport, AsyncClient
from mcp.server.fastmcp import FastMCP

from blockscout_mcp_server.api.routes import register_api_routes
from blockscout_mcp_server.config import config
from blockscout_mcp_server.constants import SESSION_ID_REQUIRED_MESSAGE
from blockscout_mcp_server.session_gate import get_store, mint_token, verify_token

_CLIENT_KEY_HEADER = "Blockscout-MCP-Pro-Api-Key"
_CLIENT_KEY = "well-formed-client-key"


class CapturingClient:
    """Fake httpx.AsyncClient that returns a canned response from .get()/.post()."""

    def __init__(self, response: httpx.Response) -> None:
        self._response = response
        self.call_count = 0
        self.last_params: dict | None = None

    async def __aenter__(self) -> "CapturingClient":
        return self

    async def __aexit__(self, *args) -> None:
        return None

    async def get(self, url: str, params=None, headers=None, **kwargs) -> httpx.Response:
        self.call_count += 1
        self.last_params = dict(params or {})
        return self._response


def _block_number_response() -> httpx.Response:
    request = httpx.Request("GET", "https://api.blockscout.com/1/api/v2/main-page/blocks")
    return httpx.Response(200, json=[{"height": 123, "timestamp": "2024-01-01T00:00:00Z"}], request=request)


def _direct_api_response() -> httpx.Response:
    request = httpx.Request("GET", "https://api.blockscout.com/1/api/v2/stats")
    return httpx.Response(
        200,
        json={"items": [{"foo": "bar"}], "next_page_params": {"page": 2}},
        request=request,
    )


@pytest.fixture
def rest_client(enabled_session_gate, monkeypatch):
    """Real registered routes, real decorated tools, upstream HTTP mocked one level deeper."""
    monkeypatch.setattr(config, "pro_api_key_header", _CLIENT_KEY_HEADER, raising=False)
    monkeypatch.setattr(config, "pro_api_key", "server-configured-key")
    mcp = FastMCP(name="test-rest-session-gate-e2e")
    register_api_routes(mcp)
    asgi_app = mcp.streamable_http_app()
    return AsyncClient(transport=ASGITransport(app=asgi_app), base_url="http://test")


@pytest.mark.asyncio
async def test_missing_session_id_returns_401(rest_client):
    response = await rest_client.get("/v1/get_block_number?chain_id=1")
    assert response.status_code == 401
    assert response.json() == {"error": SESSION_ID_REQUIRED_MESSAGE}


@pytest.mark.asyncio
async def test_valid_session_id_returns_200_with_budget_note_and_increments_counter(rest_client):
    session_id = mint_token()
    random_part, _ = verify_token(session_id)

    fake_client = CapturingClient(_block_number_response())
    with (
        patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=fake_client),
        patch("blockscout_mcp_server.tools.common.ensure_chain_supported", AsyncMock()),
    ):
        response = await rest_client.get(f"/v1/get_block_number?chain_id=1&session_id={session_id}")

    assert response.status_code == 200
    payload = response.json()
    notes = payload.get("notes")
    assert notes is not None
    assert any("Free session budget" in note for note in notes)
    assert get_store().get_calls(random_part) == 1


@pytest.mark.asyncio
async def test_well_formed_client_key_exempts_without_session_id(rest_client):
    fake_client = CapturingClient(_block_number_response())
    with (
        patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=fake_client),
        patch("blockscout_mcp_server.tools.common.ensure_chain_supported", AsyncMock()),
    ):
        response = await rest_client.get(
            "/v1/get_block_number?chain_id=1",
            headers={_CLIENT_KEY_HEADER: _CLIENT_KEY},
        )

    assert response.status_code == 200
    payload = response.json()
    notes = payload.get("notes")
    assert notes is None or not any("Free session budget" in note for note in notes)
    row_count = get_store()._conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    assert row_count == 0


@pytest.mark.asyncio
async def test_unlock_endpoint_gated_returns_session_id(rest_client):
    """The real unlock endpoint is pure (no upstream to mock): gated -> `data.session_id` present."""
    response = await rest_client.get("/v1/unlock_blockchain_analysis")
    assert response.status_code == 200
    payload = response.json()
    assert "session_id" in payload["data"]
    assert payload["data"]["session_id"]


@pytest.mark.asyncio
async def test_unlock_endpoint_ungated_omits_session_id(monkeypatch):
    """Ungated (no session secret / not HTTP mode by construction of this test's app): no `session_id` key at all."""
    mcp = FastMCP(name="test-rest-session-gate-ungated")
    register_api_routes(mcp)
    asgi_app = mcp.streamable_http_app()
    async with AsyncClient(transport=ASGITransport(app=asgi_app), base_url="http://test") as client:
        response = await client.get("/v1/unlock_blockchain_analysis")

    assert response.status_code == 200
    payload = response.json()
    assert "session_id" not in payload["data"]


@pytest.mark.asyncio
async def test_direct_api_call_session_id_stripped_from_upstream_and_stamped_on_pagination(rest_client):
    session_id = mint_token()

    fake_client = CapturingClient(_direct_api_response())
    with (
        patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=fake_client),
        patch("blockscout_mcp_server.tools.common.ensure_chain_supported", AsyncMock()),
    ):
        response = await rest_client.get(
            f"/v1/direct_api_call?chain_id=1&endpoint_path=/api/v2/stats&session_id={session_id}&status=ok"
        )

    assert response.status_code == 200
    # The upstream request carried the ordinary filter but never the session_id.
    assert fake_client.last_params == {"status": "ok"}

    payload = response.json()
    next_call_params = payload["pagination"]["next_call"]["params"]
    # The top-level session_id is Phase 4's injection...
    assert next_call_params["session_id"] == session_id
    # ...while the nested query_params (the upstream filter) does not carry it.
    assert "session_id" not in next_call_params.get("query_params", {})
    assert next_call_params["query_params"] == {"status": "ok"}
