# SPDX-License-Identifier: LicenseRef-Blockscout
import asyncio
import hashlib
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import mcp.types as types
import pytest
from mcp.server.fastmcp import Context
from mcp.types import RequestParams
from starlette.datastructures import Headers

from blockscout_mcp_server.api.dependencies import MockCtx
from blockscout_mcp_server.client_meta import (
    UNDEFINED_CLIENT_NAME,
    UNDEFINED_CLIENT_VERSION,
    UNKNOWN_PROTOCOL_VERSION,
)
from blockscout_mcp_server.config import config as server_config
from blockscout_mcp_server.constants import PRO_API_KEY_HASH_PREFIX
from blockscout_mcp_server.pro_api_key_context import (
    pro_api_key_scope,
    resolve_pro_api_key,
)
from blockscout_mcp_server.telemetry import resolve_auth_signals
from blockscout_mcp_server.tools.decorators import log_tool_invocation


@pytest.mark.asyncio
async def test_decorator_calls_analytics(monkeypatch, caplog: pytest.LogCaptureFixture, mock_ctx: Context) -> None:
    # Arrange
    caplog.set_level(logging.INFO, logger="blockscout_mcp_server.tools.decorators")

    calls = {}

    def fake_track(ctx, name, args, client_meta=None, auth_origin=None):  # type: ignore[no-untyped-def]
        calls["ctx"] = ctx
        calls["name"] = name
        calls["args"] = args
        calls["client_meta"] = client_meta
        calls["auth_origin"] = auth_origin

    monkeypatch.setattr("blockscout_mcp_server.tools.decorators.analytics.track_tool_invocation", fake_track)

    @log_tool_invocation
    async def dummy_tool(a: int, ctx: Context) -> int:
        return a

    # Pin community telemetry on so resolve_auth_signals derives instead of short-circuiting to
    # (None, None): with community disabled (e.g. BLOCKSCOUT_DISABLE_COMMUNITY_TELEMETRY set in the
    # env or a local .env) and HTTP mode off, no sink would consume the signals and auth_origin
    # would be None regardless of the header — making the assertion below untestable.
    monkeypatch.setattr(server_config, "disable_community_telemetry", False, raising=False)
    # A valid client PRO API key header makes the derived origin deterministic ("client").
    # Pinning the exact value is what gives the assertion teeth: `in ("client","server","none")`
    # is vacuous because every AuthOrigin member trivially satisfies it, so it would pass even
    # if the decorator threaded a constant or the wrong field.
    monkeypatch.setattr(server_config, "pro_api_key", "", raising=False)
    headers = Headers(headers={server_config.pro_api_key_header.upper(): "client-key-123"})
    mock_ctx.session = None
    mock_ctx.request_context = SimpleNamespace(request=SimpleNamespace(headers=headers))

    # Act
    await dummy_tool(7, ctx=mock_ctx)

    # Assert
    assert calls["name"] == "dummy_tool"
    assert calls["args"] == {"a": 7}
    assert calls["ctx"] is mock_ctx
    assert "client_meta" in calls
    # The decorator derives the auth signals from ctx and threads the origin into
    # track_tool_invocation. With a valid client-key header present, that origin must be
    # exactly "client" — proving a real ctx-derived value was threaded, not a constant.
    assert calls["auth_origin"] == "client"


@pytest.mark.asyncio
async def test_log_tool_invocation_decorator(caplog: pytest.LogCaptureFixture, mock_ctx: Context) -> None:
    caplog.set_level(logging.INFO, logger="blockscout_mcp_server.tools.decorators")

    @log_tool_invocation
    async def dummy_tool(a: int, b: int, ctx: Context) -> int:
        return a + b

    result = await dummy_tool(1, 2, ctx=mock_ctx)

    assert result == 3
    log_text = caplog.text
    assert "Tool invoked: dummy_tool" in log_text
    assert "'ctx'" not in log_text
    assert str(mock_ctx) not in log_text


