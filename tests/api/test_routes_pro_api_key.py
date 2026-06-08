# SPDX-License-Identifier: LicenseRef-Blockscout
"""End-to-end REST precedence tests for the PRO API key path.

Why a separate file (not tests/api/test_routes.py)
---------------------------------------------------
Rule 230 mandates that route tests in tests/api/test_routes.py patch the
wrapped tool functions with AsyncMock. That pattern is correct for
routing/parameter tests, but it replaces the real @pro_api_key_scope-decorated
tool with a bare mock, so the decorator never runs and the key is never
resolved — it would make a precedence test pass vacuously.

To exercise the real resolution path while still avoiding network calls, we
keep the real decorated tool in place and mock one level deeper, at the HTTP
transport seam. This mirrors two existing, blessed patterns:

- tests/tools/test_common_blockscout_request_auth.py — patches
  _create_httpx_client and asserts the outgoing Authorization header.
- tests/test_pro_api_key_http_transport.py — drives a real app and reads
  the resolved key.

This file is named distinctly so rule 230's exact-file convention does not
apply to it.
"""

from unittest.mock import AsyncMock, patch

import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from blockscout_mcp_server.config import config

_TEST_URL = "/v1/get_tokens_by_address?chain_id=1&address=0x0000000000000000000000000000000000000000"
_SERVER_KEY = "server-configured-key"
_CLIENT_KEY = "client-supplied-key"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class CapturingClient:
    """Fake httpx.AsyncClient that records the URL and headers from .get()."""

    def __init__(self, response: httpx.Response) -> None:
        self._response = response
        self.get_url: str | None = None
        self.get_headers: dict = {}
        self.call_count = 0

    async def __aenter__(self) -> "CapturingClient":
        return self

    async def __aexit__(self, *args) -> None:
        return None

    async def get(self, url: str, params=None, headers=None, **kwargs) -> httpx.Response:
        self.call_count += 1
        self.get_url = url
        self.get_headers = dict(headers or {})
        return self._response


class NeverCalledClient:
    """Fake client that fails the test if any HTTP method is invoked."""

    async def __aenter__(self) -> "NeverCalledClient":
        return self

    async def __aexit__(self, *args) -> None:
        return None

    async def get(self, *args, **kwargs):
        raise AssertionError("HTTP client should not have been called")


def _ok_response() -> httpx.Response:
    request = httpx.Request("GET", "https://api.blockscout.com/1/api/v2/addresses/0x0/tokens")
    return httpx.Response(200, json={"items": []}, request=request)


# ---------------------------------------------------------------------------
# Module-level autouse fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def disable_telemetry(monkeypatch):
    """Disable community telemetry for all tests in this module.

    The real @log_tool_invocation decorator schedules
    telemetry.send_community_usage_report(...) via asyncio.create_task in its
    finally block — even when the tool body raises. That coroutine builds its
    own httpx.AsyncClient inside telemetry.py, which the tools.common
    _create_httpx_client patch does not intercept. Setting
    config.disable_community_telemetry = True triggers the real gate in the
    production code and avoids flaky real network calls.
    """
    monkeypatch.setattr(config, "disable_community_telemetry", True, raising=False)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def rest_client(monkeypatch):
    """Provide a configured httpx AsyncClient using the real registered routes."""
    from mcp.server.fastmcp import FastMCP

    from blockscout_mcp_server.api.routes import register_api_routes

    monkeypatch.setattr(config, "pro_api_key", _SERVER_KEY)
    monkeypatch.setattr(config, "pro_api_key_header", "Blockscout-MCP-Pro-Api-Key", raising=False)

    mcp = FastMCP(name="test-rest-pro-key")
    register_api_routes(mcp)
    asgi_app = mcp.streamable_http_app()
    return AsyncClient(transport=ASGITransport(app=asgi_app), base_url="http://test")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rest_client_key_wins_over_server_key(rest_client):
    """Valid client header → HTTP 200 and outgoing request uses the client key."""
    fake_client = CapturingClient(_ok_response())
    with (
        patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=fake_client),
        patch("blockscout_mcp_server.tools.common.ensure_chain_supported", AsyncMock()),
    ):
        response = await rest_client.get(
            _TEST_URL,
            headers={"Blockscout-MCP-Pro-Api-Key": _CLIENT_KEY},
        )

    assert response.status_code == 200
    assert fake_client.get_headers.get("Authorization") == f"Bearer {_CLIENT_KEY}"


@pytest.mark.asyncio
async def test_rest_non_canonical_header_casing_is_honored(rest_client):
    """Non-canonical header casing exercises case-insensitive lookup."""
    fake_client = CapturingClient(_ok_response())
    with (
        patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=fake_client),
        patch("blockscout_mcp_server.tools.common.ensure_chain_supported", AsyncMock()),
    ):
        response = await rest_client.get(
            _TEST_URL,
            # Deliberate non-canonical casing
            headers={"BLOCKSCOUT-MCP-PRO-API-KEY": _CLIENT_KEY},
        )

    assert response.status_code == 200
    assert fake_client.get_headers.get("Authorization") == f"Bearer {_CLIENT_KEY}"


@pytest.mark.asyncio
async def test_rest_absent_header_falls_back_to_server_key(rest_client):
    """No client header → outgoing request uses the configured server key."""
    fake_client = CapturingClient(_ok_response())
    with (
        patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=fake_client),
        patch("blockscout_mcp_server.tools.common.ensure_chain_supported", AsyncMock()),
    ):
        response = await rest_client.get(_TEST_URL)

    assert response.status_code == 200
    assert fake_client.get_headers.get("Authorization") == f"Bearer {_SERVER_KEY}"


@pytest.mark.asyncio
async def test_rest_malformed_header_returns_400(rest_client):
    """Malformed client header (control character) → HTTP 400, HTTP client never invoked."""
    never_called = NeverCalledClient()
    with (
        patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=never_called),
        patch("blockscout_mcp_server.tools.common.ensure_chain_supported", AsyncMock()),
    ):
        response = await rest_client.get(
            _TEST_URL,
            headers={"Blockscout-MCP-Pro-Api-Key": "bad\x01key"},
        )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_rest_overlength_header_returns_400(rest_client):
    """Over-length client header → HTTP 400, HTTP client never invoked."""
    never_called = NeverCalledClient()
    with (
        patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=never_called),
        patch("blockscout_mcp_server.tools.common.ensure_chain_supported", AsyncMock()),
    ):
        response = await rest_client.get(
            _TEST_URL,
            headers={"Blockscout-MCP-Pro-Api-Key": "x" * 300},
        )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_rest_empty_header_name_config_ignores_client_header(monkeypatch, rest_client):
    """Empty pro_api_key_header config → client header is ignored, server key is used."""
    # Override the header config set by rest_client fixture: disable the feature
    monkeypatch.setattr(config, "pro_api_key_header", "")

    fake_client = CapturingClient(_ok_response())
    with (
        patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=fake_client),
        patch("blockscout_mcp_server.tools.common.ensure_chain_supported", AsyncMock()),
    ):
        response = await rest_client.get(
            _TEST_URL,
            headers={"Blockscout-MCP-Pro-Api-Key": _CLIENT_KEY},
        )

    assert response.status_code == 200
    # Feature disabled: should fall back to server key
    assert fake_client.get_headers.get("Authorization") == f"Bearer {_SERVER_KEY}"
