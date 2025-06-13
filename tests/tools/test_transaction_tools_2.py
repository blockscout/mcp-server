# tests/tools/test_transaction_tools_2.py
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import httpx

from blockscout_mcp_server.tools.transaction_tools import get_transaction_info, get_transaction_logs

@pytest.mark.asyncio
async def test_get_transaction_info_success(mock_ctx):
    """
    Verify get_transaction_info correctly processes a successful transaction lookup.
    """
    # ARRANGE
    chain_id = "1"
    hash = "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
    mock_base_url = "https://eth.blockscout.com"

    mock_api_response = {
        "hash": hash,
        "block_number": 19000000,
        "block_hash": "0xblock123...",
        "from": "0xfrom123...",
        "to": "0xto123...",
        "value": "1000000000000000000",
        "gas_limit": "21000",
        "gas_used": "21000",
        "gas_price": "20000000000",
        "status": "ok",
        "timestamp": "2024-01-01T12:00:00.000000Z",
        "transaction_index": 42,
        "nonce": 123
    }

    with patch('blockscout_mcp_server.tools.transaction_tools.get_blockscout_base_url', new_callable=AsyncMock) as mock_get_url, \
         patch('blockscout_mcp_server.tools.transaction_tools.make_blockscout_request', new_callable=AsyncMock) as mock_request:

        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response

        # ACT
        result = await get_transaction_info(chain_id=chain_id, hash=hash, ctx=mock_ctx)

        # ASSERT
        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(
            base_url=mock_base_url,
            api_path=f"/api/v2/transactions/{hash}"
        )
        assert result == mock_api_response
        assert mock_ctx.report_progress.call_count == 3
        assert mock_ctx.info.call_count == 3

@pytest.mark.asyncio
async def test_get_transaction_info_not_found(mock_ctx):
    """
    Verify get_transaction_info correctly handles transaction not found errors.
    """
    # ARRANGE
    chain_id = "1"
    hash = "0xnonexistent1234567890abcdef1234567890abcdef1234567890abcdef123456"
    mock_base_url = "https://eth.blockscout.com"

    api_error = httpx.HTTPStatusError("Not Found", request=MagicMock(), response=MagicMock(status_code=404))

    with patch('blockscout_mcp_server.tools.transaction_tools.get_blockscout_base_url', new_callable=AsyncMock) as mock_get_url, \
         patch('blockscout_mcp_server.tools.transaction_tools.make_blockscout_request', new_callable=AsyncMock) as mock_request:

        mock_get_url.return_value = mock_base_url
        mock_request.side_effect = api_error

        # ACT & ASSERT
        with pytest.raises(httpx.HTTPStatusError):
            await get_transaction_info(chain_id=chain_id, hash=hash, ctx=mock_ctx)

        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(
            base_url=mock_base_url,
            api_path=f"/api/v2/transactions/{hash}"
        )

@pytest.mark.asyncio
async def test_get_transaction_info_chain_not_found(mock_ctx):
    """
    Verify get_transaction_info correctly handles chain not found errors.
    """
    # ARRANGE
    chain_id = "999999"
    hash = "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"

    from blockscout_mcp_server.tools.common import ChainNotFoundError
    chain_error = ChainNotFoundError(f"Chain with ID '{chain_id}' not found on Chainscout.")

    with patch('blockscout_mcp_server.tools.transaction_tools.get_blockscout_base_url', new_callable=AsyncMock) as mock_get_url:
        mock_get_url.side_effect = chain_error

        # ACT & ASSERT
        with pytest.raises(ChainNotFoundError):
            await get_transaction_info(chain_id=chain_id, hash=hash, ctx=mock_ctx)

        mock_get_url.assert_called_once_with(chain_id)

