import pytest

from blockscout_mcp_server.models import ContractAbiData, ToolResponse
from blockscout_mcp_server.tools.contract.get_contract_abi import get_contract_abi

CHAIN_ID_MAINNET = "1"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_contract_abi_integration(mock_ctx):
    """Use the WETH contract to ensure a rich, stable ABI is returned."""
    address = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
    result = await get_contract_abi(chain_id=CHAIN_ID_MAINNET, address=address, ctx=mock_ctx)

    assert isinstance(result, ToolResponse)
    assert isinstance(result.data, ContractAbiData)
    assert isinstance(result.data.abi, list)
    assert len(result.data.abi) > 0
