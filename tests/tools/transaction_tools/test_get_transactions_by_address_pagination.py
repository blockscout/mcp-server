from unittest.mock import ANY, AsyncMock, MagicMock, patch

import httpx
import pytest

from blockscout_mcp_server.config import config
from blockscout_mcp_server.models import NextCallInfo, PaginationInfo
from blockscout_mcp_server.tools.transaction.get_transactions_by_address import get_transactions_by_address


@pytest.mark.asyncio
async def test_get_transactions_by_address_with_pagination(mock_ctx):
    chain_id = "1"
    address = "0x123abc"
    mock_base_url = "https://eth.blockscout.com"

    mock_filtered_items = []
    mock_has_more_pages = True  # This should trigger force_pagination

    with (
        patch(
            "blockscout_mcp_server.tools.transaction.get_transactions_by_address.get_blockscout_base_url",
            new_callable=AsyncMock,
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.transaction.get_transactions_by_address._fetch_filtered_transactions_with_smart_pagination",
            new_callable=AsyncMock,
        ) as mock_smart_pagination,
        patch("blockscout_mcp_server.tools.transaction.get_transactions_by_address.create_items_pagination") as mock_create_pagination,
    ):
        mock_get_url.return_value = mock_base_url
        mock_smart_pagination.return_value = (mock_filtered_items, mock_has_more_pages)
        mock_create_pagination.return_value = (
            [],
            PaginationInfo(
                next_call=NextCallInfo(
                    tool_name="get_transactions_by_address",
                    params={"cursor": "CUR"},
                )
            ),
        )

        result = await get_transactions_by_address(chain_id=chain_id, address=address, ctx=mock_ctx)

        mock_create_pagination.assert_called_once()
        # Verify that force_pagination was set to True due to has_more_pages
        assert mock_create_pagination.call_args.kwargs["force_pagination"] is True
        assert isinstance(result.pagination, PaginationInfo)


@pytest.mark.asyncio
async def test_get_transactions_by_address_custom_page_size(mock_ctx):
    chain_id = "1"
    address = "0x123"
    mock_base_url = "https://eth.blockscout.com"

    items = [{"block_number": i} for i in range(10)]
    mock_filtered_items = items
    mock_has_more_pages = False

    with (
        patch(
            "blockscout_mcp_server.tools.transaction.get_transactions_by_address.get_blockscout_base_url",
            new_callable=AsyncMock,
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.transaction.get_transactions_by_address._fetch_filtered_transactions_with_smart_pagination",
            new_callable=AsyncMock,
        ) as mock_smart_pagination,
        patch("blockscout_mcp_server.tools.transaction.get_transactions_by_address.create_items_pagination") as mock_create_pagination,
        patch.object(config, "advanced_filters_page_size", 5),
    ):
        mock_get_url.return_value = mock_base_url
        mock_smart_pagination.return_value = (mock_filtered_items, mock_has_more_pages)
        mock_create_pagination.return_value = (items[:5], None)

        await get_transactions_by_address(chain_id=chain_id, address=address, ctx=mock_ctx)

        mock_create_pagination.assert_called_once()
        assert mock_create_pagination.call_args.kwargs["page_size"] == 5


@pytest.mark.asyncio
async def test_get_transactions_by_address_with_cursor_param(mock_ctx):
    chain_id = "1"
    address = "0x123abc"
    cursor = "CURSOR"
    decoded = {"page": 2}
    mock_base_url = "https://eth.blockscout.com"

    mock_filtered_items = []
    mock_has_more_pages = False

    with (
        patch(
            "blockscout_mcp_server.tools.transaction.get_transactions_by_address.get_blockscout_base_url",
            new_callable=AsyncMock,
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.transaction.get_transactions_by_address._fetch_filtered_transactions_with_smart_pagination",
            new_callable=AsyncMock,
        ) as mock_smart_pagination,
        patch(
            "blockscout_mcp_server.tools.transaction.get_transactions_by_address.apply_cursor_to_params",
        ) as mock_apply_cursor,
    ):
        mock_get_url.return_value = mock_base_url
        mock_smart_pagination.return_value = (mock_filtered_items, mock_has_more_pages)
        mock_apply_cursor.side_effect = lambda cur, params: params.update(decoded)

        await get_transactions_by_address(
            chain_id=chain_id,
            address=address,
            cursor=cursor,
            ctx=mock_ctx,
        )

        mock_apply_cursor.assert_called_once_with(cursor, ANY)
        call_args, call_kwargs = mock_smart_pagination.call_args
        params = call_kwargs["initial_params"]
        expected_params = {
            "to_address_hashes_to_include": address,
            "from_address_hashes_to_include": address,
            **decoded,
        }
        assert params == expected_params


