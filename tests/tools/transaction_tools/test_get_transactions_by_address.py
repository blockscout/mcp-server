from unittest.mock import ANY, AsyncMock, MagicMock, patch

import httpx
import pytest

from blockscout_mcp_server.config import config
from blockscout_mcp_server.models import AdvancedFilterItem, NextCallInfo, PaginationInfo, ToolResponse
from blockscout_mcp_server.tools.transaction_tools import get_transactions_by_address


@pytest.mark.asyncio
async def test_get_transactions_by_address_calls_smart_pagination_correctly(mock_ctx):
    """
    Verify get_transactions_by_address calls the smart pagination function with correct arguments.
    This tests the integration without testing the pagination function's internal logic.
    """
    # ARRANGE
    chain_id = "1"
    address = "0x123abc"
    age_from = "2023-01-01T00:00:00.00Z"
    age_to = "2023-01-02T00:00:00.00Z"
    methods = "0x304e6ade"
    mock_base_url = "https://eth.blockscout.com"
    mock_filtered_items = []
    mock_has_more_pages = False

    # We patch the smart pagination function and the base URL getter
    with (
        patch(
            "blockscout_mcp_server.tools.transaction_tools.get_blockscout_base_url", new_callable=AsyncMock
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.transaction_tools._fetch_filtered_transactions_with_smart_pagination",
            new_callable=AsyncMock,
        ) as mock_smart_pagination,
    ):
        mock_get_url.return_value = mock_base_url
        mock_smart_pagination.return_value = (mock_filtered_items, mock_has_more_pages)

        # ACT
        result = await get_transactions_by_address(
            chain_id=chain_id,
            address=address,
            age_from=age_from,
            age_to=age_to,
            methods=methods,
            ctx=mock_ctx,
        )

        # ASSERT
        assert isinstance(result, ToolResponse)
        assert isinstance(result.data, list)
        assert result.data == []
        mock_get_url.assert_called_once_with(chain_id)

        # Assert that the smart pagination function was called once
        mock_smart_pagination.assert_called_once()

        # Assert that the smart pagination function was called with the correct arguments
        call_args, call_kwargs = mock_smart_pagination.call_args

        # Verify the smart pagination function was called with correct parameters
        assert call_kwargs["base_url"] == mock_base_url
        assert call_kwargs["api_path"] == "/api/v2/advanced-filters"
        assert call_kwargs["ctx"] == mock_ctx
        assert call_kwargs["progress_start_step"] == 2.0
        assert call_kwargs["total_steps"] == 12.0

        # Check the initial_params that should be passed to the smart pagination function
        expected_initial_params = {
            "to_address_hashes_to_include": address,
            "from_address_hashes_to_include": address,
            "age_from": age_from,
            "age_to": age_to,
            "methods": methods,
        }
        assert call_kwargs["initial_params"] == expected_initial_params

        # Verify progress was reported correctly before the smart pagination call
        assert mock_ctx.report_progress.call_count == 3  # Start + after URL resolution + completion


@pytest.mark.asyncio
async def test_get_transactions_by_address_minimal_params(mock_ctx):
    """
    Verify get_transactions_by_address works with minimal parameters (only required ones).
    """
    # ARRANGE
    chain_id = "1"
    address = "0x123abc"
    mock_base_url = "https://eth.blockscout.com"
    mock_filtered_items = [{"hash": "0xabc123"}]
    mock_has_more_pages = False

    with (
        patch(
            "blockscout_mcp_server.tools.transaction_tools.get_blockscout_base_url", new_callable=AsyncMock
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.transaction_tools._fetch_filtered_transactions_with_smart_pagination",
            new_callable=AsyncMock,
        ) as mock_smart_pagination,
    ):
        mock_get_url.return_value = mock_base_url
        mock_smart_pagination.return_value = (mock_filtered_items, mock_has_more_pages)

        # ACT - Only provide required parameters
        result = await get_transactions_by_address(chain_id=chain_id, address=address, ctx=mock_ctx)

        # ASSERT
        assert isinstance(result, ToolResponse)
        assert isinstance(result.data, list)
        assert len(result.data) == 1
        assert isinstance(result.data[0], AdvancedFilterItem)
        assert result.data[0].model_dump(by_alias=True)["hash"] == "0xabc123"
        mock_get_url.assert_called_once_with(chain_id)
        mock_smart_pagination.assert_called_once()

        # Check that the initial_params only include the required parameters
        call_args, call_kwargs = mock_smart_pagination.call_args
        expected_params = {
            "to_address_hashes_to_include": address,
            "from_address_hashes_to_include": address,
            # No optional parameters should be included
        }
        assert call_kwargs["initial_params"] == expected_params


