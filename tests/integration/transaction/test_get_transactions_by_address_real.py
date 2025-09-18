import httpx
import pytest

from blockscout_mcp_server.models import AdvancedFilterItem, ToolResponse
from blockscout_mcp_server.tools.transaction._shared import EXCLUDED_TX_TYPES
from blockscout_mcp_server.tools.transaction.get_transactions_by_address import (
    get_transactions_by_address,
)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_transactions_by_address_integration(mock_ctx):
    """Tests that get_transactions_by_address returns a transformed list of transactions."""
    address = "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"

    result = await get_transactions_by_address(
        chain_id="1",
        address=address,
        age_to="2017-01-01T00:00:00.00Z",
        ctx=mock_ctx,
    )

    assert isinstance(result, ToolResponse)
    items = result.data
    assert isinstance(items, list)

    assert len(items) <= 10
    if len(items) == 10:
        assert result.pagination is not None, "Pagination info should be present when a full page is returned."

    if not items:
        pytest.skip("No non-token transactions found for the given address and time range to verify.")

    for item in items:
        assert isinstance(item, AdvancedFilterItem)
        assert isinstance(item.from_address, str | type(None))
        assert isinstance(item.to_address, str | type(None))
        item_dict = item.model_dump(by_alias=True)
        assert item.model_extra.get("type") not in EXCLUDED_TX_TYPES
        assert "token" not in item_dict
        assert "total" not in item_dict
        assert "hash" in item_dict
        assert "timestamp" in item_dict
        assert "value" in item_dict


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_transactions_by_address_pagination_integration(mock_ctx):
    """Tests that get_transactions_by_address can successfully use a cursor to fetch a second page."""
    address = "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"
    chain_id = "1"

    try:
        first_page = await get_transactions_by_address(chain_id=chain_id, address=address, ctx=mock_ctx)
    except httpx.HTTPStatusError as exc:
        pytest.skip(f"API request failed: {exc}")

    if not first_page.pagination:
        pytest.skip("Pagination info missing from first page.")

    cursor = first_page.pagination.next_call.params["cursor"]

    try:
        second_page = await get_transactions_by_address(chain_id=chain_id, address=address, ctx=mock_ctx, cursor=cursor)
    except httpx.HTTPStatusError as exc:
        pytest.fail(f"Failed to fetch second page: {exc}")

    assert isinstance(second_page.data, list)
    if second_page.data:
        assert first_page.data[0] != second_page.data[0]
