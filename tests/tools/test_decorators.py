import logging
from unittest.mock import MagicMock

import mcp.types as types
import pytest
from mcp.server.fastmcp import Context

from blockscout_mcp_server.tools.decorators import log_tool_invocation


@pytest.mark.asyncio
async def test_decorator_calls_analytics(monkeypatch, caplog: pytest.LogCaptureFixture, mock_ctx: Context) -> None:
    # Arrange
    caplog.set_level(logging.INFO, logger="blockscout_mcp_server.tools.decorators")

    calls = {}

    def fake_track(ctx, name, args, client_meta=None):  # type: ignore[no-untyped-def]
        calls["ctx"] = ctx
        calls["name"] = name
        calls["args"] = args
        calls["client_meta"] = client_meta

    monkeypatch.setattr("blockscout_mcp_server.tools.decorators.analytics.track_tool_invocation", fake_track)

    @log_tool_invocation
    async def dummy_tool(a: int, ctx: Context) -> int:
        return a

    # Act
    await dummy_tool(7, ctx=mock_ctx)

    # Assert
    assert calls["name"] == "dummy_tool"
    assert calls["args"] == {"a": 7}
    assert calls["ctx"] is mock_ctx
    assert "client_meta" in calls


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
