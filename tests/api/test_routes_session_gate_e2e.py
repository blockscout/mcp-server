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
from blockscout_mcp_server.constants import (
    SESSION_ID_REQUIRED_MESSAGE,
    SESSION_OVER_MESSAGE,
    SKILL_RESOLUTION_RULE_TEXT,
)
from blockscout_mcp_server.resources import skill_resources
from blockscout_mcp_server.session_gate import get_store, mint_token, verify_token
from blockscout_mcp_server.tools.block.get_block_number import get_block_number
from blockscout_mcp_server.tools.common import chains_list_cache

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
    assert list(payload["data"].keys()) == ["session_id", "server_version"]


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
    assert list(payload["data"].keys()) == ["server_version"]
    assert payload["instructions"] == [
        skill_resources.skill_pointer_text(),
        SKILL_RESOLUTION_RULE_TEXT,
    ]


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


# ---------------------------------------------------------------------------
# Phase 7: per-surface ceilings over the real REST composition, and the
# cross-surface shared-counter guarantees.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lowered_rest_ceiling_limits_second_rest_call(rest_client, monkeypatch):
    """A REST ceiling of 1 (MCP still 5) lets one call through and refuses the second."""
    monkeypatch.setattr(config, "session_mcp_max_calls", 5)
    monkeypatch.setattr(config, "session_rest_max_calls", 1)
    session_id = mint_token()

    fake_client = CapturingClient(_block_number_response())
    with (
        patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=fake_client),
        patch("blockscout_mcp_server.tools.common.ensure_chain_supported", AsyncMock()),
    ):
        first = await rest_client.get(f"/v1/get_block_number?chain_id=1&session_id={session_id}")
        second = await rest_client.get(f"/v1/get_block_number?chain_id=1&session_id={session_id}")

    assert first.status_code == 200
    assert second.status_code == 403
    assert second.json() == {"error": SESSION_OVER_MESSAGE}


@pytest.mark.asyncio
async def test_budget_note_over_rest_reports_rest_ceiling(rest_client, monkeypatch):
    """A successful REST call's budget note reports the REST ceiling, not the MCP one."""
    monkeypatch.setattr(config, "session_mcp_max_calls", 5)
    monkeypatch.setattr(config, "session_rest_max_calls", 9)
    session_id = mint_token()

    fake_client = CapturingClient(_block_number_response())
    with (
        patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=fake_client),
        patch("blockscout_mcp_server.tools.common.ensure_chain_supported", AsyncMock()),
    ):
        response = await rest_client.get(f"/v1/get_block_number?chain_id=1&session_id={session_id}")

    assert response.status_code == 200
    notes = response.json()["notes"]
    assert any("of 9" in note for note in notes)


@pytest.mark.asyncio
async def test_zero_rest_ceiling_valid_session_id_refused_without_row(rest_client, monkeypatch):
    """A 0 REST ceiling refuses a metered call terminally, writing no row for it."""
    monkeypatch.setattr(config, "session_mcp_max_calls", 5)
    monkeypatch.setattr(config, "session_rest_max_calls", 0)
    session_id = mint_token()
    random_part, _issued_at = verify_token(session_id)

    response = await rest_client.get(f"/v1/get_block_number?chain_id=1&session_id={session_id}")

    assert response.status_code == 403
    assert response.json() == {"error": SESSION_OVER_MESSAGE}
    assert get_store().get_calls(random_part) == 0


@pytest.mark.asyncio
async def test_zero_rest_ceiling_no_session_id_still_refused_terminally(rest_client, monkeypatch):
    """The terminal 0-ceiling refusal precedes the missing-identifier 401 (decision 1)."""
    monkeypatch.setattr(config, "session_mcp_max_calls", 5)
    monkeypatch.setattr(config, "session_rest_max_calls", 0)

    response = await rest_client.get("/v1/get_block_number?chain_id=1")

    assert response.status_code == 403
    assert response.json() == {"error": SESSION_OVER_MESSAGE}


