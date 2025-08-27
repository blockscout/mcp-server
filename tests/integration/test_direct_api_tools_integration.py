import pytest

from blockscout_mcp_server.models import DirectApiData
from blockscout_mcp_server.tools.direct_api_tools import direct_api_call


@pytest.mark.integration
@pytest.mark.asyncio
async def test_direct_api_call_stats_counters(mock_ctx):
    result = await direct_api_call(chain_id="1", endpoint_path="/stats-service/api/v1/counters", ctx=mock_ctx)
    assert isinstance(result.data, DirectApiData)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_direct_api_call_arbitrum_messages_pagination(mock_ctx):
    first = await direct_api_call(
        chain_id="42161",
        endpoint_path="/api/v2/arbitrum/messages/to-rollup",
        ctx=mock_ctx,
    )
    assert first.pagination is not None
    next_params = first.pagination.next_call.params
    second = await direct_api_call(ctx=mock_ctx, **next_params)
    assert isinstance(second.data, DirectApiData)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_direct_api_call_blocks_validated_pagination(mock_ctx):
    path = "/api/v2/addresses/0x4838B106FCe9647Bdf1E7877BF73cE8B0BAD5f97/blocks-validated"
    first = await direct_api_call(chain_id="1", endpoint_path=path, ctx=mock_ctx)
    assert first.pagination is not None
    next_params = first.pagination.next_call.params
    second = await direct_api_call(ctx=mock_ctx, **next_params)
    assert isinstance(second.data, DirectApiData)