@pytest.mark.asyncio
async def test_get_transaction_info_minimal_response(mock_ctx):
    """
    Verify get_transaction_info handles minimal transaction response.
    """
    # ARRANGE
    chain_id = "1"
    hash = "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
    mock_base_url = "https://eth.blockscout.com"

    mock_api_response = {
        "hash": hash,
        "status": "pending"
        # Minimal response with most fields missing
    }

    with patch('blockscout_mcp_server.tools.transaction_tools.get_blockscout_base_url', new_callable=AsyncMock) as mock_get_url, \
         patch('blockscout_mcp_server.tools.transaction_tools.make_blockscout_request', new_callable=AsyncMock) as mock_request:

        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response

        # ACT
        result = await get_transaction_info(chain_id=chain_id, hash=hash, ctx=mock_ctx)

        # ASSERT
        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(
            base_url=mock_base_url,
            api_path=f"/api/v2/transactions/{hash}"
        )
        assert result == mock_api_response
        assert result["hash"] == hash
        assert result["status"] == "pending"
        assert mock_ctx.report_progress.call_count == 3
        assert mock_ctx.info.call_count == 3

@pytest.mark.asyncio
async def test_get_transaction_logs_success(mock_ctx):
    """
    Verify get_transaction_logs correctly processes and formats transaction logs.
    """
    # ARRANGE
    chain_id = "1"
    hash = "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
    mock_base_url = "https://eth.blockscout.com"

    mock_api_response = {
        "items": [
            {
                "address": {"hash": "0xcontract1..."},
                "topics": ["0xtopic1...", "0xtopic2..."],
                "data": "0xdata123...",
                "log_index": "0",
                "transaction_hash": hash,
                "block_number": 19000000,
                "block_hash": "0xblockhash1...",
                "decoded": {"name": "EventA"},
                "smart_contract": None,
                "index": 0,
            },
            {
                "address": {"hash": "0xcontract2..."},
                "topics": ["0xtopic3..."],
                "data": "0xdata456...",
                "log_index": "1",
                "transaction_hash": hash,
                "block_number": 19000000,
                "block_hash": "0xblockhash2...",
                "decoded": {"name": "EventB"},
                "smart_contract": None,
                "index": 1,
            }
        ],
        "next_page_params": None,
    }

    expected_transformed_response = {
        "items": [
            {
                "address": "0xcontract1...",
                "block_number": 19000000,
                "data": "0xdata123...",
                "decoded": {"name": "EventA"},
                "index": 0,
                "smart_contract": None,
                "topics": ["0xtopic1...", "0xtopic2..."],
            },
            {
                "address": "0xcontract2...",
                "block_number": 19000000,
                "data": "0xdata456...",
                "decoded": {"name": "EventB"},
                "index": 1,
                "smart_contract": None,
                "topics": ["0xtopic3..."],
            },
        ],
        "next_page_params": None,
    }

    # Patch json.dumps in the transaction_tools module
    with patch('blockscout_mcp_server.tools.transaction_tools.get_blockscout_base_url', new_callable=AsyncMock) as mock_get_url, \
         patch('blockscout_mcp_server.tools.transaction_tools.make_blockscout_request', new_callable=AsyncMock) as mock_request, \
         patch('blockscout_mcp_server.tools.transaction_tools.json.dumps') as mock_json_dumps:

        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response
        # We don't care what json.dumps returns, only that it's called correctly
        mock_json_dumps.return_value = "{...}"

        # ACT
        result = await get_transaction_logs(chain_id=chain_id, hash=hash, ctx=mock_ctx)

        # ASSERT
        # Assert that json.dumps was called with the transformed data
        mock_json_dumps.assert_called_once_with(expected_transformed_response)

        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(
            base_url=mock_base_url,
            api_path=f"/api/v2/transactions/{hash}/logs"
        )
        
        # Verify the result starts with the expected prefix
        expected_prefix = "**Items Structure:**"
        assert result.startswith(expected_prefix)

        assert mock_ctx.report_progress.call_count == 3
        assert mock_ctx.info.call_count == 3