@pytest.mark.asyncio
async def test_zero_rest_ceiling_leaves_unlock_and_navigation_open(rest_client, monkeypatch):
    """A 0 REST ceiling closes data access but not issuance or unmetered navigation."""
    monkeypatch.setattr(config, "session_mcp_max_calls", 5)
    monkeypatch.setattr(config, "session_rest_max_calls", 0)
    chains_list_cache.invalidate()

    unlock_response = await rest_client.get("/v1/unlock_blockchain_analysis")
    assert unlock_response.status_code == 200
    session_id = unlock_response.json()["data"]["session_id"]
    assert session_id

    with (
        patch(
            "blockscout_mcp_server.tools.chains.get_chains_list.ensure_pro_api_config",
            new_callable=AsyncMock,
            return_value={"1": "https://eth"},
        ),
        patch(
            "blockscout_mcp_server.tools.chains.get_chains_list.make_chainscout_request",
            new_callable=AsyncMock,
            return_value={"1": {"name": "Ethereum"}},
        ),
    ):
        chains_response = await rest_client.get(f"/v1/get_chains_list?session_id={session_id}")

    assert chains_response.status_code == 200


@pytest.mark.asyncio
async def test_cross_surface_shared_counter_refuses_rest_once_total_reaches_rest_ceiling(
    rest_client, monkeypatch, mock_ctx
):
    """Spending part of the budget via the real MCP-decorated path counts against the
    same shared identifier: a REST call is refused once the shared total reaches the
    (lower) REST ceiling."""
    monkeypatch.setattr(config, "session_mcp_max_calls", 5)
    monkeypatch.setattr(config, "session_rest_max_calls", 2)
    session_id = mint_token()
    random_part, _issued_at = verify_token(session_id)

    fake_client = CapturingClient(_block_number_response())
    with (
        patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=fake_client),
        patch("blockscout_mcp_server.tools.common.ensure_chain_supported", AsyncMock()),
    ):
        # An unmarked ctx resolves to the MCP surface — the real gate path, not a store shortcut.
        await get_block_number(chain_id="1", ctx=mock_ctx, session_id=session_id)
        await get_block_number(chain_id="1", ctx=mock_ctx, session_id=session_id)

        response = await rest_client.get(f"/v1/get_block_number?chain_id=1&session_id={session_id}")

    assert response.status_code == 403
    assert get_store().get_calls(random_part) == 2


@pytest.mark.asyncio
async def test_surface_relative_exhaustion_rest_refusal_does_not_exhaust_mcp(rest_client, monkeypatch, mock_ctx):
    """A REST ceiling of 1 (MCP ceiling 2): the first REST call succeeds, the second is
    refused, and the same identifier still succeeds through the real MCP-decorated path —
    one surface's refusal never marks the identifier exhausted for the other."""
    monkeypatch.setattr(config, "session_mcp_max_calls", 2)
    monkeypatch.setattr(config, "session_rest_max_calls", 1)
    session_id = mint_token()
    random_part, _issued_at = verify_token(session_id)

    fake_client = CapturingClient(_block_number_response())
    with (
        patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=fake_client),
        patch("blockscout_mcp_server.tools.common.ensure_chain_supported", AsyncMock()),
    ):
        first = await rest_client.get(f"/v1/get_block_number?chain_id=1&session_id={session_id}")
        second = await rest_client.get(f"/v1/get_block_number?chain_id=1&session_id={session_id}")

        assert first.status_code == 200
        assert second.status_code == 403

        result = await get_block_number(chain_id="1", ctx=mock_ctx, session_id=session_id)

    assert result.data.block_number == 123
    assert get_store().get_calls(random_part) == 2


@pytest.mark.asyncio
async def test_live_raise_of_rest_ceiling_reopens_surface_without_reregistration(rest_client, monkeypatch):
    """Retroactively raising `session_rest_max_calls` reopens an identifier exhausted on
    that surface, with no re-registration needed (the field is read at call time)."""
    monkeypatch.setattr(config, "session_mcp_max_calls", 5)
    monkeypatch.setattr(config, "session_rest_max_calls", 1)
    session_id = mint_token()
    random_part, _issued_at = verify_token(session_id)

    fake_client = CapturingClient(_block_number_response())
    with (
        patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=fake_client),
        patch("blockscout_mcp_server.tools.common.ensure_chain_supported", AsyncMock()),
    ):
        first = await rest_client.get(f"/v1/get_block_number?chain_id=1&session_id={session_id}")
        second = await rest_client.get(f"/v1/get_block_number?chain_id=1&session_id={session_id}")

        monkeypatch.setattr(config, "session_rest_max_calls", 2)

        third = await rest_client.get(f"/v1/get_block_number?chain_id=1&session_id={session_id}")

    assert first.status_code == 200
    assert second.status_code == 403
    assert third.status_code == 200
    assert get_store().get_calls(random_part) == 2
