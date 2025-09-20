from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from blockscout_mcp_server.models import TokenHoldingData, ToolResponse
from blockscout_mcp_server.tools.address.get_tokens_by_address import get_tokens_by_address
from blockscout_mcp_server.tools.common import encode_cursor


@pytest.mark.asyncio
async def test_get_tokens_by_address_with_pagination(mock_ctx):
    """
    Verify get_tokens_by_address correctly formats response and includes pagination hint.
    """
    # ARRANGE
    chain_id = "1"
    address = "0x123abc"
    mock_base_url = "https://eth.blockscout.com"

    mock_api_response = {
        "items": [
            {
                "token": {
                    "name": "MyToken",
                    "symbol": "MTK",
                    "address_hash": "0xabc123",
                    "decimals": "18",
                    "total_supply": "1000000",
                    "circulating_market_cap": "500000",
                    "exchange_rate": "1.5",
                    "volume_24h": "10000",
                    "holders_count": "150",
                },
                "value": "1000",
            },
            {
                "token": {
                    "name": "AnotherToken",
                    "symbol": "ATK",
                    "address_hash": "0xdef456",
                    "decimals": "6",
                    "total_supply": "2000000",
                    "circulating_market_cap": "800000",
                    "exchange_rate": "2.1",
                    "volume_24h": "15000",
                    "holders_count": "300",
                },
                "value": "2500",
            },
        ],
        "next_page_params": {"fiat_value": "123.45", "id": 5, "items_count": 50, "value": "1000"},
    }

    with (
        patch(
            "blockscout_mcp_server.tools.address.get_tokens_by_address.get_blockscout_base_url", new_callable=AsyncMock
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.address.get_tokens_by_address.make_blockscout_request", new_callable=AsyncMock
        ) as mock_request,
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response

        # ACT
        result = await get_tokens_by_address(chain_id=chain_id, address=address, ctx=mock_ctx)

        # ASSERT
        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(
            base_url=mock_base_url, api_path=f"/api/v2/addresses/{address}/tokens", params={"type": "ERC-20"}
        )

        assert isinstance(result, ToolResponse)
        assert isinstance(result.data, list)
        assert all(isinstance(item, TokenHoldingData) for item in result.data)

        first, second = result.data
        assert first.name == "MyToken"
        assert first.symbol == "MTK"
        assert first.address == "0xabc123"
        assert first.balance == "1000"

        assert second.name == "AnotherToken"
        assert second.symbol == "ATK"
        assert second.address == "0xdef456"
        assert second.balance == "2500"

        next_cursor = encode_cursor(mock_api_response["next_page_params"])
        assert result.pagination is not None
        assert result.pagination.next_call.params["cursor"] == next_cursor
        assert result.pagination.next_call.tool_name == "get_tokens_by_address"
        assert result.pagination.next_call.params["chain_id"] == chain_id
        assert result.pagination.next_call.params["address"] == address

        # Check progress reporting and logging
        assert mock_ctx.report_progress.await_count == 3
        assert mock_ctx.info.await_count == 3


@pytest.mark.asyncio
async def test_get_tokens_by_address_without_pagination(mock_ctx):
    """
    Verify get_tokens_by_address works correctly when there are no next page parameters.
    """
    # ARRANGE
    chain_id = "1"
    address = "0x123abc"
    mock_base_url = "https://eth.blockscout.com"

    mock_api_response = {
        "items": [
            {
                "token": {
                    "name": "SingleToken",
                    "symbol": "STK",
                    "address_hash": "0x111222",
                    "decimals": "18",
                    "total_supply": "500000",
                    "circulating_market_cap": "",
                    "exchange_rate": "",
                    "volume_24h": "",
                    "holders_count": "75",
                },
                "value": "100",
            }
        ]
        # No next_page_params
    }

    with (
        patch(
            "blockscout_mcp_server.tools.address.get_tokens_by_address.get_blockscout_base_url", new_callable=AsyncMock
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.address.get_tokens_by_address.make_blockscout_request", new_callable=AsyncMock
        ) as mock_request,
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response

        # ACT
        result = await get_tokens_by_address(chain_id=chain_id, address=address, ctx=mock_ctx)

        # ASSERT
        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(
            base_url=mock_base_url, api_path=f"/api/v2/addresses/{address}/tokens", params={"type": "ERC-20"}
        )

        assert isinstance(result, ToolResponse)
        assert isinstance(result.data, list)
        assert len(result.data) == 1
        token = result.data[0]
        assert isinstance(token, TokenHoldingData)
        assert token.name == "SingleToken"
        assert token.symbol == "STK"
        assert token.address == "0x111222"
        assert token.balance == "100"

        assert result.pagination is None

        # Check progress reporting and logging
        assert mock_ctx.report_progress.await_count == 3
        assert mock_ctx.info.await_count == 3


@pytest.mark.asyncio
async def test_get_tokens_by_address_with_pagination_params(mock_ctx):
    """
    Verify get_tokens_by_address correctly passes pagination parameters to API.
    """
    # ARRANGE
    chain_id = "1"
    address = "0x123abc"
    fiat_value = "999.99"
    id_param = 42
    items_count = 25
    value = "5000"
    mock_base_url = "https://eth.blockscout.com"

    mock_api_response = {
        "items": [],
        "next_page_params": {"fiat_value": "888.88", "id": 99, "items_count": 25, "value": "3000"},
    }

    with (
        patch(
            "blockscout_mcp_server.tools.address.get_tokens_by_address.get_blockscout_base_url", new_callable=AsyncMock
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.address.get_tokens_by_address.make_blockscout_request", new_callable=AsyncMock
        ) as mock_request,
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response

        # ACT
        result = await get_tokens_by_address(
            chain_id=chain_id,
            address=address,
            cursor=encode_cursor(
                {"fiat_value": fiat_value, "id": id_param, "items_count": items_count, "value": value}
            ),
            ctx=mock_ctx,
        )

        # ASSERT
        mock_get_url.assert_called_once_with(chain_id)

        # Verify that all pagination parameters were passed to the API
        expected_params = {
            "type": "ERC-20",
            "fiat_value": fiat_value,
            "id": id_param,
            "items_count": items_count,
            "value": value,
        }
        mock_request.assert_called_once_with(
            base_url=mock_base_url, api_path=f"/api/v2/addresses/{address}/tokens", params=expected_params
        )

        assert isinstance(result, ToolResponse)
        next_cursor = encode_cursor({"fiat_value": "888.88", "id": 99, "items_count": 25, "value": "3000"})
        assert result.pagination is not None
        assert result.pagination.next_call.params["cursor"] == next_cursor
        assert result.pagination.next_call.tool_name == "get_tokens_by_address"
        assert result.pagination.next_call.params["chain_id"] == chain_id
        assert result.pagination.next_call.params["address"] == address

        # Check progress reporting and logging
        assert mock_ctx.report_progress.await_count == 3
        assert mock_ctx.info.await_count == 3


@pytest.mark.asyncio
async def test_get_tokens_by_address_invalid_cursor(mock_ctx):
    """Verify the tool returns a user-friendly error for a bad cursor."""
    chain_id = "1"
    address = "0x123abc"
    invalid_cursor = "this-is-bad"

    with pytest.raises(ValueError):
        await get_tokens_by_address(chain_id=chain_id, address=address, cursor=invalid_cursor, ctx=mock_ctx)

    assert mock_ctx.report_progress.await_count == 0
    assert mock_ctx.info.await_count == 0


@pytest.mark.asyncio
async def test_get_tokens_by_address_empty_response(mock_ctx):
    """
    Verify get_tokens_by_address handles empty responses gracefully.
    """
    # ARRANGE
    chain_id = "1"
    address = "0x123abc"
    mock_base_url = "https://eth.blockscout.com"

    mock_api_response = {
        "items": []
        # No next_page_params
    }

    with (
        patch(
            "blockscout_mcp_server.tools.address.get_tokens_by_address.get_blockscout_base_url", new_callable=AsyncMock
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.address.get_tokens_by_address.make_blockscout_request", new_callable=AsyncMock
        ) as mock_request,
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response

        # ACT
        result = await get_tokens_by_address(chain_id=chain_id, address=address, ctx=mock_ctx)

        # ASSERT
        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(
            base_url=mock_base_url, api_path=f"/api/v2/addresses/{address}/tokens", params={"type": "ERC-20"}
        )

        assert isinstance(result, ToolResponse)
        assert result.data == []
        assert result.pagination is None

        # Check progress reporting and logging
        assert mock_ctx.report_progress.await_count == 3
        assert mock_ctx.info.await_count == 3


@pytest.mark.asyncio
async def test_get_tokens_by_address_missing_token_fields(mock_ctx):
    """
    Verify get_tokens_by_address handles missing or null token fields gracefully.
    """
    # ARRANGE
    chain_id = "1"
    address = "0x123abc"
    mock_base_url = "https://eth.blockscout.com"

    # Mock response with incomplete token data
    mock_api_response = {
        "items": [
            {
                "token": {
                    "name": None,  # Missing name
                    "symbol": "UNK",
                    "address_hash": "0x999888",
                    # Missing decimals, total_supply, etc.
                },
                "value": "123",
            },
            {
                "token": {},  # Completely empty token object
                "value": "456",
            },
        ]
    }

    with (
        patch(
            "blockscout_mcp_server.tools.address.get_tokens_by_address.get_blockscout_base_url", new_callable=AsyncMock
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.address.get_tokens_by_address.make_blockscout_request", new_callable=AsyncMock
        ) as mock_request,
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response

        # ACT
        result = await get_tokens_by_address(chain_id=chain_id, address=address, ctx=mock_ctx)

        # ASSERT
        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(
            base_url=mock_base_url, api_path=f"/api/v2/addresses/{address}/tokens", params={"type": "ERC-20"}
        )

        assert isinstance(result, ToolResponse)
        assert len(result.data) == 2
        assert isinstance(result.data[0], TokenHoldingData)
        assert result.data[0].symbol == "UNK"
        assert result.data[0].address == "0x999888"
        assert result.data[0].balance == "123"
        # Optional defaults when fields are missing
        assert result.data[0].name == ""
        assert result.data[0].decimals == ""
        assert result.data[0].total_supply == ""
        assert result.data[1].balance == "456"
        assert result.data[1].name == ""
        assert result.data[1].symbol == ""
        assert result.data[1].address == ""

        assert result.pagination is None

        # Check progress reporting and logging
        assert mock_ctx.report_progress.await_count == 3
        assert mock_ctx.info.await_count == 3


@pytest.mark.asyncio
async def test_get_tokens_by_address_api_error(mock_ctx):
    """
    Verify get_tokens_by_address correctly propagates API errors.
    """
    # ARRANGE
    chain_id = "1"
    address = "0x123abc"
    mock_base_url = "https://eth.blockscout.com"

    # Simulate a 404 error from the API
    api_error = httpx.HTTPStatusError("Not Found", request=MagicMock(), response=MagicMock(status_code=404))

    with (
        patch(
            "blockscout_mcp_server.tools.address.get_tokens_by_address.get_blockscout_base_url", new_callable=AsyncMock
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.address.get_tokens_by_address.make_blockscout_request", new_callable=AsyncMock
        ) as mock_request,
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.side_effect = api_error

        # ACT & ASSERT
        with pytest.raises(httpx.HTTPStatusError):
            await get_tokens_by_address(chain_id=chain_id, address=address, ctx=mock_ctx)

        # Verify mocks were called as expected before the exception
        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(
            base_url=mock_base_url, api_path=f"/api/v2/addresses/{address}/tokens", params={"type": "ERC-20"}
        )
        # Progress should have been reported twice (start + after chain URL resolution) before the error
        assert mock_ctx.report_progress.await_count == 2
        assert mock_ctx.info.await_count == 2
