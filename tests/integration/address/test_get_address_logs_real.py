import httpx
import pytest

from blockscout_mcp_server.models import AddressLogItem, ToolResponse
from blockscout_mcp_server.tools.address.get_address_logs import get_address_logs
from tests.integration.helpers import is_log_a_truncated_call_executed


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_address_logs_integration(mock_ctx):
    address = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"  # USDC contract
    result = await get_address_logs(chain_id="1", address=address, ctx=mock_ctx)

    assert isinstance(result, ToolResponse)
    assert result.pagination is not None
    assert isinstance(result.data, list)
    assert 0 < len(result.data) <= 10

    first_log = result.data[0]
    assert isinstance(first_log, AddressLogItem)
    assert isinstance(first_log.transaction_hash, str)
    assert first_log.transaction_hash.startswith("0x")
    assert isinstance(first_log.block_number, int)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_address_logs_pagination_integration(mock_ctx):
    """Tests that get_address_logs can successfully use a cursor to fetch a second page."""
    address = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
    chain_id = "1"

    try:
        first_page_result = await get_address_logs(chain_id=chain_id, address=address, ctx=mock_ctx)
    except httpx.HTTPStatusError as exc:
        pytest.skip(f"API request failed, skipping pagination test: {exc}")

    assert first_page_result.pagination is not None
    cursor = first_page_result.pagination.next_call.params.get("cursor")
    assert cursor

    assert isinstance(first_page_result.data, list)
    assert len(first_page_result.data) > 0

    try:
        second_page_result = await get_address_logs(chain_id=chain_id, address=address, ctx=mock_ctx, cursor=cursor)
    except httpx.HTTPStatusError as exc:
        pytest.fail(f"API request for the second page failed with cursor: {exc}")

    assert isinstance(second_page_result.data, list)
    assert len(second_page_result.data) > 0
    assert first_page_result.data != second_page_result.data


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_address_logs_paginated_search_for_truncation(mock_ctx):
    """
    Tests that get_address_logs can find a 'CallExecuted' event with truncated
    decoded data by searching across pages. This validates the handling of
    complex nested truncation from the live API.
    """

    address = "0xFe89cc7aBB2C4183683ab71653C4cdc9B02D44b7"
    chain_id = "1"
    max_pages_to_check = 5
    cursor = None
    found_truncated_log = False

    for page_num in range(max_pages_to_check):
        try:
            result = await get_address_logs(chain_id=chain_id, address=address, ctx=mock_ctx, cursor=cursor)
        except httpx.HTTPStatusError as exc:
            pytest.skip(f"API request failed on page {page_num + 1}: {exc}")

        if any(is_log_a_truncated_call_executed(item) for item in result.data):
            found_truncated_log = True
            break

        if result.pagination:
            cursor = result.pagination.next_call.params.get("cursor")
        else:
            break

    if not found_truncated_log:
        pytest.skip(f"Could not find a truncated 'CallExecuted' log within the first {max_pages_to_check} pages.")
