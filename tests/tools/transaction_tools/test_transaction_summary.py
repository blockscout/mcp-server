from unittest.mock import AsyncMock, patch

import pytest

from blockscout_mcp_server.models import ToolResponse, TransactionSummaryData
from blockscout_mcp_server.tools.transaction_tools import transaction_summary


@pytest.mark.asyncio
async def test_transaction_summary_without_wrapper(mock_ctx):
    """
    Test a transaction tool that doesn't use the periodic progress wrapper for comparison.
    This helps verify our testing approach for wrapper vs non-wrapper tools.
    """
    # ARRANGE
    chain_id = "1"
    tx_hash = "0x123abc"
    mock_base_url = "https://eth.blockscout.com"

    summary_obj = {"template": "This is a test transaction summary.", "vars": {}}
    mock_api_response = {"data": {"summaries": [summary_obj]}}

    with (
        patch(
            "blockscout_mcp_server.tools.transaction_tools.get_blockscout_base_url", new_callable=AsyncMock
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.transaction_tools.make_blockscout_request", new_callable=AsyncMock
        ) as mock_request,
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response

        # ACT
        result = await transaction_summary(chain_id=chain_id, transaction_hash=tx_hash, ctx=mock_ctx)

        # ASSERT
        assert isinstance(result, ToolResponse)
        assert isinstance(result.data, TransactionSummaryData)
        assert result.data.summary == [summary_obj]
        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(base_url=mock_base_url, api_path=f"/api/v2/transactions/{tx_hash}/summary")

        # This tool should have 3 progress reports (start, after URL, completion)
        assert mock_ctx.report_progress.call_count == 3
        assert mock_ctx.info.call_count == 3


@pytest.mark.asyncio
async def test_transaction_summary_no_summary_available(mock_ctx):
    """
    Test transaction_summary when no summary is available in the response.
    """
    # ARRANGE
    chain_id = "1"
    tx_hash = "0x123abc"
    mock_base_url = "https://eth.blockscout.com"

    # Response with no summary data
    mock_api_response = {"data": {}}

    with (
        patch(
            "blockscout_mcp_server.tools.transaction_tools.get_blockscout_base_url", new_callable=AsyncMock
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.transaction_tools.make_blockscout_request", new_callable=AsyncMock
        ) as mock_request,
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response

        # ACT
        result = await transaction_summary(chain_id=chain_id, transaction_hash=tx_hash, ctx=mock_ctx)

        # ASSERT
        assert isinstance(result, ToolResponse)
        assert isinstance(result.data, TransactionSummaryData)
        assert result.data.summary is None
        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(base_url=mock_base_url, api_path=f"/api/v2/transactions/{tx_hash}/summary")
        assert mock_ctx.report_progress.call_count == 3
        assert mock_ctx.info.call_count == 3


@pytest.mark.asyncio
async def test_transaction_summary_handles_non_string_summary(mock_ctx):
    """Verify transaction_summary correctly handles a non-string summary."""
    # ARRANGE
    chain_id = "1"
    tx_hash = "0xcomplex"
    mock_base_url = "https://eth.blockscout.com"

    complex_summary = [
        {"template": "Summary 1", "vars": {"a": 1}},
        {"template": "Summary 2", "vars": {"b": 2}},
    ]
    mock_api_response = {"data": {"summaries": complex_summary}}

    with (
        patch(
            "blockscout_mcp_server.tools.transaction_tools.get_blockscout_base_url",
            new_callable=AsyncMock,
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.transaction_tools.make_blockscout_request",
            new_callable=AsyncMock,
        ) as mock_request,
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response

        # ACT
        result = await transaction_summary(chain_id=chain_id, transaction_hash=tx_hash, ctx=mock_ctx)

        # ASSERT
        assert isinstance(result, ToolResponse)
        assert isinstance(result.data, TransactionSummaryData)
        assert result.data.summary == complex_summary  # Assert it's the original list
        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(base_url=mock_base_url, api_path=f"/api/v2/transactions/{tx_hash}/summary")
        assert mock_ctx.report_progress.call_count == 3
        assert mock_ctx.info.call_count == 3


@pytest.mark.asyncio
async def test_transaction_summary_handles_empty_list(mock_ctx):
    """Return an empty list when Blockscout summarizes to nothing."""
    chain_id = "1"
    tx_hash = "0xempty"
    mock_base_url = "https://eth.blockscout.com"

    mock_api_response = {"data": {"summaries": []}}

    with (
        patch(
            "blockscout_mcp_server.tools.transaction_tools.get_blockscout_base_url",
            new_callable=AsyncMock,
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.transaction_tools.make_blockscout_request",
            new_callable=AsyncMock,
        ) as mock_request,
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response

        result = await transaction_summary(chain_id=chain_id, transaction_hash=tx_hash, ctx=mock_ctx)

        assert isinstance(result, ToolResponse)
        assert isinstance(result.data, TransactionSummaryData)
        assert result.data.summary == []
        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(base_url=mock_base_url, api_path=f"/api/v2/transactions/{tx_hash}/summary")
        assert mock_ctx.report_progress.call_count == 3
        assert mock_ctx.info.call_count == 3


@pytest.mark.asyncio
async def test_transaction_summary_invalid_format(mock_ctx):
    """Raise RuntimeError when Blockscout returns unexpected summary format."""
    chain_id = "1"
    tx_hash = "0xdeadbeef"
    mock_base_url = "https://eth.blockscout.com"

    mock_api_response = {"data": {"summaries": "unexpected"}}

    with (
        patch(
            "blockscout_mcp_server.tools.transaction_tools.get_blockscout_base_url",
            new_callable=AsyncMock,
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.transaction_tools.make_blockscout_request",
            new_callable=AsyncMock,
        ) as mock_request,
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response

        with pytest.raises(RuntimeError):
            await transaction_summary(chain_id=chain_id, transaction_hash=tx_hash, ctx=mock_ctx)

        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(
            base_url=mock_base_url,
            api_path=f"/api/v2/transactions/{tx_hash}/summary",
        )
        assert mock_ctx.report_progress.call_count == 3
        assert mock_ctx.info.call_count == 3
