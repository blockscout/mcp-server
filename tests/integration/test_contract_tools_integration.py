import json
from pathlib import Path
from typing import Any

import aiohttp
import httpx
import pytest
from eth_utils import to_checksum_address

from blockscout_mcp_server.models import ContractAbiData, ContractReadData, ToolResponse
from blockscout_mcp_server.tools.contract_tools import get_contract_abi, read_contract
from blockscout_mcp_server.web3_pool import WEB3_POOL

CHAIN_ID_SEPOLIA = "11155111"
CONTRACT_ADDRESS = "0xD9a3039cfC70aF84AC9E566A2526fD3b683B995B"
ABI_PATH = Path(__file__).with_name("web3py_test_contract_abi.json")
TEST_CONTRACT_ABI = json.loads(ABI_PATH.read_text())
ABI_BY_NAME = {entry["name"]: entry for entry in TEST_CONTRACT_ABI}


async def _invoke(mock_ctx, function_name: str, args: list[Any]) -> Any:
    try:
        result = await read_contract(
            chain_id=CHAIN_ID_SEPOLIA,
            address=CONTRACT_ADDRESS,
            abi=ABI_BY_NAME[function_name],
            function_name=function_name,
            args=args,
            ctx=mock_ctx,
        )
    except (aiohttp.ClientError, httpx.HTTPError, OSError) as e:
        pytest.skip(f"Network connectivity issue: {e}")
    finally:
        await WEB3_POOL.close()
    return result.data.result


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
    abi = {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function",
    }
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
    abi = {
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


@pytest.mark.integration
@pytest.mark.asyncio
async def test_read_contract_sepolia_testInt(mock_ctx):
    res = await _invoke(mock_ctx, "testInt", [-42])
    assert res == -42


@pytest.mark.integration
@pytest.mark.asyncio
async def test_read_contract_sepolia_testUint(mock_ctx):
    res = await _invoke(mock_ctx, "testUint", [12345])
    assert res == 12345


@pytest.mark.integration
@pytest.mark.asyncio
async def test_read_contract_sepolia_testAddress(mock_ctx):
    addr = "0x742d35cc6634c0532925a3b8d98d8e35ce02e52a"
    res = await _invoke(mock_ctx, "testAddress", [addr])
    assert res == to_checksum_address(addr)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_read_contract_sepolia_testBytes(mock_ctx):
    data = "0x64617461"
    res = await _invoke(mock_ctx, "testBytes", [data])
    assert res == data


@pytest.mark.integration
@pytest.mark.asyncio
async def test_read_contract_sepolia_testBool(mock_ctx):
    res = await _invoke(mock_ctx, "testBool", [True])
    assert res is True


@pytest.mark.integration
@pytest.mark.asyncio
async def test_read_contract_sepolia_testUintArray(mock_ctx):
    res = await _invoke(mock_ctx, "testUintArray", [[1, 2, 3, 4, 5]])
    assert res == [1, 2, 3, 4, 5]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_read_contract_sepolia_testAddressArray(mock_ctx):
    addr1 = "0x742d35cc6634c0532925a3b8d98d8e35ce02e52a"
    addr2 = "0x8ba1f109551bd432803012645ff1c26ad3dbebf9"
    res = await _invoke(mock_ctx, "testAddressArray", [[addr1, addr2]])
    assert res == 2


@pytest.mark.integration
@pytest.mark.asyncio
async def test_read_contract_sepolia_testBytesArray(mock_ctx):
    data1 = "0x64617461"
    data2 = "0x6461746132"
    res = await _invoke(mock_ctx, "testBytesArray", [[data1, data2]])
    assert res == 2


@pytest.mark.integration
@pytest.mark.asyncio
async def test_read_contract_sepolia_testSimpleStruct(mock_ctx):
    simple_struct = {"id": 1, "name": "first", "active": True}
    res = await _invoke(mock_ctx, "testSimpleStruct", [simple_struct])
    assert res[0] == 1 and res[1] == "first" and res[2] is True


@pytest.mark.integration
@pytest.mark.asyncio
async def test_read_contract_sepolia_testNestedStruct(mock_ctx):
    addr1 = "0x742d35cc6634c0532925a3b8d98d8e35ce02e52a"
    nested_struct = {
        "value": 100,
        "inner": {"id": 1, "name": "inner", "active": False},
        "owner": addr1,
    }
    res = await _invoke(mock_ctx, "testNestedStruct", [nested_struct])
    assert res[0] == 100 and res[1][0] == 1 and res[2] == to_checksum_address(addr1)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_read_contract_sepolia_testStructArray(mock_ctx):
    struct_arr = [
        {"id": 1, "name": "first", "active": True},
        {"id": 2, "name": "second", "active": False},
    ]
    res = await _invoke(mock_ctx, "testStructArray", [struct_arr])
    assert res == 2


@pytest.mark.integration
@pytest.mark.asyncio
async def test_read_contract_sepolia_testArrayStruct(mock_ctx):
    addr1 = "0x742d35cc6634c0532925a3b8d98d8e35ce02e52a"
    addr2 = "0x8ba1f109551bd432803012645ff1c26ad3dbebf9"
    array_struct = {
        "title": "title",
        "numbers": [1, 2, 3],
        "addresses": [addr1, addr2],
    }
    res = await _invoke(mock_ctx, "testArrayStruct", [array_struct])
    assert res[0] == "title" and res[1] == [1, 2, 3] and res[2][1] == to_checksum_address(addr2)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_read_contract_sepolia_testMultipleParams(mock_ctx):
    addr = "0x8ba1f109551bd432803012645ff1c26ad3dbebf9"
    res = await _invoke(
        mock_ctx,
        "testMultipleParams",
        [-100, 200, addr, True, "0x64617461", {"id": 1, "name": "struct", "active": False}],
    )
    assert res[0] == -100 and res[1] == 200 and res[2] == to_checksum_address(addr)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_read_contract_sepolia_testFixedArray(mock_ctx):
    res = await _invoke(mock_ctx, "testFixedArray", [[10, 20, 30]])
    assert res == [10, 20, 30]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_read_contract_sepolia_testBytes32(mock_ctx):
    value = "0x" + "1234567890abcdef" * 4
    res = await _invoke(mock_ctx, "testBytes32", [value])
    assert res == value


@pytest.mark.integration
@pytest.mark.asyncio
async def test_read_contract_sepolia_testString(mock_ctx):
    res = await _invoke(mock_ctx, "testString", ["World"])
    assert res == "World"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_read_contract_sepolia_testEnum(mock_ctx):
    res = await _invoke(mock_ctx, "testEnum", [0])
    assert res == 0
