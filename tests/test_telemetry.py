# SPDX-License-Identifier: LicenseRef-Blockscout
from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest
from pro_api_key_helpers import ctx_with_header

from blockscout_mcp_server import analytics, pro_api_key_context, telemetry
from blockscout_mcp_server.config import config
from blockscout_mcp_server.constants import (
    COMMUNITY_TELEMETRY_ENDPOINT,
    COMMUNITY_TELEMETRY_URL,
    RESOURCE_READ_EVENT,
)

# ---------------------------------------------------------------------------
# resolve_auth_signals — shared derivation entry point + all-disabled short-circuit
# ---------------------------------------------------------------------------


def test_resolve_auth_signals_short_circuits_when_all_telemetry_disabled(monkeypatch):
    """With HTTP mode off AND community telemetry disabled, derivation is skipped entirely.

    No sink can consume the signals in that state, so the helper must return
    (None, None) without extracting ctx or hashing a key.
    """
    monkeypatch.setattr(config, "disable_community_telemetry", True, raising=False)
    analytics.set_http_mode(False)
    compute_spy = MagicMock()
    monkeypatch.setattr("blockscout_mcp_server.telemetry.compute_auth_signals", compute_spy)

    assert telemetry.resolve_auth_signals(object()) == (None, None)
    compute_spy.assert_not_called()


def test_resolve_auth_signals_derives_when_community_enabled(monkeypatch):
    """Community telemetry enabled (HTTP mode off) still needs the signals -> derivation runs.

    The community sink consumes the fingerprint, so the helper delegates to
    compute_auth_signals and returns its pair unchanged.
    """
    monkeypatch.setattr(config, "disable_community_telemetry", False, raising=False)
    analytics.set_http_mode(False)
    compute_spy = MagicMock(return_value=("server", "d" * 64))
    monkeypatch.setattr("blockscout_mcp_server.telemetry.compute_auth_signals", compute_spy)

    ctx = object()
    assert telemetry.resolve_auth_signals(ctx) == ("server", "d" * 64)
    compute_spy.assert_called_once_with(ctx)


def test_resolve_auth_signals_derives_in_http_mode_even_if_community_disabled(monkeypatch):
    """HTTP mode on feeds the analytics sink, so derivation runs even when community is disabled.

    The short-circuit is a superset guard keyed only on "no sink at all"; with HTTP
    mode on it never fires, so the helper delegates to compute_auth_signals.
    """
    monkeypatch.setattr(config, "disable_community_telemetry", True, raising=False)
    analytics.set_http_mode(True)
    try:
        compute_spy = MagicMock(return_value=("client", "e" * 64))
        monkeypatch.setattr("blockscout_mcp_server.telemetry.compute_auth_signals", compute_spy)

        ctx = object()
        assert telemetry.resolve_auth_signals(ctx) == ("client", "e" * 64)
        compute_spy.assert_called_once_with(ctx)
    finally:
        analytics.set_http_mode(False)


def test_resolve_auth_signals_returns_server_fingerprint_in_http_mode(monkeypatch):
    """End-to-end: absent client key + server key + HTTP on + community off -> ("server", <hash>).

    Uses the real compute_auth_signals (no spy). The server-key SHA-256 is no longer
    gated away in this exact config — it is memoized once per process — so the helper
    returns the full ("server", fingerprint) pair rather than ("server", None).
    """
    monkeypatch.setattr(config, "disable_community_telemetry", True, raising=False)
    monkeypatch.setattr(config, "pro_api_key_header", "Blockscout-MCP-Pro-Api-Key", raising=False)
    monkeypatch.setattr(config, "pro_api_key", "server-key", raising=False)
    analytics.set_http_mode(True)
    try:
        ctx = ctx_with_header("Blockscout-MCP-Pro-Api-Key", "")
        expected = pro_api_key_context._fingerprint_pro_api_key("server-key")
        assert telemetry.resolve_auth_signals(ctx) == ("server", expected)
    finally:
        analytics.set_http_mode(False)


def test_resolve_auth_signals_never_raises(monkeypatch):
    """A hypothetical failure in compute_auth_signals degrades to (None, None), never propagates."""
    monkeypatch.setattr(config, "disable_community_telemetry", False, raising=False)
    analytics.set_http_mode(False)
    monkeypatch.setattr(
        "blockscout_mcp_server.telemetry.compute_auth_signals",
        MagicMock(side_effect=RuntimeError("boom")),
    )

    assert telemetry.resolve_auth_signals(object()) == (None, None)


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
                "auth_origin": None,
                "api_key_fingerprint": None,
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


