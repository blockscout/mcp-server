# tests/tools/test_chains_tools.py
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from blockscout_mcp_server.models import ChainInfo, ToolResponse
from blockscout_mcp_server.tools.chains_tools import get_chains_list
from blockscout_mcp_server.tools.common import chains_list_cache


@pytest.fixture(autouse=True)
def clear_chains_list_cache():
    chains_list_cache.chains_snapshot = None
    chains_list_cache.expiry_timestamp = 0.0
    yield
    chains_list_cache.chains_snapshot = None
    chains_list_cache.expiry_timestamp = 0.0


@pytest.mark.asyncio
async def test_get_chains_list_success(mock_ctx):
    """
    Verify that get_chains_list correctly processes a successful API response.
    """
    # 1. ARRANGE: Set up our mocks and test data.

    # This is the fake JSON data we want our mocked API call to return.
    mock_api_response = {
        "1": {
            "name": "Ethereum",
            "isTestnet": False,
            "native_currency": "ETH",
            "ecosystem": "Ethereum",
            "explorers": [{"hostedBy": "blockscout", "url": "https://eth"}],
        },
        "137": {
            "name": "Polygon PoS",
            "isTestnet": False,
            "native_currency": "POL",
            "ecosystem": "Polygon",
            "explorers": [{"hostedBy": "blockscout", "url": "https://polygon"}],
        },
    }

    expected_data = [
        ChainInfo(
            name="Ethereum",
            chain_id="1",
            is_testnet=False,
            native_currency="ETH",
            ecosystem="Ethereum",
        ),
        ChainInfo(
            name="Polygon PoS",
            chain_id="137",
            is_testnet=False,
            native_currency="POL",
            ecosystem="Polygon",
        ),
    ]

    # Use `patch` to replace the real `make_chainscout_request` with our mock.
    # The string points to where the function is *used*.
    with patch(
        "blockscout_mcp_server.tools.chains_tools.make_chainscout_request", new_callable=AsyncMock
    ) as mock_request:
        # Configure our mock to return our fake data when it's called.
        mock_request.return_value = mock_api_response

        # 2. ACT: Call the actual tool function we want to test.
        result = await get_chains_list(ctx=mock_ctx)

        # 3. ASSERT: Check if the function behaved as expected.

        # Was the API helper called correctly?
        mock_request.assert_called_once_with(api_path="/api/chains")

        assert isinstance(result, ToolResponse)
        assert result.data == expected_data

        # Was progress reported correctly? (Check the number of calls)
        assert mock_ctx.report_progress.call_count == 2
        assert mock_ctx.info.call_count == 2


@pytest.mark.asyncio
async def test_get_chains_list_caches_filtered_chains(mock_ctx):
    """Verify that get_chains_list caches only chains with Blockscout explorers."""
    mock_api_response = {
        "1": {"name": "Ethereum", "explorers": [{"hostedBy": "blockscout", "url": "https://eth"}]},
        "999": {"name": "No Blockscout", "explorers": [{"hostedBy": "other", "url": "https://other"}]},
    }

    with patch(
        "blockscout_mcp_server.tools.chains_tools.make_chainscout_request", new_callable=AsyncMock
    ) as mock_request:
        with patch("blockscout_mcp_server.tools.chains_tools.chain_cache") as mock_cache:
            mock_request.return_value = mock_api_response

            await get_chains_list(ctx=mock_ctx)

            mock_cache.bulk_set.assert_called_once()
            cached = mock_cache.bulk_set.call_args.args[0]
            assert cached == {"1": "https://eth"}


