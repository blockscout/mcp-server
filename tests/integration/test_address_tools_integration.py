import json
import pytest

from blockscout_mcp_server.tools.address_tools import (
    nft_tokens_by_address,
    get_tokens_by_address,
    get_address_logs,
)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_nft_tokens_by_address_integration(mock_ctx):
    address = "0xBd3531dA5CF5857e7CfAA92426877b022e612cf8"  # Pudgy Penguins contract
    result = await nft_tokens_by_address(chain_id="1", address=address, ctx=mock_ctx)

    assert isinstance(result, list) and len(result) > 0
    first_collection = result[0]
    assert "collection" in first_collection and "token_instances" in first_collection
    assert "name" in first_collection["collection"]
    assert "address" in first_collection["collection"]
    if first_collection["token_instances"]:
        assert "id" in first_collection["token_instances"][0]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_tokens_by_address_integration(mock_ctx):
    address = "0x47ac0fb4f2d84898e4d9e7b4dab3c24507a6d503"  # Binance wallet
    result = await get_tokens_by_address(chain_id="1", address=address, ctx=mock_ctx)

    assert isinstance(result, str)
    assert "To get the next page call" in result
    assert 'cursor="' in result

    main_json = json.loads(result.split("----")[0])
    assert isinstance(main_json, list) and len(main_json) > 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_address_logs_integration(mock_ctx):
    address = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"  # USDC contract
    result = await get_address_logs(chain_id="1", address=address, ctx=mock_ctx)

    assert isinstance(result, str)
    assert "To get the next page call" in result
    assert 'cursor="' in result
    assert "**Items Structure:**" in result
    assert "\"items\": [" in result
