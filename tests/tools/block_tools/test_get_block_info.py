from unittest.mock import AsyncMock, MagicMock, call, patch

import httpx
import pytest

from blockscout_mcp_server.models import BlockInfoData, ToolResponse
from blockscout_mcp_server.tools.block.get_block_info import get_block_info


@pytest.mark.asyncio
async def test_get_block_info_success_no_txs(mock_ctx):
    """Verify get_block_info returns structured data without transactions."""
    chain_id = "1"
    number_or_hash = "19000000"
    mock_base_url = "https://eth.blockscout.com"
    mock_api_response = {"height": 19000000, "timestamp": "2023-01-01T00:00:00Z"}

    with (
        patch(
            "blockscout_mcp_server.tools.block.get_block_info.get_blockscout_base_url", new_callable=AsyncMock
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.block.get_block_info.make_blockscout_request", new_callable=AsyncMock
        ) as mock_request,
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response

        result = await get_block_info(chain_id=chain_id, number_or_hash=number_or_hash, ctx=mock_ctx)

        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(base_url=mock_base_url, api_path=f"/api/v2/blocks/{number_or_hash}")
        assert isinstance(result, ToolResponse)
        assert isinstance(result.data, BlockInfoData)
        assert result.data.block_details == mock_api_response
        assert result.data.transaction_hashes is None
        assert result.notes is None
        assert mock_ctx.report_progress.await_count == 3
        assert mock_ctx.info.await_count == 3


@pytest.mark.asyncio
async def test_get_block_info_with_txs_success(mock_ctx):
    """Verify get_block_info returns structured data with a list of transaction hashes."""
    chain_id = "1"
    number_or_hash = "19000000"
    mock_base_url = "https://eth.blockscout.com"
    mock_block_response = {"height": 19000000, "transactions_count": 2}
    mock_txs_response = {"items": [{"hash": "0xtx1"}, {"hash": "0xtx2"}]}

    async def mock_request_side_effect(base_url, api_path, params=None):
        if "transactions" in api_path:
            return mock_txs_response
        return mock_block_response

    with (
        patch(
            "blockscout_mcp_server.tools.block.get_block_info.get_blockscout_base_url", new_callable=AsyncMock
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.block.get_block_info.make_blockscout_request", new_callable=AsyncMock
        ) as mock_request,
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.side_effect = mock_request_side_effect

        result = await get_block_info(
            chain_id=chain_id, number_or_hash=number_or_hash, include_transactions=True, ctx=mock_ctx
        )

        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_has_awaits(
            [
                call(base_url=mock_base_url, api_path=f"/api/v2/blocks/{number_or_hash}"),
                call(base_url=mock_base_url, api_path=f"/api/v2/blocks/{number_or_hash}/transactions"),
            ],
            any_order=True,
        )
        assert isinstance(result, ToolResponse)
        assert isinstance(result.data, BlockInfoData)
        assert result.data.block_details == mock_block_response
        assert result.data.transaction_hashes == ["0xtx1", "0xtx2"]
        assert result.notes is None
        assert mock_ctx.report_progress.await_count == 4
        assert mock_ctx.info.await_count == 4


@pytest.mark.asyncio
async def test_get_block_info_with_txs_partial_failure(mock_ctx):
    """Verify get_block_info handles failure when fetching transactions but not block info."""
    chain_id = "1"
    number_or_hash = "19000000"
    mock_base_url = "https://eth.blockscout.com"
    mock_block_response = {"height": 19000000}
    tx_error = httpx.HTTPStatusError("Server Error", request=MagicMock(), response=MagicMock(status_code=500))

    async def mock_request_side_effect(base_url, api_path, params=None):
        if "transactions" in api_path:
            raise tx_error
        return mock_block_response

    with (
        patch(
            "blockscout_mcp_server.tools.block.get_block_info.get_blockscout_base_url", new_callable=AsyncMock
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.block.get_block_info.make_blockscout_request", new_callable=AsyncMock
        ) as mock_request,
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.side_effect = mock_request_side_effect

        result = await get_block_info(
            chain_id=chain_id, number_or_hash=number_or_hash, include_transactions=True, ctx=mock_ctx
        )

        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_has_awaits(
            [
                call(base_url=mock_base_url, api_path=f"/api/v2/blocks/{number_or_hash}"),
                call(base_url=mock_base_url, api_path=f"/api/v2/blocks/{number_or_hash}/transactions"),
            ],
            any_order=True,
        )
        assert isinstance(result, ToolResponse)
        assert isinstance(result.data, BlockInfoData)
        assert result.data.block_details == mock_block_response
        assert result.data.transaction_hashes is None
        assert result.notes is not None
        assert "Could not retrieve the list of transactions" in result.notes[0]
        assert mock_ctx.report_progress.await_count == 4
        assert mock_ctx.info.await_count == 4


@pytest.mark.asyncio
async def test_get_block_info_total_failure(mock_ctx):
    """Verify get_block_info raises an exception if the main block call fails."""
    chain_id = "1"
    number_or_hash = "19000000"
    mock_base_url = "https://eth.blockscout.com"
    block_error = httpx.HTTPStatusError("Not Found", request=MagicMock(), response=MagicMock(status_code=404))

    async def mock_request_side_effect(base_url, api_path, params=None):
        if "transactions" in api_path:
            return {"items": []}
        raise block_error

    with (
        patch(
            "blockscout_mcp_server.tools.block.get_block_info.get_blockscout_base_url", new_callable=AsyncMock
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.block.get_block_info.make_blockscout_request", new_callable=AsyncMock
        ) as mock_request,
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.side_effect = mock_request_side_effect

        with pytest.raises(httpx.HTTPStatusError):
            await get_block_info(
                chain_id=chain_id, number_or_hash=number_or_hash, include_transactions=True, ctx=mock_ctx
            )
        assert mock_request.await_count == 2
        assert mock_ctx.report_progress.await_count == 3
        assert mock_ctx.info.await_count == 3
