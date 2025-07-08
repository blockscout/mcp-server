from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from blockscout_mcp_server.config import config
from blockscout_mcp_server.models import (
    AddressLogItem,
    NextCallInfo,
    PaginationInfo,
    ToolResponse,
)
from blockscout_mcp_server.tools.address_tools import get_address_logs
from blockscout_mcp_server.tools.common import encode_cursor


@pytest.mark.asyncio
async def test_get_address_logs_success(mock_ctx):
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
                "decoded": None,
                "index": 0,
            }
        ]
    }

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
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response
        mock_process_logs.return_value = (mock_api_response["items"], False)

        result = await get_address_logs(chain_id=chain_id, address=address, ctx=mock_ctx)

        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(
            base_url=mock_base_url, api_path=f"/api/v2/addresses/{address}/logs", params={}
        )
        mock_process_logs.assert_called_once_with(mock_api_response["items"])

        assert isinstance(result, ToolResponse)
        assert isinstance(result.data[0], AddressLogItem)
        assert result.data[0].transaction_hash == "0xtx123..."
        assert "address" not in result.data[0].model_dump()
        assert result.data_description is not None
        assert "Items Structure:" in result.data_description[0]
        assert result.pagination is None
        assert result.notes is None
        assert mock_ctx.report_progress.call_count == 3
        assert mock_ctx.info.call_count == 3


@pytest.mark.asyncio
async def test_get_address_logs_with_pagination(mock_ctx):
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
                "index": 0,
            }
        ],
        "next_page_params": {"block_number": 18999999, "index": "42", "items_count": 50},
    }

    fake_cursor = "ENCODED_CURSOR_STRING_FROM_TEST"

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
        patch("blockscout_mcp_server.tools.address_tools.create_items_pagination") as mock_create_pagination,
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response
        mock_process_logs.return_value = (mock_api_response["items"], False)
        mock_create_pagination.return_value = (
            mock_api_response["items"],
            PaginationInfo(
                next_call=NextCallInfo(
                    tool_name="get_address_logs",
                    params={"chain_id": chain_id, "address": address, "cursor": fake_cursor},
                )
            ),
        )

        result = await get_address_logs(chain_id=chain_id, address=address, ctx=mock_ctx)

        mock_create_pagination.assert_called_once()
        assert isinstance(result, ToolResponse)
        assert isinstance(result.data[0], AddressLogItem)
        assert result.pagination is not None
        assert result.pagination.next_call.tool_name == "get_address_logs"
        assert result.pagination.next_call.params["cursor"] == fake_cursor

        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(
            base_url=mock_base_url, api_path=f"/api/v2/addresses/{address}/logs", params={}
        )
        mock_process_logs.assert_called_once_with(mock_api_response["items"])
        assert mock_ctx.report_progress.call_count == 3
        assert mock_ctx.info.call_count == 3


@pytest.mark.asyncio
async def test_get_address_logs_custom_page_size(mock_ctx):
    chain_id = "1"
    address = "0x123"
    mock_base_url = "https://eth.blockscout.com"

    mock_api_response = {"items": [{"block_number": i, "index": i} for i in range(10)]}

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
        patch("blockscout_mcp_server.tools.address_tools.create_items_pagination") as mock_create_pagination,
        patch.object(config, "logs_page_size", 5),
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response
        mock_process_logs.return_value = (mock_api_response["items"], False)
        mock_create_pagination.return_value = (mock_api_response["items"][:5], None)

        await get_address_logs(chain_id=chain_id, address=address, ctx=mock_ctx)

        mock_create_pagination.assert_called_once()
        assert mock_create_pagination.call_args.kwargs["page_size"] == 5


@pytest.mark.asyncio
async def test_get_address_logs_with_optional_params(mock_ctx):
    chain_id = "1"
    address = "0x123abc"
    block_number = 18999999
    index = 42
    items_count = 25
    mock_base_url = "https://eth.blockscout.com"

    mock_api_response = {"items": []}
    cursor = encode_cursor({"block_number": block_number, "index": index, "items_count": items_count})

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
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response
        mock_process_logs.return_value = (mock_api_response["items"], False)

        result = await get_address_logs(chain_id=chain_id, address=address, cursor=cursor, ctx=mock_ctx)

        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(
            base_url=mock_base_url,
            api_path=f"/api/v2/addresses/{address}/logs",
            params={"block_number": block_number, "index": index, "items_count": items_count},
        )
        mock_process_logs.assert_called_once_with(mock_api_response["items"])

        assert isinstance(result, ToolResponse)
        assert result.data == []
        assert mock_ctx.report_progress.call_count == 3
        assert mock_ctx.info.call_count == 3


