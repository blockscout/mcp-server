# SPDX-License-Identifier: LicenseRef-Blockscout
from unittest.mock import ANY, AsyncMock, patch

import pytest

from blockscout_mcp_server import analytics, telemetry
from blockscout_mcp_server.config import config
from blockscout_mcp_server.constants import (
    COMMUNITY_TELEMETRY_ENDPOINT,
    COMMUNITY_TELEMETRY_URL,
    RESOURCE_READ_EVENT,
)


@pytest.mark.asyncio
async def test_send_community_usage_report_sent(monkeypatch):
    monkeypatch.setattr(config, "disable_community_telemetry", False, raising=False)
    monkeypatch.setattr(config, "mixpanel_token", "", raising=False)
    mock_client = AsyncMock()
    mock_ctx_mgr = AsyncMock()
    mock_ctx_mgr.__aenter__.return_value = mock_client
    with patch("httpx.AsyncClient", return_value=mock_ctx_mgr):
        await telemetry.send_community_usage_report("tool", {"a": 1}, "client", "1.0", "1.1")
        url = f"{COMMUNITY_TELEMETRY_URL}{COMMUNITY_TELEMETRY_ENDPOINT}"
        mock_client.post.assert_awaited_once_with(
            url,
            json={
                "tool_name": "tool",
                "tool_args": {"a": 1},
                "client_name": "client",
                "client_version": "1.0",
                "protocol_version": "1.1",
            },
            headers=ANY,
            timeout=2.0,
        )


@pytest.mark.asyncio
async def test_send_community_usage_report_disabled(monkeypatch):
    monkeypatch.setattr(config, "disable_community_telemetry", True, raising=False)
    with patch("httpx.AsyncClient", AsyncMock()) as mock_ac:
        await telemetry.send_community_usage_report("tool", {}, "client", "1.0", "1.1")
        mock_ac.assert_not_called()


@pytest.mark.asyncio
async def test_send_community_usage_report_direct_mode(monkeypatch):
    monkeypatch.setattr(config, "disable_community_telemetry", False, raising=False)
    monkeypatch.setattr(config, "mixpanel_token", "token", raising=False)
    analytics.set_http_mode(True)
    try:
        with patch("httpx.AsyncClient", AsyncMock()) as mock_ac:
            await telemetry.send_community_usage_report("tool", {}, "client", "1.0", "1.1")
            mock_ac.assert_not_called()
    finally:
        analytics.set_http_mode(False)


@pytest.mark.asyncio
async def test_send_community_usage_report_network_error(monkeypatch):
    monkeypatch.setattr(config, "disable_community_telemetry", False, raising=False)
    monkeypatch.setattr(config, "mixpanel_token", "", raising=False)
    mock_client = AsyncMock()
    mock_client.post.side_effect = Exception("boom")
    mock_ctx_mgr = AsyncMock()
    mock_ctx_mgr.__aenter__.return_value = mock_client
    with patch("httpx.AsyncClient", return_value=mock_ctx_mgr):
        await telemetry.send_community_usage_report("tool", {}, "client", "1.0", "1.1")
        mock_client.post.assert_awaited_once()


# ---------------------------------------------------------------------------
# send_community_resource_report tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_community_resource_report_sent(monkeypatch):
    """Payload is sent with tool_name == RESOURCE_READ and uri in tool_args."""
    monkeypatch.setattr(config, "disable_community_telemetry", False, raising=False)
    monkeypatch.setattr(config, "mixpanel_token", "", raising=False)
    uri = "blockscout-mcp://skill/SKILL.md"
    mock_client = AsyncMock()
    mock_ctx_mgr = AsyncMock()
    mock_ctx_mgr.__aenter__.return_value = mock_client
    with patch("httpx.AsyncClient", return_value=mock_ctx_mgr):
        await telemetry.send_community_resource_report(uri, "client", "1.0", "1.1")
        url = f"{COMMUNITY_TELEMETRY_URL}{COMMUNITY_TELEMETRY_ENDPOINT}"
        mock_client.post.assert_awaited_once_with(
            url,
            json={
                "tool_name": RESOURCE_READ_EVENT,
                "tool_args": {"uri": uri},
                "client_name": "client",
                "client_version": "1.0",
                "protocol_version": "1.1",
            },
            headers=ANY,
            timeout=2.0,
        )


@pytest.mark.asyncio
async def test_send_community_resource_report_suppressed_when_disabled(monkeypatch):
    """No HTTP call when community telemetry is disabled."""
    monkeypatch.setattr(config, "disable_community_telemetry", True, raising=False)
    with patch("httpx.AsyncClient", AsyncMock()) as mock_ac:
        await telemetry.send_community_resource_report("blockscout-mcp://skill/SKILL.md", "c", "1.0", "1.1")
        mock_ac.assert_not_called()


@pytest.mark.asyncio
async def test_send_community_resource_report_suppressed_in_direct_mode(monkeypatch):
    """No HTTP call when HTTP mode is on and Mixpanel token is set (direct mode)."""
    monkeypatch.setattr(config, "disable_community_telemetry", False, raising=False)
    monkeypatch.setattr(config, "mixpanel_token", "token", raising=False)
    analytics.set_http_mode(True)
    try:
        with patch("httpx.AsyncClient", AsyncMock()) as mock_ac:
            await telemetry.send_community_resource_report("blockscout-mcp://skill/SKILL.md", "c", "1.0", "1.1")
            mock_ac.assert_not_called()
    finally:
        analytics.set_http_mode(False)


@pytest.mark.asyncio
async def test_send_community_resource_report_network_error_swallowed(monkeypatch):
    """Network errors during POST do not propagate."""
    monkeypatch.setattr(config, "disable_community_telemetry", False, raising=False)
    monkeypatch.setattr(config, "mixpanel_token", "", raising=False)
    mock_client = AsyncMock()
    mock_client.post.side_effect = Exception("network failure")
    mock_ctx_mgr = AsyncMock()
    mock_ctx_mgr.__aenter__.return_value = mock_client
    with patch("httpx.AsyncClient", return_value=mock_ctx_mgr):
        # Must not raise
        await telemetry.send_community_resource_report("blockscout-mcp://skill/SKILL.md", "c", "1.0", "1.1")
        mock_client.post.assert_awaited_once()