@pytest.mark.asyncio
async def test_get_transactions_by_address_smart_pagination_error(mock_ctx):
    """
    Verify that errors from the smart pagination function are properly propagated.
    """
    # ARRANGE
    chain_id = "1"
    address = "0x123abc"
    mock_base_url = "https://eth.blockscout.com"

    # Simulate an error from the smart pagination function
    smart_pagination_error = httpx.HTTPStatusError(
        "Service Unavailable", request=MagicMock(), response=MagicMock(status_code=503)
    )

    with (
        patch(
            "blockscout_mcp_server.tools.transaction.get_transactions_by_address.get_blockscout_base_url", new_callable=AsyncMock
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.transaction.get_transactions_by_address._fetch_filtered_transactions_with_smart_pagination",
            new_callable=AsyncMock,
        ) as mock_smart_pagination,
    ):
        mock_get_url.return_value = mock_base_url
        mock_smart_pagination.side_effect = smart_pagination_error

        # ACT & ASSERT
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            await get_transactions_by_address(
                chain_id=chain_id,
                address=address,
                ctx=mock_ctx,
            )

        assert exc_info.value is smart_pagination_error
        mock_smart_pagination.assert_called_once()


@pytest.mark.asyncio
async def test_get_transactions_by_address_sparse_data_scenario(mock_ctx):
    """
    Test handling of scenarios where most transactions are filtered out, requiring multiple page fetches.

    This test simulates a realistic sparse data scenario where the API returns many pages
    of mostly filtered transactions (ERC-20, ERC-721, etc.) but only a few valid transactions
    per page, requiring the smart pagination to accumulate results across multiple pages.
    """
    # ARRANGE
    chain_id = "1"
    address = "0x123abc"
    mock_base_url = "https://eth.blockscout.com"

    # Create a scenario where we have many filtered transactions but few valid ones
    # This simulates a real-world scenario where an address has many token transfers
    # but few direct contract calls

    # Each page has 20 transactions but only 1-2 are valid (not filtered)
    page_responses = []
    valid_transactions = []

    for page_num in range(1, 6):  # 5 pages total
        page_items = []

        # Add 1-2 valid transactions per page
        for i in range(1, 3):  # 2 valid transactions per page
            valid_tx = {
                "type": "call",
                "hash": f"0x{page_num}_{i}",
                "block_number": 1000 - (page_num * 10) - i,
                "from": "0xfrom",
                "to": "0xto",
                "value": "1000000000000000000",
            }
            page_items.append(valid_tx)
            valid_transactions.append(valid_tx)

        # Add many filtered transactions to simulate sparse data
        for i in range(18):  # 18 filtered transactions per page
            filtered_tx = {
                "type": "ERC-20",  # Will be filtered out
                "hash": f"0xfiltered_{page_num}_{i}",
                "block_number": 1000 - (page_num * 10) - i - 10,
                "from": "0xfrom",
                "to": "0xto",
                "token": {"symbol": "USDC"},
                "total": "1000000",
            }
            page_items.append(filtered_tx)

        page_responses.append(
            {"items": page_items, "next_page_params": {"page": page_num + 1} if page_num < 5 else None}
        )

    # Mock the smart pagination function to return accumulated results
    # In real implementation, this would be handled by _fetch_filtered_transactions_with_smart_pagination
    accumulated_valid_transactions = valid_transactions[:10]  # First 10 valid transactions
    has_more_pages = True

    with (
        patch(
            "blockscout_mcp_server.tools.transaction.get_transactions_by_address.get_blockscout_base_url", new_callable=AsyncMock
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.transaction.get_transactions_by_address._fetch_filtered_transactions_with_smart_pagination",
            new_callable=AsyncMock,
        ) as mock_smart_pagination,
        patch.object(config, "advanced_filters_page_size", 10),
    ):
        mock_get_url.return_value = mock_base_url
        mock_smart_pagination.return_value = (accumulated_valid_transactions, has_more_pages)

        # ACT
        result = await get_transactions_by_address(
            chain_id=chain_id,
            address=address,
            ctx=mock_ctx,
        )

        # ASSERT
        # Should have called smart pagination function
        mock_smart_pagination.assert_called_once()

        # Verify the call arguments to smart pagination
        call_args = mock_smart_pagination.call_args
        assert call_args[1]["base_url"] == mock_base_url
        assert call_args[1]["api_path"] == "/api/v2/advanced-filters"
        assert call_args[1]["target_page_size"] == 10
        assert call_args[1]["ctx"] == mock_ctx

        # Should return exactly 10 transactions (page size)
        assert len(result.data) == 10

        # Should have pagination since has_more_pages is True
        assert result.pagination is not None
        assert result.pagination.next_call.tool_name == "get_transactions_by_address"

        # All returned transactions should be valid (not filtered)
        assert all(item.type == "call" for item in result.data)

        # Verify transactions are properly transformed
        assert result.data[0].hash == "0x1_1"  # First valid transaction
        assert result.data[1].hash == "0x1_2"  # Second valid transaction
        assert result.data[2].hash == "0x2_1"  # Third valid transaction

        # Verify no filtered transactions made it through
        assert all(hasattr(item, "token") is False for item in result.data)  # token field should be removed


