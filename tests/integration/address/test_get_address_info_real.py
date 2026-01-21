import httpx
import pytest

from blockscout_mcp_server.models import AddressInfoData, ToolResponse
from blockscout_mcp_server.tools.address.get_address_info import get_address_info


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_address_info_integration(mock_ctx):
    """Validate get_address_info against the live API for a well-known contract."""
    address = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"  # USDC contract

    try:
        result = await get_address_info(chain_id="1", address=address, ctx=mock_ctx)
    except httpx.RequestError as exc:
        pytest.skip(f"Skipping test due to network error on primary API call: {exc}")

    assert isinstance(result, ToolResponse)
    assert isinstance(result.data, AddressInfoData)

    assert result.data.basic_info["hash"].lower() == address.lower()
    assert result.data.basic_info["is_contract"] is True

    if result.notes:
        if any("Could not retrieve first transaction details" in note for note in result.notes):
            pytest.skip("First-transaction endpoint unavailable; skipping first-tx assertions.")
        assert "Could not retrieve address metadata" in result.notes[0]
        assert result.data.metadata is None
        pytest.skip("Metadata service was unavailable, but the tool handled it gracefully as expected.")

    # Verify first transaction details
    assert result.data.first_transaction_details is not None, "First transaction details should be populated"
    assert result.data.first_transaction_details.block_number is not None
    assert isinstance(result.data.first_transaction_details.block_number, int)
    assert result.data.first_transaction_details.block_number > 0
    assert result.data.first_transaction_details.timestamp is not None
    assert isinstance(result.data.first_transaction_details.timestamp, str)

    metadata = result.data.metadata
    assert isinstance(metadata, dict)
    assert "tags" in metadata

    usdc_tag = next((tag for tag in metadata["tags"] if tag.get("slug") == "usdc"), None)
    assert usdc_tag is not None, "Could not find the 'usdc' tag in metadata"
    assert usdc_tag["name"].lower() in {"usd coin", "usdc"}
