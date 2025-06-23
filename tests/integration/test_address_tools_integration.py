import json
import re
import httpx
import pytest

from blockscout_mcp_server.tools.address_tools import (
    get_address_info,
    nft_tokens_by_address,
    get_tokens_by_address,
    get_address_logs,
)
from blockscout_mcp_server.tools.common import get_blockscout_base_url


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
    assert "**Address logs JSON:**" in result

    json_part = result.split("----")[0]
    data = json.loads(json_part.split("**Address logs JSON:**\n")[-1])

    assert "items" in data
    assert isinstance(data["items"], list)
    assert len(data["items"]) > 0

    first_log = data["items"][0]
    expected_keys = {
        "block_number",
        "data",
        "decoded",
        "index",
        "topics",
        "transaction_hash",
    }
    assert expected_keys.issubset(first_log.keys())
    if "data_truncated" in first_log:
        assert isinstance(first_log["data_truncated"], bool)
    assert isinstance(first_log["transaction_hash"], str)
    assert first_log["transaction_hash"].startswith("0x")
    assert isinstance(first_log["block_number"], int)
    assert isinstance(first_log["index"], int)
    assert isinstance(first_log["topics"], list)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_address_logs_with_decoded_truncation_integration(mock_ctx):
    """Ensure decoded parameter truncation is detected."""
    address = "0x703806E61847984346d2D7DDd853049627e50A40"
    chain_id = "1"

    base_url = await get_blockscout_base_url(chain_id)
    try:
        result = await get_address_logs(chain_id=chain_id, address=address, ctx=mock_ctx)
    except httpx.HTTPStatusError as e:
        pytest.skip(f"Address logs unavailable from the API: {e}")

    assert "**Note on Truncated Data:**" in result
    assert f"`curl \"{base_url}/api/v2/transactions/{{THE_TRANSACTION_HASH}}/logs\"`" in result

    json_part = result.split("**Address logs JSON:**\n")[1].split("----")[0]
    data = json.loads(json_part)

    scope_function_log = next(
        (
            item
            for item in data.get("items", [])
            if isinstance(item.get("decoded"), dict)
            and item["decoded"].get("method_call", "").startswith("ScopeFunction")
        ),
        None,
    )

    if not scope_function_log:
        pytest.skip("Could not find a 'ScopeFunction' event log in the live data.")

    conditions_param = next(
        (
            p
            for p in scope_function_log["decoded"].get("parameters", [])
            if p.get("name") == "conditions"
        ),
        None,
    )

    if not conditions_param:
        pytest.skip("Could not find 'conditions' parameter in the 'ScopeFunction' event.")

    found_truncation = False
    for condition_tuple in conditions_param.get("value", []):
        if isinstance(condition_tuple[-1], dict) and condition_tuple[-1].get("value_truncated"):
            found_truncation = True
            break

    if not found_truncation:
        pytest.skip("Could not find a truncated 'bytes' value in the 'conditions' parameter.")



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


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_tokens_by_address_pagination_integration(mock_ctx):
    """Tests that get_tokens_by_address can successfully use a cursor to fetch a second page."""
    address = "0x47ac0fb4f2d84898e4d9e7b4dab3c24507a6d503"
    chain_id = "1"

    try:
        first_page_result = await get_tokens_by_address(chain_id=chain_id, address=address, ctx=mock_ctx)
    except httpx.HTTPStatusError as e:
        pytest.skip(f"API request failed, skipping pagination test: {e}")

    assert "To get the next page call" in first_page_result
    cursor_match = re.search(r'cursor="([^"]+)"', first_page_result)
    assert cursor_match is not None, "Could not find cursor in the first page response."
    cursor = cursor_match.group(1)
    assert len(cursor) > 0

    try:
        second_page_result = await get_tokens_by_address(chain_id=chain_id, address=address, ctx=mock_ctx, cursor=cursor)
    except httpx.HTTPStatusError as e:
        pytest.fail(f"API request for the second page failed with cursor: {e}")

    assert "Error: Invalid or expired pagination cursor" not in second_page_result

    first_page_json_str = first_page_result.split("----")[0]
    second_page_json_str = second_page_result.split("----")[0]

    first_page_data = json.loads(first_page_json_str)
    second_page_data = json.loads(second_page_json_str)

    assert isinstance(second_page_data, list)
    assert len(second_page_data) > 0
    assert first_page_data[0] != second_page_data[0]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_nft_tokens_by_address_pagination_integration(mock_ctx):
    """Tests that nft_tokens_by_address can successfully use a cursor to fetch a second page."""
    address = "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"
    chain_id = "1"

    try:
        first_page_result = await nft_tokens_by_address(chain_id=chain_id, address=address, ctx=mock_ctx)
    except httpx.HTTPStatusError as e:
        pytest.skip(f"API request failed, skipping pagination test: {e}")

    assert "To get the next page call" in first_page_result
    cursor_match = re.search(r'cursor="([^"]+)"', first_page_result)
    assert cursor_match is not None, "Could not find cursor in the first page response."
    cursor = cursor_match.group(1)
    assert len(cursor) > 0

    try:
        second_page_result = await nft_tokens_by_address(chain_id=chain_id, address=address, ctx=mock_ctx, cursor=cursor)
    except httpx.HTTPStatusError as e:
        pytest.fail(f"API request for the second page failed with cursor: {e}")

    assert "Error: Invalid or expired pagination cursor" not in second_page_result

    first_page_json_str = first_page_result.split("----")[0]
    second_page_json_str = second_page_result.split("----")[0]

    first_page_data = json.loads(first_page_json_str)
    second_page_data = json.loads(second_page_json_str)

    assert isinstance(second_page_data, list)
    assert len(second_page_data) > 0
    assert first_page_data[0] != second_page_data[0]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_address_logs_pagination_integration(mock_ctx):
    """Tests that get_address_logs can successfully use a cursor to fetch a second page."""
    address = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
    chain_id = "1"

    try:
        first_page_result = await get_address_logs(chain_id=chain_id, address=address, ctx=mock_ctx)
    except httpx.HTTPStatusError as e:
        pytest.skip(f"API request failed, skipping pagination test: {e}")

    assert "To get the next page call" in first_page_result
    cursor_match = re.search(r'cursor="([^"]+)"', first_page_result)
    assert cursor_match is not None, "Could not find cursor in the first page response."
    cursor = cursor_match.group(1)
    assert len(cursor) > 0

    try:
        second_page_result = await get_address_logs(chain_id=chain_id, address=address, ctx=mock_ctx, cursor=cursor)
    except httpx.HTTPStatusError as e:
        pytest.fail(f"API request for the second page failed with cursor: {e}")

    assert "Error: Invalid or expired pagination cursor" not in second_page_result

    first_page_json_str = first_page_result.split("----")[0].split("**Address logs JSON:**\n")[-1]
    second_page_json_str = second_page_result.split("----")[0].split("**Address logs JSON:**\n")[-1]

    first_page_data = json.loads(first_page_json_str)
    second_page_data = json.loads(second_page_json_str)

    assert isinstance(second_page_data.get("items"), list)
    assert len(second_page_data["items"]) > 0
    assert first_page_data["items"][0] != second_page_data["items"][0]
