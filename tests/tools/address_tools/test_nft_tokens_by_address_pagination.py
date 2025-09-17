from unittest.mock import ANY, AsyncMock, patch

import pytest

from blockscout_mcp_server.config import config
from blockscout_mcp_server.models import (
    NextCallInfo,
    PaginationInfo,
    ToolResponse,
)
from blockscout_mcp_server.tools.address.nft_tokens_by_address import (
    nft_tokens_by_address,
)
from blockscout_mcp_server.tools.common import encode_cursor


@pytest.mark.asyncio
async def test_nft_tokens_by_address_with_pagination(mock_ctx):
    """Verify pagination hint is included when next_page_params present."""
    chain_id = "1"
    address = "0x123abc"
    mock_base_url = "https://eth.blockscout.com"

    items = [
        {
            "token": {"address_hash": f"0xhash{i}", "type": "ERC-721"},
            "amount": "1",
            "token_instances": [],
        }
        for i in range(11)
    ]
    mock_api_response = {"items": items}
    fake_cursor = "ENCODED_CURSOR"

    mock_pagination = PaginationInfo(
        next_call=NextCallInfo(
            tool_name="nft_tokens_by_address",
            params={"chain_id": chain_id, "address": address, "cursor": fake_cursor},
        )
    )

    with (
        patch(
            "blockscout_mcp_server.tools.address.nft_tokens_by_address.get_blockscout_base_url", new_callable=AsyncMock
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.address.nft_tokens_by_address.make_blockscout_request", new_callable=AsyncMock
        ) as mock_request,
        patch("blockscout_mcp_server.tools.address.nft_tokens_by_address.create_items_pagination") as mock_create_pagination,
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response

        # Create processed items format that the function expects
        processed_items = []
        for item in items[:10]:
            token = item.get("token", {})
            processed_item = {
                "token": token,
                "amount": item.get("amount", ""),
                "token_instances": [],
                "collection_info": {
                    "type": token.get("type", ""),
                    "address": token.get("address_hash", ""),
                    "name": token.get("name"),
                    "symbol": token.get("symbol"),
                    "holders_count": token.get("holders_count") or 0,
                    "total_supply": token.get("total_supply") or 0,
                },
            }
            processed_items.append(processed_item)

        # Return processed items and pagination info
        mock_create_pagination.return_value = (processed_items, mock_pagination)

        result = await nft_tokens_by_address(chain_id=chain_id, address=address, ctx=mock_ctx)

        # Verify create_items_pagination was called with correct parameters
        mock_create_pagination.assert_called_once()
        call_args = mock_create_pagination.call_args
        assert call_args[1]["page_size"] == config.nft_page_size
        assert call_args[1]["tool_name"] == "nft_tokens_by_address"
        assert call_args[1]["next_call_base_params"] == {"chain_id": chain_id, "address": address}
        assert callable(call_args[1]["cursor_extractor"])
        assert call_args[1]["force_pagination"] is False

        assert isinstance(result, ToolResponse)
        assert isinstance(result.pagination, PaginationInfo)
        assert result.pagination.next_call.tool_name == "nft_tokens_by_address"
        assert result.pagination.next_call.params["cursor"] == fake_cursor


@pytest.mark.asyncio
async def test_nft_tokens_by_address_with_cursor(mock_ctx):
    """Verify decoded cursor parameters are passed to the API call."""
    chain_id = "1"
    address = "0x123abc"
    mock_base_url = "https://eth.blockscout.com"
    decoded_params = {"block_number": 100, "index": 1, "items_count": 25}
    cursor = encode_cursor(decoded_params)

    with (
        patch(
            "blockscout_mcp_server.tools.address.nft_tokens_by_address.get_blockscout_base_url", new_callable=AsyncMock
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.address.nft_tokens_by_address.make_blockscout_request", new_callable=AsyncMock
        ) as mock_request,
        patch("blockscout_mcp_server.tools.address.nft_tokens_by_address.apply_cursor_to_params") as mock_apply_cursor,
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.return_value = {"items": []}
        mock_apply_cursor.side_effect = lambda cur, params: params.update(decoded_params)

        await nft_tokens_by_address(chain_id=chain_id, address=address, cursor=cursor, ctx=mock_ctx)

        mock_apply_cursor.assert_called_once_with(cursor, ANY)
        mock_request.assert_called_once_with(
            base_url=mock_base_url,
            api_path=f"/api/v2/addresses/{address}/nft/collections",
            params={"type": "ERC-721,ERC-404,ERC-1155", **decoded_params},
        )


@pytest.mark.asyncio
async def test_nft_tokens_by_address_invalid_cursor(mock_ctx):
    """Verify ValueError is raised for an invalid cursor."""
    chain_id = "1"
    address = "0x123abc"
    invalid_cursor = "bad_cursor"

    with patch(
        "blockscout_mcp_server.tools.address.nft_tokens_by_address.apply_cursor_to_params",
        side_effect=ValueError("bad"),
    ):
        with pytest.raises(ValueError, match="bad"):
            await nft_tokens_by_address(chain_id=chain_id, address=address, cursor=invalid_cursor, ctx=mock_ctx)


@pytest.mark.asyncio
async def test_nft_tokens_by_address_response_sliced(mock_ctx):
    chain_id = "1"
    address = "0x123abc"
    mock_base_url = "https://eth.blockscout.com"

    items = [
        {
            "token": {"address_hash": f"0xhash{i}", "type": "ERC-721"},
            "amount": "1",
            "token_instances": [],
        }
        for i in range(15)
    ]
    mock_api_response = {"items": items}

    mock_pagination = PaginationInfo(
        next_call=NextCallInfo(
            tool_name="nft_tokens_by_address",
            params={"chain_id": chain_id, "address": address, "cursor": "CURSOR"},
        )
    )

    with (
        patch(
            "blockscout_mcp_server.tools.address.nft_tokens_by_address.get_blockscout_base_url", new_callable=AsyncMock
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.address.nft_tokens_by_address.make_blockscout_request", new_callable=AsyncMock
        ) as mock_request,
        patch("blockscout_mcp_server.tools.address.nft_tokens_by_address.create_items_pagination") as mock_create_pagination,
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response

        # Create processed items format that the function expects
        processed_items = []
        for item in items[:10]:
            token = item.get("token", {})
            processed_item = {
                "token": token,
                "amount": item.get("amount", ""),
                "token_instances": [],
                "collection_info": {
                    "type": token.get("type", ""),
                    "address": token.get("address_hash", ""),
                    "name": token.get("name"),
                    "symbol": token.get("symbol"),
                    "holders_count": token.get("holders_count") or 0,
                    "total_supply": token.get("total_supply") or 0,
                },
            }
            processed_items.append(processed_item)

        # Return processed items and pagination info
        mock_create_pagination.return_value = (processed_items, mock_pagination)

        result = await nft_tokens_by_address(chain_id=chain_id, address=address, ctx=mock_ctx)

        assert len(result.data) == 10
        assert result.pagination is not None
        # Verify create_items_pagination was called with correct parameters
        mock_create_pagination.assert_called_once()
        call_args = mock_create_pagination.call_args
        assert call_args[1]["page_size"] == config.nft_page_size
        assert call_args[1]["tool_name"] == "nft_tokens_by_address"


@pytest.mark.asyncio
async def test_nft_tokens_by_address_custom_page_size(mock_ctx):
    chain_id = "1"
    address = "0x123abc"
    mock_base_url = "https://eth.blockscout.com"

    items = [
        {
            "token": {"address_hash": f"0xhash{i}", "type": "ERC-721"},
            "amount": "1",
            "token_instances": [],
        }
        for i in range(10)
    ]
    mock_api_response = {"items": items}

    mock_pagination = PaginationInfo(
        next_call=NextCallInfo(
            tool_name="nft_tokens_by_address",
            params={"chain_id": chain_id, "address": address, "cursor": "CURSOR"},
        )
    )

    with (
        patch(
            "blockscout_mcp_server.tools.address.nft_tokens_by_address.get_blockscout_base_url", new_callable=AsyncMock
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.address.nft_tokens_by_address.make_blockscout_request", new_callable=AsyncMock
        ) as mock_request,
        patch("blockscout_mcp_server.tools.address.nft_tokens_by_address.create_items_pagination") as mock_create_pagination,
        patch.object(config, "nft_page_size", 5),
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response

        # Create processed items format that the function expects
        processed_items = []
        for item in items[:5]:
            token = item.get("token", {})
            processed_item = {
                "token": token,
                "amount": item.get("amount", ""),
                "token_instances": [],
                "collection_info": {
                    "type": token.get("type", ""),
                    "address": token.get("address_hash", ""),
                    "name": token.get("name"),
                    "symbol": token.get("symbol"),
                    "holders_count": token.get("holders_count") or 0,
                    "total_supply": token.get("total_supply") or 0,
                },
            }
            processed_items.append(processed_item)

        # Return processed items and pagination info
        mock_create_pagination.return_value = (processed_items, mock_pagination)

        result = await nft_tokens_by_address(chain_id=chain_id, address=address, ctx=mock_ctx)

        assert len(result.data) == 5
        assert result.pagination is not None
        # Verify create_items_pagination was called with custom page size
        mock_create_pagination.assert_called_once()
        call_args = mock_create_pagination.call_args
        assert call_args[1]["page_size"] == 5
