import aiohttp
import httpx
import pytest

from blockscout_mcp_server.models import ContractAbiData, ContractReadData, ToolResponse
from blockscout_mcp_server.tools.contract_tools import get_contract_abi, read_contract
from blockscout_mcp_server.web3_pool import WEB3_POOL


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
    finally:
        await WEB3_POOL.close()
    assert isinstance(result, ToolResponse)
    assert isinstance(result.data, ContractReadData)
    assert isinstance(result.data.result, int)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_read_contract_decodes_tuple_result(mock_ctx):
    """Verify that tuple-based return values are decoded correctly."""
    address = "0x1c479675ad559DC151F6Ec7ed3FbF8ceE79582B6"
    abi = [
        {
            "inputs": [],
            "name": "buffer",
            "outputs": [
                {"internalType": "uint64", "name": "bufferBlocks", "type": "uint64"},
                {"internalType": "uint64", "name": "max", "type": "uint64"},
                {"internalType": "uint64", "name": "threshold", "type": "uint64"},
                {"internalType": "uint64", "name": "prevBlockNumber", "type": "uint64"},
                {
                    "internalType": "uint64",
                    "name": "replenishRateInBasis",
                    "type": "uint64",
                },
                {
                    "internalType": "uint64",
                    "name": "prevSequencedBlockNumber",
                    "type": "uint64",
                },
            ],
            "stateMutability": "view",
            "type": "function",
        }
    ]
    try:
        result = await read_contract(
            chain_id="1",
            address=address,
            abi=abi,
            function_name="buffer",
            args=[],
            ctx=mock_ctx,
        )
    except (aiohttp.ClientError, httpx.HTTPError, OSError) as e:
        pytest.skip(f"Network connectivity issue: {e}")
    finally:
        await WEB3_POOL.close()
    assert isinstance(result, ToolResponse)
    assert isinstance(result.data, ContractReadData)
    assert isinstance(result.data.result, list | tuple)
    assert len(result.data.result) == 6
    for value in result.data.result:
        assert isinstance(value, int)
