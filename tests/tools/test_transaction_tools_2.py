# tests/tools/test_transaction_tools_2.py
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import httpx

from blockscout_mcp_server.tools.transaction_tools import get_transaction_info, get_transaction_logs
from blockscout_mcp_server.tools.common import encode_cursor
import json
from blockscout_mcp_server.constants import INPUT_DATA_TRUNCATION_LIMIT

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
        "from": {"hash": "0xfrom123..."},
        "to": {"hash": "0xto123..."},
        "value": "1000000000000000000",
        "gas_limit": "21000",
        "gas_used": "21000",
        "gas_price": "20000000000",
        "status": "ok",
        "timestamp": "2024-01-01T12:00:00.000000Z",
        "transaction_index": 42,
        "nonce": 123
    }

    expected_transformed_result = {
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
        "nonce": 123,
    }

    with patch('blockscout_mcp_server.tools.transaction_tools.get_blockscout_base_url', new_callable=AsyncMock) as mock_get_url, \
         patch('blockscout_mcp_server.tools.transaction_tools.make_blockscout_request', new_callable=AsyncMock) as mock_request:

        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response

        # ACT
        result = await get_transaction_info(chain_id=chain_id, transaction_hash=hash, ctx=mock_ctx)

        # ASSERT
        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(
            base_url=mock_base_url,
            api_path=f"/api/v2/transactions/{hash}"
        )
        assert result == expected_transformed_result
        assert mock_ctx.report_progress.call_count == 3
        assert mock_ctx.info.call_count == 3


@pytest.mark.asyncio
async def test_get_transaction_info_no_truncation(mock_ctx):
    """Verify behavior when no data is large enough to be truncated."""
    chain_id = "1"
    tx_hash = "0x123"
    mock_base_url = "https://eth.blockscout.com"
    mock_api_response = {
        "hash": tx_hash,
        "decoded_input": {"parameters": ["short_string"]},
        "raw_input": "0xshort"
    }

    with patch('blockscout_mcp_server.tools.transaction_tools.get_blockscout_base_url', new_callable=AsyncMock) as mock_get_url, \
         patch('blockscout_mcp_server.tools.transaction_tools.make_blockscout_request', new_callable=AsyncMock) as mock_request:
        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response.copy()

        result = await get_transaction_info(chain_id=chain_id, transaction_hash=tx_hash, ctx=mock_ctx)

        assert isinstance(result, dict)
        assert "raw_input" not in result
        assert "raw_input_truncated" not in result
        assert result["decoded_input"]["parameters"][0] == "short_string"


@pytest.mark.asyncio
async def test_get_transaction_info_truncates_raw_input(mock_ctx):
    """Verify raw_input is truncated when it's too long and there's no decoded_input."""
    chain_id = "1"
    tx_hash = "0x123"
    mock_base_url = "https://eth.blockscout.com"
    long_raw_input = "0x" + "a" * INPUT_DATA_TRUNCATION_LIMIT
    mock_api_response = {
        "hash": tx_hash,
        "decoded_input": None,
        "raw_input": long_raw_input
    }

    with patch('blockscout_mcp_server.tools.transaction_tools.get_blockscout_base_url', new_callable=AsyncMock) as mock_get_url, \
         patch('blockscout_mcp_server.tools.transaction_tools.make_blockscout_request', new_callable=AsyncMock) as mock_request:
        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response.copy()

        result = await get_transaction_info(chain_id=chain_id, transaction_hash=tx_hash, ctx=mock_ctx)

        assert isinstance(result, str)
        assert "**Note on Truncated Data:**" in result

        json_part = result.split("----")[0]
        data = json.loads(json_part)

        assert data["raw_input_truncated"] is True
        assert len(data["raw_input"]) == INPUT_DATA_TRUNCATION_LIMIT


@pytest.mark.asyncio
async def test_get_transaction_info_truncates_decoded_input(mock_ctx):
    """Verify a parameter in decoded_input is truncated."""
    chain_id = "1"
    tx_hash = "0x123"
    mock_base_url = "https://eth.blockscout.com"
    long_param = "0x" + "a" * INPUT_DATA_TRUNCATION_LIMIT
    mock_api_response = {
        "hash": tx_hash,
        "decoded_input": {"parameters": [long_param]},
        "raw_input": "0xshort"
    }

    with patch('blockscout_mcp_server.tools.transaction_tools.get_blockscout_base_url', new_callable=AsyncMock) as mock_get_url, \
         patch('blockscout_mcp_server.tools.transaction_tools.make_blockscout_request', new_callable=AsyncMock) as mock_request:
        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response.copy()

        result = await get_transaction_info(chain_id=chain_id, transaction_hash=tx_hash, ctx=mock_ctx)

        assert isinstance(result, str)
        assert "**Note on Truncated Data:**" in result

        json_part = result.split("----")[0]
        data = json.loads(json_part)

        param = data["decoded_input"]["parameters"][0]
        assert param["value_truncated"] is True
        assert len(param["value_sample"]) == INPUT_DATA_TRUNCATION_LIMIT


