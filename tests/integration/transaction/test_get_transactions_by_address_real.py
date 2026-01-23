import pytest

from blockscout_mcp_server.models import AdvancedFilterItem, ToolResponse
from blockscout_mcp_server.tools.transaction._shared import EXCLUDED_TX_TYPES
from blockscout_mcp_server.tools.transaction.get_transactions_by_address import (
    get_transactions_by_address,
)
from tests.integration.helpers import retry_on_network_error


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_transactions_by_address_integration(mock_ctx):
    """Tests that get_transactions_by_address returns a transformed list of transactions."""
    address = "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"
    age_from = "2016-01-01T00:00:00Z"

    result = await retry_on_network_error(
        lambda: get_transactions_by_address(
            chain_id="1",
            address=address,
            age_from=age_from,
            age_to="2017-01-01T00:00:00.00Z",
            ctx=mock_ctx,
        ),
        action_description="get_transactions_by_address request",
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
        assert item.from_address is None or isinstance(item.from_address, str)
        assert item.to_address is None or isinstance(item.to_address, str)
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
    age_from = "2016-01-01T00:00:00Z"

    first_page = await retry_on_network_error(
        lambda: get_transactions_by_address(
            chain_id=chain_id,
            address=address,
            age_from=age_from,
            ctx=mock_ctx,
        ),
        action_description="get_transactions_by_address first page request",
    )

    if not first_page.pagination:
        pytest.skip("Pagination info missing from first page.")

    cursor = first_page.pagination.next_call.params["cursor"]

    second_page = await retry_on_network_error(
        lambda: get_transactions_by_address(
            chain_id=chain_id,
            address=address,
            age_from=age_from,
            ctx=mock_ctx,
            cursor=cursor,
        ),
        action_description="get_transactions_by_address second page request",
    )

    assert isinstance(second_page.data, list)
    if second_page.data:
        assert first_page.data[0] != second_page.data[0]
