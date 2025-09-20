import httpx
import pytest

from blockscout_mcp_server.models import NftCollectionHolding, ToolResponse
from blockscout_mcp_server.tools.address.nft_tokens_by_address import nft_tokens_by_address


@pytest.mark.integration
@pytest.mark.asyncio
async def test_nft_tokens_by_address_integration(mock_ctx):
    address = "0xA94b3E48215c72266f5006bcA6EE67Fff7122307"  # Address with NFT holdings
    try:
        result = await nft_tokens_by_address(chain_id="1", address=address, ctx=mock_ctx)
    except httpx.HTTPError as exc:
        pytest.skip(f"Skipping nft_tokens_by_address integration test due to network issue: {exc}")

    assert isinstance(result, ToolResponse)
    assert isinstance(result.data, list)
    assert 0 < len(result.data) <= 10
    assert result.pagination is not None

    first_holding = result.data[0]
    assert isinstance(first_holding, NftCollectionHolding)
    assert isinstance(first_holding.collection.address, str)
    assert first_holding.collection.address.startswith("0x")
    assert first_holding.collection.name is None or isinstance(first_holding.collection.name, str)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_nft_tokens_by_address_pagination_integration(mock_ctx):
    """Tests that nft_tokens_by_address can successfully use a cursor to fetch a second page."""
    address = "0xA94b3E48215c72266f5006bcA6EE67Fff7122307"
    chain_id = "1"

    try:
        first_page_response = await nft_tokens_by_address(chain_id=chain_id, address=address, ctx=mock_ctx)
    except httpx.HTTPError as exc:
        pytest.skip(f"API request failed, skipping pagination test: {exc}")

    assert isinstance(first_page_response, ToolResponse)
    assert first_page_response.pagination is not None, "Pagination info is missing."
    next_call_info = first_page_response.pagination.next_call
    assert next_call_info.tool_name == "nft_tokens_by_address"

    try:
        second_page_response = await nft_tokens_by_address(**next_call_info.params, ctx=mock_ctx)
    except httpx.HTTPError as exc:
        pytest.fail(f"API request for the second page failed with cursor: {exc}")

    assert isinstance(second_page_response, ToolResponse)
    assert isinstance(second_page_response.data, list)
    assert len(second_page_response.data) > 0
    assert first_page_response.data[0].collection.address != second_page_response.data[0].collection.address