@pytest.mark.asyncio
async def test_get_transactions_by_address_transforms_response(mock_ctx):
    """Verify that get_transactions_by_address correctly transforms its response."""
    chain_id = "1"
    address = "0x123"
    mock_base_url = "https://eth.blockscout.com"

    # Mock the filtered items returned by smart pagination (ERC-20 transactions already filtered out)
    mock_filtered_items = [
        {
            "type": "call",
            "from": {"hash": "0xfrom_hash_1"},
            "to": {"hash": "0xto_hash_1"},
            "value": "kept1",
            "token": "should be removed",
            "total": "should be removed",
        },
        {
            "type": "creation",
            "from": {"hash": "0xfrom_hash_3"},
            "to": None,
            "value": "kept2",
        },
    ]
    mock_has_more_pages = False

    expected_items = [
        {
            "from": "0xfrom_hash_1",
            "to": "0xto_hash_1",
            "value": "kept1",
        },
        {
            "from": "0xfrom_hash_3",
            "to": None,
            "value": "kept2",
        },
    ]

    with (
        patch(
            "blockscout_mcp_server.tools.transaction_tools.get_blockscout_base_url", new_callable=AsyncMock
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.transaction_tools._fetch_filtered_transactions_with_smart_pagination",
            new_callable=AsyncMock,
        ) as mock_smart_pagination,
    ):
        mock_get_url.return_value = mock_base_url
        mock_smart_pagination.return_value = (mock_filtered_items, mock_has_more_pages)

        result = await get_transactions_by_address(chain_id=chain_id, address=address, ctx=mock_ctx)

        assert isinstance(result, ToolResponse)
        assert isinstance(result.data, list)
        assert len(result.data) == 2
        for idx, expected in enumerate(expected_items):
            item_model = result.data[idx]
            assert isinstance(item_model, AdvancedFilterItem)
            assert item_model.from_address == expected["from"]
            assert item_model.to_address == expected["to"]
            item_dict = item_model.model_dump(by_alias=True)
            assert item_dict.get("value") == expected["value"]
            # removed fields should not be present after transformation
            assert "token" not in item_dict
        assert "total" not in item_dict


