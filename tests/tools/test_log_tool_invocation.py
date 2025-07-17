import logging

import pytest
from mcp.server.fastmcp import Context

from blockscout_mcp_server.tools.common import log_tool_invocation


@pytest.mark.asyncio
async def test_log_tool_invocation_decorator(caplog: pytest.LogCaptureFixture, mock_ctx: Context) -> None:
    caplog.set_level(logging.INFO, logger="blockscout_mcp_server.tools.common")

    @log_tool_invocation
    async def dummy_tool(a: int, b: int, ctx: Context) -> int:
        return a + b

    result = await dummy_tool(1, 2, ctx=mock_ctx)

    assert result == 3
    log_text = caplog.text
    assert "Tool invoked: dummy_tool" in log_text
    assert "'ctx'" not in log_text
    assert str(mock_ctx) not in log_text
