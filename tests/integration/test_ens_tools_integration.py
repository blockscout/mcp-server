import pytest

from blockscout_mcp_server.models import EnsAddressData, ToolResponse
from blockscout_mcp_server.tools.ens_tools import get_address_by_ens_name


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_address_by_ens_name_integration(mock_ctx):
    result = await get_address_by_ens_name(name="vitalik.eth", ctx=mock_ctx)

    assert isinstance(result, ToolResponse)
    assert isinstance(result.data, EnsAddressData)
    assert result.data.resolved_address is not None
    assert result.data.resolved_address.lower() == "0xd8da6bf26964af9d7eed9e03e53415d37aa96045".lower()