@pytest.mark.asyncio
async def test_get_transaction_info_removes_raw_input_by_default(mock_ctx):
    """Verify raw_input is removed by default when decoded_input is present."""
    # ARRANGE
    chain_id = "1"
    tx_hash = "0x123"
    mock_base_url = "https://eth.blockscout.com"
    mock_api_response = {
        "hash": tx_hash,
        "decoded_input": {"method_call": "transfer(...)"},
        "raw_input": "0xverylongstring"
    }

    with patch('blockscout_mcp_server.tools.transaction_tools.get_blockscout_base_url', new_callable=AsyncMock) as mock_get_url, \
         patch('blockscout_mcp_server.tools.transaction_tools.make_blockscout_request', new_callable=AsyncMock) as mock_request:

        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response.copy()

        # ACT
        result = await get_transaction_info(chain_id=chain_id, hash=tx_hash, ctx=mock_ctx)

        # ASSERT
        assert "raw_input" not in result
        assert "decoded_input" in result

@pytest.mark.asyncio
async def test_get_transaction_info_keeps_raw_input_when_flagged(mock_ctx):
    """Verify raw_input is kept when include_raw_input is True."""
    # ARRANGE
    chain_id = "1"
    tx_hash = "0x123"
    mock_base_url = "https://eth.blockscout.com"
    mock_api_response = {
        "hash": tx_hash,
        "decoded_input": {"method_call": "transfer(...)"},
        "raw_input": "0xverylongstring"
    }

    with patch('blockscout_mcp_server.tools.transaction_tools.get_blockscout_base_url', new_callable=AsyncMock) as mock_get_url, \
         patch('blockscout_mcp_server.tools.transaction_tools.make_blockscout_request', new_callable=AsyncMock) as mock_request:

        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response.copy()

        # ACT
        result = await get_transaction_info(chain_id=chain_id, hash=tx_hash, ctx=mock_ctx, include_raw_input=True)

        # ASSERT
        assert "raw_input" in result
        assert result["raw_input"] == "0xverylongstring"

@pytest.mark.asyncio
async def test_get_transaction_info_keeps_raw_input_if_no_decoded(mock_ctx):
    """Verify raw_input is kept by default if decoded_input is null."""
    # ARRANGE
    chain_id = "1"
    tx_hash = "0x123"
    mock_base_url = "https://eth.blockscout.com"
    mock_api_response = {
        "hash": tx_hash,
        "decoded_input": None,
        "raw_input": "0xverylongstring"
    }

    with patch('blockscout_mcp_server.tools.transaction_tools.get_blockscout_base_url', new_callable=AsyncMock) as mock_get_url, \
         patch('blockscout_mcp_server.tools.transaction_tools.make_blockscout_request', new_callable=AsyncMock) as mock_request:

        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response.copy()

        # ACT
        result = await get_transaction_info(chain_id=chain_id, hash=tx_hash, ctx=mock_ctx)

        # ASSERT
        assert "raw_input" in result
        assert result["raw_input"] == "0xverylongstring"

@pytest.mark.asyncio
async def test_get_transaction_logs_empty_logs(mock_ctx):
    """
    Verify get_transaction_logs handles transactions with no logs.
    """
    # ARRANGE
    chain_id = "1"
    hash = "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
    mock_base_url = "https://eth.blockscout.com"

    mock_api_response = {"items": []}

    expected_transformed_response = {
        "items": [],
        "next_page_params": None,
    }

    # Patch json.dumps directly since it's imported locally in the function
    with patch('blockscout_mcp_server.tools.transaction_tools.get_blockscout_base_url', new_callable=AsyncMock) as mock_get_url, \
         patch('blockscout_mcp_server.tools.transaction_tools.make_blockscout_request', new_callable=AsyncMock) as mock_request, \
         patch('blockscout_mcp_server.tools.transaction_tools.json.dumps') as mock_json_dumps:

        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response
        # We don't care what json.dumps returns, only that it's called correctly
        mock_json_dumps.return_value = "{...}"

        # ACT
        result = await get_transaction_logs(chain_id=chain_id, hash=hash, ctx=mock_ctx)

        # ASSERT
        # Assert that json.dumps was called with the transformed data
        mock_json_dumps.assert_called_once_with(expected_transformed_response)

        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(
            base_url=mock_base_url,
            api_path=f"/api/v2/transactions/{hash}/logs"
        )
        
        # Verify the result structure
        assert result.startswith("**Items Structure:**")

        assert mock_ctx.report_progress.call_count == 3
        assert mock_ctx.info.call_count == 3