@pytest.mark.asyncio
async def test_get_transactions_by_address_with_pagination(mock_ctx):
    chain_id = "1"
    address = "0x123abc"
    mock_base_url = "https://eth.blockscout.com"

    mock_filtered_items = []
    mock_has_more_pages = True  # This should trigger force_pagination

    with (
        patch(
            "blockscout_mcp_server.tools.transaction_tools.get_blockscout_base_url",
            new_callable=AsyncMock,
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.transaction_tools._fetch_filtered_transactions_with_smart_pagination",
            new_callable=AsyncMock,
        ) as mock_smart_pagination,
        patch("blockscout_mcp_server.tools.transaction_tools.create_items_pagination") as mock_create_pagination,
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
            "blockscout_mcp_server.tools.transaction_tools.get_blockscout_base_url",
            new_callable=AsyncMock,
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.transaction_tools._fetch_filtered_transactions_with_smart_pagination",
            new_callable=AsyncMock,
        ) as mock_smart_pagination,
        patch("blockscout_mcp_server.tools.transaction_tools.create_items_pagination") as mock_create_pagination,
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
            "blockscout_mcp_server.tools.transaction_tools.get_blockscout_base_url",
            new_callable=AsyncMock,
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.transaction_tools._fetch_filtered_transactions_with_smart_pagination",
            new_callable=AsyncMock,
        ) as mock_smart_pagination,
        patch(
            "blockscout_mcp_server.tools.transaction_tools.apply_cursor_to_params",
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
            "blockscout_mcp_server.tools.transaction_tools.get_blockscout_base_url", new_callable=AsyncMock
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.transaction_tools._fetch_filtered_transactions_with_smart_pagination",
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

        assert exc_info.value == smart_pagination_error
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
            "blockscout_mcp_server.tools.transaction_tools.get_blockscout_base_url", new_callable=AsyncMock
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.transaction_tools._fetch_filtered_transactions_with_smart_pagination",
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
            "blockscout_mcp_server.tools.transaction_tools.get_blockscout_base_url", new_callable=AsyncMock
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.transaction_tools._fetch_filtered_transactions_with_smart_pagination",
            new_callable=AsyncMock,
        ) as mock_smart_pagination,
        patch(
            "blockscout_mcp_server.tools.transaction_tools.report_and_log_progress", new_callable=AsyncMock
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


@pytest.mark.asyncio
async def test_get_transactions_by_address_invalid_cursor(mock_ctx):
    """Verify ValueError is raised when the cursor is invalid."""
    with patch(
        "blockscout_mcp_server.tools.transaction_tools.apply_cursor_to_params",
        side_effect=ValueError("Invalid cursor"),
    ) as mock_apply:
        with pytest.raises(ValueError, match="Invalid cursor"):
            await get_transactions_by_address(chain_id="1", address="0x123", cursor="bad", ctx=mock_ctx)
    mock_apply.assert_called_once()


@pytest.mark.asyncio
async def test_get_transactions_by_address_multi_page_fetching(mock_ctx):
    """
    Test that get_transactions_by_address fetches multiple pages when initial results are sparse due to filtering.

    This test simulates the scenario where each page contains mostly filtered-out transactions
    (ERC-20, ERC-721, etc.) but some valid transactions, requiring multiple pages to accumulate
    enough results for pagination decision.
    """
    # ARRANGE
    chain_id = "1"
    address = "0x123abc"
    mock_base_url = "https://eth.blockscout.com"

    # Mock page 1: mostly filtered transactions with 2 valid ones
    page1_items = [
        {"type": "call", "hash": "0x1", "block_number": 100},
        {"type": "ERC-20", "hash": "0x2", "block_number": 99},  # will be filtered out
        {"type": "call", "hash": "0x3", "block_number": 98},
        {"type": "ERC-721", "hash": "0x4", "block_number": 97},  # will be filtered out
        {"type": "ERC-1155", "hash": "0x5", "block_number": 96},  # will be filtered out
    ]

    # Mock page 2: mostly filtered transactions with 2 valid ones
    page2_items = [
        {"type": "call", "hash": "0x6", "block_number": 95},
        {"type": "ERC-20", "hash": "0x7", "block_number": 94},  # will be filtered out
        {"type": "call", "hash": "0x8", "block_number": 93},
        {"type": "ERC-404", "hash": "0x9", "block_number": 92},  # will be filtered out
    ]

    # Mock page 3: enough valid transactions to trigger pagination
    page3_items = [
        {"type": "call", "hash": "0x10", "block_number": 91},
        {"type": "call", "hash": "0x11", "block_number": 90},
        {"type": "call", "hash": "0x12", "block_number": 89},
        {"type": "call", "hash": "0x13", "block_number": 88},
        {"type": "call", "hash": "0x14", "block_number": 87},
        {"type": "call", "hash": "0x15", "block_number": 86},
        {"type": "call", "hash": "0x16", "block_number": 85},
        {"type": "call", "hash": "0x17", "block_number": 84},
        {"type": "call", "hash": "0x18", "block_number": 83},
        {"type": "call", "hash": "0x19", "block_number": 82},
    ]

    # Expected API responses for each page
    api_responses = [
        {"items": page1_items, "next_page_params": {"page": 2}},
        {"items": page2_items, "next_page_params": {"page": 3}},
        {"items": page3_items, "next_page_params": {"page": 4}},
    ]

    with (
        patch(
            "blockscout_mcp_server.tools.transaction_tools.get_blockscout_base_url", new_callable=AsyncMock
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.transaction_tools.make_request_with_periodic_progress", new_callable=AsyncMock
        ) as mock_request,
        patch.object(config, "advanced_filters_page_size", 10),
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.side_effect = api_responses

        # ACT
        result = await get_transactions_by_address(
            chain_id=chain_id,
            address=address,
            ctx=mock_ctx,
        )

        # ASSERT
        # Should have called make_request_with_periodic_progress 3 times (3 pages)
        assert mock_request.call_count == 3

        # Should have accumulated filtered transactions from all 3 pages
        # Page 1: 2 valid transactions (types "call")
        # Page 2: 2 valid transactions (types "call")
        # Page 3: 10 valid transactions (types "call")
        # Total: 14 valid transactions
        assert len(result.data) == 10  # Should be sliced to page_size

        # Should have pagination since we have more than page_size valid transactions
        assert result.pagination is not None

        # Verify the transactions are properly transformed and ordered
        assert all(item.type == "call" for item in result.data)
        assert result.data[0].hash == "0x1"  # First transaction from page 1
        assert result.data[1].hash == "0x3"  # Second valid transaction from page 1


@pytest.mark.asyncio
async def test_get_transactions_by_address_stops_at_10_pages(mock_ctx):
    """
    Test that get_transactions_by_address stops fetching at 10 pages maximum.

    This test ensures that even if there are more pages available, the function
    will stop at 10 pages to prevent infinite loops or excessive API calls.
    """
    # ARRANGE
    chain_id = "1"
    address = "0x123abc"
    mock_base_url = "https://eth.blockscout.com"

    # Create 10 pages of sparse results (1 valid transaction per page)
    api_responses = []
    for i in range(10):
        page_items = [
            {"type": "call", "hash": f"0x{i + 1}", "block_number": 100 - i},
            {"type": "ERC-20", "hash": f"0x{i + 100}", "block_number": 99 - i},  # filtered out
            {"type": "ERC-721", "hash": f"0x{i + 200}", "block_number": 98 - i},  # filtered out
        ]
        api_responses.append(
            {
                "items": page_items,
                "next_page_params": {"page": i + 2},  # Always indicate more pages
            }
        )

    with (
        patch(
            "blockscout_mcp_server.tools.transaction_tools.get_blockscout_base_url", new_callable=AsyncMock
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.transaction_tools.make_request_with_periodic_progress", new_callable=AsyncMock
        ) as mock_request,
        patch.object(
            config, "advanced_filters_page_size", 20
        ),  # Large page size to ensure we don't hit pagination limit
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.side_effect = api_responses

        # ACT
        result = await get_transactions_by_address(
            chain_id=chain_id,
            address=address,
            ctx=mock_ctx,
        )

        # ASSERT
        # Should have called make_request_with_periodic_progress exactly 10 times (max pages)
        assert mock_request.call_count == 10

        # Should have accumulated 10 valid transactions (1 per page)
        assert len(result.data) == 10

        # Should still have pagination since we stopped at max pages and had next_page_params
        assert result.pagination is not None

        # Verify all transactions are valid (not filtered out)
        assert all(item.type == "call" for item in result.data)
        assert result.data[0].hash == "0x1"
        assert result.data[9].hash == "0x10"


@pytest.mark.asyncio
async def test_get_transactions_by_address_single_page_sufficient(mock_ctx):
    """
    Test that get_transactions_by_address works correctly when a single page has sufficient results.

    This test ensures that when the first page contains enough valid transactions
    after filtering, no additional pages are fetched.
    """
    # ARRANGE
    chain_id = "1"
    address = "0x123abc"
    mock_base_url = "https://eth.blockscout.com"

    # Create a single page with enough valid transactions
    page_items = [{"type": "call", "hash": f"0x{i + 1}", "block_number": 100 - i} for i in range(15)]

    # Add some filtered transactions to ensure filtering works
    page_items.extend(
        [
            {"type": "ERC-20", "hash": "0x100", "block_number": 85},
            {"type": "ERC-721", "hash": "0x101", "block_number": 84},
        ]
    )

    api_response = {
        "items": page_items,
        "next_page_params": {"page": 2},  # Indicate more pages available
    }

    with (
        patch(
            "blockscout_mcp_server.tools.transaction_tools.get_blockscout_base_url", new_callable=AsyncMock
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.transaction_tools.make_request_with_periodic_progress", new_callable=AsyncMock
        ) as mock_request,
        patch.object(config, "advanced_filters_page_size", 10),
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.return_value = api_response

        # ACT
        result = await get_transactions_by_address(
            chain_id=chain_id,
            address=address,
            ctx=mock_ctx,
        )

        # ASSERT
        # Should have called make_request_with_periodic_progress only once
        assert mock_request.call_count == 1

        # Should have 10 transactions (page size limit)
        assert len(result.data) == 10

        # Should have pagination since we have more than page_size valid transactions
        assert result.pagination is not None

        # Verify all returned transactions are valid (not filtered out)
        assert all(item.type == "call" for item in result.data)


@pytest.mark.asyncio
async def test_get_transactions_by_address_no_more_pages_available(mock_ctx):
    """
    Test that get_transactions_by_address correctly handles the case when no more pages are available.

    This test ensures that when the API indicates no more pages (next_page_params is None),
    the function returns all available results without pagination.
    """
    # ARRANGE
    chain_id = "1"
    address = "0x123abc"
    mock_base_url = "https://eth.blockscout.com"

    # Create a single page with few valid transactions and no next page
    page_items = [
        {"type": "call", "hash": "0x1", "block_number": 100},
        {"type": "call", "hash": "0x2", "block_number": 99},
        {"type": "ERC-20", "hash": "0x3", "block_number": 98},  # filtered out
        {"type": "call", "hash": "0x4", "block_number": 97},
    ]

    api_response = {
        "items": page_items,
        "next_page_params": None,  # No more pages available
    }

    with (
        patch(
            "blockscout_mcp_server.tools.transaction_tools.get_blockscout_base_url", new_callable=AsyncMock
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.transaction_tools.make_request_with_periodic_progress", new_callable=AsyncMock
        ) as mock_request,
        patch.object(config, "advanced_filters_page_size", 10),
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.return_value = api_response

        # ACT
        result = await get_transactions_by_address(
            chain_id=chain_id,
            address=address,
            ctx=mock_ctx,
        )

        # ASSERT
        # Should have called make_request_with_periodic_progress only once
        assert mock_request.call_count == 1

        # Should have 3 valid transactions (filtered out 1 ERC-20)
        assert len(result.data) == 3

        # Should NOT have pagination since we have fewer than page_size and no more pages
        assert result.pagination is None

        # Verify all returned transactions are valid (not filtered out)
        assert all(item.type == "call" for item in result.data)
        assert result.data[0].hash == "0x1"
        assert result.data[1].hash == "0x2"
        assert result.data[2].hash == "0x4"
