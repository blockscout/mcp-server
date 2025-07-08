"""
Tests for enhanced pagination functionality in transaction tools.

This module tests the multi-page fetching strategy introduced in issue-130
where the server fetches up to 10 full-size pages when filtering results.
"""

from unittest.mock import AsyncMock, patch

import pytest

from blockscout_mcp_server.config import config
from blockscout_mcp_server.tools.transaction_tools import get_transactions_by_address


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
