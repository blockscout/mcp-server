import logging
from unittest.mock import MagicMock

import mcp.types as types
import pytest
from mcp.server.fastmcp import Context

from blockscout_mcp_server.tools.decorators import log_tool_invocation


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
async def test_log_tool_invocation_mcp_context(caplog: pytest.LogCaptureFixture) -> None:
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

    full_mock_ctx = MagicMock()
    full_mock_ctx.session = mock_session

    await dummy_tool(1, ctx=full_mock_ctx)

    log_text = caplog.text
    assert "Tool invoked: dummy_tool" in log_text
    assert "with args: {'a': 1}" in log_text
    assert "(Client: test-client, Version: 1.2.3, Protocol: 2024-11-05)" in log_text
