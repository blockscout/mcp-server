# tests/tools/test_search_tools.py
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import httpx

from blockscout_mcp_server.tools.search_tools import lookup_token_by_symbol

@pytest.mark.asyncio
async def test_lookup_token_by_symbol_success():
    """
    Verify lookup_token_by_symbol correctly processes a successful token search.
    """
    # ARRANGE
    mock_ctx = MagicMock()
    mock_ctx.report_progress = AsyncMock()
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
                "exchange_rate": "1.0"
            },
            {
                "address_hash": "0xb0b86a33e6dd0ba3c70de3b8e2b9e48cd6efb7b1",
                "name": "USD Coin (Alternative)",
                "symbol": "USDC",
                "total_supply": "2000000000",
                "circulating_market_cap": "600000000",
                "exchange_rate": "0.99"
            }
        ]
    }

    expected_result = [
        {
            "address": "0xa0b86a33e6dd0ba3c70de3b8e2b9e48cd6efb7b0",
            "name": "USD Coin",
            "symbol": "USDC",
            "token_type": "",
            "total_supply": "1000000000",
            "circulating_market_cap": "500000000",
            "exchange_rate": "1.0",
            "is_smart_contract_verified": False,
            "is_verified_via_admin_panel": False
        },
        {
            "address": "0xb0b86a33e6dd0ba3c70de3b8e2b9e48cd6efb7b1",
            "name": "USD Coin (Alternative)",
            "symbol": "USDC",
            "token_type": "",
            "total_supply": "2000000000",
            "circulating_market_cap": "600000000",
            "exchange_rate": "0.99",
            "is_smart_contract_verified": False,
            "is_verified_via_admin_panel": False
        }
    ]

    with patch('blockscout_mcp_server.tools.search_tools.get_blockscout_base_url', new_callable=AsyncMock) as mock_get_url, \
         patch('blockscout_mcp_server.tools.search_tools.make_blockscout_request', new_callable=AsyncMock) as mock_request:

        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response

        # ACT
        result = await lookup_token_by_symbol(chain_id=chain_id, symbol=symbol, ctx=mock_ctx)

        # ASSERT
        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(
            base_url=mock_base_url,
            api_path="/api/v2/search",
            params={"q": symbol}
        )
        assert result == expected_result
        assert mock_ctx.report_progress.call_count == 3

@pytest.mark.asyncio
async def test_lookup_token_by_symbol_empty_results():
    """
    Verify lookup_token_by_symbol handles empty search results.
    """
    # ARRANGE
    mock_ctx = MagicMock()
    mock_ctx.report_progress = AsyncMock()
    chain_id = "1"
    symbol = "NONEXISTENT"
    mock_base_url = "https://eth.blockscout.com"

    mock_api_response = {"items": []}
    expected_result = []

    with patch('blockscout_mcp_server.tools.search_tools.get_blockscout_base_url', new_callable=AsyncMock) as mock_get_url, \
         patch('blockscout_mcp_server.tools.search_tools.make_blockscout_request', new_callable=AsyncMock) as mock_request:

        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response

        # ACT
        result = await lookup_token_by_symbol(chain_id=chain_id, symbol=symbol, ctx=mock_ctx)

        # ASSERT
        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(
            base_url=mock_base_url,
            api_path="/api/v2/search",
            params={"q": symbol}
        )
        assert result == expected_result
        assert mock_ctx.report_progress.call_count == 3

