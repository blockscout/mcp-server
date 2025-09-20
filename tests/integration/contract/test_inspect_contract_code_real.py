import aiohttp
import httpx
import pytest

from blockscout_mcp_server.tools.contract.inspect_contract_code import inspect_contract_code

CHAIN_ID_MAINNET = "1"
CHAIN_ID_ARBITRUM = "42161"
CHAIN_ID_SEPOLIA = "11155111"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_inspect_vyper_contract(mock_ctx):
    address = "0xa96832746393aA4465050580D35A1DfD626D0C6f"
    try:
        result = await inspect_contract_code(chain_id=CHAIN_ID_MAINNET, address=address, ctx=mock_ctx)
    except (aiohttp.ClientError, httpx.HTTPError, OSError) as exc:
        pytest.skip(f"Network connectivity issue: {exc}")

    assert result.data.language.lower() == "vyper"
    assert result.data.source_code_tree_structure


@pytest.mark.integration
@pytest.mark.asyncio
async def test_inspect_flattened_solidity_contract(mock_ctx):
    address = "0x88ad09518695c6c3712AC10a214bE5109a655671"
    try:
        result = await inspect_contract_code(chain_id=CHAIN_ID_MAINNET, address=address, ctx=mock_ctx)
    except (aiohttp.ClientError, httpx.HTTPError, OSError) as exc:
        pytest.skip(f"Network connectivity issue: {exc}")

    assert result.data.source_code_tree_structure == ["EternalStorageProxy.sol"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_inspect_multipart_stylus_contract(mock_ctx):
    address = "0xe51D13971f74CEEb1e66219E457D6F3F9C64a9e6"
    try:
        result = await inspect_contract_code(chain_id=CHAIN_ID_ARBITRUM, address=address, ctx=mock_ctx)
    except (aiohttp.ClientError, httpx.HTTPError, OSError) as exc:
        pytest.skip(f"Network connectivity issue: {exc}")

    assert len(result.data.source_code_tree_structure) > 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_inspect_single_file_solidity_contract(mock_ctx):
    address = "0xdAC17F958D2ee523a2206206994597C13D831ec7"
    try:
        meta = await inspect_contract_code(chain_id=CHAIN_ID_MAINNET, address=address, ctx=mock_ctx)
        file_name = meta.data.source_code_tree_structure[0]
        content = await inspect_contract_code(
            chain_id=CHAIN_ID_MAINNET, address=address, file_name=file_name, ctx=mock_ctx
        )
    except (aiohttp.ClientError, httpx.HTTPError, OSError) as exc:
        pytest.skip(f"Network connectivity issue: {exc}")

    assert "pragma solidity" in content.data.file_content


@pytest.mark.integration
@pytest.mark.asyncio
async def test_inspect_multipart_solidity_contract(mock_ctx):
    address = "0x0BcDfF5A966967FfB799F5030A227a6d62cE3ea6"
    try:
        result = await inspect_contract_code(chain_id=CHAIN_ID_MAINNET, address=address, ctx=mock_ctx)
    except (aiohttp.ClientError, httpx.HTTPError, OSError) as exc:
        pytest.skip(f"Network connectivity issue: {exc}")

    assert len(result.data.source_code_tree_structure) > 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_inspect_multipart_vyper_contract(mock_ctx):
    """Test inspection of a Vyper contract with additional source files."""
    address = "0xD80e9d69CDb26a6A036FFe08d0Dd5140Aca6945A"
    try:
        result = await inspect_contract_code(chain_id=CHAIN_ID_SEPOLIA, address=address, ctx=mock_ctx)
    except (aiohttp.ClientError, httpx.HTTPError, OSError) as exc:
        pytest.skip(f"Network connectivity issue: {exc}")

    assert result.data.language.lower() == "vyper"
    assert len(result.data.source_code_tree_structure) > 1

    main_file = result.data.source_code_tree_structure[0]
    assert main_file.endswith(".vy")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_inspect_not_verified_contract(mock_ctx):
    address = "0xc0a47dFe034B400B47bDaD5FecDa2621de6c4d95"
    try:
        result = await inspect_contract_code(chain_id=CHAIN_ID_MAINNET, address=address, ctx=mock_ctx)
    except (aiohttp.ClientError, httpx.HTTPError, OSError) as exc:
        pytest.skip(f"Network connectivity issue: {exc}")

    assert result.data.source_code_tree_structure == []
