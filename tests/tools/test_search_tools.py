# tests/tools/test_search_tools.py
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from blockscout_mcp_server.models import TokenSearchResult
from blockscout_mcp_server.tools.common import build_tool_response
from blockscout_mcp_server.tools.search_tools import (
    TOKEN_RESULTS_LIMIT,
    lookup_token_by_symbol,
)


@pytest.mark.asyncio
async def test_lookup_token_by_symbol_success(mock_ctx):
    """
    Verify lookup_token_by_symbol correctly processes a successful token search.
    """
    # ARRANGE
    chain_id = "1"
    symbol = "USDC"
    mock_base_url = "https://eth.blockscout.com"

    mock_api_response = {
        "items": [
            {
                "address_hash": "0xa0b86a33e6dd0ba3c70de3b8e2b9e48cd6efb7b0",
                "name": "USD Coin",
                "symbol": "USDC",
                "total_supply": "1000000000",
                "circulating_market_cap": "500000000",
                "exchange_rate": "1.0",
            },
            {
                "address_hash": "0xb0b86a33e6dd0ba3c70de3b8e2b9e48cd6efb7b1",
                "name": "USD Coin (Alternative)",
                "symbol": "USDC",
                "total_supply": "2000000000",
                "circulating_market_cap": "600000000",
                "exchange_rate": "0.99",
            },
        ]
    }

    # **It's Still DAMP (Descriptive and Meaningful Phrases):** The logic for
    # generating the expected result is simple, contained within the test, and
    # explicitly documents the transformations
    # **It's More DRY (Don't Repeat Yourself):** No need to manually copy all
    # the values
    expected_data = [
        TokenSearchResult(
            address=item.get("address_hash", ""),
            name=item.get("name", ""),
            symbol=item.get("symbol", ""),
            token_type="",
            total_supply=item.get("total_supply", ""),
            circulating_market_cap=item.get("circulating_market_cap"),
            exchange_rate=item.get("exchange_rate"),
            is_smart_contract_verified=False,
            is_verified_via_admin_panel=False,
        )
        for item in mock_api_response["items"]
    ]
    expected_result = build_tool_response(data=expected_data)

    with (
        patch(
            "blockscout_mcp_server.tools.search_tools.get_blockscout_base_url", new_callable=AsyncMock
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.search_tools.make_blockscout_request", new_callable=AsyncMock
        ) as mock_request,
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response

        # ACT
        result = await lookup_token_by_symbol(chain_id=chain_id, symbol=symbol, ctx=mock_ctx)

        # ASSERT
        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(base_url=mock_base_url, api_path="/api/v2/search", params={"q": symbol})
        assert result == expected_result
        assert mock_ctx.report_progress.call_count == 3
        assert mock_ctx.info.call_count == 3


@pytest.mark.asyncio
async def test_lookup_token_by_symbol_limit_more_than_seven(mock_ctx):
    """Verify only the first 7 items are returned when API provides more."""
    chain_id = "1"
    symbol = "TEST"
    mock_base_url = "https://eth.blockscout.com"

    mock_items = [
        {
            "address_hash": f"0x{i:040d}",
            "name": f"Token{i}",
            "symbol": "TEST",
            "total_supply": str(i),
            "circulating_market_cap": str(i * 10),
            "exchange_rate": "1.0",
        }
        for i in range(8)
    ]

    mock_api_response = {"items": mock_items}

    expected_data = [
        TokenSearchResult(
            address=item.get("address_hash", ""),
            name=item.get("name", ""),
            symbol=item.get("symbol", ""),
            token_type="",
            total_supply=item.get("total_supply", ""),
            circulating_market_cap=item.get("circulating_market_cap"),
            exchange_rate=item.get("exchange_rate"),
            is_smart_contract_verified=False,
            is_verified_via_admin_panel=False,
        )
        for item in mock_items[:TOKEN_RESULTS_LIMIT]
    ]

    expected_notes = [
        (
            f"The number of results exceeds the limit of {TOKEN_RESULTS_LIMIT}. "
            f"Only the first {TOKEN_RESULTS_LIMIT} are shown."
        )
    ]
    expected_result = build_tool_response(data=expected_data, notes=expected_notes)

    with (
        patch(
            "blockscout_mcp_server.tools.search_tools.get_blockscout_base_url", new_callable=AsyncMock
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.search_tools.make_blockscout_request", new_callable=AsyncMock
        ) as mock_request,
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response

        result = await lookup_token_by_symbol(chain_id=chain_id, symbol=symbol, ctx=mock_ctx)

        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(base_url=mock_base_url, api_path="/api/v2/search", params={"q": symbol})
        assert result == expected_result
        assert len(result.data) == 7
        assert mock_ctx.report_progress.call_count == 3
        assert mock_ctx.info.call_count == 3
        assert mock_ctx.info.call_count == 3


@pytest.mark.asyncio
async def test_lookup_token_by_symbol_limit_exactly_seven(mock_ctx):
    """Verify all 7 items are returned when API provides exactly seven."""
    chain_id = "1"
    symbol = "TEST"
    mock_base_url = "https://eth.blockscout.com"

    mock_items = [
        {
            "address_hash": f"0x{i:040d}",
            "name": f"Token{i}",
            "symbol": "TEST",
            "total_supply": str(i),
            "circulating_market_cap": str(i * 10),
            "exchange_rate": "1.0",
        }
        for i in range(7)
    ]

    mock_api_response = {"items": mock_items}

    expected_data = [
        TokenSearchResult(
            address=item.get("address_hash", ""),
            name=item.get("name", ""),
            symbol=item.get("symbol", ""),
            token_type="",
            total_supply=item.get("total_supply", ""),
            circulating_market_cap=item.get("circulating_market_cap"),
            exchange_rate=item.get("exchange_rate"),
            is_smart_contract_verified=False,
            is_verified_via_admin_panel=False,
        )
        for item in mock_items
    ]
    expected_result = build_tool_response(data=expected_data)

    with (
        patch(
            "blockscout_mcp_server.tools.search_tools.get_blockscout_base_url", new_callable=AsyncMock
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.search_tools.make_blockscout_request", new_callable=AsyncMock
        ) as mock_request,
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response

        result = await lookup_token_by_symbol(chain_id=chain_id, symbol=symbol, ctx=mock_ctx)

        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(base_url=mock_base_url, api_path="/api/v2/search", params={"q": symbol})
        assert result == expected_result
        assert len(result.data) == 7
        assert mock_ctx.report_progress.call_count == 3


@pytest.mark.asyncio
async def test_lookup_token_by_symbol_empty_results(mock_ctx):
    """
    Verify lookup_token_by_symbol handles empty search results.
    """
    # ARRANGE
    chain_id = "1"
    symbol = "NONEXISTENT"
    mock_base_url = "https://eth.blockscout.com"

    mock_api_response = {"items": []}
    expected_result = build_tool_response(data=[])

    with (
        patch(
            "blockscout_mcp_server.tools.search_tools.get_blockscout_base_url", new_callable=AsyncMock
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.search_tools.make_blockscout_request", new_callable=AsyncMock
        ) as mock_request,
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response

        # ACT
        result = await lookup_token_by_symbol(chain_id=chain_id, symbol=symbol, ctx=mock_ctx)

        # ASSERT
        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(base_url=mock_base_url, api_path="/api/v2/search", params={"q": symbol})
        assert result == expected_result
        assert mock_ctx.report_progress.call_count == 3


@pytest.mark.asyncio
async def test_lookup_token_by_symbol_missing_fields(mock_ctx):
    """
    Verify lookup_token_by_symbol handles tokens with missing fields gracefully.
    """
    # ARRANGE
    chain_id = "1"
    symbol = "PARTIAL"
    mock_base_url = "https://eth.blockscout.com"

    mock_api_response = {
        "items": [
            {
                "address_hash": "0xa0b86a33e6dd0ba3c70de3b8e2b9e48cd6efb7b0",
                "name": "Partial Token",
                "symbol": "PARTIAL",
                # Missing token_type, total_supply, etc.
            },
            {
                "address_hash": "0xb0b86a33e6dd0ba3c70de3b8e2b9e48cd6efb7b1",
                "name": "",  # Empty name
                "symbol": "PARTIAL",
                "token_type": "ERC-20",
                # Some fields present, some missing
            },
        ]
    }

    expected_data = [
        TokenSearchResult(
            address=item.get("address_hash", ""),
            name=item.get("name", ""),
            symbol=item.get("symbol", ""),
            token_type=item.get("token_type", ""),
            total_supply=item.get("total_supply", ""),
            circulating_market_cap=item.get("circulating_market_cap"),
            exchange_rate=item.get("exchange_rate"),
            is_smart_contract_verified=False,
            is_verified_via_admin_panel=False,
        )
        for item in mock_api_response["items"]
    ]
    expected_result = build_tool_response(data=expected_data)

    with (
        patch(
            "blockscout_mcp_server.tools.search_tools.get_blockscout_base_url", new_callable=AsyncMock
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.search_tools.make_blockscout_request", new_callable=AsyncMock
        ) as mock_request,
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response

        # ACT
        result = await lookup_token_by_symbol(chain_id=chain_id, symbol=symbol, ctx=mock_ctx)

        # ASSERT
        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(base_url=mock_base_url, api_path="/api/v2/search", params={"q": symbol})
        assert result == expected_result
        assert mock_ctx.report_progress.call_count == 3


@pytest.mark.asyncio
async def test_lookup_token_by_symbol_api_error(mock_ctx):
    """
    Verify lookup_token_by_symbol correctly propagates API errors.
    """
    # ARRANGE
    chain_id = "1"
    symbol = "ERROR"
    mock_base_url = "https://eth.blockscout.com"

    api_error = httpx.HTTPStatusError("Internal Server Error", request=MagicMock(), response=MagicMock(status_code=500))

    with (
        patch(
            "blockscout_mcp_server.tools.search_tools.get_blockscout_base_url", new_callable=AsyncMock
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.search_tools.make_blockscout_request", new_callable=AsyncMock
        ) as mock_request,
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.side_effect = api_error

        # ACT & ASSERT
        with pytest.raises(httpx.HTTPStatusError):
            await lookup_token_by_symbol(chain_id=chain_id, symbol=symbol, ctx=mock_ctx)

        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(base_url=mock_base_url, api_path="/api/v2/search", params={"q": symbol})


@pytest.mark.asyncio
async def test_lookup_token_by_symbol_chain_not_found(mock_ctx):
    """
    Verify lookup_token_by_symbol correctly handles chain not found errors.
    """
    # ARRANGE
    chain_id = "999999"
    symbol = "TEST"

    from blockscout_mcp_server.tools.common import ChainNotFoundError

    chain_error = ChainNotFoundError(f"Chain with ID '{chain_id}' not found on Chainscout.")

    with patch(
        "blockscout_mcp_server.tools.search_tools.get_blockscout_base_url", new_callable=AsyncMock
    ) as mock_get_url:
        mock_get_url.side_effect = chain_error

        # ACT & ASSERT
        with pytest.raises(ChainNotFoundError):
            await lookup_token_by_symbol(chain_id=chain_id, symbol=symbol, ctx=mock_ctx)

        mock_get_url.assert_called_once_with(chain_id)


@pytest.mark.asyncio
async def test_lookup_token_by_symbol_no_items_field(mock_ctx):
    """
    Verify lookup_token_by_symbol handles response without items field.
    """
    # ARRANGE
    chain_id = "1"
    symbol = "TEST"
    mock_base_url = "https://eth.blockscout.com"

    mock_api_response = {}  # No items field
    expected_result = build_tool_response(data=[])

    with (
        patch(
            "blockscout_mcp_server.tools.search_tools.get_blockscout_base_url", new_callable=AsyncMock
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.search_tools.make_blockscout_request", new_callable=AsyncMock
        ) as mock_request,
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response

        # ACT
        result = await lookup_token_by_symbol(chain_id=chain_id, symbol=symbol, ctx=mock_ctx)

        # ASSERT
        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(base_url=mock_base_url, api_path="/api/v2/search", params={"q": symbol})
        assert result == expected_result
        assert mock_ctx.report_progress.call_count == 3
