from unittest.mock import AsyncMock, patch

import pytest

from blockscout_mcp_server.models import AdvancedFilterItem, ToolResponse
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
async def test_get_transactions_by_address_invalid_cursor(mock_ctx):
    """Verify ValueError is raised when the cursor is invalid."""
    with patch(
        "blockscout_mcp_server.tools.transaction_tools.apply_cursor_to_params",
        side_effect=ValueError("Invalid cursor"),
    ) as mock_apply:
        with pytest.raises(ValueError, match="Invalid cursor"):
            await get_transactions_by_address(chain_id="1", address="0x123", cursor="bad", ctx=mock_ctx)
    mock_apply.assert_called_once()
