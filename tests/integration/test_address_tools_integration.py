import json
import re
import httpx
import pytest

from .utils import _find_truncated_call_executed_function_in_logs, _extract_next_cursor

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

@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_address_logs_paginated_search_for_truncation(mock_ctx):
    """
    Tests that get_address_logs can find truncated data by searching across pages.
    """
    address = "0xFe89cc7aBB2C4183683ab71653C4cdc9B02D44b7"
    chain_id = "1"
    MAX_PAGES_TO_CHECK = 5
    cursor = None
    found_truncated_log = False

    for page_num in range(MAX_PAGES_TO_CHECK):
        try:
            result_str = await get_address_logs(
                chain_id=chain_id,
                address=address,
                ctx=mock_ctx,
                cursor=cursor,
            )
        except httpx.HTTPStatusError as e:
            pytest.skip(f"API request failed on page {page_num + 1}: {e}")

        json_part = result_str.split("**Address logs JSON:**\n")[1].split("----")[0]
        data = json.loads(json_part)

        if _find_truncated_call_executed_function_in_logs(data):
            found_truncated_log = True
            break

        next_cursor = _extract_next_cursor(result_str)
        if next_cursor:
            cursor = next_cursor
        else:
            break

    if not found_truncated_log:
        pytest.skip(
            f"Could not find a truncated 'CallExecuted' log within the first {MAX_PAGES_TO_CHECK} pages."
        )
