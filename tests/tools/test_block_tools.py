# tests/tools/test_block_tools.py
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import httpx
import json

from blockscout_mcp_server.tools.block_tools import get_latest_block, get_block_info

@pytest.mark.asyncio
async def test_get_latest_block_success(mock_ctx):
    """
    Verify get_latest_block works correctly on a successful API call.
    """
    # ARRANGE
    chain_id = "1"
    mock_base_url = "https://eth.blockscout.com"

    # Mock API response is a list of blocks
    mock_api_response = [
        {"height": 12345, "timestamp": "2023-01-01T00:00:00Z"}
    ]
    expected_result = {
        "block_number": 12345,
        "timestamp": "2023-01-01T00:00:00Z"
    }

    # Patch both helpers used by the tool
    with patch('blockscout_mcp_server.tools.block_tools.get_blockscout_base_url', new_callable=AsyncMock) as mock_get_url, \
         patch('blockscout_mcp_server.tools.block_tools.make_blockscout_request', new_callable=AsyncMock) as mock_request:

        # Configure the mocks
        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response

        # ACT
        result = await get_latest_block(chain_id=chain_id, ctx=mock_ctx)

        # ASSERT
        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(base_url=mock_base_url, api_path="/api/v2/main-page/blocks")
        assert result == expected_result
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

    with patch('blockscout_mcp_server.tools.block_tools.get_blockscout_base_url', new_callable=AsyncMock) as mock_get_url, \
         patch('blockscout_mcp_server.tools.block_tools.make_blockscout_request', new_callable=AsyncMock) as mock_request:

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
    expected_result = {
        "block_number": None,
        "timestamp": None
    }

    with patch('blockscout_mcp_server.tools.block_tools.get_blockscout_base_url', new_callable=AsyncMock) as mock_get_url, \
         patch('blockscout_mcp_server.tools.block_tools.make_blockscout_request', new_callable=AsyncMock) as mock_request:

        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response

        # ACT
        result = await get_latest_block(chain_id=chain_id, ctx=mock_ctx)

        # ASSERT
        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(base_url=mock_base_url, api_path="/api/v2/main-page/blocks")
        assert result == expected_result
        assert mock_ctx.report_progress.call_count == 3

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

    with patch('blockscout_mcp_server.tools.block_tools.get_blockscout_base_url', new_callable=AsyncMock) as mock_get_url:
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
async def test_get_block_info_success(mock_ctx):
    """
    Verify get_block_info works correctly with parameters.
    """
    # ARRANGE
    chain_id = "1"
    number_or_hash = "19000000"
    mock_base_url = "https://eth.blockscout.com"

    # Mock API response - complete block info
    mock_api_response = {
        "height": 19000000,
        "timestamp": "2023-01-01T00:00:00Z",
        "gas_used": "12345678",
        "gas_limit": "30000000",
        "transaction_count": 150
    }

    with patch('blockscout_mcp_server.tools.block_tools.get_blockscout_base_url', new_callable=AsyncMock) as mock_get_url, \
         patch('blockscout_mcp_server.tools.block_tools.make_blockscout_request', new_callable=AsyncMock) as mock_request:

        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response

        # ACT
        result = await get_block_info(chain_id=chain_id, number_or_hash=number_or_hash, ctx=mock_ctx)

        # ASSERT
        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(base_url=mock_base_url, api_path=f"/api/v2/blocks/{number_or_hash}")
        expected_output = f"Basic block info:\n{json.dumps(mock_api_response)}"
        assert result == expected_output
        assert mock_ctx.report_progress.call_count == 3
        assert mock_ctx.info.call_count == 3

@pytest.mark.asyncio
async def test_get_block_info_with_hash(mock_ctx):
    """
    Verify get_block_info works correctly when given a block hash instead of number.
    """
    # ARRANGE
    chain_id = "1"
    block_hash = "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
    mock_base_url = "https://eth.blockscout.com"

    mock_api_response = {
        "hash": block_hash,
        "height": 19000000,
        "timestamp": "2023-01-01T00:00:00Z"
    }

    with patch('blockscout_mcp_server.tools.block_tools.get_blockscout_base_url', new_callable=AsyncMock) as mock_get_url, \
         patch('blockscout_mcp_server.tools.block_tools.make_blockscout_request', new_callable=AsyncMock) as mock_request:

        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response

        # ACT
        result = await get_block_info(chain_id=chain_id, number_or_hash=block_hash, ctx=mock_ctx)

        # ASSERT
        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(base_url=mock_base_url, api_path=f"/api/v2/blocks/{block_hash}")
        expected_output = f"Basic block info:\n{json.dumps(mock_api_response)}"
        assert result == expected_output
        assert mock_ctx.report_progress.call_count == 3
        assert mock_ctx.info.call_count == 3

