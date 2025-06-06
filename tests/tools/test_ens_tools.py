# tests/tools/test_ens_tools.py
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import httpx

from blockscout_mcp_server.tools.ens_tools import get_address_by_ens_name

@pytest.mark.asyncio
async def test_get_address_by_ens_name_success():
    """
    Verify get_address_by_ens_name correctly processes a successful ENS resolution.
    """
    # ARRANGE
    mock_ctx = MagicMock()
    mock_ctx.report_progress = AsyncMock()
    ens_name = "blockscout.eth"

    mock_api_response = {
        "resolved_address": {
            "hash": "0x1234567890abcdef1234567890abcdef12345678"
        }
    }
    expected_result = {
        "resolved_address": "0x1234567890abcdef1234567890abcdef12345678"
    }

    with patch('blockscout_mcp_server.tools.ens_tools.make_bens_request', new_callable=AsyncMock) as mock_request:
        mock_request.return_value = mock_api_response

        # ACT
        result = await get_address_by_ens_name(name=ens_name, ctx=mock_ctx)

        # ASSERT
        mock_request.assert_called_once_with(api_path=f"/api/v1/1/domains/{ens_name}")
        assert result == expected_result
        assert mock_ctx.report_progress.call_count == 2

@pytest.mark.asyncio
async def test_get_address_by_ens_name_missing_resolved_address():
    """
    Verify get_address_by_ens_name handles missing resolved_address field.
    """
    # ARRANGE
    mock_ctx = MagicMock()
    mock_ctx.report_progress = AsyncMock()
    ens_name = "nonexistent.eth"

    mock_api_response = {}  # No resolved_address field
    expected_result = {"resolved_address": None}

    with patch('blockscout_mcp_server.tools.ens_tools.make_bens_request', new_callable=AsyncMock) as mock_request:
        mock_request.return_value = mock_api_response

        # ACT
        result = await get_address_by_ens_name(name=ens_name, ctx=mock_ctx)

        # ASSERT
        mock_request.assert_called_once_with(api_path=f"/api/v1/1/domains/{ens_name}")
        assert result == expected_result
        assert mock_ctx.report_progress.call_count == 2

@pytest.mark.asyncio
async def test_get_address_by_ens_name_missing_hash():
    """
    Verify get_address_by_ens_name handles missing hash field in resolved_address.
    """
    # ARRANGE
    mock_ctx = MagicMock()
    mock_ctx.report_progress = AsyncMock()
    ens_name = "incomplete.eth"

    mock_api_response = {
        "resolved_address": {}  # No hash field
    }
    expected_result = {"resolved_address": None}

    with patch('blockscout_mcp_server.tools.ens_tools.make_bens_request', new_callable=AsyncMock) as mock_request:
        mock_request.return_value = mock_api_response

        # ACT
        result = await get_address_by_ens_name(name=ens_name, ctx=mock_ctx)

        # ASSERT
        mock_request.assert_called_once_with(api_path=f"/api/v1/1/domains/{ens_name}")
        assert result == expected_result
        assert mock_ctx.report_progress.call_count == 2

@pytest.mark.asyncio
async def test_get_address_by_ens_name_api_error():
    """
    Verify get_address_by_ens_name correctly propagates API errors.
    """
    # ARRANGE
    mock_ctx = MagicMock()
    mock_ctx.report_progress = AsyncMock()
    ens_name = "error.eth"

    api_error = httpx.HTTPStatusError("Not Found", request=MagicMock(), response=MagicMock(status_code=404))

    with patch('blockscout_mcp_server.tools.ens_tools.make_bens_request', new_callable=AsyncMock) as mock_request:
        mock_request.side_effect = api_error

        # ACT & ASSERT
        with pytest.raises(httpx.HTTPStatusError):
            await get_address_by_ens_name(name=ens_name, ctx=mock_ctx)

        mock_request.assert_called_once_with(api_path=f"/api/v1/1/domains/{ens_name}")

@pytest.mark.asyncio
async def test_get_address_by_ens_name_with_special_characters():
    """
    Verify get_address_by_ens_name handles ENS names with special characters.
    """
    # ARRANGE
    mock_ctx = MagicMock()
    mock_ctx.report_progress = AsyncMock()
    ens_name = "test-domain_123.eth"

    mock_api_response = {
        "resolved_address": {
            "hash": "0xabcdef1234567890abcdef1234567890abcdef12"
        }
    }
    expected_result = {
        "resolved_address": "0xabcdef1234567890abcdef1234567890abcdef12"
    }

    with patch('blockscout_mcp_server.tools.ens_tools.make_bens_request', new_callable=AsyncMock) as mock_request:
        mock_request.return_value = mock_api_response

        # ACT
        result = await get_address_by_ens_name(name=ens_name, ctx=mock_ctx)

        # ASSERT
        mock_request.assert_called_once_with(api_path=f"/api/v1/1/domains/{ens_name}")
        assert result == expected_result
        assert mock_ctx.report_progress.call_count == 2

@pytest.mark.asyncio
async def test_get_address_by_ens_name_timeout_error():
    """
    Verify get_address_by_ens_name correctly handles timeout errors.
    """
    # ARRANGE
    mock_ctx = MagicMock()
    mock_ctx.report_progress = AsyncMock()
    ens_name = "timeout.eth"

    timeout_error = httpx.TimeoutException("Request timed out")

    with patch('blockscout_mcp_server.tools.ens_tools.make_bens_request', new_callable=AsyncMock) as mock_request:
        mock_request.side_effect = timeout_error

        # ACT & ASSERT
        with pytest.raises(httpx.TimeoutException):
            await get_address_by_ens_name(name=ens_name, ctx=mock_ctx)

        mock_request.assert_called_once_with(api_path=f"/api/v1/1/domains/{ens_name}") 