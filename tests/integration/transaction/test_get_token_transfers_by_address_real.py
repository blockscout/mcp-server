import httpx
import pytest

from blockscout_mcp_server.models import AdvancedFilterItem, ToolResponse
from blockscout_mcp_server.tools.transaction.get_token_transfers_by_address import (
    get_token_transfers_by_address,
)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_token_transfers_by_address_integration(mock_ctx):
    """Tests that get_token_transfers_by_address returns a transformed list of transfers."""
    address = "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"

    try:
        result = await get_token_transfers_by_address(
            chain_id="1",
            address=address,
            age_to="2017-01-01T00:00:00.00Z",
            ctx=mock_ctx,
        )
    except httpx.HTTPError as exc:
        pytest.skip(f"Skipping get_token_transfers_by_address integration test due to network issue: {exc}")

    assert isinstance(result, ToolResponse)
    items = result.data
    assert isinstance(items, list)

    assert len(items) <= 10
    if len(items) == 10:
        assert result.pagination is not None, "Pagination info should be present when a full page is returned."

    if not items:
        pytest.skip("No token transfers found for the given address and time range.")

    for item in items:
        assert isinstance(item, AdvancedFilterItem)
        assert item.from_address is None or isinstance(item.from_address, str)
        assert item.to_address is None or isinstance(item.to_address, str)
        item_dict = item.model_dump(by_alias=True)
        assert "value" not in item_dict
        assert "internal_transaction_index" not in item_dict
        assert "hash" in item_dict
        assert "timestamp" in item_dict
        assert "token" in item_dict
        assert "total" in item_dict


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_token_transfers_by_address_pagination_integration(mock_ctx):
    """Tests that get_token_transfers_by_address can successfully use a cursor to fetch a second page."""
    address = "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"
    chain_id = "1"

    try:
        first_page = await get_token_transfers_by_address(chain_id=chain_id, address=address, ctx=mock_ctx)
    except httpx.HTTPError as exc:
        pytest.skip(f"API request failed: {exc}")

    if not first_page.pagination:
        pytest.skip("Pagination info missing from first page.")

    cursor = first_page.pagination.next_call.params["cursor"]

    try:
        second_page = await get_token_transfers_by_address(
            chain_id=chain_id,
            address=address,
            ctx=mock_ctx,
            cursor=cursor,
        )
    except httpx.HTTPError as exc:
        pytest.fail(f"Failed to fetch second page: {exc}")

    assert isinstance(second_page.data, list)
    if second_page.data:
        assert first_page.data[0] != second_page.data[0]