@pytest.mark.asyncio
async def test_get_block_info_api_error(mock_ctx):
    """
    Verify get_block_info correctly propagates API errors.
    """
    # ARRANGE
    chain_id = "1"
    number_or_hash = "999999999"  # Probably non-existent block
    mock_base_url = "https://eth.blockscout.com"

    # Simulate a 404 error for non-existent block
    api_error = httpx.HTTPStatusError("Not Found", request=MagicMock(), response=MagicMock(status_code=404))

    with patch('blockscout_mcp_server.tools.block_tools.get_blockscout_base_url', new_callable=AsyncMock) as mock_get_url, \
         patch('blockscout_mcp_server.tools.block_tools.make_blockscout_request', new_callable=AsyncMock) as mock_request:

        mock_get_url.return_value = mock_base_url
        mock_request.side_effect = api_error

        # ACT & ASSERT
        with pytest.raises(httpx.HTTPStatusError):
            await get_block_info(chain_id=chain_id, number_or_hash=number_or_hash, ctx=mock_ctx)

        # Verify mocks were called as expected before the exception
        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(base_url=mock_base_url, api_path=f"/api/v2/blocks/{number_or_hash}")
        # Progress should have been reported twice (start + after chain URL resolution) before the error
        assert mock_ctx.report_progress.call_count == 2
        assert mock_ctx.info.call_count == 2


@pytest.mark.asyncio
async def test_get_block_info_with_transactions_success(mock_ctx):
    """
    Verify get_block_info correctly fetches and formats block info with transaction hashes.
    """
    # ARRANGE
    chain_id = "1"
    number_or_hash = "19000000"
    mock_base_url = "https://eth.blockscout.com"

    mock_block_response = {"height": 19000000, "transaction_count": 2}
    mock_txs_response = {"items": [{"hash": "0xtx1"}, {"hash": "0xtx2"}]}

    async def mock_request_side_effect(base_url, api_path, params=None):
        if "transactions" in api_path:
            return mock_txs_response
        else:
            return mock_block_response

    with patch('blockscout_mcp_server.tools.block_tools.get_blockscout_base_url', new_callable=AsyncMock) as mock_get_url, \
         patch('blockscout_mcp_server.tools.block_tools.make_blockscout_request', new_callable=AsyncMock) as mock_request:

        mock_get_url.return_value = mock_base_url
        mock_request.side_effect = mock_request_side_effect

        # ACT
        result = await get_block_info(chain_id=chain_id, number_or_hash=number_or_hash, include_transactions=True, ctx=mock_ctx)

        # ASSERT
        assert mock_get_url.call_count == 1
        assert mock_request.call_count == 2

        assert "Basic block info:" in result
        assert json.dumps(mock_block_response) in result
        assert "Transactions in the block:" in result
        assert json.dumps(["0xtx1", "0xtx2"]) in result
        assert "No transactions in the block." not in result
        assert mock_ctx.report_progress.call_count == 4
        assert mock_ctx.info.call_count == 4


@pytest.mark.asyncio
async def test_get_block_info_with_no_transactions(mock_ctx):
    """
    Verify get_block_info correctly handles a block with no transactions when requested.
    """
    # ARRANGE
    chain_id = "1"
    number_or_hash = "19000001"
    mock_base_url = "https://eth.blockscout.com"

    mock_block_response = {"height": 19000001, "transaction_count": 0}
    mock_txs_response = {"items": []}

    async def mock_request_side_effect(base_url, api_path, params=None):
        if "transactions" in api_path:
            return mock_txs_response
        else:
            return mock_block_response

    with patch('blockscout_mcp_server.tools.block_tools.get_blockscout_base_url', new_callable=AsyncMock) as mock_get_url, \
         patch('blockscout_mcp_server.tools.block_tools.make_blockscout_request', new_callable=AsyncMock) as mock_request:

        mock_get_url.return_value = mock_base_url
        mock_request.side_effect = mock_request_side_effect

        # ACT
        result = await get_block_info(chain_id=chain_id, number_or_hash=number_or_hash, include_transactions=True, ctx=mock_ctx)

        # ASSERT
        assert "Basic block info:" in result
        assert json.dumps(mock_block_response) in result
        assert "No transactions in the block." in result
        assert "Transactions in the block:" not in result
        assert mock_ctx.report_progress.call_count == 4


@pytest.mark.asyncio
async def test_get_block_info_with_transactions_api_error(mock_ctx):
    """
    Verify get_block_info handles an error when fetching transactions but not block info.
    """
    # ARRANGE
    chain_id = "1"
    number_or_hash = "19000000"
    mock_base_url = "https://eth.blockscout.com"
    mock_block_response = {"height": 19000000}
    tx_error = httpx.HTTPStatusError("Server Error", request=MagicMock(), response=MagicMock(status_code=500))

    async def mock_request_side_effect(base_url, api_path, params=None):
        if "transactions" in api_path:
            raise tx_error
        else:
            return mock_block_response

    with patch('blockscout_mcp_server.tools.block_tools.get_blockscout_base_url', new_callable=AsyncMock) as mock_get_url, \
         patch('blockscout_mcp_server.tools.block_tools.make_blockscout_request', new_callable=AsyncMock) as mock_request:

        mock_get_url.return_value = mock_base_url
        mock_request.side_effect = mock_request_side_effect

        # ACT
        result = await get_block_info(chain_id=chain_id, number_or_hash=number_or_hash, include_transactions=True, ctx=mock_ctx)

        # ASSERT
        assert "Basic block info:" in result
        assert json.dumps(mock_block_response) in result
        assert "Error fetching transactions for the block:" in result
        assert str(tx_error) in result