@pytest.mark.asyncio
async def test_get_transactions_by_address_multi_page_progress_reporting(mock_ctx):
    """
    Test that progress is correctly reported during multi-page fetching operations.

    This test verifies that the enhanced progress reporting system correctly tracks
    and reports progress through all phases of the multi-page smart pagination:
    1. Initial operation start (step 0)
    2. URL resolution (step 1)
    3. Multi-page fetching (steps 2-11, handled by smart pagination)
    4. Final completion (step 12)
    """
    # ARRANGE
    chain_id = "1"
    address = "0x123abc"
    mock_base_url = "https://eth.blockscout.com"

    # Mock data that would be returned by smart pagination
    mock_transactions = [
        {"type": "call", "hash": f"0x{i}", "block_number": 1000 - i, "from": "0xfrom", "to": "0xto"} for i in range(5)
    ]
    has_more_pages = False

    with (
        patch(
            "blockscout_mcp_server.tools.transaction.get_transactions_by_address.get_blockscout_base_url", new_callable=AsyncMock
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.transaction.get_transactions_by_address._fetch_filtered_transactions_with_smart_pagination",
            new_callable=AsyncMock,
        ) as mock_smart_pagination,
        patch(
            "blockscout_mcp_server.tools.transaction.get_transactions_by_address.report_and_log_progress", new_callable=AsyncMock
        ) as mock_progress,
        patch.object(config, "advanced_filters_page_size", 10),
    ):
        mock_get_url.return_value = mock_base_url
        mock_smart_pagination.return_value = (mock_transactions, has_more_pages)

        # ACT
        result = await get_transactions_by_address(
            chain_id=chain_id,
            address=address,
            ctx=mock_ctx,
        )

        # ASSERT
        # Verify the result is correct
        assert len(result.data) == 5
        assert result.pagination is None  # No pagination since has_more_pages is False

        # Verify progress reporting was called correctly
        progress_calls = mock_progress.call_args_list

        # Should have exactly 3 progress reports from get_transactions_by_address:
        # 1. Initial start (progress=0.0, total=12.0)
        # 2. After URL resolution (progress=1.0, total=12.0)
        # 3. Final completion (progress=12.0, total=12.0)
        assert len(progress_calls) == 3

        # Each call structure: call(ctx, progress=X, total=Y, message=Z)
        # args are in call_args_list[i][0] tuple (just ctx)
        # kwargs are in call_args_list[i][1] dict (progress, total, message)

        # Verify initial progress report (step 0)
        initial_call_args, initial_call_kwargs = progress_calls[0]
        assert initial_call_args[0] == mock_ctx  # ctx
        assert initial_call_kwargs["progress"] == 0.0
        assert initial_call_kwargs["total"] == 12.0
        assert "Starting to fetch transactions" in initial_call_kwargs["message"]
        assert address in initial_call_kwargs["message"]
        assert chain_id in initial_call_kwargs["message"]

        # Verify URL resolution progress (step 1)
        url_resolution_call_args, url_resolution_call_kwargs = progress_calls[1]
        assert url_resolution_call_args[0] == mock_ctx  # ctx
        assert url_resolution_call_kwargs["progress"] == 1.0
        assert url_resolution_call_kwargs["total"] == 12.0
        assert "Resolved Blockscout instance URL" in url_resolution_call_kwargs["message"]

        # Verify final completion progress (step 12)
        completion_call_args, completion_call_kwargs = progress_calls[2]
        assert completion_call_args[0] == mock_ctx  # ctx
        assert completion_call_kwargs["progress"] == 12.0
        assert completion_call_kwargs["total"] == 12.0
        assert "Successfully fetched transaction data" in completion_call_kwargs["message"]

        # Verify smart pagination was called with correct progress parameters
        smart_pagination_call_args = mock_smart_pagination.call_args[1]
        assert smart_pagination_call_args["progress_start_step"] == 2.0
        assert smart_pagination_call_args["total_steps"] == 12.0
        assert smart_pagination_call_args["ctx"] == mock_ctx