@pytest.mark.asyncio
async def test_send_community_usage_report_includes_auth_origin_and_fingerprint(monkeypatch):
    """A call passing auth_origin='client' and a fingerprint string includes both verbatim."""
    monkeypatch.setattr(config, "disable_community_telemetry", False, raising=False)
    monkeypatch.setattr(config, "mixpanel_token", "", raising=False)
    fingerprint = "a" * 64
    mock_client = AsyncMock()
    mock_ctx_mgr = AsyncMock()
    mock_ctx_mgr.__aenter__.return_value = mock_client
    with patch("httpx.AsyncClient", return_value=mock_ctx_mgr):
        await telemetry.send_community_usage_report(
            "tool",
            {"a": 1},
            "client",
            "1.0",
            "1.1",
            auth_origin="client",
            api_key_fingerprint=fingerprint,
        )
        url = f"{COMMUNITY_TELEMETRY_URL}{COMMUNITY_TELEMETRY_ENDPOINT}"
        mock_client.post.assert_awaited_once_with(
            url,
            json={
                "tool_name": "tool",
                "tool_args": {"a": 1},
                "client_name": "client",
                "client_version": "1.0",
                "protocol_version": "1.1",
                "auth_origin": "client",
                "api_key_fingerprint": fingerprint,
            },
            headers=ANY,
            timeout=2.0,
        )


@pytest.mark.asyncio
async def test_send_community_usage_report_none_origin_serializes_null_fingerprint(monkeypatch):
    """A call passing auth_origin='none' and api_key_fingerprint=None serializes the fingerprint as JSON null."""
    monkeypatch.setattr(config, "disable_community_telemetry", False, raising=False)
    monkeypatch.setattr(config, "mixpanel_token", "", raising=False)
    mock_client = AsyncMock()
    mock_ctx_mgr = AsyncMock()
    mock_ctx_mgr.__aenter__.return_value = mock_client
    with patch("httpx.AsyncClient", return_value=mock_ctx_mgr):
        await telemetry.send_community_usage_report(
            "tool",
            {"a": 1},
            "client",
            "1.0",
            "1.1",
            auth_origin="none",
            api_key_fingerprint=None,
        )
        url = f"{COMMUNITY_TELEMETRY_URL}{COMMUNITY_TELEMETRY_ENDPOINT}"
        _, kwargs = mock_client.post.call_args
        assert "api_key_fingerprint" in kwargs["json"]
        assert kwargs["json"]["api_key_fingerprint"] is None
        mock_client.post.assert_awaited_once_with(
            url,
            json={
                "tool_name": "tool",
                "tool_args": {"a": 1},
                "client_name": "client",
                "client_version": "1.0",
                "protocol_version": "1.1",
                "auth_origin": "none",
                "api_key_fingerprint": None,
            },
            headers=ANY,
            timeout=2.0,
        )


@pytest.mark.asyncio
async def test_send_community_usage_report_raw_key_never_in_payload(monkeypatch):
    """A representative raw key value never appears anywhere in the posted payload."""
    monkeypatch.setattr(config, "disable_community_telemetry", False, raising=False)
    monkeypatch.setattr(config, "mixpanel_token", "", raising=False)
    raw_key = "super-secret-raw-pro-api-key-value"
    fingerprint = "b" * 64
    mock_client = AsyncMock()
    mock_ctx_mgr = AsyncMock()
    mock_ctx_mgr.__aenter__.return_value = mock_client
    with patch("httpx.AsyncClient", return_value=mock_ctx_mgr):
        await telemetry.send_community_usage_report(
            "tool",
            {"a": 1},
            "client",
            "1.0",
            "1.1",
            auth_origin="client",
            api_key_fingerprint=fingerprint,
        )
        _, kwargs = mock_client.post.call_args
        posted_payload = kwargs["json"]
        assert raw_key not in str(posted_payload)
        assert posted_payload["api_key_fingerprint"] == fingerprint


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
                "auth_origin": None,
                "api_key_fingerprint": None,
            },
            headers=ANY,
            timeout=2.0,
        )


@pytest.mark.asyncio
async def test_send_community_resource_report_forwards_auth_origin_and_fingerprint(monkeypatch):
    """auth_origin and api_key_fingerprint passed in are forwarded verbatim to the delegated call."""
    monkeypatch.setattr(config, "disable_community_telemetry", False, raising=False)
    monkeypatch.setattr(config, "mixpanel_token", "", raising=False)
    uri = "blockscout-mcp://skill/SKILL.md"
    fingerprint = "c" * 64
    mock_client = AsyncMock()
    mock_ctx_mgr = AsyncMock()
    mock_ctx_mgr.__aenter__.return_value = mock_client
    with patch("httpx.AsyncClient", return_value=mock_ctx_mgr):
        await telemetry.send_community_resource_report(
            uri,
            "client",
            "1.0",
            "1.1",
            auth_origin="server",
            api_key_fingerprint=fingerprint,
        )
        url = f"{COMMUNITY_TELEMETRY_URL}{COMMUNITY_TELEMETRY_ENDPOINT}"
        mock_client.post.assert_awaited_once_with(
            url,
            json={
                "tool_name": RESOURCE_READ_EVENT,
                "tool_args": {"uri": uri},
                "client_name": "client",
                "client_version": "1.0",
                "protocol_version": "1.1",
                "auth_origin": "server",
                "api_key_fingerprint": fingerprint,
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