@pytest.mark.asyncio
async def test_get_chains_list_empty_response(mock_ctx):
    """
    Verify that get_chains_list handles empty API responses gracefully.
    """
    # ARRANGE

    # Empty response
    mock_api_response = {}
    expected_data: list[ChainInfo] = []

    with patch(
        "blockscout_mcp_server.tools.chains_tools.make_chainscout_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = mock_api_response

        # ACT
        result = await get_chains_list(ctx=mock_ctx)

        # ASSERT
        mock_request.assert_called_once_with(api_path="/api/chains")
        assert isinstance(result, ToolResponse)
        assert result.data == expected_data
        assert mock_ctx.report_progress.call_count == 2
        assert mock_ctx.info.call_count == 2


@pytest.mark.asyncio
async def test_get_chains_list_invalid_response_format(mock_ctx):
    """
    Verify that get_chains_list handles invalid response formats gracefully.
    """
    # ARRANGE

    # Invalid response (not a list)
    mock_api_response = {"error": "Invalid data"}
    expected_data: list[ChainInfo] = []

    with patch(
        "blockscout_mcp_server.tools.chains_tools.make_chainscout_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = mock_api_response

        # ACT
        result = await get_chains_list(ctx=mock_ctx)

        # ASSERT
        mock_request.assert_called_once_with(api_path="/api/chains")
        assert isinstance(result, ToolResponse)
        assert result.data == expected_data
        assert mock_ctx.report_progress.call_count == 2
        assert mock_ctx.info.call_count == 2


@pytest.mark.asyncio
async def test_get_chains_list_chains_with_missing_fields(mock_ctx):
    """
    Verify that get_chains_list handles chains with missing name or chainid fields.
    """
    # ARRANGE

    # Mix of valid and invalid chain entries
    mock_api_response = {
        "1": {
            "name": "Ethereum",
            "isTestnet": False,
            "native_currency": "ETH",
            "ecosystem": "Ethereum",
            "explorers": [{"hostedBy": "blockscout", "url": "https://eth"}],
        },
        "invalid": {"name": "Incomplete Chain"},
        "137": {
            "name": "Polygon PoS",
            "isTestnet": False,
            "native_currency": "POL",
            "ecosystem": "Polygon",
            "explorers": [{"hostedBy": "blockscout", "url": "https://polygon"}],
        },
        "empty": {},
    }

    expected_data = [
        ChainInfo(
            name="Ethereum",
            chain_id="1",
            is_testnet=False,
            native_currency="ETH",
            ecosystem="Ethereum",
        ),
        ChainInfo(
            name="Polygon PoS",
            chain_id="137",
            is_testnet=False,
            native_currency="POL",
            ecosystem="Polygon",
        ),
    ]

    with patch(
        "blockscout_mcp_server.tools.chains_tools.make_chainscout_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = mock_api_response

        # ACT
        result = await get_chains_list(ctx=mock_ctx)

        # ASSERT
        mock_request.assert_called_once_with(api_path="/api/chains")
        assert isinstance(result, ToolResponse)
        assert result.data == expected_data
        assert mock_ctx.report_progress.call_count == 2
        assert mock_ctx.info.call_count == 2


@pytest.mark.asyncio
async def test_get_chains_list_api_error(mock_ctx):
    """
    Verify the tool correctly propagates an exception when the API call fails.
    """
    # We'll simulate a network error from the API
    import httpx

    api_error = httpx.HTTPStatusError("Service Unavailable", request=MagicMock(), response=MagicMock(status_code=503))

    with patch(
        "blockscout_mcp_server.tools.chains_tools.make_chainscout_request", new_callable=AsyncMock
    ) as mock_request:
        # Configure the mock to raise the error instead of returning a value
        mock_request.side_effect = api_error

        # ACT & ASSERT
        # Use pytest.raises to assert that the specific exception is raised.
        with pytest.raises(httpx.HTTPStatusError):
            await get_chains_list(ctx=mock_ctx)

        # Verify mock was called as expected before the exception
        mock_request.assert_called_once_with(api_path="/api/chains")
        # Progress should have been reported once (at start) before the error
        assert mock_ctx.report_progress.call_count == 1
        assert mock_ctx.info.call_count == 1
