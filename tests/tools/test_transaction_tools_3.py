# tests/tools/test_transaction_tools_3.py
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from blockscout_mcp_server.config import config
from blockscout_mcp_server.models import (
    NextCallInfo,
    PaginationInfo,
    ToolResponse,
    TransactionLogItem,
)
from blockscout_mcp_server.tools.common import encode_cursor
from blockscout_mcp_server.tools.transaction_tools import get_transaction_logs


@pytest.mark.asyncio
async def test_get_transaction_logs_empty_logs(mock_ctx):
    """
    Verify get_transaction_logs handles transactions with no logs.
    """
    # ARRANGE
    chain_id = "1"
    tx_hash = "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
    mock_base_url = "https://eth.blockscout.com"

    mock_api_response = {"items": []}

    expected_log_items: list[TransactionLogItem] = []

    with (
        patch(
            "blockscout_mcp_server.tools.transaction_tools.get_blockscout_base_url", new_callable=AsyncMock
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.transaction_tools.make_blockscout_request", new_callable=AsyncMock
        ) as mock_request,
        patch("blockscout_mcp_server.tools.transaction_tools._process_and_truncate_log_items") as mock_process_logs,
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response
        mock_process_logs.return_value = (mock_api_response["items"], False)

        # ACT
        result = await get_transaction_logs(chain_id=chain_id, transaction_hash=tx_hash, ctx=mock_ctx)

        # ASSERT
        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(
            base_url=mock_base_url, api_path=f"/api/v2/transactions/{tx_hash}/logs", params={}
        )
        mock_process_logs.assert_called_once_with(mock_api_response["items"])
        assert isinstance(result, ToolResponse)
        assert result.pagination is None
        assert result.data == expected_log_items

        assert mock_ctx.report_progress.call_count == 3
        assert mock_ctx.info.call_count == 3


@pytest.mark.asyncio
async def test_get_transaction_logs_api_error(mock_ctx):
    """
    Verify get_transaction_logs correctly propagates API errors.
    """
    # ARRANGE
    chain_id = "1"
    tx_hash = "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
    mock_base_url = "https://eth.blockscout.com"

    api_error = httpx.HTTPStatusError("Internal Server Error", request=MagicMock(), response=MagicMock(status_code=500))

    with (
        patch(
            "blockscout_mcp_server.tools.transaction_tools.get_blockscout_base_url", new_callable=AsyncMock
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.transaction_tools.make_blockscout_request", new_callable=AsyncMock
        ) as mock_request,
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.side_effect = api_error

        # ACT & ASSERT
        with pytest.raises(httpx.HTTPStatusError):
            await get_transaction_logs(chain_id=chain_id, transaction_hash=tx_hash, ctx=mock_ctx)

        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(
            base_url=mock_base_url, api_path=f"/api/v2/transactions/{tx_hash}/logs", params={}
        )


@pytest.mark.asyncio
async def test_get_transaction_logs_complex_logs(mock_ctx):
    """
    Verify get_transaction_logs handles complex log structures correctly.
    """
    # ARRANGE
    chain_id = "1"
    tx_hash = "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
    mock_base_url = "https://eth.blockscout.com"

    mock_api_response = {
        "items": [
            {
                "address": {"hash": "0xa0b86a33e6dd0ba3c70de3b8e2b9e48cd6efb7b0"},
                "topics": [
                    "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef",
                    "0x000000000000000000000000d8da6bf26964af9d7eed9e03e53415d37aa96045",
                    "0x000000000000000000000000f81c1a7e8d3c1a1d3c1a1d3c1a1d3c1a1d3c1a1d",
                ],
                "data": "0x0000000000000000000000000000000000000000000000000de0b6b3a7640000",
                "log_index": "42",
                "transaction_hash": tx_hash,
                "block_number": 19000000,
                "block_hash": "0xblock123...",
                "transaction_index": 10,
                "removed": False,
                "decoded": {"name": "Transfer"},
                "index": 42,
            }
        ],
    }

    expected_log_items = [
        TransactionLogItem(
            address="0xa0b86a33e6dd0ba3c70de3b8e2b9e48cd6efb7b0",
            block_number=19000000,
            data="0x0000000000000000000000000000000000000000000000000de0b6b3a7640000",
            decoded={"name": "Transfer"},
            index=42,
            topics=[
                "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef",
                "0x000000000000000000000000d8da6bf26964af9d7eed9e03e53415d37aa96045",
                "0x000000000000000000000000f81c1a7e8d3c1a1d3c1a1d3c1a1d3c1a1d3c1a1d",
            ],
        )
    ]

    with (
        patch(
            "blockscout_mcp_server.tools.transaction_tools.get_blockscout_base_url", new_callable=AsyncMock
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.transaction_tools.make_blockscout_request", new_callable=AsyncMock
        ) as mock_request,
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response

        # ACT
        result = await get_transaction_logs(chain_id=chain_id, transaction_hash=tx_hash, ctx=mock_ctx)

        # ASSERT
        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(
            base_url=mock_base_url, api_path=f"/api/v2/transactions/{tx_hash}/logs", params={}
        )
        assert isinstance(result, ToolResponse)
        assert result.pagination is None
        actual = result.data[0]
        expected = expected_log_items[0]
        assert actual.address == expected.address
        assert actual.block_number == expected.block_number
        assert actual.data == expected.data
        assert actual.decoded == expected.decoded
        assert actual.index == expected.index
        assert actual.topics == expected.topics

        assert mock_ctx.report_progress.call_count == 3
        assert mock_ctx.info.call_count == 3


@pytest.mark.asyncio
async def test_get_transaction_logs_with_pagination(mock_ctx):
    """Verify pagination hint is included when next_page_params present."""
    chain_id = "1"
    tx_hash = "0xabc123"
    mock_base_url = "https://eth.blockscout.com"

    mock_api_response = {
        "items": [
            {
                "address": {"hash": "0xcontract1"},
                "topics": [],
                "data": "0x",
                "log_index": "0",
                "transaction_hash": tx_hash,
                "block_number": 1,
                "decoded": None,
                "index": 0,
            }
        ],
        "next_page_params": {"block_number": 0, "index": "0", "items_count": 50},
    }

    expected_log_items = [
        TransactionLogItem(
            address="0xcontract1",
            block_number=1,
            data="0x",
            decoded=None,
            index=0,
            topics=[],
        )
    ]

    fake_cursor = "ENCODED_CURSOR"

    with (
        patch(
            "blockscout_mcp_server.tools.transaction_tools.get_blockscout_base_url",
            new_callable=AsyncMock,
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.transaction_tools.make_blockscout_request",
            new_callable=AsyncMock,
        ) as mock_request,
        patch("blockscout_mcp_server.tools.transaction_tools._process_and_truncate_log_items") as mock_process_logs,
        patch("blockscout_mcp_server.tools.transaction_tools.create_items_pagination") as mock_create_pagination,
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response
        mock_process_logs.return_value = (mock_api_response["items"], False)
        curated_dicts = [
            {
                "address": "0xcontract1",
                "block_number": 1,
                "topics": [],
                "data": "0x",
                "decoded": None,
                "index": 0,
            }
        ]
        mock_create_pagination.return_value = (
            curated_dicts,
            PaginationInfo(
                next_call=NextCallInfo(
                    tool_name="get_transaction_logs",
                    params={"chain_id": chain_id, "transaction_hash": tx_hash, "cursor": fake_cursor},
                )
            ),
        )

        result = await get_transaction_logs(chain_id=chain_id, transaction_hash=tx_hash, ctx=mock_ctx)

        mock_create_pagination.assert_called_once()
        assert isinstance(result, ToolResponse)
        actual = result.data[0]
        expected = expected_log_items[0]
        assert actual.address == expected.address
        assert actual.block_number == expected.block_number
        assert actual.data == expected.data
        assert actual.decoded == expected.decoded
        assert actual.index == expected.index
        assert actual.topics == expected.topics
        assert result.pagination.next_call.params["cursor"] == fake_cursor

        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(
            base_url=mock_base_url,
            api_path=f"/api/v2/transactions/{tx_hash}/logs",
            params={},
        )
        mock_process_logs.assert_called_once_with(mock_api_response["items"])
        assert mock_ctx.report_progress.call_count == 3
        assert mock_ctx.info.call_count == 3


@pytest.mark.asyncio
async def test_get_transaction_logs_with_cursor(mock_ctx):
    """Verify provided cursor is decoded and used in request."""
    chain_id = "1"
    tx_hash = "0xabc123"
    mock_base_url = "https://eth.blockscout.com"

    decoded_params = {"block_number": 42, "index": 1, "items_count": 25}
    cursor = encode_cursor(decoded_params)

    mock_api_response = {"items": [], "next_page_params": None}

    with (
        patch(
            "blockscout_mcp_server.tools.transaction_tools.get_blockscout_base_url",
            new_callable=AsyncMock,
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.transaction_tools.make_blockscout_request",
            new_callable=AsyncMock,
        ) as mock_request,
        patch("blockscout_mcp_server.tools.transaction_tools._process_and_truncate_log_items") as mock_process_logs,
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response
        mock_process_logs.return_value = (mock_api_response["items"], False)

        result = await get_transaction_logs(chain_id=chain_id, transaction_hash=tx_hash, cursor=cursor, ctx=mock_ctx)

        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(
            base_url=mock_base_url,
            api_path=f"/api/v2/transactions/{tx_hash}/logs",
            params=decoded_params,
        )
        mock_process_logs.assert_called_once_with(mock_api_response["items"])
        assert isinstance(result, ToolResponse)
        assert result.pagination is None
        assert result.data == []
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
        with pytest.raises(ValueError):
            await get_transaction_logs(chain_id=chain_id, transaction_hash=hash, cursor=invalid_cursor, ctx=mock_ctx)
        mock_request.assert_not_called()


@pytest.mark.asyncio
async def test_get_transaction_logs_with_truncation_note(mock_ctx):
    """Verify the truncation note is added when the helper indicates truncation."""
    # ARRANGE
    chain_id = "1"
    tx_hash = "0xabc123"
    mock_base_url = "https://eth.blockscout.com"
    truncated_item = {"data": "0xlong...", "data_truncated": True}
    mock_api_response = {"items": [truncated_item]}

    with (
        patch(
            "blockscout_mcp_server.tools.transaction_tools.get_blockscout_base_url", new_callable=AsyncMock
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.transaction_tools.make_blockscout_request", new_callable=AsyncMock
        ) as mock_request,
        patch("blockscout_mcp_server.tools.transaction_tools._process_and_truncate_log_items") as mock_process_logs,
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response
        mock_process_logs.return_value = ([truncated_item], True)

        # ACT
        result = await get_transaction_logs(chain_id=chain_id, transaction_hash=tx_hash, ctx=mock_ctx)

        # ASSERT
        expected_log_items = [
            TransactionLogItem(
                address=None,
                block_number=None,
                data=truncated_item["data"],
                decoded=None,
                index=None,
                topics=None,
            )
        ]

        mock_process_logs.assert_called_once_with(mock_api_response["items"])
        assert isinstance(result, ToolResponse)
        actual = result.data[0]
        expected = expected_log_items[0]
        assert actual.model_extra.get("address") == expected.address
        assert actual.block_number == expected.block_number
        assert actual.data == expected.data
        assert actual.decoded == expected.decoded
        assert actual.index == expected.index
        assert actual.topics == expected.topics
        assert actual.model_extra.get("data_truncated") is True
        assert result.notes is not None
        assert "One or more log items" in result.notes[0]


@pytest.mark.asyncio
async def test_get_transaction_logs_with_decoded_truncation_note(mock_ctx):
    """Verify truncation note appears when decoded data is truncated."""
    chain_id = "1"
    tx_hash = "0xabc123"
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
            "blockscout_mcp_server.tools.transaction_tools.get_blockscout_base_url",
            new_callable=AsyncMock,
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.transaction_tools.make_blockscout_request",
            new_callable=AsyncMock,
        ) as mock_request,
        patch("blockscout_mcp_server.tools.transaction_tools._process_and_truncate_log_items") as mock_process_logs,
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response
        mock_process_logs.return_value = ([truncated_item], True)

        result = await get_transaction_logs(chain_id=chain_id, transaction_hash=tx_hash, ctx=mock_ctx)

        expected_log_items = [
            TransactionLogItem(
                address=None,
                block_number=None,
                data=truncated_item["data"],
                decoded=truncated_item["decoded"],
                index=None,
                topics=None,
            )
        ]
        mock_process_logs.assert_called_once_with(mock_api_response["items"])
        assert isinstance(result, ToolResponse)
        actual = result.data[0]
        expected = expected_log_items[0]
        assert actual.model_extra.get("address") == expected.address
        assert actual.block_number == expected.block_number
        assert actual.data == expected.data
        assert actual.decoded == expected.decoded
        assert actual.index == expected.index
        assert actual.topics == expected.topics
        assert result.notes is not None
        assert "One or more log items" in result.notes[0]
        assert actual.model_extra.get("data_truncated") is None


@pytest.mark.asyncio
async def test_get_transaction_logs_custom_page_size(mock_ctx):
    chain_id = "1"
    tx_hash = "0xabc"
    mock_base_url = "https://eth.blockscout.com"

    mock_api_response = {"items": [{"block_number": i, "index": i} for i in range(10)]}

    with (
        patch(
            "blockscout_mcp_server.tools.transaction_tools.get_blockscout_base_url",
            new_callable=AsyncMock,
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.transaction_tools.make_blockscout_request",
            new_callable=AsyncMock,
        ) as mock_request,
        patch("blockscout_mcp_server.tools.transaction_tools._process_and_truncate_log_items") as mock_process_logs,
        patch("blockscout_mcp_server.tools.transaction_tools.create_items_pagination") as mock_create_pagination,
        patch.object(config, "logs_page_size", 5),
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response
        mock_process_logs.return_value = (mock_api_response["items"], False)
        mock_create_pagination.return_value = (mock_api_response["items"][:5], None)

        await get_transaction_logs(chain_id=chain_id, transaction_hash=tx_hash, ctx=mock_ctx)

        mock_create_pagination.assert_called_once()
        assert mock_create_pagination.call_args.kwargs["page_size"] == 5
