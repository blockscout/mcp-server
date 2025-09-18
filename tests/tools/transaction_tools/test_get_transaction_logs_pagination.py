from unittest.mock import AsyncMock, patch

import pytest

from blockscout_mcp_server.config import config
from blockscout_mcp_server.models import NextCallInfo, PaginationInfo, ToolResponse, TransactionLogItem
from blockscout_mcp_server.tools.common import encode_cursor
from blockscout_mcp_server.tools.transaction.get_transaction_logs import get_transaction_logs


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
            "blockscout_mcp_server.tools.transaction.get_transaction_logs.get_blockscout_base_url",
            new_callable=AsyncMock,
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.transaction.get_transaction_logs.make_blockscout_request",
            new_callable=AsyncMock,
        ) as mock_request,
        patch(
            "blockscout_mcp_server.tools.transaction.get_transaction_logs._process_and_truncate_log_items",
        ) as mock_process_logs,
        patch(
            "blockscout_mcp_server.tools.transaction.get_transaction_logs.create_items_pagination",
        ) as mock_create_pagination,
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
            "blockscout_mcp_server.tools.transaction.get_transaction_logs.get_blockscout_base_url",
            new_callable=AsyncMock,
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.transaction.get_transaction_logs.make_blockscout_request",
            new_callable=AsyncMock,
        ) as mock_request,
        patch(
            "blockscout_mcp_server.tools.transaction.get_transaction_logs._process_and_truncate_log_items",
        ) as mock_process_logs,
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
async def test_get_transaction_logs_custom_page_size(mock_ctx):
    chain_id = "1"
    tx_hash = "0xabc"
    mock_base_url = "https://eth.blockscout.com"

    mock_api_response = {"items": [{"block_number": i, "index": i} for i in range(10)]}

    with (
        patch(
            "blockscout_mcp_server.tools.transaction.get_transaction_logs.get_blockscout_base_url",
            new_callable=AsyncMock,
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.transaction.get_transaction_logs.make_blockscout_request",
            new_callable=AsyncMock,
        ) as mock_request,
        patch(
            "blockscout_mcp_server.tools.transaction.get_transaction_logs._process_and_truncate_log_items",
        ) as mock_process_logs,
        patch(
            "blockscout_mcp_server.tools.transaction.get_transaction_logs.create_items_pagination",
        ) as mock_create_pagination,
        patch.object(config, "logs_page_size", 5),
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response
        mock_process_logs.return_value = (mock_api_response["items"], False)
        mock_create_pagination.return_value = (mock_api_response["items"][:5], None)

        await get_transaction_logs(chain_id=chain_id, transaction_hash=tx_hash, ctx=mock_ctx)

        mock_create_pagination.assert_called_once()
        assert mock_create_pagination.call_args.kwargs["page_size"] == 5
