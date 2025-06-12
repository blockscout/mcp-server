# tests/tools/test_address_tools.py
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import httpx
import json

from blockscout_mcp_server.tools.address_tools import (
    get_tokens_by_address,
    get_address_info,
)
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
                    "holders_count": "150"
                },
                "value": "1000"
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
                    "holders_count": "300"
                },
                "value": "2500"
            }
        ],
        "next_page_params": {
            "fiat_value": "123.45",
            "id": 5,
            "items_count": 50,
            "value": "1000"
        }
    }

    with patch('blockscout_mcp_server.tools.address_tools.get_blockscout_base_url', new_callable=AsyncMock) as mock_get_url, \
         patch('blockscout_mcp_server.tools.address_tools.make_blockscout_request', new_callable=AsyncMock) as mock_request:

        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response

        # ACT
        result = await get_tokens_by_address(chain_id=chain_id, address=address, ctx=mock_ctx)

        # ASSERT
        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(
            base_url=mock_base_url,
            api_path=f"/api/v2/addresses/{address}/tokens",
            params={"tokens": "ERC-20"}
        )

        # Check that the main content from mock API response is present (data flow verification)
        assert '"name": "MyToken"' in result
        assert '"symbol": "MTK"' in result
        assert '"address": "0xabc123"' in result
        assert '"balance": "1000"' in result

        assert '"name": "AnotherToken"' in result
        assert '"symbol": "ATK"' in result
        assert '"address": "0xdef456"' in result
        assert '"balance": "2500"' in result

        # Check that the pagination hint is correctly formatted and included
        next_cursor = encode_cursor(mock_api_response["next_page_params"])
        expected_pagination = (
            f'To get the next page call get_tokens_by_address(chain_id="{chain_id}", address="{address}", cursor="{next_cursor}")'
        )
        assert expected_pagination in result
        
        # Check JSON array structure
        assert result.startswith('[')
        assert ']' in result
        
        # Check progress reporting
        assert mock_ctx.report_progress.call_count == 3

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
                    "holders_count": "75"
                },
                "value": "100"
            }
        ]
        # No next_page_params
    }

    with patch('blockscout_mcp_server.tools.address_tools.get_blockscout_base_url', new_callable=AsyncMock) as mock_get_url, \
         patch('blockscout_mcp_server.tools.address_tools.make_blockscout_request', new_callable=AsyncMock) as mock_request:

        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response

        # ACT
        result = await get_tokens_by_address(chain_id=chain_id, address=address, ctx=mock_ctx)

        # ASSERT
        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(
            base_url=mock_base_url,
            api_path=f"/api/v2/addresses/{address}/tokens",
            params={"tokens": "ERC-20"}
        )

        # Check that the main content from mock API response is present (data flow verification)
        assert '"name": "SingleToken"' in result
        assert '"symbol": "STK"' in result
        assert '"address": "0x111222"' in result
        assert '"balance": "100"' in result
        
        # Check that no pagination hint is included
        assert "To get the next page call" not in result
        
        # Check JSON array structure
        assert result.startswith('[')
        assert result.endswith(']')
        
        # Check progress reporting
        assert mock_ctx.report_progress.call_count == 3

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
        "next_page_params": {
            "fiat_value": "888.88",
            "id": 99,
            "items_count": 25,
            "value": "3000"
        }
    }

    with patch('blockscout_mcp_server.tools.address_tools.get_blockscout_base_url', new_callable=AsyncMock) as mock_get_url, \
         patch('blockscout_mcp_server.tools.address_tools.make_blockscout_request', new_callable=AsyncMock) as mock_request:

        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response

        # ACT
        result = await get_tokens_by_address(
            chain_id=chain_id,
            address=address,
            cursor=encode_cursor({"fiat_value": fiat_value, "id": id_param, "items_count": items_count, "value": value}),
            ctx=mock_ctx
        )

        # ASSERT
        mock_get_url.assert_called_once_with(chain_id)
        
        # Verify that all pagination parameters were passed to the API
        expected_params = {
            "tokens": "ERC-20",
            "fiat_value": fiat_value,
            "id": id_param,
            "items_count": items_count,
            "value": value,
        }
        mock_request.assert_called_once_with(
            base_url=mock_base_url,
            api_path=f"/api/v2/addresses/{address}/tokens",
            params=expected_params
        )

        # Check that pagination hint reflects the new parameters
        next_cursor = encode_cursor({"fiat_value": "888.88", "id": 99, "items_count": 25, "value": "3000"})
        expected_pagination = f'To get the next page call get_tokens_by_address(chain_id="{chain_id}", address="{address}", cursor="{next_cursor}")'
        assert expected_pagination in result
        
        # Check progress reporting
        assert mock_ctx.report_progress.call_count == 3

