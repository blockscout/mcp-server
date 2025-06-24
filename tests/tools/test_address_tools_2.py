# tests/tools/test_address_tools_2.py
import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

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
                    {"id": "123", "metadata": {"name": "Punk #123", "attributes": []}},
                    {"id": "456", "metadata": {"name": "Punk #456", "attributes": []}},
                ],
            }
        ]
    }

    expected_result = [
        {
            "collection": {
                "type": "ERC-721",
                "address": "0xb47e3cd837ddf8e4c57f05d70ab865de6e193bbb",
                "name": "CryptoPunks",
                "symbol": "PUNK",
                "holders_count": 1000,
                "total_supply": 10000,
            },
            "amount": "3",
            "token_instances": [{"id": "123", "name": "Punk #123"}, {"id": "456", "name": "Punk #456"}],
        }
    ]

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
        result_json = json.loads(result)
        assert result_json == expected_result
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
    expected_result = []

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
        result_json = json.loads(result)
        assert result_json == expected_result
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
                    "name": "Incomplete NFT",
                    "address_hash": "0xincomplete123",
                    # Missing symbol, type, holders_count, total_supply
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

    expected_result = [
        {
            "collection": {
                "type": "",
                "address": "0xincomplete123",
                "name": "Incomplete NFT",
                "symbol": "",
                "holders_count": 0,
                "total_supply": 0,
            },
            "amount": "",
            "token_instances": [{"id": "999"}],
        },
        {
            "collection": {
                "type": "ERC-721",
                "address": "0xempty456",
                "name": "Empty Token",
                "symbol": "EMPTY",
                "holders_count": 0,
                "total_supply": 0,
            },
            "amount": "",
            "token_instances": [],
        },
    ]

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
        result_json = json.loads(result)
        assert result_json == expected_result
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

    expected_result = [
        {
            "collection": {
                "type": "ERC-1155",
                "address": "0xmulti123",
                "name": "Multi-Token",
                "symbol": "MULTI",
                "holders_count": 500,
                "total_supply": 5000,
            },
            "amount": "10",
            "token_instances": [
                {
                    "id": "1",
                    "name": "Token #1",
                    "description": "First token",
                    "external_app_url": "https://example.com/1",
                    "metadata_attributes": [{"trait_type": "Color", "value": "Blue"}],
                },
                {"id": "2", "name": "Token #2"},
            ],
        }
    ]

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
        result_json = json.loads(result)
        assert result_json == expected_result
        assert mock_ctx.report_progress.call_count == 3
        assert mock_ctx.info.call_count == 3


@pytest.mark.asyncio
async def test_nft_tokens_by_address_with_pagination(mock_ctx):
    """Verify pagination hint is included when next_page_params present."""
    chain_id = "1"
    address = "0x123abc"
    mock_base_url = "https://eth.blockscout.com"

    mock_api_response = {"items": [], "next_page_params": {"block_number": 123, "cursor": "foo"}}
    fake_cursor = "ENCODED_CURSOR"

    with (
        patch(
            "blockscout_mcp_server.tools.address_tools.get_blockscout_base_url", new_callable=AsyncMock
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.address_tools.make_blockscout_request", new_callable=AsyncMock
        ) as mock_request,
        patch("blockscout_mcp_server.tools.address_tools.encode_cursor") as mock_encode_cursor,
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response
        mock_encode_cursor.return_value = fake_cursor

        result = await nft_tokens_by_address(chain_id=chain_id, address=address, ctx=mock_ctx)

        mock_encode_cursor.assert_called_once_with(mock_api_response["next_page_params"])
        assert f'cursor="{fake_cursor}"' in result
        assert "To get the next page call" in result


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
        patch("blockscout_mcp_server.tools.address_tools.decode_cursor") as mock_decode_cursor,
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.return_value = {"items": []}
        mock_decode_cursor.return_value = decoded_params

        await nft_tokens_by_address(chain_id=chain_id, address=address, cursor=cursor, ctx=mock_ctx)

        mock_decode_cursor.assert_called_once_with(cursor)
        mock_request.assert_called_once_with(
            base_url=mock_base_url,
            api_path=f"/api/v2/addresses/{address}/nft/collections",
            params={"type": "ERC-721,ERC-404,ERC-1155", **decoded_params},
        )
