# SPDX-License-Identifier: LicenseRef-Blockscout
import pytest

from blockscout_mcp_server.config import config
from blockscout_mcp_server.models import DirectApiData
from blockscout_mcp_server.tools.common import ResponseTooLargeError
from blockscout_mcp_server.tools.direct_api.direct_api_call import direct_api_call
from tests.integration.helpers import retry_on_network_error


@pytest.mark.integration
@pytest.mark.asyncio
async def test_direct_api_call_stats_counters(mock_ctx):
    result = await retry_on_network_error(
        lambda: direct_api_call(chain_id="1", endpoint_path="/stats-service/api/v1/counters", ctx=mock_ctx),
        action_description="direct_api_call stats counters request",
    )
    assert isinstance(result.data, DirectApiData)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_direct_api_call_arbitrum_messages_pagination(mock_ctx):
    first = await retry_on_network_error(
        lambda: direct_api_call(
            chain_id="42161",
            endpoint_path="/api/v2/arbitrum/messages/to-rollup",
            ctx=mock_ctx,
        ),
        action_description="direct_api_call arbitrum messages first page request",
    )
    assert first.pagination is not None
    next_params = first.pagination.next_call.params
    second = await retry_on_network_error(
        lambda: direct_api_call(ctx=mock_ctx, **next_params),
        action_description="direct_api_call arbitrum messages second page request",
    )
    assert isinstance(second.data, DirectApiData)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_direct_api_call_blocks_validated_pagination(mock_ctx):
    path = "/api/v2/addresses/0x4838B106FCe9647Bdf1E7877BF73cE8B0BAD5f97/blocks-validated"
    first = await retry_on_network_error(
        lambda: direct_api_call(chain_id="1", endpoint_path=path, ctx=mock_ctx),
        action_description="direct_api_call blocks validated first page request",
    )
    assert first.pagination is not None
    next_params = first.pagination.next_call.params
    second = await retry_on_network_error(
        lambda: direct_api_call(ctx=mock_ctx, **next_params),
        action_description="direct_api_call blocks validated second page request",
    )
    assert isinstance(second.data, DirectApiData)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_direct_api_call_operations_query_params_pagination(mock_ctx):
    sender = "0x9bE1B9b87D189dF444f4f8a66f1A50398bcEba37"
    first = await retry_on_network_error(
        lambda: direct_api_call(
            chain_id="100",
            endpoint_path="/api/v2/proxy/account-abstraction/operations",
            query_params={"sender": sender},
            ctx=mock_ctx,
        ),
        action_description="direct_api_call account abstraction first page request",
    )

    assert first.pagination is not None
    next_params = first.pagination.next_call.params
    assert next_params["chain_id"] == "100"
    assert next_params["endpoint_path"] == "/api/v2/proxy/account-abstraction/operations"
    assert next_params["query_params"]["sender"] == sender

    second = await retry_on_network_error(
        lambda: direct_api_call(ctx=mock_ctx, **next_params),
        action_description="direct_api_call account abstraction second page request",
    )
    assert isinstance(second.data, DirectApiData)


# The size cap is monkeypatched to 10 bytes so that any non-empty JSON
# response exceeds it. This intentionally tests "the size guard fires when
# payload > cap" end-to-end through the HTTP layer, rather than depending on
# a specific endpoint that happens to return a large payload — third-party
# response sizes drift, which made the prior "real big query" approach flaky.
# Do not remove the monkeypatch in pursuit of realism.
@pytest.mark.integration
@pytest.mark.asyncio
async def test_direct_api_call_raises_on_large_response(mock_ctx, monkeypatch):
    monkeypatch.setattr(config, "direct_api_response_size_limit", 10)
    with pytest.raises(ResponseTooLargeError):
        await retry_on_network_error(
            lambda: direct_api_call(
                chain_id="100",
                endpoint_path="/api/v2/stats",
                ctx=mock_ctx,
            ),
            action_description="direct_api_call large response request",
        )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_direct_api_call_main_page_blocks_list_response(mock_ctx):
    result = await retry_on_network_error(
        lambda: direct_api_call(chain_id="1", endpoint_path="/api/v2/main-page/blocks", ctx=mock_ctx),
        action_description="direct_api_call main page blocks list response request",
    )
    assert isinstance(result.data, DirectApiData)
    assert result.pagination is None
    items = result.data.model_dump()["items"]
    assert isinstance(items, list)
    assert items
    assert isinstance(items[0], dict)
    assert "height" in items[0]
    assert "timestamp" in items[0]
