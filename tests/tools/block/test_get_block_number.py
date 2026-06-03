# SPDX-License-Identifier: LicenseRef-Blockscout
from unittest.mock import AsyncMock, patch

import pytest

from blockscout_mcp_server.config import config
from blockscout_mcp_server.models import BlockNumberData, ToolResponse
from blockscout_mcp_server.tools.block.get_block_number import get_block_number


@pytest.mark.asyncio
async def test_get_block_number_latest_success(mock_ctx):
    """Verify get_block_number returns the latest block when datetime is omitted."""
    chain_id = "1"
    mock_api_response = [{"height": 12345, "timestamp": "2023-01-01T00:00:00Z"}]

    with (
        patch(
            "blockscout_mcp_server.tools.block.get_block_number.make_blockscout_request", new_callable=AsyncMock
        ) as mock_request,
    ):
        mock_request.return_value = mock_api_response

        result = await get_block_number(chain_id=chain_id, ctx=mock_ctx)

        mock_request.assert_called_once_with(
            chain_id=chain_id,
            api_path="/api/v2/main-page/blocks",
            timeout=config.bs_light_timeout,
        )
        assert isinstance(result, ToolResponse)
        assert isinstance(result.data, BlockNumberData)
        assert result.data.block_number == 12345
        assert result.data.timestamp == "2023-01-01T00:00:00Z"
        assert mock_ctx.report_progress.await_count == 2
        assert mock_ctx.info.await_count == 2
        assert "Latest block on chain" in result.content_text


@pytest.mark.asyncio
async def test_get_block_number_by_time_success(mock_ctx):
    """Verify get_block_number resolves a block number for a specific datetime."""
    chain_id = "1"
    lookup_response = {"status": "1", "result": {"blockNumber": "12345"}}
    block_response = {"timestamp": "2023-01-01T00:00:00Z"}

    with (
        patch(
            "blockscout_mcp_server.tools.block.get_block_number.make_blockscout_request", new_callable=AsyncMock
        ) as mock_request,
    ):
        mock_request.side_effect = [lookup_response, block_response]

        result = await get_block_number(chain_id=chain_id, ctx=mock_ctx, datetime="2023-01-01T00:00:00Z")

        assert result.data.block_number == 12345
        assert result.data.timestamp == "2023-01-01T00:00:00Z"
        assert mock_request.await_args_list[0].kwargs == {
            "chain_id": chain_id,
            "api_path": "/api",
            "params": {
                "module": "block",
                "action": "getblocknobytime",
                "timestamp": 1672531200,
                "closest": "before",
            },
            "timeout": config.bs_light_timeout,
        }
        assert mock_request.await_args_list[1].kwargs == {
            "chain_id": chain_id,
            "api_path": "/api/v2/blocks/12345",
            "timeout": config.bs_light_timeout,
        }
        assert mock_ctx.report_progress.await_count == 3
        assert mock_ctx.info.await_count == 3
        assert "closest block before" in result.content_text


@pytest.mark.asyncio
async def test_get_block_number_latest_upstream_failure(mock_ctx):
    """Verify get_block_number (latest branch) emits only the start beat when the request fails."""
    chain_id = "1"

    with (
        patch(
            "blockscout_mcp_server.tools.block.get_block_number.make_blockscout_request", new_callable=AsyncMock
        ) as mock_request,
    ):
        mock_request.side_effect = ValueError("upstream error")

        with pytest.raises(ValueError, match="upstream error"):
            await get_block_number(chain_id=chain_id, ctx=mock_ctx)

        assert mock_ctx.report_progress.await_count == 1
        assert mock_ctx.info.await_count == 1


@pytest.mark.asyncio
async def test_get_block_number_invalid_date(mock_ctx):
    """Verify get_block_number rejects malformed datetime input."""
    with (
        patch(
            "blockscout_mcp_server.tools.block.get_block_number.make_blockscout_request", new_callable=AsyncMock
        ) as mock_request,
    ):
        with pytest.raises(ValueError, match="Invalid datetime format"):
            await get_block_number(chain_id="1", ctx=mock_ctx, datetime="not-a-date")

        mock_request.assert_not_called()


@pytest.mark.asyncio
async def test_get_block_number_api_failure(mock_ctx):
    """Verify get_block_number surfaces API failures when resolving block by time."""
    chain_id = "1"
    lookup_response = {"status": "0", "message": "NOTOK"}

    with (
        patch(
            "blockscout_mcp_server.tools.block.get_block_number.make_blockscout_request", new_callable=AsyncMock
        ) as mock_request,
    ):
        mock_request.return_value = lookup_response

        with pytest.raises(ValueError, match="Blockscout API error while resolving block by time"):
            await get_block_number(chain_id=chain_id, ctx=mock_ctx, datetime="2023-01-01T00:00:00Z")

        mock_request.assert_called_once()
