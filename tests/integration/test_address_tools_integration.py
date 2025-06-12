import json
import pytest

from blockscout_mcp_server.tools.address_tools import (
    get_address_info,
    nft_tokens_by_address,
    get_tokens_by_address,
    get_address_logs,
)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_nft_tokens_by_address_integration(mock_ctx):
    address = "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"  # Vitalik Buterin
    result = await nft_tokens_by_address(chain_id="1", address=address, ctx=mock_ctx)

    assert isinstance(result, str)
    assert "To get the next page call" in result
    assert 'cursor="' in result

    main_json = json.loads(result.split("----")[0])
    assert isinstance(main_json, list) and len(main_json) > 0


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


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_address_info_integration(mock_ctx):
    # Using a well-known, stable address with public tags (USDC contract)
    address = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
    result_str = await get_address_info(chain_id="1", address=address, ctx=mock_ctx)

    assert isinstance(result_str, str)

    metadata_prefix = "\nMetadata associated with the address:\n"
    assert metadata_prefix in result_str

    parts = result_str.split(metadata_prefix)
    assert len(parts) == 2, "Expected output to contain both a basic info and a metadata part"

    assert parts[0].startswith("Basic address info:")
    basic_info_json_str = parts[0].replace("Basic address info:\n", "")
    basic_info = json.loads(basic_info_json_str)
    assert basic_info["hash"].lower() == address.lower()
    assert basic_info["is_contract"] is True

    metadata_json_str = parts[1]
    metadata = json.loads(metadata_json_str)
    assert "tags" in metadata
    assert len(metadata["tags"]) > 0
    usdc_tag = next((tag for tag in metadata["tags"] if tag.get("slug") == "usdc"), None)
    assert usdc_tag is not None, "Could not find the 'usdc' tag in metadata"
    assert usdc_tag["name"].lower() in {"usd coin", "usdc"}
