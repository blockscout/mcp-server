# SPDX-License-Identifier: LicenseRef-Blockscout
"""End-to-end tests for the low-credits advisory note in MCP mode.

Exercises the full chain — @pro_api_credit_scope establishes the sink,
make_blockscout_request captures the x-credits-remaining header, and
build_tool_response emits (or withholds) the advisory note — by calling the
real get_block_number tool with only the HTTP transport patched.

The REST-mode counterpart lives in tests/api/test_routes.py.
"""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from blockscout_mcp_server.config import config


class _MockResponse:
    """Minimal fake httpx response for GET/POST helpers."""

    def __init__(self, json_data=None, status_code=200, headers=None):
        self._json_data = json_data
        self.status_code = status_code
        self.reason_phrase = "OK"
        self.request = httpx.Request("GET", "https://api.blockscout.com/1/x")
        self.text = ""
        self.headers = headers if headers is not None else {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("boom", request=self.request, response=self)

    def json(self):
        return self._json_data


class _SimpleClient:
    """Async context-manager client that returns a fixed response."""

    def __init__(self, response):
        self._response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def get(self, url, **kwargs):
        return self._response

    async def post(self, url, json, params, headers=None, **kwargs):
        return self._response


@pytest.mark.asyncio
async def test_mcp_mode_low_credits_note_in_tool_response(mock_ctx):
    """MCP mode: decorated get_block_number call with a low x-credits-remaining
    produces a ToolResponse whose notes contain the low-credits advisory.

    This exercises the full chain:
      @pro_api_credit_scope decorator (establishes sink)
      → make_blockscout_request (captures header into sink)
      → build_tool_response (reads sink and emits advisory note)
    """
    from blockscout_mcp_server.tools.block.get_block_number import get_block_number

    # Response that looks like the /api/v2/main-page/blocks payload.
    block_payload = [{"height": 21000000, "timestamp": "2025-01-01T00:00:00.000000Z"}]
    # x-credits-remaining is below the default threshold of 5000.
    response = _MockResponse(block_payload, headers={"x-credits-remaining": "4200"})

    with (
        patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=_SimpleClient(response)),
        patch("blockscout_mcp_server.tools.common.ensure_chain_supported", AsyncMock()),
        patch.object(config, "pro_api_key", "test_key"),
        patch.object(config, "pro_api_low_credits_threshold", 5000),
    ):
        result = await get_block_number(chain_id="1", ctx=mock_ctx)

    assert result.notes is not None
    assert any("4200" in note for note in result.notes)
    assert any("https://dev.blockscout.com" in note for note in result.notes)
    assert mock_ctx.report_progress.call_count > 0


@pytest.mark.asyncio
async def test_mcp_mode_healthy_credits_no_note_in_tool_response(mock_ctx):
    """MCP mode: same call with a healthy balance (at or above threshold) yields no advisory note."""
    from blockscout_mcp_server.tools.block.get_block_number import get_block_number

    block_payload = [{"height": 21000000, "timestamp": "2025-01-01T00:00:00.000000Z"}]
    # x-credits-remaining is at the threshold — not strictly below, so no note.
    response = _MockResponse(block_payload, headers={"x-credits-remaining": "5000"})

    with (
        patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=_SimpleClient(response)),
        patch("blockscout_mcp_server.tools.common.ensure_chain_supported", AsyncMock()),
        patch.object(config, "pro_api_key", "test_key"),
        patch.object(config, "pro_api_low_credits_threshold", 5000),
    ):
        result = await get_block_number(chain_id="1", ctx=mock_ctx)

    # notes should be None (no advisory, no caller-supplied notes)
    assert result.notes is None
    assert mock_ctx.report_progress.call_count > 0