@pytest.mark.asyncio
async def test_get_transaction_info_keeps_and_truncates_raw_input_when_flagged(mock_ctx):
    """Verify raw_input is kept but truncated when include_raw_input is True."""
    chain_id = "1"
    tx_hash = "0x123"
    mock_base_url = "https://eth.blockscout.com"
    long_raw_input = "0x" + "a" * INPUT_DATA_TRUNCATION_LIMIT
    mock_api_response = {
        "hash": tx_hash,
        "decoded_input": {"parameters": ["short"]},
        "raw_input": long_raw_input
    }

    with patch('blockscout_mcp_server.tools.transaction_tools.get_blockscout_base_url', new_callable=AsyncMock) as mock_get_url, \
         patch('blockscout_mcp_server.tools.transaction_tools.make_blockscout_request', new_callable=AsyncMock) as mock_request:
        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response.copy()

        result = await get_transaction_info(chain_id=chain_id, transaction_hash=tx_hash, ctx=mock_ctx, include_raw_input=True)

        assert isinstance(result, str)
        assert "**Note on Truncated Data:**" in result

        json_part = result.split("----")[0]
        data = json.loads(json_part)

        assert "raw_input" in data
        assert data["raw_input_truncated"] is True
        assert len(data["raw_input"]) == INPUT_DATA_TRUNCATION_LIMIT
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
            await get_transaction_info(chain_id=chain_id, transaction_hash=hash, ctx=mock_ctx)

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
            await get_transaction_info(chain_id=chain_id, transaction_hash=hash, ctx=mock_ctx)

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
        result = await get_transaction_info(chain_id=chain_id, transaction_hash=hash, ctx=mock_ctx)

        # ASSERT
        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(
            base_url=mock_base_url,
            api_path=f"/api/v2/transactions/{hash}"
        )
        expected_result = {"status": "pending"}
        assert result == expected_result
        assert mock_ctx.report_progress.call_count == 3
        assert mock_ctx.info.call_count == 3


@pytest.mark.asyncio
async def test_get_transaction_info_with_token_transfers_transformation(mock_ctx):
    """
    Verify get_transaction_info correctly transforms the token_transfers list.
    """
    # ARRANGE
    chain_id = "1"
    tx_hash = "0xd4df84bf9e45af2aa8310f74a2577a28b420c59f2e3da02c52b6d39dc83ef10f"
    mock_base_url = "https://eth.blockscout.com"

    mock_api_response = {
        "hash": tx_hash,
        "from": {"hash": "0xe725..."},
        "to": {"hash": "0x3328..."},
        "token_transfers": [
            {
                "block_hash": "0x841ad...",
                "block_number": 22697200,
                "from": {"hash": "0x000..."},
                "to": {"hash": "0x3328..."},
                "token": {"name": "WETH", "symbol": "WETH"},
                "total": {"value": "2046..."},
                "transaction_hash": tx_hash,
                "timestamp": "2025-06-13T17:42:23.000000Z",
                "type": "token_minting",
                "log_index": 13,
            }
        ],
    }

    expected_transformed_result = {
        "from": "0xe725...",
        "to": "0x3328...",
        "token_transfers": [
            {
                "from": "0x000...",
                "to": "0x3328...",
                "token": {"name": "WETH", "symbol": "WETH"},
                "total": {"value": "2046..."},
                "type": "token_minting",
                "log_index": 13,
            }
        ],
    }

    with patch('blockscout_mcp_server.tools.transaction_tools.get_blockscout_base_url', new_callable=AsyncMock) as mock_get_url, \
         patch('blockscout_mcp_server.tools.transaction_tools.make_blockscout_request', new_callable=AsyncMock) as mock_request:

        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response

        # ACT
        result = await get_transaction_info(chain_id=chain_id, transaction_hash=tx_hash, ctx=mock_ctx)

        # ASSERT
        assert result == expected_transformed_result

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
                "index": 1,
            }
        ],
    }

    expected_transformed_response = {
        "items": [
            {
                "address": "0xcontract1...",
                "block_number": 19000000,
                "data": "0xdata123...",
                "decoded": {"name": "EventA"},
                "index": 0,
                "topics": ["0xtopic1...", "0xtopic2..."],
            },
            {
                "address": "0xcontract2...",
                "block_number": 19000000,
                "data": "0xdata456...",
                "decoded": {"name": "EventB"},
                "index": 1,
                "topics": ["0xtopic3..."],
            },
        ],
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
        result = await get_transaction_logs(chain_id=chain_id, transaction_hash=hash, ctx=mock_ctx)

        # ASSERT
        # Assert that json.dumps was called with the transformed data
        mock_json_dumps.assert_called_once_with(expected_transformed_response)

        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(
            base_url=mock_base_url,
            api_path=f"/api/v2/transactions/{hash}/logs",
            params={}
        )
        
        # Verify the result starts with the expected prefix
        expected_prefix = "**Items Structure:**"
        assert result.startswith(expected_prefix)

        assert mock_ctx.report_progress.call_count == 3
        assert mock_ctx.info.call_count == 3