@pytest.mark.asyncio
async def test_get_transaction_logs_api_error(mock_ctx):
    """
    Verify get_transaction_logs correctly propagates API errors.
    """
    # ARRANGE
    chain_id = "1"
    hash = "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
    mock_base_url = "https://eth.blockscout.com"

    api_error = httpx.HTTPStatusError("Internal Server Error", request=MagicMock(), response=MagicMock(status_code=500))

    with patch('blockscout_mcp_server.tools.transaction_tools.get_blockscout_base_url', new_callable=AsyncMock) as mock_get_url, \
         patch('blockscout_mcp_server.tools.transaction_tools.make_blockscout_request', new_callable=AsyncMock) as mock_request:

        mock_get_url.return_value = mock_base_url
        mock_request.side_effect = api_error

        # ACT & ASSERT
        with pytest.raises(httpx.HTTPStatusError):
            await get_transaction_logs(chain_id=chain_id, hash=hash, ctx=mock_ctx)

        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(
            base_url=mock_base_url,
            api_path=f"/api/v2/transactions/{hash}/logs"
        )

@pytest.mark.asyncio
async def test_get_transaction_logs_complex_logs(mock_ctx):
    """
    Verify get_transaction_logs handles complex log structures correctly.
    """
    # ARRANGE
    chain_id = "1"
    hash = "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
    mock_base_url = "https://eth.blockscout.com"

    mock_api_response = {
        "items": [
            {
                "address": {"hash": "0xa0b86a33e6dd0ba3c70de3b8e2b9e48cd6efb7b0"},
                "topics": [
                    "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef",
                    "0x000000000000000000000000d8da6bf26964af9d7eed9e03e53415d37aa96045",
                    "0x000000000000000000000000f81c1a7e8d3c1a1d3c1a1d3c1a1d3c1a1d3c1a1d"
                ],
                "data": "0x0000000000000000000000000000000000000000000000000de0b6b3a7640000",
                "log_index": "42",
                "transaction_hash": hash,
                "block_number": 19000000,
                "block_hash": "0xblock123...",
                "transaction_index": 10,
                "removed": False,
                "decoded": {"name": "Transfer"},
                "smart_contract": None,
                "index": 42,
            }
        ],
        "next_page_params": None
    }

    expected_transformed_response = {
        "items": [
            {
                "address": "0xa0b86a33e6dd0ba3c70de3b8e2b9e48cd6efb7b0",
                "block_number": 19000000,
                "data": "0x0000000000000000000000000000000000000000000000000de0b6b3a7640000",
                "decoded": {"name": "Transfer"},
                "index": 42,
                "smart_contract": None,
                "topics": [
                    "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef",
                    "0x000000000000000000000000d8da6bf26964af9d7eed9e03e53415d37aa96045",
                    "0x000000000000000000000000f81c1a7e8d3c1a1d3c1a1d3c1a1d3c1a1d3c1a1d"
                ],
            }
        ],
        "next_page_params": None
    }

    # Patch json.dumps directly since it's imported locally in the function
    with patch('blockscout_mcp_server.tools.transaction_tools.get_blockscout_base_url', new_callable=AsyncMock) as mock_get_url, \
         patch('blockscout_mcp_server.tools.transaction_tools.make_blockscout_request', new_callable=AsyncMock) as mock_request, \
         patch('blockscout_mcp_server.tools.transaction_tools.json.dumps') as mock_json_dumps:

        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response
        # We don't care what json.dumps returns, only that it's called correctly
        mock_json_dumps.return_value = "{...}"

        # ACT
        result = await get_transaction_logs(chain_id=chain_id, hash=hash, ctx=mock_ctx)

        # ASSERT
        # Assert that json.dumps was called with the transformed data
        mock_json_dumps.assert_called_once_with(expected_transformed_response)

        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(
            base_url=mock_base_url,
            api_path=f"/api/v2/transactions/{hash}/logs"
        )
        
        # Verify the result starts with the expected prefix
        expected_prefix = "**Items Structure:**"
        assert result.startswith(expected_prefix)
        
        assert mock_ctx.report_progress.call_count == 3 
