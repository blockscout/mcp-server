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
    sender = "0x91f51371D33e4E50e838057E8045265372f8d448"
    first = await retry_on_network_error(
        lambda: direct_api_call(
            chain_id="1",
            endpoint_path="/api/v2/proxy/account-abstraction/operations",
            query_params={"sender": sender},
            ctx=mock_ctx,
        ),
        action_description="direct_api_call account abstraction first page request",
    )

    assert first.pagination is not None
    next_params = first.pagination.next_call.params
    assert next_params["chain_id"] == "1"
    assert next_params["endpoint_path"] == "/api/v2/proxy/account-abstraction/operations"
    assert next_params["query_params"]["sender"] == sender

    second = await retry_on_network_error(
        lambda: direct_api_call(ctx=mock_ctx, **next_params),
        action_description="direct_api_call account abstraction second page request",
    )
    assert isinstance(second.data, DirectApiData)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_direct_api_call_raises_on_large_response(mock_ctx, monkeypatch):
    monkeypatch.setattr(config, "direct_api_response_size_limit", 10)
    with pytest.raises(ResponseTooLargeError):
        await retry_on_network_error(
            lambda: direct_api_call(
                chain_id="1",
                endpoint_path="/api",
                query_params={
                    "module": "logs",
                    "action": "getLogs",
                    "address": "0x000000000004444c5dc75cB358380D2e3dE08A90",
                    "topic0": "0x40e9cecb9f5f1f1c5b9c97dec2917b7ee92e57ba5563708daca94dd84ad7112f",
                    "topic1": "0x80235dd0d2b0fbac1fc5b9e04d4af3e030efd2b1026823affec8f5a6c9306c38",
                    "fromBlock": "0",
                    "toBlock": "latest",
                    "page": "1",
                    "offset": "10",
                    "sort": "desc",
                    "topic0_1_opr": "and",
                },
                ctx=mock_ctx,
            ),
            action_description="direct_api_call large response request",
        )
