import httpx
import pytest

from blockscout_mcp_server.constants import INPUT_DATA_TRUNCATION_LIMIT
from blockscout_mcp_server.models import TokenTransfer, ToolResponse, TransactionInfoData
from blockscout_mcp_server.tools.common import get_blockscout_base_url
from blockscout_mcp_server.tools.transaction.get_transaction_info import get_transaction_info


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_transaction_info_integration(mock_ctx):
    """Tests that get_transaction_info returns full data and omits raw_input by default."""
    tx_hash = "0xd4df84bf9e45af2aa8310f74a2577a28b420c59f2e3da02c52b6d39dc83ef10f"
    result = await get_transaction_info(chain_id="1", transaction_hash=tx_hash, ctx=mock_ctx)

    assert isinstance(result, ToolResponse)
    assert isinstance(result.data, TransactionInfoData)
    data = result.data
    assert data.status == "ok"
    assert data.decoded_input is not None
    assert data.raw_input is None
    assert isinstance(data.from_address, str) and data.from_address.startswith("0x")
    assert isinstance(data.to_address, str) and data.to_address.startswith("0x")

    assert isinstance(data.token_transfers, list)
    for transfer in data.token_transfers:
        assert isinstance(transfer, TokenTransfer)
        assert isinstance(transfer.transfer_type, str)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_transaction_info_integration_no_decoded_input(mock_ctx):
    """Tests that get_transaction_info keeps raw_input when decoded_input is null."""
    tx_hash = "0x12341be874149efc8c714f4ef431db0ce29f64532e5c70d3882257705e2b1ad2"
    chain_id = "1"

    base_url = await get_blockscout_base_url(chain_id)
    result = await get_transaction_info(chain_id=chain_id, transaction_hash=tx_hash, ctx=mock_ctx)

    assert isinstance(result, ToolResponse)
    assert isinstance(result.data, TransactionInfoData)
    assert result.notes is not None
    assert f'`curl "{base_url.rstrip("/")}/api/v2/transactions/{tx_hash}"`' in result.notes[1]

    data = result.data
    assert data.decoded_input is None
    assert isinstance(data.from_address, str)
    assert data.to_address is None

    assert data.raw_input is not None
    assert data.raw_input_truncated is True

    assert len(data.token_transfers) > 0
    first_transfer = data.token_transfers[0]
    assert isinstance(first_transfer, TokenTransfer)
    assert first_transfer.transfer_type == "token_minting"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_transaction_info_with_truncation_integration(mock_ctx):
    """Tests that get_transaction_info correctly truncates oversized decoded_input fields."""
    tx_hash = "0x31cf78a3d5161fdfd3dd196064d6b8bcb6185d574bf96a66d2a7af38d83e82a4"
    chain_id = "1"

    base_url = await get_blockscout_base_url(chain_id)
    try:
        result = await get_transaction_info(chain_id=chain_id, transaction_hash=tx_hash, ctx=mock_ctx)
    except httpx.HTTPStatusError as exc:
        pytest.skip(f"Transaction data is currently unavailable from the API: {exc}")

    assert isinstance(result, ToolResponse)
    assert isinstance(result.data, TransactionInfoData)
    assert result.notes is not None
    assert f'`curl "{base_url.rstrip("/")}/api/v2/transactions/{tx_hash}"`' in result.notes[1]

    data = result.data
    assert data.decoded_input is not None
    params = data.decoded_input.parameters
    calldatas_param = next((p for p in params if p["name"] == "calldatas"), None)
    assert calldatas_param is not None

    truncated_value = calldatas_param["value"][0]
    assert truncated_value["value_truncated"] is True
    assert len(truncated_value["value_sample"]) == INPUT_DATA_TRUNCATION_LIMIT


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_transaction_info_integration_user_ops(mock_ctx):
    """Tests that get_transaction_info returns user operations for an AA transaction on Base."""
    tx_hash = "0xf477d77e222a8ba10923a5c8876af11a01845795bc5bfe7cb1a5e1eaecc898fc"
    chain_id = "8453"

    try:
        result = await get_transaction_info(chain_id=chain_id, transaction_hash=tx_hash, ctx=mock_ctx)
    except (httpx.TimeoutException, httpx.ConnectError) as exc:
        pytest.skip(f"Network connectivity issue while fetching AA transaction: {exc}")
    except httpx.HTTPStatusError as exc:
        pytest.skip(f"AA transaction data unavailable from the API: {exc}")

    assert isinstance(result, ToolResponse)
    assert isinstance(result.data, TransactionInfoData)
    assert result.data.user_operations is not None
    assert len(result.data.user_operations) > 0
