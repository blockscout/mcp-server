import pytest

from blockscout_mcp_server.constants import INPUT_DATA_TRUNCATION_LIMIT
from blockscout_mcp_server.models import AddressInfoData, ToolResponse
from blockscout_mcp_server.tools.address.get_address_info import get_address_info
from tests.integration.helpers import retry_on_network_error


def _assert_no_oversized_strings(value: object) -> None:
    if isinstance(value, str):
        assert len(value) <= INPUT_DATA_TRUNCATION_LIMIT
        return

    if isinstance(value, list):
        for item in value:
            _assert_no_oversized_strings(item)
        return

    if isinstance(value, dict):
        if value.get("value_truncated") is True:
            assert "value_sample" in value
            return

        for nested_value in value.values():
            _assert_no_oversized_strings(nested_value)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_address_info_integration(mock_ctx):
    """Validate get_address_info against the live API for a well-known contract."""
    address = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"  # USDC contract

    result = await retry_on_network_error(
        lambda: get_address_info(chain_id="1", address=address, ctx=mock_ctx),
        action_description="get_address_info request",
    )

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


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_address_info_vitalik_metadata_meta_is_parsed_and_truncated(mock_ctx):
    address = "0xd8da6bf26964af9d7eed9e03e53415d37aa96045"  # vitalik.eth

    result = await retry_on_network_error(
        lambda: get_address_info(chain_id="1", address=address, ctx=mock_ctx),
        action_description="get_address_info vitalik.eth address request",
    )

    if result.notes and any("Could not retrieve address metadata" in note for note in result.notes):
        pytest.skip("Metadata service unavailable; cannot verify metadata meta truncation.")

    metadata = result.data.metadata
    assert isinstance(metadata, dict)

    tags = metadata.get("tags")
    if not isinstance(tags, list):
        pytest.skip("No metadata tags found; cannot verify truncation.")

    tags_with_meta = [tag for tag in tags if isinstance(tag, dict) and "meta" in tag]
    if not tags_with_meta:
        pytest.skip("No metadata tags with meta field found; cannot verify truncation.")

    for tag in tags_with_meta:
        meta = tag["meta"]
        if isinstance(meta, dict | list):
            _assert_no_oversized_strings(meta)
        elif isinstance(meta, str):
            assert len(meta) <= INPUT_DATA_TRUNCATION_LIMIT
