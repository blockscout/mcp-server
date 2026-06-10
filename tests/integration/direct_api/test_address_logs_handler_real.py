# SPDX-License-Identifier: LicenseRef-Blockscout
import pytest

from blockscout_mcp_server.config import config
from blockscout_mcp_server.models import AddressLogItem, ToolResponse
from blockscout_mcp_server.tools.direct_api.direct_api_call import direct_api_call
from tests.integration.helpers import is_log_a_truncated_call_executed, retry_on_network_error


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.skipif(not config.pro_api_key, reason="BLOCKSCOUT_PRO_API_KEY not configured")
async def test_direct_api_call_dispatches_to_logs_handler(mock_ctx):
    address = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"  # USDC contract
    endpoint_path = f"/api/v2/addresses/{address}/logs"
    result = await retry_on_network_error(
        lambda: direct_api_call(chain_id="1", endpoint_path=endpoint_path, ctx=mock_ctx),
        action_description="direct_api_call address logs request",
    )

    assert isinstance(result, ToolResponse)
    assert isinstance(result.data, list)
    assert result.data, "Expected at least one log item"
    assert isinstance(result.data[0], AddressLogItem)
    assert result.pagination is not None


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.skipif(not config.pro_api_key, reason="BLOCKSCOUT_PRO_API_KEY not configured")
async def test_direct_api_call_pagination_integration(mock_ctx):
    """direct_api_call should provide pagination when the handler slices results."""
    address = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
    chain_id = "1"
    endpoint_path = f"/api/v2/addresses/{address}/logs"

    first_page_result = await retry_on_network_error(
        lambda: direct_api_call(chain_id=chain_id, endpoint_path=endpoint_path, ctx=mock_ctx),
        action_description="direct_api_call logs first page request",
    )

    assert first_page_result.pagination is not None
    cursor = first_page_result.pagination.next_call.params.get("cursor")
    assert cursor

    assert isinstance(first_page_result.data, list)
    assert len(first_page_result.data) > 0

    second_page_result = await retry_on_network_error(
        lambda: direct_api_call(
            chain_id=chain_id,
            endpoint_path=endpoint_path,
            cursor=cursor,
            ctx=mock_ctx,
        ),
        action_description="direct_api_call logs second page request",
    )

    assert isinstance(second_page_result.data, list)
    assert len(second_page_result.data) > 0
    assert first_page_result.data != second_page_result.data


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.skipif(not config.pro_api_key, reason="BLOCKSCOUT_PRO_API_KEY not configured")
async def test_direct_api_call_paginated_search_for_truncation(mock_ctx):
    """direct_api_call should surface truncated logs when paging through results."""

    address = "0xFe89cc7aBB2C4183683ab71653C4cdc9B02D44b7"
    chain_id = "1"
    endpoint_path = f"/api/v2/addresses/{address}/logs"
    max_pages_to_check = 5
    cursor = None
    found_truncated_log = False

    for page_num in range(max_pages_to_check):
        result = await retry_on_network_error(
            lambda: direct_api_call(
                chain_id=chain_id,
                endpoint_path=endpoint_path,
                cursor=cursor,
                ctx=mock_ctx,
            ),
            action_description=f"direct_api_call logs page {page_num + 1} request",
        )

        if any(is_log_a_truncated_call_executed(item) for item in result.data):
            found_truncated_log = True
            assert result.notes is not None
            assert any(
                f"{config.pro_api_base_url}/1/api/v2/transactions/{{THE_TRANSACTION_HASH}}/logs" in note
                for note in result.notes
            )
            assert all("curl" not in note for note in result.notes)
            assert any("`web3-dev` skill" in note for note in result.notes)
            break

        if result.pagination:
            cursor = result.pagination.next_call.params.get("cursor")
        else:
            break

    if not found_truncated_log:
        pytest.skip(f"Could not find a truncated 'CallExecuted' log within the first {max_pages_to_check} pages.")


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.skipif(not config.pro_api_key, reason="BLOCKSCOUT_PRO_API_KEY not configured")
async def test_topic_filter_survives_pagination(mock_ctx):
    """query_params topic filter must be carried forward into the next-page call."""
    address = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"  # WETH — heavily used, many Transfer logs
    chain_id = "1"
    endpoint_path = f"/api/v2/addresses/{address}/logs"
    transfer_topic = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
    query_params = {"topic": transfer_topic}

    first_page = await retry_on_network_error(
        lambda: direct_api_call(
            chain_id=chain_id,
            endpoint_path=endpoint_path,
            query_params=query_params,
            ctx=mock_ctx,
        ),
        action_description="direct_api_call WETH Transfer logs first page",
    )

    assert isinstance(first_page.data, list)
    assert first_page.data, "Expected at least one log item on page 1"
    for item in first_page.data:
        assert item.topics, f"Log item has no topics: {item}"
        assert item.topics[0].lower() == transfer_topic.lower(), (
            f"Page-1 item topic mismatch: expected {transfer_topic}, got {item.topics[0]}"
        )

    assert first_page.pagination is not None, "Expected pagination on page 1"
    assert "query_params" in first_page.pagination.next_call.params, (
        "query_params must be forwarded into next_call.params"
    )
    assert first_page.pagination.next_call.params["query_params"].get("topic") == transfer_topic, (
        "topic filter must survive in next_call.params['query_params']"
    )

    second_page = await retry_on_network_error(
        lambda: direct_api_call(**first_page.pagination.next_call.params, ctx=mock_ctx),
        action_description="direct_api_call WETH Transfer logs second page (replayed next_call)",
    )

    assert isinstance(second_page.data, list)
    assert second_page.data, "Expected at least one log item on page 2"
    for item in second_page.data:
        assert item.topics, f"Page-2 log item has no topics: {item}"
        assert item.topics[0].lower() == transfer_topic.lower(), (
            f"Page-2 item topic mismatch: expected {transfer_topic}, got {item.topics[0]}. "
            "The topic filter was likely dropped from the next-page call."
        )

    assert first_page.data != second_page.data, "Page 1 and page 2 data must differ"
