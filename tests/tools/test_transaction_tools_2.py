# tests/tools/test_transaction_tools_2.py
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import httpx
import json

from blockscout_mcp_server.tools.transaction_tools import get_transaction_info, get_transaction_logs

@pytest.mark.asyncio
async def test_get_transaction_info_success():
    """
    Verify get_transaction_info correctly processes a successful transaction lookup.
    """
    # ARRANGE
    mock_ctx = MagicMock()
    mock_ctx.report_progress = AsyncMock()
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

@pytest.mark.asyncio
async def test_get_transaction_info_not_found():
    """
    Verify get_transaction_info correctly handles transaction not found errors.
    """
    # ARRANGE
    mock_ctx = MagicMock()
    mock_ctx.report_progress = AsyncMock()
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
async def test_get_transaction_info_chain_not_found():
    """
    Verify get_transaction_info correctly handles chain not found errors.
    """
    # ARRANGE
    mock_ctx = MagicMock()
    mock_ctx.report_progress = AsyncMock()
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
async def test_get_transaction_info_minimal_response():
    """
    Verify get_transaction_info handles minimal transaction response.
    """
    # ARRANGE
    mock_ctx = MagicMock()
    mock_ctx.report_progress = AsyncMock()
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

@pytest.mark.asyncio
async def test_get_transaction_logs_success():
    """
    Verify get_transaction_logs correctly processes and formats transaction logs.
    """
    # ARRANGE
    mock_ctx = MagicMock()
    mock_ctx.report_progress = AsyncMock()
    chain_id = "1"
    hash = "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
    mock_base_url = "https://eth.blockscout.com"

    mock_api_response = {
        "items": [
            {
                "address": "0xcontract1...",
                "topics": ["0xtopic1...", "0xtopic2..."],
                "data": "0xdata123...",
                "log_index": "0",
                "transaction_hash": hash,
                "block_number": 19000000
            },
            {
                "address": "0xcontract2...",
                "topics": ["0xtopic3..."],
                "data": "0xdata456...",
                "log_index": "1",
                "transaction_hash": hash,
                "block_number": 19000000
            }
        ]
    }

    with patch('blockscout_mcp_server.tools.transaction_tools.get_blockscout_base_url', new_callable=AsyncMock) as mock_get_url, \
         patch('blockscout_mcp_server.tools.transaction_tools.make_blockscout_request', new_callable=AsyncMock) as mock_request:

        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response

        # ACT
        result = await get_transaction_logs(chain_id=chain_id, hash=hash, ctx=mock_ctx)

        # ASSERT
        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(
            base_url=mock_base_url,
            api_path=f"/api/v2/transactions/{hash}/logs"
        )
        
        # Verify the result starts with the expected prefix
        expected_prefix = "**Items Structure:**"
        assert result.startswith(expected_prefix)
        
        # Verify the JSON content is included
        assert '"address": "0xcontract1..."' in result
        assert '"0xtopic1..."' in result
        assert '"0xtopic2..."' in result
        assert '"data": "0xdata123..."' in result
        assert '"log_index": "0"' in result
        
        assert '"address": "0xcontract2..."' in result
        assert '"0xtopic3..."' in result
        assert '"data": "0xdata456..."' in result
        assert '"log_index": "1"' in result
        
        # Check that the JSON is properly formatted
        json_content = result.split("**Transaction logs JSON:**\n")[1]
        parsed_json = json.loads(json_content)
        assert parsed_json == mock_api_response
        
        assert mock_ctx.report_progress.call_count == 3

@pytest.mark.asyncio
async def test_get_transaction_logs_empty_logs():
    """
    Verify get_transaction_logs handles transactions with no logs.
    """
    # ARRANGE
    mock_ctx = MagicMock()
    mock_ctx.report_progress = AsyncMock()
    chain_id = "1"
    hash = "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
    mock_base_url = "https://eth.blockscout.com"

    mock_api_response = {"items": []}

    with patch('blockscout_mcp_server.tools.transaction_tools.get_blockscout_base_url', new_callable=AsyncMock) as mock_get_url, \
         patch('blockscout_mcp_server.tools.transaction_tools.make_blockscout_request', new_callable=AsyncMock) as mock_request:

        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response

        # ACT
        result = await get_transaction_logs(chain_id=chain_id, hash=hash, ctx=mock_ctx)

        # ASSERT
        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(
            base_url=mock_base_url,
            api_path=f"/api/v2/transactions/{hash}/logs"
        )
        
        # Verify the result structure
        assert result.startswith("**Items Structure:**")
        assert '"items": []' in result
        
        # Verify we can parse the JSON part
        json_content = result.split("**Transaction logs JSON:**\n")[1]
        parsed_json = json.loads(json_content)
        assert parsed_json == mock_api_response
        
        assert mock_ctx.report_progress.call_count == 3

@pytest.mark.asyncio
async def test_get_transaction_logs_api_error():
    """
    Verify get_transaction_logs correctly propagates API errors.
    """
    # ARRANGE
    mock_ctx = MagicMock()
    mock_ctx.report_progress = AsyncMock()
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
async def test_get_transaction_logs_complex_logs():
    """
    Verify get_transaction_logs handles complex log structures correctly.
    """
    # ARRANGE
    mock_ctx = MagicMock()
    mock_ctx.report_progress = AsyncMock()
    chain_id = "1"
    hash = "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
    mock_base_url = "https://eth.blockscout.com"

    mock_api_response = {
        "items": [
            {
                "address": "0xa0b86a33e6dd0ba3c70de3b8e2b9e48cd6efb7b0",
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
                "removed": False
            }
        ],
        "next_page_params": None
    }

    with patch('blockscout_mcp_server.tools.transaction_tools.get_blockscout_base_url', new_callable=AsyncMock) as mock_get_url, \
         patch('blockscout_mcp_server.tools.transaction_tools.make_blockscout_request', new_callable=AsyncMock) as mock_request:

        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response

        # ACT
        result = await get_transaction_logs(chain_id=chain_id, hash=hash, ctx=mock_ctx)

        # ASSERT
        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(
            base_url=mock_base_url,
            api_path=f"/api/v2/transactions/{hash}/logs"
        )
        
        # Verify complex fields are included
        assert "0xa0b86a33e6dd0ba3c70de3b8e2b9e48cd6efb7b0" in result
        assert "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef" in result
        assert '"log_index": "42"' in result
        assert '"block_number": 19000000' in result
        assert '"removed": false' in result
        
        # Verify JSON structure
        json_content = result.split("**Transaction logs JSON:**\n")[1]
        parsed_json = json.loads(json_content)
        assert parsed_json == mock_api_response
        
        assert mock_ctx.report_progress.call_count == 3 