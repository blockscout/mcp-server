# tests/tools/test_address_logs.py
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from blockscout_mcp_server.tools.address_tools import get_address_logs
from blockscout_mcp_server.tools.common import encode_cursor


@pytest.mark.asyncio
async def test_get_address_logs_success(mock_ctx):
    """
    Verify get_address_logs correctly processes and formats address logs.
    """
    # ARRANGE
    chain_id = "1"
    address = "0x123abc"
    mock_base_url = "https://eth.blockscout.com"

    mock_api_response = {
        "items": [
            {
                "address": {"hash": "0xcontract1..."},
                "topics": ["0xtopic1...", "0xtopic2..."],
                "data": "0xdata123...",
                "log_index": "0",
                "transaction_hash": "0xtx123...",
                "block_number": 19000000,
                "block_hash": "0x...",
                "smart_contract": {},
                "decoded": None,
                "index": 0,
            }
        ]
    }

    expected_transformed_response = {
        "items": [
            {
                "block_number": 19000000,
                "data": "0xdata123...",
                "decoded": None,
                "index": 0,
                "topics": ["0xtopic1...", "0xtopic2..."],
                "transaction_hash": "0xtx123...",
            }
        ]
    }

    with (
        patch(
            "blockscout_mcp_server.tools.address_tools.get_blockscout_base_url", new_callable=AsyncMock
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.address_tools.make_blockscout_request", new_callable=AsyncMock
        ) as mock_request,
        patch("blockscout_mcp_server.tools.address_tools._process_and_truncate_log_items") as mock_process_logs,
        patch("blockscout_mcp_server.tools.address_tools.json.dumps") as mock_json_dumps,
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response
        mock_process_logs.return_value = (mock_api_response.get("items", []), False)
        mock_json_dumps.return_value = '{"fake_json": true}'

        # ACT
        result = await get_address_logs(chain_id=chain_id, address=address, ctx=mock_ctx)

        # ASSERT
        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(
            base_url=mock_base_url, api_path=f"/api/v2/addresses/{address}/logs", params={}
        )
        mock_process_logs.assert_called_once_with(mock_api_response.get("items", []))

        mock_json_dumps.assert_called_once_with(expected_transformed_response)

        assert result.startswith("**Items Structure:**")
        assert "fake_json" in result

        assert mock_ctx.report_progress.call_count == 3
        assert mock_ctx.info.call_count == 3


@pytest.mark.asyncio
async def test_get_address_logs_with_pagination(mock_ctx):
    """Verify get_address_logs includes pagination hint and correctly formats the main JSON body."""
    chain_id = "1"
    address = "0x123abc"
    mock_base_url = "https://eth.blockscout.com"

    mock_api_response = {
        "items": [
            {
                "address": {"hash": "0xcontract1"},
                "topics": ["0xtopic1..."],
                "data": "0xdata123...",
                "log_index": "0",
                "transaction_hash": "0xtx123...",
                "block_number": 19000000,
                "decoded": None,
                "block_hash": "0x...",
                "smart_contract": {},
                "index": 0,
            }
        ],
        "next_page_params": {"block_number": 18999999, "index": "42", "items_count": 50},
    }

    expected_transformed_response = {
        "items": [
            {
                "block_number": 19000000,
                "data": "0xdata123...",
                "decoded": None,
                "index": 0,
                "topics": ["0xtopic1..."],
                "transaction_hash": "0xtx123...",
            }
        ]
    }

    fake_cursor = "ENCODED_CURSOR_STRING_FROM_TEST"
    fake_json_body = '{"fake_json": true}'

    with (
        patch(
            "blockscout_mcp_server.tools.address_tools.get_blockscout_base_url", new_callable=AsyncMock
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.address_tools.make_blockscout_request", new_callable=AsyncMock
        ) as mock_request,
        patch("blockscout_mcp_server.tools.address_tools._process_and_truncate_log_items") as mock_process_logs,
        patch("blockscout_mcp_server.tools.address_tools.json.dumps") as mock_json_dumps,
        patch("blockscout_mcp_server.tools.address_tools.encode_cursor") as mock_encode_cursor,
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response
        mock_process_logs.return_value = (mock_api_response["items"], False)
        mock_json_dumps.return_value = fake_json_body
        mock_encode_cursor.return_value = fake_cursor

        result = await get_address_logs(chain_id=chain_id, address=address, ctx=mock_ctx)

        mock_json_dumps.assert_called_once_with(expected_transformed_response)
        mock_encode_cursor.assert_called_once_with(mock_api_response["next_page_params"])

        assert result.startswith("**Items Structure:**")
        assert fake_json_body in result
        assert f'cursor="{fake_cursor}"' in result

        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(
            base_url=mock_base_url, api_path=f"/api/v2/addresses/{address}/logs", params={}
        )
        mock_process_logs.assert_called_once_with(mock_api_response["items"])
        assert mock_ctx.report_progress.call_count == 3
        assert mock_ctx.info.call_count == 3


@pytest.mark.asyncio
async def test_get_address_logs_with_optional_params(mock_ctx):
    """
    Verify get_address_logs correctly passes optional pagination parameters.
    """
    # ARRANGE
    chain_id = "1"
    address = "0x123abc"
    block_number = 18999999
    index = 42  # Fixed parameter name from log_index to index
    items_count = 25
    mock_base_url = "https://eth.blockscout.com"

    mock_api_response = {"items": []}
    expected_transformed_response = {"items": []}

    cursor = encode_cursor({"block_number": block_number, "index": index, "items_count": items_count})

    with (
        patch(
            "blockscout_mcp_server.tools.address_tools.get_blockscout_base_url", new_callable=AsyncMock
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.address_tools.make_blockscout_request", new_callable=AsyncMock
        ) as mock_request,
        patch("blockscout_mcp_server.tools.address_tools._process_and_truncate_log_items") as mock_process_logs,
        patch("blockscout_mcp_server.tools.address_tools.json.dumps") as mock_json_dumps,
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response
        mock_process_logs.return_value = (mock_api_response["items"], False)
        mock_json_dumps.return_value = '{"empty": true}'

        # ACT
        result = await get_address_logs(chain_id=chain_id, address=address, cursor=cursor, ctx=mock_ctx)

        # ASSERT
        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(
            base_url=mock_base_url,
            api_path=f"/api/v2/addresses/{address}/logs",
            params={
                "block_number": block_number,
                "index": index,
                "items_count": items_count,
            },
        )
        mock_process_logs.assert_called_once_with(mock_api_response["items"])

        mock_json_dumps.assert_called_once_with(expected_transformed_response)

        # Verify result structure
        assert result.startswith("**Items Structure:**")
        assert "empty" in result

        assert mock_ctx.report_progress.call_count == 3
        assert mock_ctx.info.call_count == 3


@pytest.mark.asyncio
async def test_get_address_logs_invalid_cursor(mock_ctx):
    """Verify the tool returns a user-friendly error for a bad cursor."""
    chain_id = "1"
    address = "0x123abc"
    invalid_cursor = "bad-cursor"

    result = await get_address_logs(chain_id=chain_id, address=address, cursor=invalid_cursor, ctx=mock_ctx)

    assert "Error: Invalid or expired pagination cursor." in result


@pytest.mark.asyncio
async def test_get_address_logs_api_error(mock_ctx):
    """
    Verify get_address_logs correctly propagates API errors.
    """
    # ARRANGE
    chain_id = "1"
    address = "0x123abc"
    mock_base_url = "https://eth.blockscout.com"

    api_error = httpx.HTTPStatusError("Internal Server Error", request=MagicMock(), response=MagicMock(status_code=500))

    with (
        patch(
            "blockscout_mcp_server.tools.address_tools.get_blockscout_base_url", new_callable=AsyncMock
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.address_tools.make_blockscout_request", new_callable=AsyncMock
        ) as mock_request,
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.side_effect = api_error

        # ACT & ASSERT
        with pytest.raises(httpx.HTTPStatusError):
            await get_address_logs(chain_id=chain_id, address=address, ctx=mock_ctx)

        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(
            base_url=mock_base_url, api_path=f"/api/v2/addresses/{address}/logs", params={}
        )


@pytest.mark.asyncio
async def test_get_address_logs_empty_logs(mock_ctx):
    """
    Verify get_address_logs handles addresses with no logs.
    """
    # ARRANGE
    chain_id = "1"
    address = "0x123abc"
    mock_base_url = "https://eth.blockscout.com"

    mock_api_response = {"items": []}
    expected_transformed_response = {"items": []}

    # Patch json.dumps directly since it's imported locally in the function
    with (
        patch(
            "blockscout_mcp_server.tools.address_tools.get_blockscout_base_url", new_callable=AsyncMock
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.address_tools.make_blockscout_request", new_callable=AsyncMock
        ) as mock_request,
        patch("blockscout_mcp_server.tools.address_tools._process_and_truncate_log_items") as mock_process_logs,
        patch("blockscout_mcp_server.tools.address_tools.json.dumps") as mock_json_dumps,
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response
        mock_process_logs.return_value = (mock_api_response["items"], False)
        # We don't care what json.dumps returns, only that it's called correctly
        mock_json_dumps.return_value = "{...}"

        # ACT
        result = await get_address_logs(chain_id=chain_id, address=address, ctx=mock_ctx)

        # ASSERT
        # Assert that json.dumps was called with the transformed data
        mock_json_dumps.assert_called_once_with(expected_transformed_response)

        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(
            base_url=mock_base_url, api_path=f"/api/v2/addresses/{address}/logs", params={}
        )
        mock_process_logs.assert_called_once_with(mock_api_response["items"])

        # Verify the result structure
        assert result.startswith("**Items Structure:**")

        # Verify no pagination hint is included
        assert "To get the next page call" not in result

        assert mock_ctx.report_progress.call_count == 3
        assert mock_ctx.info.call_count == 3


@pytest.mark.asyncio
async def test_get_address_logs_with_truncation_note(mock_ctx):
    """Verify the truncation note is added when the helper indicates truncation."""
    # ARRANGE
    chain_id = "1"
    address = "0x123abc"
    mock_base_url = "https://eth.blockscout.com"
    truncated_item = {"data": "0xlong...", "data_truncated": True}
    mock_api_response = {"items": [truncated_item]}

    with (
        patch(
            "blockscout_mcp_server.tools.address_tools.get_blockscout_base_url", new_callable=AsyncMock
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.address_tools.make_blockscout_request", new_callable=AsyncMock
        ) as mock_request,
        patch("blockscout_mcp_server.tools.address_tools._process_and_truncate_log_items") as mock_process_logs,
        patch("blockscout_mcp_server.tools.address_tools.json.dumps") as mock_json_dumps,
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response
        # Simulate truncated data
        mock_process_logs.return_value = ([truncated_item], True)
        mock_json_dumps.return_value = '{"fake":true}'

        # ACT
        result = await get_address_logs(chain_id=chain_id, address=address, ctx=mock_ctx)

        # ASSERT
        expected_transformed = {
            "items": [
                {
                    "block_number": None,
                    "data": truncated_item["data"],
                    "decoded": None,
                    "index": None,
                    "topics": None,
                    "transaction_hash": None,
                    "data_truncated": True,
                }
            ]
        }

        mock_process_logs.assert_called_once_with(mock_api_response["items"])
        mock_json_dumps.assert_called_once_with(expected_transformed)
        assert "**Note on Truncated Data:**" in result
        assert f'`curl "{mock_base_url}/api/v2/transactions/{{THE_TRANSACTION_HASH}}/logs"`' in result


@pytest.mark.asyncio
async def test_get_address_logs_with_decoded_truncation_note(mock_ctx):
    """Verify truncation note when decoded field is truncated."""
    chain_id = "1"
    address = "0x123abc"
    mock_base_url = "https://eth.blockscout.com"

    truncated_item = {
        "data": "0xshort",
        "decoded": {
            "parameters": [
                {
                    "name": "foo",
                    "value": {"value_sample": "0x", "value_truncated": True},
                }
            ]
        },
    }
    mock_api_response = {"items": [truncated_item]}

    with (
        patch(
            "blockscout_mcp_server.tools.address_tools.get_blockscout_base_url",
            new_callable=AsyncMock,
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.address_tools.make_blockscout_request",
            new_callable=AsyncMock,
        ) as mock_request,
        patch("blockscout_mcp_server.tools.address_tools._process_and_truncate_log_items") as mock_process_logs,
        patch("blockscout_mcp_server.tools.address_tools.json.dumps") as mock_json_dumps,
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response
        mock_process_logs.return_value = ([truncated_item], True)
        mock_json_dumps.return_value = '{"fake":true}'

        result = await get_address_logs(chain_id=chain_id, address=address, ctx=mock_ctx)

        expected_transformed = {
            "items": [
                {
                    "block_number": None,
                    "data": truncated_item["data"],
                    "decoded": truncated_item["decoded"],
                    "index": None,
                    "topics": None,
                    "transaction_hash": None,
                }
            ]
        }
        mock_process_logs.assert_called_once_with(mock_api_response["items"])
        mock_json_dumps.assert_called_once_with(expected_transformed)
        assert "**Note on Truncated Data:**" in result
        assert f'`curl "{mock_base_url}/api/v2/transactions/{{THE_TRANSACTION_HASH}}/logs"`' in result
