# SPDX-License-Identifier: LicenseRef-Blockscout
# tests/integration/test_common_helpers.py
import re

import httpx
import pytest

from blockscout_mcp_server.config import config
from blockscout_mcp_server.tools.common import (
    ChainNotFoundError,
    get_blockscout_base_url,
    make_bens_request,
    make_blockscout_request,
    make_chainscout_request,
    make_metadata_request,
)
from tests.integration.helpers import retry_on_network_error


@pytest.mark.integration
@pytest.mark.asyncio
async def test_make_chainscout_request_for_chains_list():
    """
    Tests that we can successfully fetch the list of chains from the live Chainscout API.
    """
    # 1. ARRANGE
    # The only arrangement needed is to define the API path we want to test.
    api_path = "/api/chains"

    # 2. ACT
    # This will make a REAL network request.
    response_data = await make_chainscout_request(api_path=api_path)

    # 3. ASSERT
    # We can't know the exact chains, but we can check the response structure.
    assert isinstance(response_data, dict)
    assert len(response_data) > 0

    first_key = next(iter(response_data))
    first_chain = response_data[first_key]
    assert "name" in first_chain
    assert isinstance(first_chain["name"], str)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_make_bens_request_for_ens_lookup():
    """
    Tests that we can resolve a known ENS name via the live BENS API.
    """
    # ARRANGE
    # Using vitalik.eth - a stable, well-known ENS name owned by Ethereum's co-founder
    # This is more reliable than blockscout.eth which isn't owned by the Blockscout team
    ens_name = "vitalik.eth"
    api_path = f"/api/v1/1/domains/{ens_name}"
    # Vitalik's well-known and stable Ethereum address
    expected_address = "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"

    # ACT
    response_data = await make_bens_request(api_path=api_path)

    # ASSERT
    assert isinstance(response_data, dict)
    assert "resolved_address" in response_data
    assert "hash" in response_data["resolved_address"]

    # Verify the resolved address matches Vitalik's well-known address
    resolved_hash = response_data["resolved_address"]["hash"]
    assert isinstance(resolved_hash, str)
    assert resolved_hash.lower() == expected_address.lower()

    # Additional format validation for robustness
    assert resolved_hash.startswith("0x")
    assert len(resolved_hash) == 42  # Standard Ethereum address length


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize("chain_id", ["1", "137", "10", "8453"])
async def test_get_blockscout_base_url_for_known_chains(chain_id):
    """
    Tests that we can resolve the Blockscout instance URL for several known chain IDs.
    This also implicitly tests that the caching logic doesn't break things.
    """

    async def run_check():
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(config.pro_api_config_url)
            response.raise_for_status()
            cfg = response.json()
        expected_url = cfg["chains"][chain_id]
        resolved_url = await get_blockscout_base_url(chain_id=chain_id)
        assert resolved_url.rstrip("/") == expected_url.rstrip("/")

    await retry_on_network_error(run_check, action_description="known chain URL resolution")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_blockscout_base_url_for_nonexistent_chain():
    """
    Tests that get_blockscout_base_url raises the correct exception for a
    chain ID that does not exist.
    """
    # ARRANGE
    # A chain ID that is highly unlikely to ever exist.
    nonexistent_chain_id = "999999999999"

    # ACT & ASSERT
    # Use pytest.raises to confirm that the expected exception is thrown.
    expected_message = f"Chain ID '{nonexistent_chain_id}' is not supported by the Blockscout API."
    with pytest.raises(ChainNotFoundError, match=re.escape(expected_message)):
        await get_blockscout_base_url(chain_id=nonexistent_chain_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_make_blockscout_request_for_block_info():
    """
    Tests the full flow: resolving a URL and then making a request
    to that Blockscout instance.
    """
    # ARRANGE
    chain_id = "100"  # Gnosis Chain
    block_number = "46282564"
    api_path = f"/api/v2/blocks/{block_number}"

    # First, get the base URL for our target chain. This re-uses a function
    # we've already tested, which is fine for an integration test.
    base_url = await get_blockscout_base_url(chain_id=chain_id)

    # ACT
    response_data = await make_blockscout_request(base_url=base_url, api_path=api_path)

    # ASSERT
    # Check the structure of the response for this specific block.
    assert isinstance(response_data, dict)
    assert response_data["height"] == 46282564
    assert "timestamp" in response_data
    assert isinstance(response_data["gas_used"], str)  # Blockscout API returns this as a string
    assert "parent_hash" in response_data


@pytest.mark.integration
@pytest.mark.asyncio
async def test_make_metadata_request_for_address_tags():
    """
    Tests that we can successfully fetch address metadata from the live Metadata API.
    """
    # Using a well-known address with stable tags (USDC contract)
    address = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
    chain_id = "1"  # Ethereum Mainnet
    api_path = "/api/v1/metadata"
    params = {"addresses": address, "chainId": chain_id}

    response_data = await make_metadata_request(api_path=api_path, params=params)

    assert isinstance(response_data, dict)
    assert "addresses" in response_data
    address_key = next(iter(response_data["addresses"].keys()))
    assert address_key.lower() == address.lower()
    assert "tags" in response_data["addresses"][address_key]
    assert len(response_data["addresses"][address_key]["tags"]) > 0
    assert "name" in response_data["addresses"][address_key]["tags"][0]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_make_blockscout_post_request_eth_rpc():
    from blockscout_mcp_server.tools.common import make_blockscout_post_request

    base_url = await get_blockscout_base_url(chain_id="1")
    response_data = await make_blockscout_post_request(
        base_url=base_url,
        api_path="/api/eth-rpc",
        json_body={"jsonrpc": "2.0", "method": "eth_blockNumber", "params": [], "id": 1},
    )
    assert isinstance(response_data, dict)
    assert response_data.get("jsonrpc") == "2.0"
    assert isinstance(response_data.get("result"), str)
    assert response_data["result"].startswith("0x")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_blockscout_base_url_for_pro_api_only_chain():
    async def run_check():
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(config.pro_api_config_url)
            response.raise_for_status()
            cfg = response.json()
        resolved = await get_blockscout_base_url("480")
        assert resolved.rstrip("/") == cfg["chains"]["480"].rstrip("/")

    await retry_on_network_error(run_check, action_description="pro-api-only chain resolution")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_blockscout_base_url_for_chainscout_only_chain():
    with pytest.raises(ChainNotFoundError):
        await get_blockscout_base_url("17000")
