import httpx
import pytest

from blockscout_mcp_server.models import ToolResponse
from blockscout_mcp_server.tools.address.get_tokens_by_address import get_tokens_by_address


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_tokens_by_address_integration(mock_ctx):
    address = "0x47ac0fb4f2d84898e4d9e7b4dab3c24507a6d503"  # Binance wallet
    try:
        result = await get_tokens_by_address(chain_id="1", address=address, ctx=mock_ctx)
    except httpx.HTTPError as exc:
        pytest.skip(f"Skipping get_tokens_by_address integration test due to network issue: {exc}")

    assert isinstance(result, ToolResponse)
    assert isinstance(result.data, list) and len(result.data) > 0
    assert result.pagination is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_tokens_by_address_pagination_integration(mock_ctx):
    """Tests that get_tokens_by_address can successfully use a cursor to fetch a second page."""
    address = "0x47ac0fb4f2d84898e4d9e7b4dab3c24507a6d503"
    chain_id = "1"

    try:
        first_page_response = await get_tokens_by_address(chain_id=chain_id, address=address, ctx=mock_ctx)
    except httpx.HTTPError as exc:
        pytest.skip(f"API request failed, skipping pagination test: {exc}")

    assert first_page_response.pagination is not None, "Pagination info is missing."
    next_call_info = first_page_response.pagination.next_call
    assert next_call_info.tool_name == "get_tokens_by_address"

    cursor = next_call_info.params.get("cursor")
    assert cursor is not None, "Cursor is missing from next_call params."

    try:
        second_page_response = await get_tokens_by_address(**next_call_info.params, ctx=mock_ctx)
    except httpx.HTTPError as exc:
        pytest.fail(f"API request for the second page failed with cursor: {exc}")

    assert isinstance(second_page_response, ToolResponse)
    assert isinstance(second_page_response.data, list)
    assert len(second_page_response.data) > 0

    first_page_addresses = {token.address for token in first_page_response.data}
    second_page_addresses = {token.address for token in second_page_response.data}
    assert len(first_page_addresses.intersection(second_page_addresses)) == 0, (
        "Pagination error: Found overlapping tokens between page 1 and page 2."
    )