@pytest.mark.asyncio
async def test_log_tool_invocation_mcp_context(caplog: pytest.LogCaptureFixture, mock_ctx: Context) -> None:
    """Verify that client info is logged correctly from a full MCP context."""
    caplog.set_level(logging.INFO, logger="blockscout_mcp_server.tools.decorators")

    @log_tool_invocation
    async def dummy_tool(a: int, ctx: Context) -> int:
        return a

    mock_session = MagicMock()
    mock_session.client_params = types.InitializeRequestParams(
        protocolVersion="2024-11-05",
        capabilities=types.ClientCapabilities(),
        clientInfo=types.Implementation(name="test-client", version="1.2.3"),
    )
    mock_ctx.session = mock_session

    await dummy_tool(1, ctx=mock_ctx)

    log_text = caplog.text
    assert "Tool invoked: dummy_tool" in log_text
    assert "with args: {'a': 1}" in log_text
    assert "(Client: test-client, Version: 1.2.3, Protocol: 2024-11-05)" in log_text
    # Exact full-message assertion: ensures byte-identical output (catches double spaces, stray text, etc.)
    assert (
        caplog.records[-1].getMessage()
        == "Tool invoked: dummy_tool with args: {'a': 1} (Client: test-client, Version: 1.2.3, Protocol: 2024-11-05)"
    )


@pytest.mark.asyncio
async def test_log_tool_invocation_with_intermediary(caplog: pytest.LogCaptureFixture, mock_ctx: Context) -> None:
    caplog.set_level(logging.INFO, logger="blockscout_mcp_server.tools.decorators")

    @log_tool_invocation
    async def dummy_tool(a: int, ctx: Context) -> int:
        return a

    headers = {"Blockscout-MCP-Intermediary": "HigressPlugin"}
    mock_ctx.request_context = SimpleNamespace(request=SimpleNamespace(headers=headers))
    mock_ctx.session = MagicMock()
    mock_ctx.session.client_params = types.InitializeRequestParams(
        protocolVersion="2024-11-05",
        capabilities=types.ClientCapabilities(),
        clientInfo=types.Implementation(name="test-client", version="1.2.3"),
    )

    await dummy_tool(1, ctx=mock_ctx)

    log_text = caplog.text
    assert "(Client: test-client/HigressPlugin, Version: 1.2.3, Protocol: 2024-11-05)" in log_text


@pytest.mark.asyncio
@patch(
    "blockscout_mcp_server.tools.decorators.telemetry.send_community_usage_report",
    new_callable=AsyncMock,
)
async def test_decorator_reports_telemetry(mock_report, monkeypatch, mock_ctx: Context) -> None:
    # Keep community telemetry enabled so resolve_auth_signals derives auth_origin instead of
    # short-circuiting to (None, None) when BLOCKSCOUT_DISABLE_COMMUNITY_TELEMETRY is set ambiently.
    monkeypatch.setattr(server_config, "disable_community_telemetry", False, raising=False)
    monkeypatch.setattr(server_config, "pro_api_key", "", raising=False)

    @log_tool_invocation
    async def dummy_tool(a: int, ctx: Context) -> int:
        return a

    mock_ctx.session = None
    mock_ctx.request_context = None
    await dummy_tool(5, ctx=mock_ctx)
    await asyncio.sleep(0)
    mock_report.assert_awaited_once_with(
        "dummy_tool",
        {"a": 5},
        UNDEFINED_CLIENT_NAME,
        UNDEFINED_CLIENT_VERSION,
        UNKNOWN_PROTOCOL_VERSION,
        auth_origin="none",
        api_key_fingerprint=None,
    )


@pytest.mark.asyncio
@patch(
    "blockscout_mcp_server.tools.decorators.telemetry.send_community_usage_report",
    new_callable=AsyncMock,
)
async def test_decorator_reports_telemetry_with_client_key(mock_report, monkeypatch, mock_ctx: Context) -> None:
    """A client-supplied PRO API key header is forwarded as a non-reversible fingerprint."""
    # Keep community telemetry enabled so resolve_auth_signals derives auth_origin instead of
    # short-circuiting to (None, None) when BLOCKSCOUT_DISABLE_COMMUNITY_TELEMETRY is set ambiently.
    monkeypatch.setattr(server_config, "disable_community_telemetry", False, raising=False)
    monkeypatch.setattr(server_config, "pro_api_key", "", raising=False)
    raw_key = "super-secret-client-key"

    @log_tool_invocation
    async def dummy_tool(a: int, ctx: Context) -> int:
        return a

    headers = Headers(headers={server_config.pro_api_key_header.upper(): raw_key})
    mock_ctx.session = None
    mock_ctx.request_context = SimpleNamespace(request=SimpleNamespace(headers=headers))
    await dummy_tool(5, ctx=mock_ctx)
    await asyncio.sleep(0)

    mock_report.assert_awaited_once()
    call_kwargs = mock_report.await_args.kwargs
    assert call_kwargs["auth_origin"] == "client"
    assert call_kwargs["api_key_fingerprint"] is not None
    assert call_kwargs["api_key_fingerprint"] != raw_key


