import pytest

from blockscout_mcp_server.models import ToolResponse, UserOperationData
from blockscout_mcp_server.tools.direct_api.direct_api_call import direct_api_call
from tests.integration.helpers import retry_on_network_error

USER_OPERATION_HASH = "0xcb0bb9a3335bb964bd54561e438f143e5b218729c45ebc62c081d5e95fcc4044"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_user_operation_handler_dispatch_real(mock_ctx):
    """Ensure direct_api_call dispatches user operation responses to the specialized handler."""
    endpoint_path = f"/api/v2/proxy/account-abstraction/operations/{USER_OPERATION_HASH}"

    result = await retry_on_network_error(
        lambda: direct_api_call(chain_id="1", endpoint_path=endpoint_path, ctx=mock_ctx),
        action_description="direct_api_call user operation request",
    )

    assert isinstance(result, ToolResponse)
    assert isinstance(result.data, UserOperationData)

    assert isinstance(result.data.sender, str)
    assert result.data.sender.startswith("0x")
    assert isinstance(result.data.entry_point, str)
    assert result.data.entry_point.startswith("0x")
    if result.data.bundler is not None:
        assert isinstance(result.data.bundler, str)
        assert result.data.bundler.startswith("0x")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_user_operation_handler_data_types_real(mock_ctx):
    """Validate basic schema expectations for user operation responses."""
    endpoint_path = f"/api/v2/proxy/account-abstraction/operations/{USER_OPERATION_HASH}"

    result = await retry_on_network_error(
        lambda: direct_api_call(chain_id="1", endpoint_path=endpoint_path, ctx=mock_ctx),
        action_description="direct_api_call user operation schema request",
    )

    data = result.data.model_dump()

    assert isinstance(data.get("hash"), str)
    assert data["hash"].startswith("0x")
    assert isinstance(data.get("transaction_hash"), str)
    assert data["transaction_hash"].startswith("0x")
    assert isinstance(data.get("status"), bool)
    assert isinstance(data.get("bundle_index"), int)
    assert isinstance(data.get("gas_used"), str)
    assert isinstance(data.get("block_number"), str)