@pytest.mark.asyncio
async def test_lookup_token_by_symbol_missing_fields():
    """
    Verify lookup_token_by_symbol handles tokens with missing fields gracefully.
    """
    # ARRANGE
    mock_ctx = MagicMock()
    mock_ctx.report_progress = AsyncMock()
    chain_id = "1"
    symbol = "PARTIAL"
    mock_base_url = "https://eth.blockscout.com"

    mock_api_response = {
        "items": [
            {
                "address_hash": "0xa0b86a33e6dd0ba3c70de3b8e2b9e48cd6efb7b0",
                "name": "Partial Token",
                "symbol": "PARTIAL"
                # Missing token_type, total_supply, etc.
            },
            {
                "address_hash": "0xb0b86a33e6dd0ba3c70de3b8e2b9e48cd6efb7b1",
                "name": "",  # Empty name
                "symbol": "PARTIAL",
                "token_type": "ERC-20"
                # Some fields present, some missing
            }
        ]
    }

    expected_result = [
        {
            "address": "0xa0b86a33e6dd0ba3c70de3b8e2b9e48cd6efb7b0",
            "name": "Partial Token",
            "symbol": "PARTIAL",
            "token_type": "",
            "total_supply": "",
            "circulating_market_cap": "",
            "exchange_rate": "",
            "is_smart_contract_verified": False,
            "is_verified_via_admin_panel": False
        },
        {
            "address": "0xb0b86a33e6dd0ba3c70de3b8e2b9e48cd6efb7b1",
            "name": "",
            "symbol": "PARTIAL",
            "token_type": "ERC-20",
            "total_supply": "",
            "circulating_market_cap": "",
            "exchange_rate": "",
            "is_smart_contract_verified": False,
            "is_verified_via_admin_panel": False
        }
    ]

    with patch('blockscout_mcp_server.tools.search_tools.get_blockscout_base_url', new_callable=AsyncMock) as mock_get_url, \
         patch('blockscout_mcp_server.tools.search_tools.make_blockscout_request', new_callable=AsyncMock) as mock_request:

        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response

        # ACT
        result = await lookup_token_by_symbol(chain_id=chain_id, symbol=symbol, ctx=mock_ctx)

        # ASSERT
        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(
            base_url=mock_base_url,
            api_path="/api/v2/search",
            params={"q": symbol}
        )
        assert result == expected_result
        assert mock_ctx.report_progress.call_count == 3

@pytest.mark.asyncio
async def test_lookup_token_by_symbol_api_error():
    """
    Verify lookup_token_by_symbol correctly propagates API errors.
    """
    # ARRANGE
    mock_ctx = MagicMock()
    mock_ctx.report_progress = AsyncMock()
    chain_id = "1"
    symbol = "ERROR"
    mock_base_url = "https://eth.blockscout.com"

    api_error = httpx.HTTPStatusError("Internal Server Error", request=MagicMock(), response=MagicMock(status_code=500))

    with patch('blockscout_mcp_server.tools.search_tools.get_blockscout_base_url', new_callable=AsyncMock) as mock_get_url, \
         patch('blockscout_mcp_server.tools.search_tools.make_blockscout_request', new_callable=AsyncMock) as mock_request:

        mock_get_url.return_value = mock_base_url
        mock_request.side_effect = api_error

        # ACT & ASSERT
        with pytest.raises(httpx.HTTPStatusError):
            await lookup_token_by_symbol(chain_id=chain_id, symbol=symbol, ctx=mock_ctx)

        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(
            base_url=mock_base_url,
            api_path="/api/v2/search",
            params={"q": symbol}
        )

@pytest.mark.asyncio
async def test_lookup_token_by_symbol_chain_not_found():
    """
    Verify lookup_token_by_symbol correctly handles chain not found errors.
    """
    # ARRANGE
    mock_ctx = MagicMock()
    mock_ctx.report_progress = AsyncMock()
    chain_id = "999999"
    symbol = "TEST"

    from blockscout_mcp_server.tools.common import ChainNotFoundError
    chain_error = ChainNotFoundError(f"Chain with ID '{chain_id}' not found on Chainscout.")

    with patch('blockscout_mcp_server.tools.search_tools.get_blockscout_base_url', new_callable=AsyncMock) as mock_get_url:
        mock_get_url.side_effect = chain_error

        # ACT & ASSERT
        with pytest.raises(ChainNotFoundError):
            await lookup_token_by_symbol(chain_id=chain_id, symbol=symbol, ctx=mock_ctx)

        mock_get_url.assert_called_once_with(chain_id)

@pytest.mark.asyncio
async def test_lookup_token_by_symbol_no_items_field():
    """
    Verify lookup_token_by_symbol handles response without items field.
    """
    # ARRANGE
    mock_ctx = MagicMock()
    mock_ctx.report_progress = AsyncMock()
    chain_id = "1"
    symbol = "TEST"
    mock_base_url = "https://eth.blockscout.com"

    mock_api_response = {}  # No items field
    expected_result = []

    with patch('blockscout_mcp_server.tools.search_tools.get_blockscout_base_url', new_callable=AsyncMock) as mock_get_url, \
         patch('blockscout_mcp_server.tools.search_tools.make_blockscout_request', new_callable=AsyncMock) as mock_request:

        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response

        # ACT
        result = await lookup_token_by_symbol(chain_id=chain_id, symbol=symbol, ctx=mock_ctx)

        # ASSERT
        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(
            base_url=mock_base_url,
            api_path="/api/v2/search",
            params={"q": symbol}
        )
        assert result == expected_result
        assert mock_ctx.report_progress.call_count == 3 