@pytest.mark.asyncio
@patch(
    "blockscout_mcp_server.tools.decorators.telemetry.send_community_usage_report",
    new_callable=AsyncMock,
)
async def test_decorator_derives_auth_signals_once_and_threads_to_both_sinks(
    mock_report, monkeypatch, mock_ctx: Context
) -> None:
    """The (auth_origin, fingerprint) pair is derived a single time per invocation and the
    identical values flow to both the Mixpanel sink and the community report — with no second
    ctx extraction / SHA-256 on the hot path (regression guard for the de-dup fix).

    This drives the *real* analytics sink (only the Mixpanel client is mocked) and spies on the
    real derivation helper rather than mocking it away. That is what makes the guard meaningful:
    the origin is derived exactly once, by the decorator, and the identical value is observed in
    the Mixpanel property bag — proving it was threaded through rather than recomputed by the sink.
    Mocking the derivation away (the previous approach) made the "derived once" claim structurally
    true by construction instead of observing it.
    """
    # Spy on the single derivation point — the shared telemetry.resolve_auth_signals helper the
    # decorator delegates to — while keeping the real implementation.
    signals_spy = MagicMock(side_effect=resolve_auth_signals)
    monkeypatch.setattr("blockscout_mcp_server.telemetry.resolve_auth_signals", signals_spy)

    # Drive the real analytics sink with a mocked Mixpanel client so the property bag is
    # genuinely exercised rather than structurally bypassed.
    mock_mp = MagicMock()
    monkeypatch.setattr("blockscout_mcp_server.analytics._is_http_mode_enabled", True, raising=False)
    monkeypatch.setattr("blockscout_mcp_server.analytics._get_mixpanel_client", lambda: mock_mp)

    # Deterministic valid client-key header -> origin "client", fingerprint = client-key hash.
    monkeypatch.setattr(server_config, "pro_api_key", "", raising=False)
    raw_key = "client-key-123"
    headers = Headers(headers={server_config.pro_api_key_header.upper(): raw_key})
    req = SimpleNamespace(headers=headers, client=SimpleNamespace(host="127.0.0.1"))
    mock_ctx.session = None
    mock_ctx.request_context = SimpleNamespace(request=req)

    @log_tool_invocation
    async def dummy_tool(a: int, ctx: Context) -> int:
        return a

    await dummy_tool(5, ctx=mock_ctx)
    await asyncio.sleep(0)

    # Derived exactly once by the decorator...
    signals_spy.assert_called_once()

    # ...and the same origin reached the Mixpanel property bag (3rd positional arg of mp.track),
    # confirming the sink reused the threaded value instead of re-deriving it.
    mock_mp.track.assert_called_once()
    props = mock_mp.track.call_args.args[2]
    assert props["auth_origin"] == "client"
    # The fingerprint is never emitted to Mixpanel (privacy invariant).
    assert "api_key_fingerprint" not in props

    # ...and the identical pair reached the community report.
    expected_fingerprint = hashlib.sha256(f"{PRO_API_KEY_HASH_PREFIX}{raw_key}".encode()).hexdigest()
    mock_report.assert_awaited_once()
    call_kwargs = mock_report.await_args.kwargs
    assert call_kwargs["auth_origin"] == "client"
    assert call_kwargs["api_key_fingerprint"] == expected_fingerprint


@pytest.mark.asyncio
async def test_log_tool_invocation_logs_meta_fields(caplog: pytest.LogCaptureFixture, mock_ctx: Context) -> None:
    """Verify that MCP meta fields including OpenAI fields are logged in Tool invoked message."""
    caplog.set_level(logging.INFO, logger="blockscout_mcp_server.tools.decorators")

    @log_tool_invocation
    async def dummy_tool(a: int, ctx: Context) -> int:
        return a

    # Create context with meta
    meta = RequestParams.Meta(
        **{
            "openai/userAgent": "ChatGPT/1.0",
            "openai/userLocation": "US-CA",
        }
    )

    mock_request = SimpleNamespace(headers={})
    mock_ctx.request_context = SimpleNamespace(meta=meta, request=mock_request)
    mock_ctx.session = None

    await dummy_tool(1, ctx=mock_ctx)

    log_text = caplog.text
    assert "Tool invoked: dummy_tool" in log_text
    assert "Meta:" in log_text
    assert "openai/userAgent" in log_text
    assert "ChatGPT/1.0" in log_text
    assert "openai/userLocation" in log_text
    assert "US-CA" in log_text


