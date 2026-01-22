from unittest.mock import ANY, AsyncMock, patch

import pytest

from blockscout_mcp_server.config import config
from blockscout_mcp_server.models import AdvancedFilterItem, NextCallInfo, PaginationInfo, ToolResponse
from blockscout_mcp_server.tools.transaction.get_token_transfers_by_address import get_token_transfers_by_address


@pytest.mark.asyncio
async def test_get_token_transfers_by_address_calls_wrapper_correctly(mock_ctx):
    """
    Verify get_token_transfers_by_address calls the periodic progress wrapper with correct arguments.
    """
    # ARRANGE
    chain_id = "1"
    address = "0x123abc"
    age_from = "2023-01-01T00:00:00.00Z"
    age_to = "2023-01-02T00:00:00.00Z"
    token = "0xDeaDDeaDDeaDDeaDDeaDDeaDDeaDDeaDDeaDDeaD"  # gitleaks:allow (test placeholder)
    mock_base_url = "https://eth.blockscout.com"
    mock_api_response = {"items": [], "next_page_params": None}

    with (
        patch(
            "blockscout_mcp_server.tools.transaction.get_token_transfers_by_address.get_blockscout_base_url",
            new_callable=AsyncMock,
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.transaction.get_token_transfers_by_address."
            "make_request_with_periodic_progress",
            new_callable=AsyncMock,
        ) as mock_wrapper,
    ):
        mock_get_url.return_value = mock_base_url
        mock_wrapper.return_value = mock_api_response

        # ACT
        result = await get_token_transfers_by_address(
            chain_id=chain_id, address=address, age_from=age_from, age_to=age_to, token=token, ctx=mock_ctx
        )

        # ASSERT
        assert isinstance(result, ToolResponse)
        assert isinstance(result.data, list)
        assert result.data == []
        mock_get_url.assert_called_once_with(chain_id)
        mock_wrapper.assert_called_once()

        # Check the wrapper call arguments
        call_args, call_kwargs = mock_wrapper.call_args
        assert call_kwargs["ctx"] == mock_ctx

        from blockscout_mcp_server.tools.common import make_blockscout_request

        assert call_kwargs["request_function"] == make_blockscout_request

        # Check the request_args for token transfers
        expected_request_args = {
            "base_url": mock_base_url,
            "api_path": "/api/v2/advanced-filters",
            "params": {
                "transaction_types": "ERC-20",
                "to_address_hashes_to_include": address,
                "from_address_hashes_to_include": address,
                "age_from": age_from,
                "age_to": age_to,
                "token_contract_address_hashes_to_include": token,
            },
        }
        assert call_kwargs["request_args"] == expected_request_args

        # Verify other wrapper configuration
        assert call_kwargs["tool_overall_total_steps"] == 2.0
        assert call_kwargs["current_step_number"] == 2.0
        assert call_kwargs["current_step_message_prefix"] == "Fetching token transfers"

        # Verify progress was reported correctly before the wrapper call
        assert mock_ctx.report_progress.await_count == 2
        assert mock_ctx.info.await_count == 2

        # Verify timing hints are passed through from config
        assert call_kwargs["total_duration_hint"] == config.bs_timeout
        assert call_kwargs["progress_interval_seconds"] == config.progress_interval_seconds


