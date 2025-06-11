import pytest

from blockscout_mcp_server.tools.contract_tools import get_contract_abi


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_contract_abi_integration(mock_ctx):
    # Use the WETH contract to ensure a rich, stable ABI is returned
    address = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
    result = await get_contract_abi(chain_id="1", address=address, ctx=mock_ctx)

    assert isinstance(result, dict)
    assert "abi" in result and isinstance(result["abi"], list)
    assert len(result["abi"]) > 0
