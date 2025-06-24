# tests/tools/test_chains_tools.py
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from blockscout_mcp_server.tools.chains_tools import get_chains_list


@pytest.mark.asyncio
async def test_get_chains_list_success(mock_ctx):
    """
    Verify that get_chains_list correctly processes a successful API response.
    """
    # 1. ARRANGE: Set up our mocks and test data.

    # This is the fake JSON data we want our mocked API call to return.
    mock_api_response = [
        {"name": "Ethereum", "chainid": "1"},
        {"name": "Polygon PoS", "chainid": "137"},
    ]

    # This is the expected string output from the tool function.
    expected_output = "The list of known chains with their ids:\nEthereum: 1\nPolygon PoS: 137"

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
        mock_request.assert_called_once_with(api_path="/api/chains/list")

        # Did the function return the correctly formatted string?
        assert result == expected_output

        # Was progress reported correctly? (Check the number of calls)
        assert mock_ctx.report_progress.call_count == 2
        assert mock_ctx.info.call_count == 2


@pytest.mark.asyncio
async def test_get_chains_list_empty_response(mock_ctx):
    """
    Verify that get_chains_list handles empty API responses gracefully.
    """
    # ARRANGE

    # Empty response
    mock_api_response = []
    expected_output = "The list of known chains with their ids:\nNo chains found or invalid response format."

    with patch(
        "blockscout_mcp_server.tools.chains_tools.make_chainscout_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = mock_api_response

        # ACT
        result = await get_chains_list(ctx=mock_ctx)

        # ASSERT
        mock_request.assert_called_once_with(api_path="/api/chains/list")
        assert result == expected_output
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
    expected_output = "The list of known chains with their ids:\nNo chains found or invalid response format."

    with patch(
        "blockscout_mcp_server.tools.chains_tools.make_chainscout_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = mock_api_response

        # ACT
        result = await get_chains_list(ctx=mock_ctx)

        # ASSERT
        mock_request.assert_called_once_with(api_path="/api/chains/list")
        assert result == expected_output
        assert mock_ctx.report_progress.call_count == 2
        assert mock_ctx.info.call_count == 2


@pytest.mark.asyncio
async def test_get_chains_list_chains_with_missing_fields(mock_ctx):
    """
    Verify that get_chains_list handles chains with missing name or chainid fields.
    """
    # ARRANGE

    # Mix of valid and invalid chain entries
    mock_api_response = [
        {"name": "Ethereum", "chainid": "1"},  # Valid
        {"name": "Incomplete Chain"},  # Missing chainid
        {"chainid": "137"},  # Missing name
        {"name": "Polygon PoS", "chainid": "137"},  # Valid
        {},  # Empty entry
    ]

    # Only valid entries should appear in output
    expected_output = "The list of known chains with their ids:\nEthereum: 1\nPolygon PoS: 137"

    with patch(
        "blockscout_mcp_server.tools.chains_tools.make_chainscout_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = mock_api_response

        # ACT
        result = await get_chains_list(ctx=mock_ctx)

        # ASSERT
        mock_request.assert_called_once_with(api_path="/api/chains/list")
        assert result == expected_output
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
        mock_request.assert_called_once_with(api_path="/api/chains/list")
        # Progress should have been reported once (at start) before the error
        assert mock_ctx.report_progress.call_count == 1
        assert mock_ctx.info.call_count == 1