@pytest.mark.asyncio
async def test_get_token_transfers_by_address_chain_error(mock_ctx):
    """
    Verify that chain lookup errors are properly propagated without calling the wrapper.
    """
    # ARRANGE
    chain_id = "999999"  # Invalid chain ID
    address = "0x123abc"
    age_from = "2024-01-01T00:00:00Z"

    from blockscout_mcp_server.tools.common import ChainNotFoundError

    chain_error = ChainNotFoundError(f"Chain with ID '{chain_id}' not found on Blockscout.")

    with (
        patch(
            "blockscout_mcp_server.tools.transaction.get_token_transfers_by_address.get_blockscout_base_url",
            new_callable=AsyncMock,
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.transaction.get_token_transfers_by_address."
            "make_request_with_periodic_progress",
            new_callable=AsyncMock,
        ) as mock_wrapper,
    ):
        mock_get_url.side_effect = chain_error

        # ACT & ASSERT
        with pytest.raises(ChainNotFoundError):
            await get_token_transfers_by_address(
                chain_id=chain_id,
                address=address,
                age_from=age_from,
                ctx=mock_ctx,
            )

        # Verify the chain lookup was attempted
        mock_get_url.assert_called_once_with(chain_id)

        # Verify the wrapper was NOT called since chain lookup failed
        mock_wrapper.assert_not_called()

        # Progress should have been reported once (at start) before the error
        assert mock_ctx.report_progress.await_count == 1
        assert mock_ctx.info.await_count == 1


@pytest.mark.asyncio
async def test_get_token_transfers_by_address_transforms_response(mock_ctx):
    """Verify that get_token_transfers_by_address correctly transforms its response."""
    chain_id = "1"
    address = "0x123"
    age_from = "2024-01-01T00:00:00Z"
    mock_base_url = "https://eth.blockscout.com"

    mock_api_response = {
        "items": [
            {
                "from": {"hash": "0xfrom_hash"},
                "to": {"hash": "0xto_hash"},
                "token": "kept",
                "total": "kept",
                "value": "should be removed",
                "internal_transaction_index": 1,
                "created_contract": "should be removed",
            }
        ],
        "next_page_params": None,
    }

    expected_items = [
        {
            "from": "0xfrom_hash",
            "to": "0xto_hash",
            "token": "kept",
            "total": "kept",
        }
    ]

    with (
        patch(
            "blockscout_mcp_server.tools.transaction.get_token_transfers_by_address.get_blockscout_base_url",
            new_callable=AsyncMock,
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.transaction.get_token_transfers_by_address."
            "make_request_with_periodic_progress",
            new_callable=AsyncMock,
        ) as mock_wrapper,
    ):
        mock_get_url.return_value = mock_base_url
        mock_wrapper.return_value = mock_api_response

        result = await get_token_transfers_by_address(
            chain_id=chain_id,
            address=address,
            age_from=age_from,
            ctx=mock_ctx,
        )

        assert isinstance(result, ToolResponse)
        assert isinstance(result.data, list)
        assert len(result.data) == 1
        item_model = result.data[0]
        assert isinstance(item_model, AdvancedFilterItem)
        assert item_model.from_address == expected_items[0]["from"]
        assert item_model.to_address == expected_items[0]["to"]
        item_dict = item_model.model_dump(by_alias=True)
        assert item_dict["token"] == expected_items[0]["token"]
        assert item_dict["total"] == expected_items[0]["total"]

        # Unwanted fields must be absent
        assert "value" not in item_dict
        assert "internal_transaction_index" not in item_dict
        assert "created_contract" not in item_dict


@pytest.mark.asyncio
async def test_get_token_transfers_by_address_with_pagination(mock_ctx):
    chain_id = "1"
    address = "0x123abc"
    age_from = "2024-01-01T00:00:00Z"
    mock_base_url = "https://eth.blockscout.com"

    mock_api_response = {"items": []}

    with (
        patch(
            "blockscout_mcp_server.tools.transaction.get_token_transfers_by_address.get_blockscout_base_url",
            new_callable=AsyncMock,
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.transaction.get_token_transfers_by_address."
            "make_request_with_periodic_progress",
            new_callable=AsyncMock,
        ) as mock_wrapper,
        patch(
            "blockscout_mcp_server.tools.transaction.get_token_transfers_by_address.create_items_pagination",
        ) as mock_create_pagination,
    ):
        mock_get_url.return_value = mock_base_url
        mock_wrapper.return_value = mock_api_response
        mock_create_pagination.return_value = (
            [],
            PaginationInfo(
                next_call=NextCallInfo(
                    tool_name="get_token_transfers_by_address",
                    params={"cursor": "CUR"},
                )
            ),
        )

        result = await get_token_transfers_by_address(
            chain_id=chain_id,
            address=address,
            age_from=age_from,
            ctx=mock_ctx,
        )

        mock_create_pagination.assert_called_once()
        assert isinstance(result.pagination, PaginationInfo)
        assert result.pagination.next_call.tool_name == "get_token_transfers_by_address"
        assert "cursor" in result.pagination.next_call.params