@pytest.mark.asyncio
async def test_log_tool_invocation_no_meta_no_log(caplog: pytest.LogCaptureFixture, mock_ctx: Context) -> None:
    """Verify that empty meta_dict doesn't appear in log."""
    caplog.set_level(logging.INFO, logger="blockscout_mcp_server.tools.decorators")

    @log_tool_invocation
    async def dummy_tool(a: int, ctx: Context) -> int:
        return a

    # Context with no meta
    mock_ctx.request_context = None
    mock_ctx.session = None

    result = await dummy_tool(1, ctx=mock_ctx)
    assert result == 1

    log_text = caplog.text
    assert "Tool invoked: dummy_tool" in log_text
    assert "Meta:" not in log_text


# ---------------------------------------------------------------------------
# pro_api_key_scope decorator tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pro_api_key_scope_mcp_context_resolves_client_key(monkeypatch, mock_ctx: Context) -> None:
    """Invoking a tool stacked with log_tool_invocation + pro_api_key_scope and an MCP-like
    context carrying the client-key header causes resolve_pro_api_key() to return the
    client key during the tool body, and the ContextVar is reset to its default afterward."""
    monkeypatch.setattr(server_config, "pro_api_key_header", "Blockscout-MCP-Pro-Api-Key", raising=False)
    monkeypatch.setattr(server_config, "pro_api_key", "server-key", raising=False)

    client_key_during_call = None

    @log_tool_invocation
    @pro_api_key_scope
    async def dummy_tool(a: int, ctx: Context) -> int:
        nonlocal client_key_during_call
        client_key_during_call = resolve_pro_api_key()
        return a

    # Build a real Starlette Headers object with a non-canonical header casing
    headers = Headers(headers={"BLOCKSCOUT-MCP-PRO-API-KEY": "my-client-secret"})
    mock_ctx.call_source = "mcp"
    mock_ctx.request_context = SimpleNamespace(request=SimpleNamespace(headers=headers))
    mock_ctx.session = None

    await dummy_tool(42, ctx=mock_ctx)

    # The client key was resolved inside the tool body
    assert client_key_during_call == "my-client-secret"

    # After the call the ContextVar is reset — resolve_pro_api_key falls back to server key
    assert resolve_pro_api_key() == "server-key"


@pytest.mark.asyncio
async def test_pro_api_key_scope_rest_context_reads_client_key(monkeypatch) -> None:
    """A REST MockCtx call carrying the configured header resolves the client key."""
    monkeypatch.setattr(server_config, "pro_api_key_header", "Blockscout-MCP-Pro-Api-Key", raising=False)
    monkeypatch.setattr(server_config, "pro_api_key", "server-key", raising=False)

    resolved_key = None

    @log_tool_invocation
    @pro_api_key_scope
    async def dummy_tool(a: int, ctx) -> int:  # type: ignore[no-untyped-def]
        nonlocal resolved_key
        resolved_key = resolve_pro_api_key()
        return a

    # Build a REST-style MockCtx that carries the header — it must now be honored
    rest_ctx = MockCtx()
    headers = Headers(headers={"Blockscout-MCP-Pro-Api-Key": "client-secret"})
    rest_ctx.request_context = SimpleNamespace(request=SimpleNamespace(headers=headers))

    await dummy_tool(1, ctx=rest_ctx)

    assert resolved_key == "client-secret"


@pytest.mark.asyncio
async def test_pro_api_key_never_appears_in_logs(
    monkeypatch, caplog: pytest.LogCaptureFixture, mock_ctx: Context
) -> None:
    """The client-key value must not appear in any log output from log_tool_invocation
    or any other logger captured during the invocation."""
    monkeypatch.setattr(server_config, "pro_api_key_header", "Blockscout-MCP-Pro-Api-Key", raising=False)
    caplog.set_level(logging.DEBUG)

    client_key = "super-secret-key-xyz"

    @log_tool_invocation
    @pro_api_key_scope
    async def dummy_tool(a: int, ctx: Context) -> int:
        return a

    headers = Headers(headers={"Blockscout-MCP-Pro-Api-Key": client_key})
    mock_ctx.call_source = "mcp"
    mock_ctx.request_context = SimpleNamespace(request=SimpleNamespace(headers=headers))
    mock_ctx.session = None

    await dummy_tool(7, ctx=mock_ctx)

    # Case-insensitive: catch a leaked header name/value regardless of logger casing.
    logged_text = caplog.text.lower()
    assert client_key.lower() not in logged_text
    assert "blockscout-mcp-pro-api-key" not in logged_text
