import pytest

from blockscout_mcp_server.models import ToolResponse, UserOperationData
from blockscout_mcp_server.tools.direct_api.direct_api_call import direct_api_call
from tests.integration.helpers import retry_on_network_error

USER_OPERATION_HASH = "0xcb0bb9a3335bb964bd54561e438f143e5b218729c45ebc62c081d5e95fcc4044"
COMPLEX_DECODED_CALL_DATA_HASH = "0x0670c393762002a1a1f0f7dd2df608142a02c06961a922d63f4cdc6a5456d248"
FAILED_WITH_INIT_CODE_HASH = "0x8baac2e15bd423d407641b53ae305b9d38819229636cc79343da7e75b00af758"
HUGE_CALL_DATA_HASH = "0x96283c06e89a8209baba3e2342c9ed54ced8dbab2c904272a4db03ab7943f049"
HUGE_EXECUTE_PARAMS_HASH = "0xafff4862a8e1245728fc51fbba72a44e0bf3f47c5c09f80ba712d1632fcd68b5"
HUGE_SIGNATURE_HASH = "0xa2235963faaacbcce49ee36f84379bc92ec73c82e7812b1ea222d39bb609ac14"


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


@pytest.mark.integration
@pytest.mark.asyncio
async def test_user_operation_handler_complex_decoded_call_data_real(mock_ctx):
    """Ensure complex decoded_call_data is preserved and optimized."""
    endpoint_path = f"/api/v2/proxy/account-abstraction/operations/{COMPLEX_DECODED_CALL_DATA_HASH}"

    result = await retry_on_network_error(
        lambda: direct_api_call(chain_id="1", endpoint_path=endpoint_path, ctx=mock_ctx),
        action_description="direct_api_call user operation complex decoded_call_data request",
    )

    assert isinstance(result, ToolResponse)
    assert isinstance(result.data, UserOperationData)
    decoded = result.data.model_dump().get("decoded_call_data")
    assert isinstance(decoded, dict)
    assert isinstance(decoded.get("parameters"), list)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_user_operation_handler_failed_with_init_code_real(mock_ctx):
    """Validate failed user operation includes factory and raw init_code truncation flags."""
    endpoint_path = f"/api/v2/proxy/account-abstraction/operations/{FAILED_WITH_INIT_CODE_HASH}"

    result = await retry_on_network_error(
        lambda: direct_api_call(chain_id="1", endpoint_path=endpoint_path, ctx=mock_ctx),
        action_description="direct_api_call user operation failed init_code request",
    )

    assert isinstance(result, ToolResponse)
    assert isinstance(result.data, UserOperationData)
    data = result.data.model_dump()
    assert data.get("status") is False
    assert isinstance(data.get("factory"), str)
    raw = data.get("raw")
    assert isinstance(raw, dict)
    assert raw.get("init_code_truncated") is True


@pytest.mark.integration
@pytest.mark.asyncio
async def test_user_operation_handler_huge_call_data_real(mock_ctx):
    """Validate huge raw.call_data and decoded parameters trigger truncation flags."""
    endpoint_path = f"/api/v2/proxy/account-abstraction/operations/{HUGE_CALL_DATA_HASH}"

    result = await retry_on_network_error(
        lambda: direct_api_call(chain_id="1", endpoint_path=endpoint_path, ctx=mock_ctx),
        action_description="direct_api_call user operation huge call_data request",
    )

    assert isinstance(result, ToolResponse)
    assert isinstance(result.data, UserOperationData)
    data = result.data.model_dump()
    raw = data.get("raw")
    assert isinstance(raw, dict)
    assert raw.get("call_data_truncated") is True
    assert data.get("call_data_truncated") is True


@pytest.mark.integration
@pytest.mark.asyncio
async def test_user_operation_handler_huge_execute_params_real(mock_ctx):
    """Validate huge decoded_execute_call_data parameters trigger truncation flags."""
    endpoint_path = f"/api/v2/proxy/account-abstraction/operations/{HUGE_EXECUTE_PARAMS_HASH}"

    result = await retry_on_network_error(
        lambda: direct_api_call(chain_id="1", endpoint_path=endpoint_path, ctx=mock_ctx),
        action_description="direct_api_call user operation huge execute params request",
    )

    assert isinstance(result, ToolResponse)
    assert isinstance(result.data, UserOperationData)
    decoded = result.data.model_dump().get("decoded_execute_call_data")
    assert isinstance(decoded, dict)
    parameters = decoded.get("parameters")
    assert isinstance(parameters, list)
    assert result.notes is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_user_operation_handler_huge_signature_real(mock_ctx):
    """Validate huge signature is truncated and flagged."""
    endpoint_path = f"/api/v2/proxy/account-abstraction/operations/{HUGE_SIGNATURE_HASH}"

    result = await retry_on_network_error(
        lambda: direct_api_call(chain_id="1", endpoint_path=endpoint_path, ctx=mock_ctx),
        action_description="direct_api_call user operation huge signature request",
    )

    assert isinstance(result, ToolResponse)
    assert isinstance(result.data, UserOperationData)
    data = result.data.model_dump()
    assert data.get("signature_truncated") is True
    assert result.notes is not None
