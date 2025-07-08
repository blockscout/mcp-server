import httpx
import pytest

from blockscout_mcp_server.models import (
    AddressInfoData,
    AddressLogItem,
    NftCollectionHolding,
    ToolResponse,
)
from blockscout_mcp_server.tools.address_tools import (
    get_address_info,
    get_address_logs,
    get_tokens_by_address,
    nft_tokens_by_address,
)
from tests.integration.helpers import is_log_a_truncated_call_executed


@pytest.mark.integration
@pytest.mark.asyncio
async def test_nft_tokens_by_address_integration(mock_ctx):
    address = "0xA94b3E48215c72266f5006bcA6EE67Fff7122307"  # Address with NFT holdings
    result = await nft_tokens_by_address(chain_id="1", address=address, ctx=mock_ctx)

    assert isinstance(result, ToolResponse)
    assert isinstance(result.data, list)
    assert 0 < len(result.data) <= 10
    assert result.pagination is not None

    first_holding = result.data[0]
    assert isinstance(first_holding, NftCollectionHolding)
    assert isinstance(first_holding.collection.address, str)
    assert first_holding.collection.address.startswith("0x")
    # Collection name can be None from the API
    assert first_holding.collection.name is None or isinstance(first_holding.collection.name, str)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_tokens_by_address_integration(mock_ctx):
    address = "0x47ac0fb4f2d84898e4d9e7b4dab3c24507a6d503"  # Binance wallet
    result = await get_tokens_by_address(chain_id="1", address=address, ctx=mock_ctx)

    assert isinstance(result, ToolResponse)
    assert isinstance(result.data, list) and len(result.data) > 0
    assert result.pagination is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_address_logs_integration(mock_ctx):
    address = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"  # USDC contract
    result = await get_address_logs(chain_id="1", address=address, ctx=mock_ctx)

    assert isinstance(result, ToolResponse)
    assert result.pagination is not None
    assert isinstance(result.data, list)
    assert 0 < len(result.data) <= 10

    first_log = result.data[0]
    assert isinstance(first_log, AddressLogItem)
    assert isinstance(first_log.transaction_hash, str)
    assert first_log.transaction_hash.startswith("0x")
    assert isinstance(first_log.block_number, int)


@pytest.mark.asyncio
async def test_get_address_info_integration(mock_ctx):
    # Using a well-known, stable address with public tags (USDC contract)
    address = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
    try:
        result = await get_address_info(chain_id="1", address=address, ctx=mock_ctx)
    except httpx.RequestError as e:
        pytest.skip(f"Skipping test due to network error on primary API call: {e}")

    assert isinstance(result, ToolResponse)
    assert isinstance(result.data, AddressInfoData)

    assert result.data.basic_info["hash"].lower() == address.lower()
    assert result.data.basic_info["is_contract"] is True

    if result.notes:
        assert "Could not retrieve address metadata" in result.notes[0]
        assert result.data.metadata is None
        pytest.skip("Metadata service was unavailable, but the tool handled it gracefully as expected.")
    else:
        metadata = result.data.metadata
        assert isinstance(metadata, dict)
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
        first_page_response = await get_tokens_by_address(chain_id=chain_id, address=address, ctx=mock_ctx)
    except httpx.HTTPStatusError as e:
        pytest.skip(f"API request failed, skipping pagination test: {e}")

    assert first_page_response.pagination is not None, "Pagination info is missing."
    next_call_info = first_page_response.pagination.next_call
    assert next_call_info.tool_name == "get_tokens_by_address"
    cursor = next_call_info.params.get("cursor")
    assert cursor is not None, "Cursor is missing from next_call params."

    try:
        second_page_response = await get_tokens_by_address(**next_call_info.params, ctx=mock_ctx)
    except httpx.HTTPStatusError as e:
        pytest.fail(f"API request for the second page failed with cursor: {e}")

    assert isinstance(second_page_response, ToolResponse)
    assert isinstance(second_page_response.data, list)
    assert len(second_page_response.data) > 0
    first_page_addresses = {token.address for token in first_page_response.data}
    second_page_addresses = {token.address for token in second_page_response.data}
    assert len(first_page_addresses.intersection(second_page_addresses)) == 0, (
        "Pagination error: Found overlapping tokens between page 1 and page 2."
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_nft_tokens_by_address_pagination_integration(mock_ctx):
    """Tests that nft_tokens_by_address can successfully use a cursor to fetch a second page."""
    address = "0xA94b3E48215c72266f5006bcA6EE67Fff7122307"
    chain_id = "1"

    try:
        first_page_response = await nft_tokens_by_address(chain_id=chain_id, address=address, ctx=mock_ctx)
    except httpx.HTTPStatusError as e:
        pytest.skip(f"API request failed, skipping pagination test: {e}")

    assert isinstance(first_page_response, ToolResponse)
    assert first_page_response.pagination is not None, "Pagination info is missing."
    next_call_info = first_page_response.pagination.next_call
    assert next_call_info.tool_name == "nft_tokens_by_address"

    try:
        second_page_response = await nft_tokens_by_address(**next_call_info.params, ctx=mock_ctx)
    except httpx.HTTPStatusError as e:
        pytest.fail(f"API request for the second page failed with cursor: {e}")

    assert isinstance(second_page_response, ToolResponse)
    assert isinstance(second_page_response.data, list)
    assert len(second_page_response.data) > 0
    assert first_page_response.data[0].collection.address != second_page_response.data[0].collection.address


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

    assert first_page_result.pagination is not None
    cursor = first_page_result.pagination.next_call.params.get("cursor")
    assert cursor

    try:
        second_page_result = await get_address_logs(chain_id=chain_id, address=address, ctx=mock_ctx, cursor=cursor)
    except httpx.HTTPStatusError as e:
        pytest.fail(f"API request for the second page failed with cursor: {e}")

    assert isinstance(second_page_result.data, list)
    assert len(second_page_result.data) > 0
    assert first_page_result.data[0].transaction_hash != second_page_result.data[0].transaction_hash


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_address_logs_paginated_search_for_truncation(mock_ctx):
    """
    Tests that get_address_logs can find a 'CallExecuted' event with truncated
    decoded data by searching across pages. This validates the handling of
    complex nested truncation from the live API.
    """
    address = "0xFe89cc7aBB2C4183683ab71653C4cdc9B02D44b7"
    chain_id = "1"
    MAX_PAGES_TO_CHECK = 5
    cursor = None
    found_truncated_log = False

    for page_num in range(MAX_PAGES_TO_CHECK):
        try:
            result = await get_address_logs(chain_id=chain_id, address=address, ctx=mock_ctx, cursor=cursor)
        except httpx.HTTPStatusError as e:
            pytest.skip(f"API request failed on page {page_num + 1}: {e}")

        for item in result.data:
            if is_log_a_truncated_call_executed(item):
                found_truncated_log = True
                break

        if found_truncated_log:
            break

        if result.pagination:
            cursor = result.pagination.next_call.params.get("cursor")
        else:
            break

    if not found_truncated_log:
        pytest.skip(f"Could not find a truncated 'CallExecuted' log within the first {MAX_PAGES_TO_CHECK} pages.")