@pytest.mark.asyncio
async def test_get_token_transfers_by_address_custom_page_size(mock_ctx):
    chain_id = "1"
    address = "0x123"
    age_from = "2024-01-01T00:00:00Z"
    mock_base_url = "https://eth.blockscout.com"

    items = [{"block_number": i} for i in range(10)]
    mock_api_response = {"items": items}

    with (
        patch(
            "blockscout_mcp_server.tools.transaction.get_token_transfers_by_address.get_blockscout_base_url",
            new_callable=AsyncMock,
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.transaction.get_token_transfers_by_address."
            "make_request_with_periodic_progress",
            new_callable=AsyncMock,
        ) as mock_wrapper,
        patch(
            "blockscout_mcp_server.tools.transaction.get_token_transfers_by_address.create_items_pagination",
        ) as mock_create_pagination,
        patch.object(config, "advanced_filters_page_size", 5),
    ):
        mock_get_url.return_value = mock_base_url
        mock_wrapper.return_value = mock_api_response
        mock_create_pagination.return_value = (items[:5], None)

        await get_token_transfers_by_address(
            chain_id=chain_id,
            address=address,
            age_from=age_from,
            ctx=mock_ctx,
        )

        mock_create_pagination.assert_called_once()
        assert mock_create_pagination.call_args.kwargs["page_size"] == 5


@pytest.mark.asyncio
async def test_get_token_transfers_by_address_with_cursor_param(mock_ctx):
    chain_id = "1"
    address = "0x123abc"
    cursor = "CURSOR"
    decoded = {"page": 2}
    age_from = "2024-01-01T00:00:00Z"
    mock_base_url = "https://eth.blockscout.com"

    with (
        patch(
            "blockscout_mcp_server.tools.transaction.get_token_transfers_by_address.get_blockscout_base_url",
            new_callable=AsyncMock,
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.transaction.get_token_transfers_by_address."
            "make_request_with_periodic_progress",
            new_callable=AsyncMock,
        ) as mock_wrapper,
        patch(
            "blockscout_mcp_server.tools.transaction.get_token_transfers_by_address.apply_cursor_to_params",
        ) as mock_apply_cursor,
    ):
        mock_get_url.return_value = mock_base_url
        mock_wrapper.return_value = {"items": []}
        mock_apply_cursor.side_effect = lambda cur, params: params.update(decoded)

        await get_token_transfers_by_address(
            chain_id=chain_id,
            address=address,
            age_from=age_from,
            cursor=cursor,
            ctx=mock_ctx,
        )

        mock_apply_cursor.assert_called_once_with(cursor, ANY)
        call_args, call_kwargs = mock_wrapper.call_args
        params = call_kwargs["request_args"]["params"]
        expected_params = {
            "transaction_types": "ERC-20",
            "to_address_hashes_to_include": address,
            "from_address_hashes_to_include": address,
            "age_from": age_from,
            **decoded,
        }
        assert params == expected_params


@pytest.mark.asyncio
async def test_get_token_transfers_by_address_invalid_cursor(mock_ctx):
    """Verify ValueError is raised when the cursor is invalid."""
    with patch(
        "blockscout_mcp_server.tools.transaction.get_token_transfers_by_address.apply_cursor_to_params",
        side_effect=ValueError("invalid"),
    ) as mock_apply:
        with pytest.raises(ValueError, match="invalid"):
            await get_token_transfers_by_address(
                chain_id="1",
                address="0xabc",
                age_from="2024-01-01T00:00:00Z",
                cursor="bad",
                ctx=mock_ctx,
            )
    mock_apply.assert_called_once()
