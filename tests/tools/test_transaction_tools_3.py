# tests/tools/test_transaction_tools_3.py
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import httpx

from blockscout_mcp_server.tools.transaction_tools import get_transaction_logs
from blockscout_mcp_server.tools.common import encode_cursor

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
    }

    # Patch json.dumps directly since it's imported locally in the function
    with patch('blockscout_mcp_server.tools.transaction_tools.get_blockscout_base_url', new_callable=AsyncMock) as mock_get_url, \
         patch('blockscout_mcp_server.tools.transaction_tools.make_blockscout_request', new_callable=AsyncMock) as mock_request, \
         patch('blockscout_mcp_server.tools.transaction_tools._process_and_truncate_log_items') as mock_process_logs, \
         patch('blockscout_mcp_server.tools.transaction_tools.json.dumps') as mock_json_dumps:

        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response
        mock_process_logs.return_value = (mock_api_response["items"], False)
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
        mock_process_logs.assert_called_once_with(mock_api_response["items"])
        
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
            await get_transaction_logs(chain_id=chain_id, transaction_hash=hash, ctx=mock_ctx)

        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(
            base_url=mock_base_url,
            api_path=f"/api/v2/transactions/{hash}/logs",
            params={}
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
                "index": 42,
            }
        ],
    }

    expected_transformed_response = {
        "items": [
            {
                "address": "0xa0b86a33e6dd0ba3c70de3b8e2b9e48cd6efb7b0",
                "block_number": 19000000,
                "data": "0x0000000000000000000000000000000000000000000000000de0b6b3a7640000",
                "decoded": {"name": "Transfer"},
                "index": 42,
                "topics": [
                    "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef",
                    "0x000000000000000000000000d8da6bf26964af9d7eed9e03e53415d37aa96045",
                    "0x000000000000000000000000f81c1a7e8d3c1a1d3c1a1d3c1a1d3c1a1d3c1a1d"
                ],
            }
        ],
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


@pytest.mark.asyncio
async def test_get_transaction_logs_with_pagination(mock_ctx):
    """Verify pagination hint is included when next_page_params present."""
    chain_id = "1"
    hash = "0xabc123"
    mock_base_url = "https://eth.blockscout.com"

    mock_api_response = {
        "items": [
            {
                "address": {"hash": "0xcontract1"},
                "topics": [],
                "data": "0x",
                "log_index": "0",
                "transaction_hash": hash,
                "block_number": 1,
                "decoded": None,
                "index": 0,
            }
        ],
        "next_page_params": {"block_number": 0, "index": "0", "items_count": 50},
    }

    expected_transformed_response = {
        "items": [
            {
                "address": "0xcontract1",
                "block_number": 1,
                "data": "0x",
                "decoded": None,
                "index": 0,
                "topics": [],
            }
        ],
    }

    fake_cursor = "ENCODED_CURSOR"
    fake_json_body = "{...}"

    with patch(
        "blockscout_mcp_server.tools.transaction_tools.get_blockscout_base_url",
        new_callable=AsyncMock,
    ) as mock_get_url, patch(
        "blockscout_mcp_server.tools.transaction_tools.make_blockscout_request",
        new_callable=AsyncMock,
    ) as mock_request, patch(
        "blockscout_mcp_server.tools.transaction_tools._process_and_truncate_log_items"
    ) as mock_process_logs, patch(
        "blockscout_mcp_server.tools.transaction_tools.json.dumps"
    ) as mock_json_dumps, patch(
        "blockscout_mcp_server.tools.transaction_tools.encode_cursor"
    ) as mock_encode_cursor:
        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response
        mock_process_logs.return_value = (mock_api_response["items"], False)
        mock_json_dumps.return_value = fake_json_body
        mock_encode_cursor.return_value = fake_cursor

        result = await get_transaction_logs(chain_id=chain_id, transaction_hash=hash, ctx=mock_ctx)

        mock_json_dumps.assert_called_once_with(expected_transformed_response)
        mock_encode_cursor.assert_called_once_with(
            mock_api_response["next_page_params"]
        )

        assert result.startswith("**Items Structure:**")
        assert fake_json_body in result
        assert f'cursor="{fake_cursor}"' in result

        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(
            base_url=mock_base_url,
            api_path=f"/api/v2/transactions/{hash}/logs",
            params={},
        )
        mock_process_logs.assert_called_once_with(mock_api_response["items"])
        assert mock_ctx.report_progress.call_count == 3
        assert mock_ctx.info.call_count == 3


@pytest.mark.asyncio
async def test_get_transaction_logs_with_cursor(mock_ctx):
    """Verify provided cursor is decoded and used in request."""
    chain_id = "1"
    hash = "0xabc123"
    mock_base_url = "https://eth.blockscout.com"

    decoded_params = {"block_number": 42, "index": 1, "items_count": 25}
    cursor = encode_cursor(decoded_params)

    mock_api_response = {"items": [], "next_page_params": None}

    with patch(
        "blockscout_mcp_server.tools.transaction_tools.get_blockscout_base_url",
        new_callable=AsyncMock,
    ) as mock_get_url, patch(
        "blockscout_mcp_server.tools.transaction_tools.make_blockscout_request",
        new_callable=AsyncMock,
    ) as mock_request, patch(
        "blockscout_mcp_server.tools.transaction_tools._process_and_truncate_log_items"
    ) as mock_process_logs, patch(
        "blockscout_mcp_server.tools.transaction_tools.json.dumps"
    ) as mock_json_dumps:
        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response
        mock_process_logs.return_value = (mock_api_response["items"], False)
        mock_json_dumps.return_value = "{...}"

        await get_transaction_logs(chain_id=chain_id, transaction_hash=hash, cursor=cursor, ctx=mock_ctx)

        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(
            base_url=mock_base_url,
            api_path=f"/api/v2/transactions/{hash}/logs",
            params=decoded_params,
        )
        mock_json_dumps.assert_called_once_with({"items": []})
        mock_process_logs.assert_called_once_with(mock_api_response["items"])
        assert mock_ctx.report_progress.call_count == 3
        assert mock_ctx.info.call_count == 3


@pytest.mark.asyncio
async def test_get_transaction_logs_invalid_cursor(mock_ctx):
    """Verify the tool returns a user-friendly error for a bad cursor."""
    chain_id = "1"
    hash = "0xabc123"
    invalid_cursor = "bad-cursor"

    with patch(
        "blockscout_mcp_server.tools.transaction_tools.make_blockscout_request",
        new_callable=AsyncMock,
    ) as mock_request:
        result = await get_transaction_logs(
            chain_id=chain_id, transaction_hash=hash, cursor=invalid_cursor, ctx=mock_ctx
        )

        assert (
            "Error: Invalid or expired pagination cursor" in result
        )
        mock_request.assert_not_called()


@pytest.mark.asyncio
async def test_get_transaction_logs_with_truncation_note(mock_ctx):
    """Verify the truncation note is added when the helper indicates truncation."""
    # ARRANGE
    chain_id = "1"
    hash = "0xabc123"
    mock_base_url = "https://eth.blockscout.com"
    truncated_item = {"data": "0xlong...", "data_truncated": True}
    mock_api_response = {"items": [truncated_item]}

    with patch('blockscout_mcp_server.tools.transaction_tools.get_blockscout_base_url', new_callable=AsyncMock) as mock_get_url, \
         patch('blockscout_mcp_server.tools.transaction_tools.make_blockscout_request', new_callable=AsyncMock) as mock_request, \
         patch('blockscout_mcp_server.tools.transaction_tools._process_and_truncate_log_items') as mock_process_logs, \
         patch('blockscout_mcp_server.tools.transaction_tools.json.dumps') as mock_json_dumps:

        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response
        mock_process_logs.return_value = ([truncated_item], True)
        mock_json_dumps.return_value = '{"fake":true}'

        # ACT
        result = await get_transaction_logs(chain_id=chain_id, transaction_hash=hash, ctx=mock_ctx)

        # ASSERT
        expected_transformed = {
            "items": [
                {
                    "address": None,
                    "block_number": None,
                    "data": truncated_item["data"],
                    "decoded": None,
                    "index": None,
                    "topics": None,
                    "data_truncated": True,
                }
            ]
        }

        mock_process_logs.assert_called_once_with(mock_api_response["items"])
        mock_json_dumps.assert_called_once_with(expected_transformed)
        assert "**Note on Truncated Data:**" in result
        assert f"`curl \"{mock_base_url}/api/v2/transactions/{hash}/logs\"`" in result

