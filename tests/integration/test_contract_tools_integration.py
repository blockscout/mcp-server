import aiohttp
import httpx
import pytest

from blockscout_mcp_server.models import ContractAbiData, ContractReadData, ToolResponse
from blockscout_mcp_server.tools.contract_tools import get_contract_abi, read_contract


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_contract_abi_integration(mock_ctx):
    # Use the WETH contract to ensure a rich, stable ABI is returned
    address = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
    result = await get_contract_abi(chain_id="1", address=address, ctx=mock_ctx)

    assert isinstance(result, ToolResponse)
    assert isinstance(result.data, ContractAbiData)
    assert isinstance(result.data.abi, list)
    assert len(result.data.abi) > 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_read_contract_integration(mock_ctx):
    address = "0xdAC17F958D2ee523a2206206994597C13D831ec7"
    abi = [
        {
            "constant": True,
            "inputs": [{"name": "_owner", "type": "address"}],
            "name": "balanceOf",
            "outputs": [{"name": "balance", "type": "uint256"}],
            "payable": False,
            "stateMutability": "view",
            "type": "function",
        }
    ]
    owner = "0xF977814e90dA44bFA03b6295A0616a897441aceC"
    try:
        result = await read_contract(
            chain_id="1",
            address=address,
            abi=abi,
            function_name="balanceOf",
            args=[owner],
            ctx=mock_ctx,
        )
    except (aiohttp.ClientError, httpx.HTTPError, OSError) as e:
        pytest.skip(f"Network connectivity issue: {e}")
    assert isinstance(result, ToolResponse)
    assert isinstance(result.data, ContractReadData)
    assert isinstance(result.data.result, int)
