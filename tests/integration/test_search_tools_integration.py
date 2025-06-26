import pytest

from blockscout_mcp_server.models import TokenSearchResult, ToolResponse
from blockscout_mcp_server.tools.search_tools import TOKEN_RESULTS_LIMIT, lookup_token_by_symbol


@pytest.mark.integration
@pytest.mark.asyncio
async def test_lookup_token_by_symbol_integration(mock_ctx):
    result = await lookup_token_by_symbol(chain_id="1", symbol="USDC", ctx=mock_ctx)

    assert isinstance(result, ToolResponse)
    assert isinstance(result.data, list)

    if result.data:
        assert isinstance(result.data[0], TokenSearchResult)
        assert result.data[0].address.startswith("0x")
        assert isinstance(result.data[0].name, str)

    if len(result.data) < TOKEN_RESULTS_LIMIT:
        assert result.notes is None
    elif result.notes is not None:
        assert f"exceeds the limit of {TOKEN_RESULTS_LIMIT}" in result.notes[0]
