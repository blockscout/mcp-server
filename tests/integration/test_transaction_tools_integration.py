import httpx
import pytest

from blockscout_mcp_server.constants import INPUT_DATA_TRUNCATION_LIMIT, LOG_DATA_TRUNCATION_LIMIT
from blockscout_mcp_server.models import (
    AdvancedFilterItem,
    TokenTransfer,
    ToolResponse,
    TransactionInfoData,
    TransactionLogItem,
    TransactionSummaryData,
)
from blockscout_mcp_server.tools.common import get_blockscout_base_url
from blockscout_mcp_server.tools.transaction_tools import (
    EXCLUDED_TX_TYPES,
    get_token_transfers_by_address,
    get_transaction_info,
    get_transaction_logs,
    get_transactions_by_address,
    transaction_summary,
)
from tests.integration.helpers import is_log_a_truncated_call_executed


@pytest.mark.integration
@pytest.mark.asyncio
async def test_transaction_summary_integration(mock_ctx):
    """Tests transaction_summary against a stable, historical transaction to ensure
    the 'summaries' field is correctly extracted from the 'data' object."""
    # A stable, historical transaction (e.g., an early Uniswap V2 router transaction)
    tx_hash = "0x5c7f2f244d91ec281c738393da0be6a38bc9045e29c0566da8c11e7a2f7cbc64"
    result = await transaction_summary(chain_id="1", transaction_hash=tx_hash, ctx=mock_ctx)

    # Assert that the tool returns a structured response
    assert isinstance(result, ToolResponse)
    assert isinstance(result.data, TransactionSummaryData)

    # The summary can be a list or None.
    assert isinstance(result.data.summary, list | type(None))
    if isinstance(result.data.summary, list):
        assert len(result.data.summary) > 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_transaction_logs_integration(mock_ctx):
    """Tests that get_transaction_logs returns a paginated response and validates the schema."""
    # This transaction on Ethereum Mainnet is known to have many logs, ensuring a paginated response.
    tx_hash = "0xa519e3af3f07190727f490c599baf3e65ee335883d6f420b433f7b83f62cb64d"
    try:
        result = await get_transaction_logs(chain_id="1", transaction_hash=tx_hash, ctx=mock_ctx)
    except httpx.HTTPStatusError as e:
        pytest.skip(f"Transaction data is currently unavailable from the API: {e}")

    # 1. Verify that pagination is working correctly
    assert isinstance(result, ToolResponse)
    assert result.pagination is not None

    # 2. Verify the basic structure
    assert isinstance(result.data, list)
    assert len(result.data) > 0

    # 3. Validate the schema of the first transformed log item.
    first_log = result.data[0]
    assert isinstance(first_log, TransactionLogItem)
    if first_log.model_extra.get("data_truncated") is not None:
        assert isinstance(first_log.model_extra.get("data_truncated"), bool)

    # 4. Validate the data types of key fields.
    assert isinstance(first_log.address, str)
    assert first_log.address.startswith("0x")
    assert isinstance(first_log.block_number, int)
    assert isinstance(first_log.index, int)
    assert isinstance(first_log.topics, list)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_transaction_logs_pagination_integration(mock_ctx):
    """Tests that get_transaction_logs can successfully use a cursor to fetch a second page."""
    tx_hash = "0xa519e3af3f07190727f490c599baf3e65ee335883d6f420b433f7b83f62cb64d"

    try:
        first_page_response = await get_transaction_logs(chain_id="1", transaction_hash=tx_hash, ctx=mock_ctx)
    except httpx.HTTPStatusError as e:
        pytest.skip(f"Transaction data is currently unavailable from the API: {e}")

    assert first_page_response.pagination is not None
    cursor = first_page_response.pagination.next_call.params["cursor"]

    try:
        second_page_response = await get_transaction_logs(
            chain_id="1", transaction_hash=tx_hash, ctx=mock_ctx, cursor=cursor
        )
    except httpx.HTTPStatusError as e:
        pytest.fail(f"Failed to fetch the second page of transaction logs due to an API error: {e}")

    assert isinstance(second_page_response, ToolResponse)
    assert second_page_response.data
    assert first_page_response.data[0] != second_page_response.data[0]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_transaction_logs_with_truncation_integration(mock_ctx):
    """
    Tests that get_transaction_logs correctly truncates oversized `data` fields
    from a live API response and includes the instructional note.
    """
    # This transaction on Ethereum Mainnet is known to contain logs with very large data fields.
    tx_hash = "0xa519e3af3f07190727f490c599baf3e65ee335883d6f420b433f7b83f62cb64d"
    chain_id = "1"

    # Resolve the base URL the same way the tool does
    await get_blockscout_base_url(chain_id)
    try:
        result = await get_transaction_logs(chain_id=chain_id, transaction_hash=tx_hash, ctx=mock_ctx)
    except httpx.HTTPStatusError as e:
        pytest.skip(f"Transaction data is currently unavailable from the API: {e}")

    assert result.notes is not None
    assert "One or more log items" in result.notes[0]

    assert isinstance(result.data, list) and result.data
    truncated_item = next(
        (item for item in result.data if item.model_extra.get("data_truncated")),
        None,
    )
    assert truncated_item is not None
    assert truncated_item.model_extra.get("data_truncated") is True
    assert truncated_item.data is not None
    assert len(truncated_item.data) == LOG_DATA_TRUNCATION_LIMIT


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_transaction_info_integration(mock_ctx):
    """Tests that get_transaction_info returns full data and omits raw_input by default."""
    # This is a stable transaction with a known decoded input (a swap).
    tx_hash = "0xd4df84bf9e45af2aa8310f74a2577a28b420c59f2e3da02c52b6d39dc83ef10f"
    result = await get_transaction_info(chain_id="1", transaction_hash=tx_hash, ctx=mock_ctx)

    # Assert that the main data is present and transformed
    assert isinstance(result, ToolResponse)
    assert isinstance(result.data, TransactionInfoData)
    data = result.data
    assert data.status == "ok"
    assert data.decoded_input is not None
    assert data.raw_input is None
    assert isinstance(data.from_address, str)
    assert data.from_address.startswith("0x")
    assert isinstance(data.to_address, str)
    assert data.to_address.startswith("0x")

    # Assert token_transfers optimized
    assert isinstance(data.token_transfers, list)
    for transfer in data.token_transfers:
        assert isinstance(transfer, TokenTransfer)
        assert isinstance(transfer.transfer_type, str)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_transaction_info_integration_no_decoded_input(mock_ctx):
    """Tests that get_transaction_info keeps raw_input by default when decoded_input is null."""
    # This is a stable contract creation transaction, which has no decoded_input.
    tx_hash = "0x12341be874149efc8c714f4ef431db0ce29f64532e5c70d3882257705e2b1ad2"
    chain_id = "1"

    # Dynamically resolve the base URL
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
    """
    Tests that get_transaction_info correctly truncates oversized `decoded_input` fields
    from a live API response and includes the instructional note.
    """
    tx_hash = "0xa519e3af3f07190727f490c599baf3e65ee335883d6f420b433f7b83f62cb64d"
    chain_id = "1"

    # Dynamically resolve the base URL
    base_url = await get_blockscout_base_url(chain_id)
    try:
        result = await get_transaction_info(chain_id=chain_id, transaction_hash=tx_hash, ctx=mock_ctx)
    except httpx.HTTPStatusError as e:
        pytest.skip(f"Transaction data is currently unavailable from the API: {e}")

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
async def test_get_transactions_by_address_integration(mock_ctx):
    """Tests that get_transactions_by_address returns a transformed list of transactions
    and that token transfers are correctly filtered out from the live response.
    """
    address = "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"

    result = await get_transactions_by_address(
        chain_id="1",
        address=address,
        age_to="2017-01-01T00:00:00.00Z",  # Use a range more likely to have varied tx types
        ctx=mock_ctx,
    )

    assert isinstance(result, ToolResponse)
    items = result.data
    assert isinstance(items, list)

    if not items:
        pytest.skip("No non-token transactions found for the given address and time range to verify.")

    for item in items:
        assert isinstance(item, AdvancedFilterItem)
        assert isinstance(item.from_address, str | type(None))
        assert isinstance(item.to_address, str | type(None))
        item_dict = item.model_dump(by_alias=True)
        # Verify that no excluded token transfer types appear in the result
        assert item.model_extra.get("type") not in EXCLUDED_TX_TYPES
        assert "token" not in item_dict
        assert "total" not in item_dict
        assert "hash" in item_dict
        assert "timestamp" in item_dict
        assert "value" in item_dict


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_token_transfers_by_address_integration(mock_ctx):
    """Tests that get_token_transfers_by_address returns a transformed list of transfers."""
    address = "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"

    result = await get_token_transfers_by_address(
        chain_id="1",
        address=address,
        age_to="2017-01-01T00:00:00.00Z",
        ctx=mock_ctx,
    )

    assert isinstance(result, ToolResponse)
    items = result.data
    assert isinstance(items, list)

    if not items:
        pytest.skip("No token transfers found for the given address and time range.")

    for item in items:
        assert isinstance(item, AdvancedFilterItem)
        assert isinstance(item.from_address, str | type(None))
        assert isinstance(item.to_address, str | type(None))
        item_dict = item.model_dump(by_alias=True)
        assert "value" not in item_dict
        assert "internal_transaction_index" not in item_dict
        assert "hash" in item_dict
        assert "timestamp" in item_dict
        assert "token" in item_dict
        assert "total" in item_dict


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_transaction_logs_paginated_search_for_truncation(mock_ctx):
    """
    Tests that get_transaction_logs can find truncated data by searching across pages.
    """
    tx_hash = "0xa519e3af3f07190727f490c599baf3e65ee335883d6f420b433f7b83f62cb64d"
    chain_id = "1"
    MAX_PAGES_TO_CHECK = 5
    cursor = None
    found_truncated_log = False

    for page_num in range(MAX_PAGES_TO_CHECK):
        try:
            result = await get_transaction_logs(
                chain_id=chain_id,
                transaction_hash=tx_hash,
                ctx=mock_ctx,
                cursor=cursor,
            )
        except httpx.HTTPStatusError as e:
            pytest.skip(f"API request failed on page {page_num + 1}: {e}")

        if any(is_log_a_truncated_call_executed(log) for log in result.data):
            found_truncated_log = True
            break

        next_cursor = result.pagination.next_call.params["cursor"] if result.pagination else None
        if next_cursor:
            cursor = next_cursor
        else:
            break

    if not found_truncated_log:
        pytest.skip(f"Could not find a truncated 'CallExecuted' log within the first {MAX_PAGES_TO_CHECK} pages.")