@pytest.mark.asyncio
async def test_get_address_logs_invalid_cursor(mock_ctx):
    chain_id = "1"
    address = "0x123abc"
    invalid_cursor = "bad-cursor"

    with pytest.raises(ValueError, match="Invalid or expired pagination cursor"):
        await get_address_logs(chain_id=chain_id, address=address, cursor=invalid_cursor, ctx=mock_ctx)


@pytest.mark.asyncio
async def test_get_address_logs_api_error(mock_ctx):
    chain_id = "1"
    address = "0x123abc"
    mock_base_url = "https://eth.blockscout.com"

    api_error = httpx.HTTPStatusError("Internal Server Error", request=MagicMock(), response=MagicMock(status_code=500))

    with (
        patch(
            "blockscout_mcp_server.tools.address_tools.get_blockscout_base_url",
            new_callable=AsyncMock,
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.address_tools.make_blockscout_request",
            new_callable=AsyncMock,
        ) as mock_request,
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.side_effect = api_error

        with pytest.raises(httpx.HTTPStatusError):
            await get_address_logs(chain_id=chain_id, address=address, ctx=mock_ctx)

        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(
            base_url=mock_base_url, api_path=f"/api/v2/addresses/{address}/logs", params={}
        )


@pytest.mark.asyncio
async def test_get_address_logs_empty_logs(mock_ctx):
    chain_id = "1"
    address = "0x123abc"
    mock_base_url = "https://eth.blockscout.com"

    mock_api_response = {"items": []}

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
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response
        mock_process_logs.return_value = (mock_api_response["items"], False)

        result = await get_address_logs(chain_id=chain_id, address=address, ctx=mock_ctx)

        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(
            base_url=mock_base_url, api_path=f"/api/v2/addresses/{address}/logs", params={}
        )
        mock_process_logs.assert_called_once_with(mock_api_response["items"])
        assert isinstance(result, ToolResponse)
        assert result.data == []
        assert result.pagination is None
        assert mock_ctx.report_progress.call_count == 3
        assert mock_ctx.info.call_count == 3


@pytest.mark.asyncio
async def test_get_address_logs_with_truncation_note(mock_ctx):
    chain_id = "1"
    address = "0x123abc"
    mock_base_url = "https://eth.blockscout.com"
    truncated_item = {"data": "0xlong...", "data_truncated": True}
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
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response
        mock_process_logs.return_value = ([truncated_item], True)

        result = await get_address_logs(chain_id=chain_id, address=address, ctx=mock_ctx)

        mock_process_logs.assert_called_once_with(mock_api_response["items"])
        assert isinstance(result, ToolResponse)
        assert result.data[0].model_extra.get("data_truncated") is True
        assert result.notes is not None
        assert "One or more log items" in result.notes[0]
        assert f'`curl "{mock_base_url}/api/v2/transactions/{{THE_TRANSACTION_HASH}}/logs"`' in result.notes[2]


@pytest.mark.asyncio
async def test_get_address_logs_with_decoded_truncation_note(mock_ctx):
    chain_id = "1"
    address = "0x123abc"
    mock_base_url = "https://eth.blockscout.com"

    truncated_item = {
        "data": "0xshort",
        "decoded": {"parameters": [{"name": "foo", "value": {"value_sample": "0x", "value_truncated": True}}]},
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
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response
        mock_process_logs.return_value = ([truncated_item], True)

        result = await get_address_logs(chain_id=chain_id, address=address, ctx=mock_ctx)

        mock_process_logs.assert_called_once_with(mock_api_response["items"])
        assert isinstance(result, ToolResponse)
        assert result.data[0].model_extra.get("data_truncated") is None
        assert result.notes is not None
        assert "One or more log items" in result.notes[0]
        assert f'`curl "{mock_base_url}/api/v2/transactions/{{THE_TRANSACTION_HASH}}/logs"`' in result.notes[2]