@pytest.mark.asyncio
async def test_get_tokens_by_address_invalid_cursor(mock_ctx):
    """Verify the tool returns a user-friendly error for a bad cursor."""
    chain_id = "1"
    address = "0x123abc"
    invalid_cursor = "this-is-bad"

    result = await get_tokens_by_address(chain_id=chain_id, address=address, cursor=invalid_cursor, ctx=mock_ctx)

    assert "Error: Invalid or expired pagination cursor." in result

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

    with patch('blockscout_mcp_server.tools.address_tools.get_blockscout_base_url', new_callable=AsyncMock) as mock_get_url, \
         patch('blockscout_mcp_server.tools.address_tools.make_blockscout_request', new_callable=AsyncMock) as mock_request:

        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response

        # ACT
        result = await get_tokens_by_address(chain_id=chain_id, address=address, ctx=mock_ctx)

        # ASSERT
        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(
            base_url=mock_base_url,
            api_path=f"/api/v2/addresses/{address}/tokens",
            params={"tokens": "ERC-20"}
        )

        # Check that we get an empty JSON array
        assert result == "[]"
        
        # Check progress reporting
        assert mock_ctx.report_progress.call_count == 3

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
                "value": "123"
            },
            {
                "token": {},  # Completely empty token object
                "value": "456"
            }
        ]
    }

    with patch('blockscout_mcp_server.tools.address_tools.get_blockscout_base_url', new_callable=AsyncMock) as mock_get_url, \
         patch('blockscout_mcp_server.tools.address_tools.make_blockscout_request', new_callable=AsyncMock) as mock_request:

        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response

        # ACT
        result = await get_tokens_by_address(chain_id=chain_id, address=address, ctx=mock_ctx)

        # ASSERT
        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(
            base_url=mock_base_url,
            api_path=f"/api/v2/addresses/{address}/tokens",
            params={"tokens": "ERC-20"}
        )

        # Check that the content from mock API response is present (data flow verification)
        # For this test, checking that the values from the mock response appear in output
        assert '"symbol": "UNK"' in result
        assert '"address": "0x999888"' in result  
        assert '"balance": "123"' in result
        assert '"balance": "456"' in result
        
        # Check JSON array structure
        assert result.startswith('[')
        assert result.endswith(']')
        
        # Check progress reporting
        assert mock_ctx.report_progress.call_count == 3

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

    with patch('blockscout_mcp_server.tools.address_tools.get_blockscout_base_url', new_callable=AsyncMock) as mock_get_url, \
         patch('blockscout_mcp_server.tools.address_tools.make_blockscout_request', new_callable=AsyncMock) as mock_request:

        mock_get_url.return_value = mock_base_url
        mock_request.side_effect = api_error

        # ACT & ASSERT
        with pytest.raises(httpx.HTTPStatusError):
            await get_tokens_by_address(chain_id=chain_id, address=address, ctx=mock_ctx)

        # Verify mocks were called as expected before the exception
        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(
            base_url=mock_base_url,
            api_path=f"/api/v2/addresses/{address}/tokens",
            params={"tokens": "ERC-20"}
        )
        # Progress should have been reported twice (start + after chain URL resolution) before the error
        assert mock_ctx.report_progress.call_count == 2

@pytest.mark.asyncio
async def test_get_address_info_success_with_metadata(mock_ctx):
    """
    Verify get_address_info correctly combines data from Blockscout and Metadata APIs.
    """
    chain_id = "1"
    address = "0x123abc"
    mock_base_url = "https://eth.blockscout.com"

    mock_blockscout_response = {
        "hash": address,
        "is_contract": True,
    }
    mock_metadata_response = {
        "addresses": {address: {"tags": [{"name": "Test Tag"}]}}
    }

    with patch('blockscout_mcp_server.tools.address_tools.get_blockscout_base_url', new_callable=AsyncMock) as mock_get_url, \
         patch('blockscout_mcp_server.tools.address_tools.make_blockscout_request', new_callable=AsyncMock) as mock_bs_request, \
         patch('blockscout_mcp_server.tools.address_tools.make_metadata_request', new_callable=AsyncMock) as mock_meta_request:

        mock_get_url.return_value = mock_base_url
        mock_bs_request.return_value = mock_blockscout_response
        mock_meta_request.return_value = mock_metadata_response

        result = await get_address_info(chain_id=chain_id, address=address, ctx=mock_ctx)

        mock_get_url.assert_called_once_with(chain_id)
        mock_bs_request.assert_called_once_with(
            base_url=mock_base_url,
            api_path=f"/api/v2/addresses/{address}"
        )
        mock_meta_request.assert_called_once_with(
            api_path="/api/v1/metadata",
            params={"addresses": address, "chainId": chain_id}
        )

        assert "Basic address info:" in result
        assert json.dumps(mock_blockscout_response) in result
        assert "Metadata associated with the address:" in result
        assert json.dumps(mock_metadata_response["addresses"][address]) in result

        assert mock_ctx.report_progress.call_count == 4


@pytest.mark.asyncio
async def test_get_address_info_success_without_metadata(mock_ctx):
    """
    Verify get_address_info correctly omits metadata section when it's not found.
    """
    chain_id = "1"
    address = "0x123abc"
    mock_base_url = "https://eth.blockscout.com"

    mock_blockscout_response = {"hash": address, "is_contract": False}
    mock_metadata_response = {"addresses": {}}

    with patch('blockscout_mcp_server.tools.address_tools.get_blockscout_base_url', new_callable=AsyncMock) as mock_get_url, \
         patch('blockscout_mcp_server.tools.address_tools.make_blockscout_request', new_callable=AsyncMock) as mock_bs_request, \
         patch('blockscout_mcp_server.tools.address_tools.make_metadata_request', new_callable=AsyncMock) as mock_meta_request:

        mock_get_url.return_value = mock_base_url
        mock_bs_request.return_value = mock_blockscout_response
        mock_meta_request.return_value = mock_metadata_response

        result = await get_address_info(chain_id=chain_id, address=address, ctx=mock_ctx)

        assert "Basic address info:" in result
        assert json.dumps(mock_blockscout_response) in result
        assert "Metadata associated with the address:" not in result

        assert mock_ctx.report_progress.call_count == 4
