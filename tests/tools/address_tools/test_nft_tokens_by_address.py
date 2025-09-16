# tests/tools/test_address_tools_2.py
from unittest.mock import ANY, AsyncMock, MagicMock, patch

import httpx
import pytest

from blockscout_mcp_server.config import config
from blockscout_mcp_server.models import (
    NextCallInfo,
    NftCollectionHolding,
    PaginationInfo,
    ToolResponse,
)
from blockscout_mcp_server.tools.address_tools import (
    nft_tokens_by_address,
)
from blockscout_mcp_server.tools.common import encode_cursor


@pytest.mark.asyncio
async def test_nft_tokens_by_address_success(mock_ctx):
    """
    Verify nft_tokens_by_address correctly processes NFT token data with nested structure.
    """
    # ARRANGE
    chain_id = "1"
    address = "0x123abc"
    mock_base_url = "https://eth.blockscout.com"

    mock_api_response = {
        "items": [
            {
                "token": {
                    "name": "CryptoPunks",
                    "symbol": "PUNK",
                    "address_hash": "0xb47e3cd837ddf8e4c57f05d70ab865de6e193bbb",
                    "type": "ERC-721",
                    "holders_count": 1000,
                    "total_supply": 10000,
                },
                "amount": "3",
                "token_instances": [
                    {
                        "id": "123",
                        "metadata": {
                            "name": "Punk #123",
                            "attributes": [{"trait_type": "Color", "value": "Blue"}],
                        },
                    },
                    {
                        "id": "456",
                        "metadata": {
                            "name": "Punk #456",
                            "attributes": {"trait_type": "Common", "value": "Gray"},
                        },
                    },
                ],
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
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response

        # ACT
        result = await nft_tokens_by_address(chain_id=chain_id, address=address, ctx=mock_ctx)

        # ASSERT
        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(
            base_url=mock_base_url,
            api_path=f"/api/v2/addresses/{address}/nft/collections",
            params={"type": "ERC-721,ERC-404,ERC-1155"},
        )
        assert isinstance(result, ToolResponse)
        assert isinstance(result.data, list)
        assert len(result.data) == 1
        holding = result.data[0]
        assert isinstance(holding, NftCollectionHolding)
        assert holding.collection.name == "CryptoPunks"
        assert holding.collection.address == "0xb47e3cd837ddf8e4c57f05d70ab865de6e193bbb"
        assert len(holding.token_instances) == 2
        assert holding.token_instances[0].name == "Punk #123"
        # Test that list format metadata_attributes works
        assert isinstance(holding.token_instances[0].metadata_attributes, list)
        assert holding.token_instances[0].metadata_attributes[0]["trait_type"] == "Color"
        assert holding.token_instances[0].metadata_attributes[0]["value"] == "Blue"
        # Test that dict format metadata_attributes works
        assert isinstance(holding.token_instances[1].metadata_attributes, dict)
        assert holding.token_instances[1].metadata_attributes["trait_type"] == "Common"
        assert holding.token_instances[1].metadata_attributes["value"] == "Gray"
        assert mock_ctx.report_progress.call_count == 3
        assert mock_ctx.info.call_count == 3


@pytest.mark.asyncio
async def test_nft_tokens_by_address_empty_response(mock_ctx):
    """
    Verify nft_tokens_by_address handles empty NFT collections.
    """
    # ARRANGE
    chain_id = "1"
    address = "0x123abc"
    mock_base_url = "https://eth.blockscout.com"

    mock_api_response = {"items": []}

    with (
        patch(
            "blockscout_mcp_server.tools.address_tools.get_blockscout_base_url", new_callable=AsyncMock
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.address_tools.make_blockscout_request", new_callable=AsyncMock
        ) as mock_request,
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response

        # ACT
        result = await nft_tokens_by_address(chain_id=chain_id, address=address, ctx=mock_ctx)

        # ASSERT
        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(
            base_url=mock_base_url,
            api_path=f"/api/v2/addresses/{address}/nft/collections",
            params={"type": "ERC-721,ERC-404,ERC-1155"},
        )
        assert isinstance(result, ToolResponse)
        assert result.data == []
        assert mock_ctx.report_progress.call_count == 3
        assert mock_ctx.info.call_count == 3


@pytest.mark.asyncio
async def test_nft_tokens_by_address_missing_fields(mock_ctx):
    """
    Verify nft_tokens_by_address handles missing fields gracefully.
    """
    # ARRANGE
    chain_id = "1"
    address = "0x123abc"
    mock_base_url = "https://eth.blockscout.com"

    mock_api_response = {
        "items": [
            {
                "token": {
                    "name": None,  # Explicit None to test the fix
                    "symbol": None,  # Explicit None to test the fix
                    "address_hash": "0xincomplete123",
                    "type": "ERC-721",
                    "holders_count": 0,
                    "total_supply": 0,
                },
                "token_instances": [
                    {
                        "id": "999"
                        # Missing metadata
                    }
                ],
            },
            {
                "token": {"name": "Empty Token", "symbol": "EMPTY", "address_hash": "0xempty456", "type": "ERC-721"},
                "token_instances": [],  # Empty instances
            },
        ]
    }

    with (
        patch(
            "blockscout_mcp_server.tools.address_tools.get_blockscout_base_url", new_callable=AsyncMock
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.address_tools.make_blockscout_request", new_callable=AsyncMock
        ) as mock_request,
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response

        # ACT
        result = await nft_tokens_by_address(chain_id=chain_id, address=address, ctx=mock_ctx)

        # ASSERT
        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(
            base_url=mock_base_url,
            api_path=f"/api/v2/addresses/{address}/nft/collections",
            params={"type": "ERC-721,ERC-404,ERC-1155"},
        )
        assert isinstance(result, ToolResponse)
        assert len(result.data) == 2
        assert result.data[0].collection.address == "0xincomplete123"
        # Test that None values are handled properly
        assert result.data[0].collection.name is None
        assert result.data[0].collection.symbol is None
        assert result.data[0].token_instances[0].id == "999"
        assert result.data[1].collection.address == "0xempty456"
        assert result.data[1].token_instances == []
        assert mock_ctx.report_progress.call_count == 3
        assert mock_ctx.info.call_count == 3


@pytest.mark.asyncio
async def test_nft_tokens_by_address_api_error(mock_ctx):
    """
    Verify nft_tokens_by_address correctly propagates API errors.
    """
    # ARRANGE
    chain_id = "1"
    address = "0x123abc"
    mock_base_url = "https://eth.blockscout.com"

    api_error = httpx.HTTPStatusError("Bad Request", request=MagicMock(), response=MagicMock(status_code=400))

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
            await nft_tokens_by_address(chain_id=chain_id, address=address, ctx=mock_ctx)

        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(
            base_url=mock_base_url,
            api_path=f"/api/v2/addresses/{address}/nft/collections",
            params={"type": "ERC-721,ERC-404,ERC-1155"},
        )


@pytest.mark.asyncio
async def test_nft_tokens_by_address_erc1155(mock_ctx):
    """
    Verify nft_tokens_by_address handles ERC-1155 tokens correctly.
    """
    # ARRANGE
    chain_id = "1"
    address = "0x123abc"
    mock_base_url = "https://eth.blockscout.com"

    mock_api_response = {
        "items": [
            {
                "token": {
                    "name": "Multi-Token",
                    "symbol": "MULTI",
                    "address_hash": "0xmulti123",
                    "type": "ERC-1155",
                    "holders_count": 500,
                    "total_supply": 5000,
                },
                "amount": "10",
                "token_instances": [
                    {
                        "id": "1",
                        "metadata": {
                            "name": "Token #1",
                            "description": "First token",
                            "external_url": "https://example.com/1",
                            "attributes": [{"trait_type": "Color", "value": "Blue"}],
                        },
                    },
                    {"id": "2", "metadata": {"name": "Token #2", "attributes": []}},
                ],
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
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response

        # ACT
        result = await nft_tokens_by_address(chain_id=chain_id, address=address, ctx=mock_ctx)

        # ASSERT
        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(
            base_url=mock_base_url,
            api_path=f"/api/v2/addresses/{address}/nft/collections",
            params={"type": "ERC-721,ERC-404,ERC-1155"},
        )
        assert isinstance(result, ToolResponse)
        assert len(result.data) == 1
        holding = result.data[0]
        assert holding.collection.address == "0xmulti123"
        assert holding.token_instances[0].description == "First token"
        assert holding.token_instances[0].external_app_url == "https://example.com/1"
        assert mock_ctx.report_progress.call_count == 3
        assert mock_ctx.info.call_count == 3


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
            "blockscout_mcp_server.tools.address_tools.get_blockscout_base_url", new_callable=AsyncMock
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.address_tools.make_blockscout_request", new_callable=AsyncMock
        ) as mock_request,
        patch("blockscout_mcp_server.tools.address_tools.create_items_pagination") as mock_create_pagination,
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
        assert call_args[1]["page_size"] == 10  # default nft_page_size
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
    decoded_params = {"block_number": 100, "cursor": "bar"}
    cursor = encode_cursor(decoded_params)

    with (
        patch(
            "blockscout_mcp_server.tools.address_tools.get_blockscout_base_url", new_callable=AsyncMock
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.address_tools.make_blockscout_request", new_callable=AsyncMock
        ) as mock_request,
        patch("blockscout_mcp_server.tools.address_tools.apply_cursor_to_params") as mock_apply_cursor,
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
        "blockscout_mcp_server.tools.address_tools.apply_cursor_to_params",
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
            "blockscout_mcp_server.tools.address_tools.get_blockscout_base_url", new_callable=AsyncMock
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.address_tools.make_blockscout_request", new_callable=AsyncMock
        ) as mock_request,
        patch("blockscout_mcp_server.tools.address_tools.create_items_pagination") as mock_create_pagination,
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
        assert call_args[1]["page_size"] == 10  # default nft_page_size
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
            "blockscout_mcp_server.tools.address_tools.get_blockscout_base_url", new_callable=AsyncMock
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.address_tools.make_blockscout_request", new_callable=AsyncMock
        ) as mock_request,
        patch("blockscout_mcp_server.tools.address_tools.create_items_pagination") as mock_create_pagination,
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
        assert call_args[1]["page_size"] == 5  # custom nft_page_size
