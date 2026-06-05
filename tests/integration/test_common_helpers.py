# SPDX-License-Identifier: LicenseRef-Blockscout
# tests/integration/test_common_helpers.py
import pytest

from blockscout_mcp_server.config import config
from blockscout_mcp_server.pro_api_key_context import _client_key_state, _Valid
from blockscout_mcp_server.tools.common import (
    ChainNotFoundError,
    ensure_chain_supported,
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
@pytest.mark.skipif(not config.pro_api_key, reason="BLOCKSCOUT_PRO_API_KEY not configured")
async def test_make_blockscout_request_for_block_info():
    """
    Tests that make_blockscout_request routes through the PRO API using chain_id.
    """
    # ARRANGE
    chain_id = "100"  # Gnosis Chain
    block_number = "46282564"
    api_path = f"/api/v2/blocks/{block_number}"

    # ACT
    response_data = await make_blockscout_request(chain_id=chain_id, api_path=api_path)

    # ASSERT
    # Check the structure of the response for this specific block.
    assert isinstance(response_data, dict)
    assert response_data["height"] == 46282564
    assert "timestamp" in response_data
    assert isinstance(response_data["gas_used"], str)  # Blockscout API returns this as a string
    assert "parent_hash" in response_data


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.skipif(not config.pro_api_key, reason="BLOCKSCOUT_PRO_API_KEY not configured")
async def test_make_metadata_request_for_address_tags():
    """
    Tests that we can successfully fetch address metadata from the live Blockscout PRO API metadata endpoint.
    """
    # Using a well-known address with stable tags (USDC contract)
    address = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
    chain_id = "1"  # Ethereum Mainnet
    api_path = "/services/metadata/api/v1/metadata"
    params = {"addresses": address, "chainId": chain_id}

    response_data = await retry_on_network_error(
        lambda: make_metadata_request(api_path=api_path, params=params),
        action_description="PRO API metadata request",
    )

    assert isinstance(response_data, dict)
    assert "addresses" in response_data
    address_key = next(iter(response_data["addresses"].keys()))
    assert address_key.lower() == address.lower()
    assert "tags" in response_data["addresses"][address_key]
    assert len(response_data["addresses"][address_key]["tags"]) > 0
    assert "name" in response_data["addresses"][address_key]["tags"][0]


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.skipif(not config.pro_api_key, reason="BLOCKSCOUT_PRO_API_KEY not configured")
async def test_make_blockscout_post_request_eth_rpc():
    from blockscout_mcp_server.tools.common import make_blockscout_post_request

    response_data = await make_blockscout_post_request(
        chain_id="1",
        api_path="/json-rpc",
        json_body={"jsonrpc": "2.0", "method": "eth_blockNumber", "params": [], "id": 1},
    )
    assert isinstance(response_data, dict)
    assert response_data.get("jsonrpc") == "2.0"
    assert isinstance(response_data.get("result"), str)
    assert response_data["result"].startswith("0x")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_ensure_chain_supported_for_known_chain():
    """
    Confirms that ensure_chain_supported does not raise for a well-known chain.
    """

    async def run_check():
        await ensure_chain_supported("1")

    await retry_on_network_error(run_check, action_description="ensure_chain_supported known chain")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_ensure_chain_supported_for_bogus_chain():
    """
    Confirms that ensure_chain_supported raises ChainNotFoundError for an
    obviously-unsupported chain id.
    """
    with pytest.raises(ChainNotFoundError):
        await ensure_chain_supported("99999999")


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.skipif(not config.pro_api_key, reason="BLOCKSCOUT_PRO_API_KEY not configured")
async def test_make_blockscout_request_client_key_via_context_var(monkeypatch):
    """
    Validates that a well-formed key placed in the request-scoped ContextVar is what
    actually authenticates a live PRO API request when config.pro_api_key is blank.

    This closes the gap that mocked unit tests leave: it proves that a resolved client
    key carries a real request against the live gateway (not just under mocks).  Header
    extraction and decorator scoping are proven separately in Phases 2–3; this test does
    not exercise them.
    """
    # ARRANGE
    # Capture the configured key as the stand-in client key, then blank the server key so
    # any accidental server-key fallback would fail the request rather than mask the bug.
    client_key = config.pro_api_key
    monkeypatch.setattr(config, "pro_api_key", "")

    # Set the ContextVar to the valid state holding the client key; reset it in finally
    # so the state never leaks into other tests.
    token = _client_key_state.set(_Valid(value=client_key))
    try:
        chain_id = "100"  # Gnosis Chain
        block_number = "46282564"
        api_path = f"/api/v2/blocks/{block_number}"

        # ACT — same chain/path as test_make_blockscout_request_for_block_info, wrapped
        # in retry_on_network_error for transient-failure resilience.
        response_data = await retry_on_network_error(
            lambda: make_blockscout_request(chain_id=chain_id, api_path=api_path),
            action_description="PRO API block request with client key via ContextVar",
        )
    finally:
        _client_key_state.reset(token)

    # ASSERT — a successful response proves the client key alone carried the request.
    assert isinstance(response_data, dict)
    assert response_data["height"] == 46282564
    assert "timestamp" in response_data
    assert isinstance(response_data["gas_used"], str)  # Blockscout API returns this as a string
    assert "parent_hash" in response_data
