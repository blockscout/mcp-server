from unittest.mock import AsyncMock, patch

import pytest

from blockscout_mcp_server.models import BlockNumberData, ToolResponse
from blockscout_mcp_server.tools.block.get_block_number import get_block_number


@pytest.mark.asyncio
async def test_get_block_number_latest_success(mock_ctx):
    """Verify get_block_number returns the latest block when datetime is omitted."""
    chain_id = "1"
    mock_base_url = "https://eth.blockscout.com"
    mock_api_response = [{"height": 12345, "timestamp": "2023-01-01T00:00:00Z"}]

    with (
        patch(
            "blockscout_mcp_server.tools.block.get_block_number.get_blockscout_base_url", new_callable=AsyncMock
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.block.get_block_number.make_blockscout_request", new_callable=AsyncMock
        ) as mock_request,
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response

        result = await get_block_number(chain_id=chain_id, ctx=mock_ctx)

        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(base_url=mock_base_url, api_path="/api/v2/main-page/blocks")
        assert isinstance(result, ToolResponse)
        assert isinstance(result.data, BlockNumberData)
        assert result.data.block_number == 12345
        assert result.data.timestamp == "2023-01-01T00:00:00Z"
        assert mock_ctx.report_progress.await_count == 3
        assert mock_ctx.info.await_count == 3
        assert "Latest block on chain" in result.content_text


@pytest.mark.asyncio
async def test_get_block_number_by_time_success(mock_ctx):
    """Verify get_block_number resolves a block number for a specific datetime."""
    chain_id = "1"
    mock_base_url = "https://eth.blockscout.com"
    lookup_response = {"status": "1", "result": {"blockNumber": "12345"}}
    block_response = {"timestamp": "2023-01-01T00:00:00Z"}

    with (
        patch(
            "blockscout_mcp_server.tools.block.get_block_number.get_blockscout_base_url", new_callable=AsyncMock
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.block.get_block_number.make_blockscout_request", new_callable=AsyncMock
        ) as mock_request,
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.side_effect = [lookup_response, block_response]

        result = await get_block_number(chain_id=chain_id, ctx=mock_ctx, datetime="2023-01-01T00:00:00Z")

        assert result.data.block_number == 12345
        assert result.data.timestamp == "2023-01-01T00:00:00Z"
        assert mock_request.await_args_list[0].kwargs == {
            "base_url": mock_base_url,
            "api_path": "/api",
            "params": {
                "module": "block",
                "action": "getblocknobytime",
                "timestamp": 1672531200,
                "closest": "before",
            },
        }
        assert mock_request.await_args_list[1].kwargs == {
            "base_url": mock_base_url,
            "api_path": "/api/v2/blocks/12345",
        }
        assert mock_ctx.report_progress.await_count == 4
        assert mock_ctx.info.await_count == 4
        assert "closest block before" in result.content_text


@pytest.mark.asyncio
async def test_get_block_number_invalid_date(mock_ctx):
    """Verify get_block_number rejects malformed datetime input."""
    with (
        patch(
            "blockscout_mcp_server.tools.block.get_block_number.get_blockscout_base_url", new_callable=AsyncMock
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.block.get_block_number.make_blockscout_request", new_callable=AsyncMock
        ) as mock_request,
    ):
        with pytest.raises(ValueError, match="Invalid datetime format"):
            await get_block_number(chain_id="1", ctx=mock_ctx, datetime="not-a-date")

        mock_get_url.assert_not_called()
        mock_request.assert_not_called()


@pytest.mark.asyncio
async def test_get_block_number_api_failure(mock_ctx):
    """Verify get_block_number surfaces API failures when resolving block by time."""
    chain_id = "1"
    mock_base_url = "https://eth.blockscout.com"
    lookup_response = {"status": "0", "message": "NOTOK"}

    with (
        patch(
            "blockscout_mcp_server.tools.block.get_block_number.get_blockscout_base_url", new_callable=AsyncMock
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.block.get_block_number.make_blockscout_request", new_callable=AsyncMock
        ) as mock_request,
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.return_value = lookup_response

        with pytest.raises(ValueError, match="Blockscout API error while resolving block by time"):
            await get_block_number(chain_id=chain_id, ctx=mock_ctx, datetime="2023-01-01T00:00:00Z")

        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once()
