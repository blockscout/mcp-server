import httpx
import pytest

from blockscout_mcp_server.constants import LOG_DATA_TRUNCATION_LIMIT
from blockscout_mcp_server.models import ToolResponse, TransactionLogItem
from blockscout_mcp_server.tools.direct_api.direct_api_call import direct_api_call
from tests.integration.helpers import is_log_a_truncated_call_executed


@pytest.mark.integration
@pytest.mark.asyncio
async def test_direct_api_call_transaction_logs_integration(mock_ctx):
    """Tests that direct_api_call dispatches transaction logs and validates the schema."""
    tx_hash = "0xa519e3af3f07190727f490c599baf3e65ee335883d6f420b433f7b83f62cb64d"
    endpoint_path = f"/api/v2/transactions/{tx_hash}/logs"

    try:
        result = await direct_api_call(chain_id="1", endpoint_path=endpoint_path, ctx=mock_ctx)
    except httpx.HTTPStatusError as exc:
        pytest.skip(f"Transaction data is currently unavailable from the API: {exc}")

    assert isinstance(result, ToolResponse)
    assert result.pagination is not None

    assert isinstance(result.data, list)
    assert 0 < len(result.data) <= 10

    first_log = result.data[0]
    assert isinstance(first_log, TransactionLogItem)
    if first_log.model_extra.get("data_truncated") is not None:
        assert isinstance(first_log.model_extra.get("data_truncated"), bool)

    assert isinstance(first_log.address, str)
    assert first_log.address.startswith("0x")
    assert isinstance(first_log.block_number, int)
    assert isinstance(first_log.index, int)
    assert isinstance(first_log.topics, list)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_direct_api_call_transaction_logs_pagination(mock_ctx):
    """Tests that direct_api_call can use a cursor to fetch a second page."""
    tx_hash = "0xa519e3af3f07190727f490c599baf3e65ee335883d6f420b433f7b83f62cb64d"
    endpoint_path = f"/api/v2/transactions/{tx_hash}/logs"

    try:
        first_page_response = await direct_api_call(chain_id="1", endpoint_path=endpoint_path, ctx=mock_ctx)
    except httpx.HTTPStatusError as exc:
        pytest.skip(f"Transaction data is currently unavailable from the API: {exc}")

    assert first_page_response.pagination is not None
    cursor = first_page_response.pagination.next_call.params["cursor"]

    try:
        second_page_response = await direct_api_call(
            chain_id="1",
            endpoint_path=endpoint_path,
            cursor=cursor,
            ctx=mock_ctx,
        )
    except httpx.HTTPStatusError as exc:
        pytest.fail(f"Failed to fetch the second page of transaction logs due to an API error: {exc}")

    assert isinstance(second_page_response, ToolResponse)
    assert second_page_response.data
    assert first_page_response.data[0] != second_page_response.data[0]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_direct_api_call_transaction_logs_with_truncation(mock_ctx):
    """Tests that direct_api_call correctly truncates oversized data fields."""
    tx_hash = "0xa519e3af3f07190727f490c599baf3e65ee335883d6f420b433f7b83f62cb64d"
    endpoint_path = f"/api/v2/transactions/{tx_hash}/logs"

    try:
        result = await direct_api_call(chain_id="1", endpoint_path=endpoint_path, ctx=mock_ctx)
    except httpx.HTTPStatusError as exc:
        pytest.skip(f"Transaction data is currently unavailable from the API: {exc}")

    assert result.notes is not None
    assert "One or more log items" in result.notes[0]

    assert isinstance(result.data, list) and result.data
    truncated_item = next(
        (item for item in result.data if item.model_extra.get("data_truncated")),
        None,
    )
    assert truncated_item is not None
    assert truncated_item.model_extra.get("data_truncated") is True
    assert truncated_item.data is not None
    assert len(truncated_item.data) == LOG_DATA_TRUNCATION_LIMIT


@pytest.mark.integration
@pytest.mark.asyncio
async def test_direct_api_call_transaction_logs_paginated_search_for_truncation(mock_ctx):
    """Tests that direct_api_call can find truncated data by searching across pages."""
    tx_hash = "0xa519e3af3f07190727f490c599baf3e65ee335883d6f420b433f7b83f62cb64d"
    endpoint_path = f"/api/v2/transactions/{tx_hash}/logs"
    max_pages_to_check = 20
    cursor = None
    found_truncated_log = False

    for page_num in range(max_pages_to_check):
        try:
            result = await direct_api_call(
                chain_id="1",
                endpoint_path=endpoint_path,
                cursor=cursor,
                ctx=mock_ctx,
            )
        except httpx.HTTPStatusError as exc:
            pytest.skip(f"API request failed on page {page_num + 1}: {exc}")

        if any(is_log_a_truncated_call_executed(log) for log in result.data):
            found_truncated_log = True
            break

        next_cursor = result.pagination.next_call.params["cursor"] if result.pagination else None
        if next_cursor:
            cursor = next_cursor
        else:
            break

    if not found_truncated_log:
        pytest.skip(f"Could not find a truncated 'CallExecuted' log within the first {max_pages_to_check} pages.")
