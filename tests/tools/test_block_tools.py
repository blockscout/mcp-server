# tests/tools/test_block_tools.py
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from blockscout_mcp_server.models import BlockInfoData, LatestBlockData, ToolResponse
from blockscout_mcp_server.tools.block_tools import get_block_info, get_latest_block


@pytest.mark.asyncio
async def test_get_latest_block_success(mock_ctx):
    """
    Verify get_latest_block works correctly on a successful API call.
    """
    # ARRANGE
    chain_id = "1"
    mock_base_url = "https://eth.blockscout.com"

    # Mock API response is a list of blocks
    mock_api_response = [{"height": 12345, "timestamp": "2023-01-01T00:00:00Z"}]

    # Patch both helpers used by the tool
    with (
        patch(
            "blockscout_mcp_server.tools.block_tools.get_blockscout_base_url", new_callable=AsyncMock
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.block_tools.make_blockscout_request", new_callable=AsyncMock
        ) as mock_request,
    ):
        # Configure the mocks
        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response

        # ACT
        result = await get_latest_block(chain_id=chain_id, ctx=mock_ctx)

        # ASSERT
        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(base_url=mock_base_url, api_path="/api/v2/main-page/blocks")
        assert isinstance(result, ToolResponse)
        assert isinstance(result.data, LatestBlockData)
        assert result.data.block_number == 12345
        assert result.data.timestamp == "2023-01-01T00:00:00Z"
        assert mock_ctx.report_progress.call_count == 3
        assert mock_ctx.info.call_count == 3


@pytest.mark.asyncio
async def test_get_latest_block_api_error(mock_ctx):
    """
    Verify the tool correctly propagates an exception when the API call fails.
    """
    # ARRANGE
    chain_id = "1"
    mock_base_url = "https://eth.blockscout.com"

    # We'll simulate a 404 Not Found error from the API
    api_error = httpx.HTTPStatusError("Not Found", request=MagicMock(), response=MagicMock(status_code=404))

    with (
        patch(
            "blockscout_mcp_server.tools.block_tools.get_blockscout_base_url", new_callable=AsyncMock
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.block_tools.make_blockscout_request", new_callable=AsyncMock
        ) as mock_request,
    ):
        mock_get_url.return_value = mock_base_url
        # Configure the mock to raise the error instead of returning a value
        mock_request.side_effect = api_error

        # ACT & ASSERT
        # Use pytest.raises to assert that the specific exception is raised.
        with pytest.raises(httpx.HTTPStatusError):
            await get_latest_block(chain_id=chain_id, ctx=mock_ctx)

        # Verify mocks were still called as expected before the exception
        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(base_url=mock_base_url, api_path="/api/v2/main-page/blocks")


@pytest.mark.asyncio
async def test_get_latest_block_empty_response(mock_ctx):
    """
    Verify get_latest_block handles empty API responses gracefully.
    """
    # ARRANGE
    chain_id = "1"
    mock_base_url = "https://eth.blockscout.com"

    # Empty response
    mock_api_response = []

    with (
        patch(
            "blockscout_mcp_server.tools.block_tools.get_blockscout_base_url", new_callable=AsyncMock
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.block_tools.make_blockscout_request", new_callable=AsyncMock
        ) as mock_request,
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response

        # ACT & ASSERT
        with pytest.raises(ValueError, match="Could not retrieve latest block data from the API."):
            await get_latest_block(chain_id=chain_id, ctx=mock_ctx)

        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(base_url=mock_base_url, api_path="/api/v2/main-page/blocks")


@pytest.mark.asyncio
async def test_get_latest_block_chain_not_found_error(mock_ctx):
    """
    Verify the tool correctly propagates ChainNotFoundError when chain lookup fails.
    """
    # ARRANGE
    chain_id = "999999"  # Invalid chain ID

    # Import the custom exception
    from blockscout_mcp_server.tools.common import ChainNotFoundError

    chain_error = ChainNotFoundError(f"Chain with ID '{chain_id}' not found on Chainscout.")

    with patch(
        "blockscout_mcp_server.tools.block_tools.get_blockscout_base_url", new_callable=AsyncMock
    ) as mock_get_url:
        # Configure the mock to raise the chain error
        mock_get_url.side_effect = chain_error

        # ACT & ASSERT
        with pytest.raises(ChainNotFoundError):
            await get_latest_block(chain_id=chain_id, ctx=mock_ctx)

        # Verify the chain lookup was attempted
        mock_get_url.assert_called_once_with(chain_id)
        # Progress should have been reported once (at start) before the error
        assert mock_ctx.report_progress.call_count == 1
        assert mock_ctx.info.call_count == 1


@pytest.mark.asyncio
async def test_get_block_info_success_no_txs(mock_ctx):
    """Verify get_block_info returns structured data without transactions."""
    chain_id = "1"
    number_or_hash = "19000000"
    mock_base_url = "https://eth.blockscout.com"
    mock_api_response = {"height": 19000000, "timestamp": "2023-01-01T00:00:00Z"}

    with (
        patch(
            "blockscout_mcp_server.tools.block_tools.get_blockscout_base_url", new_callable=AsyncMock
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.block_tools.make_blockscout_request", new_callable=AsyncMock
        ) as mock_request,
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response

        result = await get_block_info(chain_id=chain_id, number_or_hash=number_or_hash, ctx=mock_ctx)

        mock_request.assert_called_once_with(base_url=mock_base_url, api_path=f"/api/v2/blocks/{number_or_hash}")
        assert isinstance(result, ToolResponse)
        assert isinstance(result.data, BlockInfoData)
        assert result.data.block_details == mock_api_response
        assert result.data.transaction_hashes is None
        assert result.notes is None


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
            "blockscout_mcp_server.tools.block_tools.get_blockscout_base_url", new_callable=AsyncMock
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.block_tools.make_blockscout_request", new_callable=AsyncMock
        ) as mock_request,
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.side_effect = mock_request_side_effect

        result = await get_block_info(
            chain_id=chain_id, number_or_hash=number_or_hash, include_transactions=True, ctx=mock_ctx
        )

        assert isinstance(result, ToolResponse)
        assert isinstance(result.data, BlockInfoData)
        assert result.data.block_details == mock_block_response
        assert result.data.transaction_hashes == ["0xtx1", "0xtx2"]
        assert result.notes is None


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
            "blockscout_mcp_server.tools.block_tools.get_blockscout_base_url", new_callable=AsyncMock
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.block_tools.make_blockscout_request", new_callable=AsyncMock
        ) as mock_request,
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.side_effect = mock_request_side_effect

        result = await get_block_info(
            chain_id=chain_id, number_or_hash=number_or_hash, include_transactions=True, ctx=mock_ctx
        )

        assert isinstance(result, ToolResponse)
        assert isinstance(result.data, BlockInfoData)
        assert result.data.block_details == mock_block_response
        assert result.data.transaction_hashes is None
        assert result.notes is not None
        assert "Could not retrieve the list of transactions" in result.notes[0]


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
            "blockscout_mcp_server.tools.block_tools.get_blockscout_base_url", new_callable=AsyncMock
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.block_tools.make_blockscout_request", new_callable=AsyncMock
        ) as mock_request,
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.side_effect = mock_request_side_effect

        with pytest.raises(httpx.HTTPStatusError):
            await get_block_info(
                chain_id=chain_id, number_or_hash=number_or_hash, include_transactions=True, ctx=mock_ctx
            )
