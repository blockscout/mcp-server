import httpx
import pytest

from blockscout_mcp_server.models import AddressLogItem, ToolResponse
from blockscout_mcp_server.tools.direct_api.direct_api_call import direct_api_call
from tests.integration.helpers import is_log_a_truncated_call_executed


@pytest.mark.integration
@pytest.mark.asyncio
async def test_direct_api_call_dispatches_to_logs_handler(mock_ctx):
    address = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"  # USDC contract
    endpoint_path = f"/api/v2/addresses/{address}/logs"
    try:
        result = await direct_api_call(chain_id="1", endpoint_path=endpoint_path, ctx=mock_ctx)
    except httpx.HTTPError as exc:
        pytest.fail(f"Live direct_api_call request failed for {endpoint_path}: {exc}")

    assert isinstance(result, ToolResponse)
    assert isinstance(result.data, list)
    assert result.data, "Expected at least one log item"
    assert isinstance(result.data[0], AddressLogItem)
    assert result.pagination is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_direct_api_call_pagination_integration(mock_ctx):
    """direct_api_call should provide pagination when the handler slices results."""
    address = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
    chain_id = "1"
    endpoint_path = f"/api/v2/addresses/{address}/logs"

    try:
        first_page_result = await direct_api_call(chain_id=chain_id, endpoint_path=endpoint_path, ctx=mock_ctx)
    except httpx.HTTPStatusError as exc:
        pytest.skip(f"API request failed, skipping pagination test: {exc}")

    assert first_page_result.pagination is not None
    cursor = first_page_result.pagination.next_call.params.get("cursor")
    assert cursor

    assert isinstance(first_page_result.data, list)
    assert len(first_page_result.data) > 0

    try:
        second_page_result = await direct_api_call(
            chain_id=chain_id,
            endpoint_path=endpoint_path,
            cursor=cursor,
            ctx=mock_ctx,
        )
    except httpx.HTTPStatusError as exc:
        pytest.fail(f"API request for the second page failed with cursor: {exc}")

    assert isinstance(second_page_result.data, list)
    assert len(second_page_result.data) > 0
    assert first_page_result.data != second_page_result.data


@pytest.mark.integration
@pytest.mark.asyncio
async def test_direct_api_call_paginated_search_for_truncation(mock_ctx):
    """direct_api_call should surface truncated logs when paging through results."""

    address = "0xFe89cc7aBB2C4183683ab71653C4cdc9B02D44b7"
    chain_id = "1"
    endpoint_path = f"/api/v2/addresses/{address}/logs"
    max_pages_to_check = 5
    cursor = None
    found_truncated_log = False

    for page_num in range(max_pages_to_check):
        try:
            result = await direct_api_call(
                chain_id=chain_id,
                endpoint_path=endpoint_path,
                cursor=cursor,
                ctx=mock_ctx,
            )
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
