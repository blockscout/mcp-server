import pytest

from blockscout_mcp_server.tools.ens_tools import get_address_by_ens_name


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_address_by_ens_name_integration(mock_ctx):
    result = await get_address_by_ens_name(name="vitalik.eth", ctx=mock_ctx)

    assert isinstance(result, dict)
    assert "resolved_address" in result
    assert result["resolved_address"].lower() == "0xd8da6bf26964af9d7eed9e03e53415d37aa96045".lower()
