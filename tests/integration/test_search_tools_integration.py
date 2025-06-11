import pytest

from blockscout_mcp_server.tools.search_tools import lookup_token_by_symbol


@pytest.mark.integration
@pytest.mark.asyncio
async def test_lookup_token_by_symbol_integration(mock_ctx):
    result = await lookup_token_by_symbol(chain_id="1", symbol="USDC", ctx=mock_ctx)

    assert isinstance(result, list) and len(result) > 0
    first_item = result[0]
    assert "address" in first_item and first_item["address"].startswith("0x")
    assert "name" in first_item and isinstance(first_item["name"], str)
    assert "symbol" in first_item and isinstance(first_item["symbol"], str)
