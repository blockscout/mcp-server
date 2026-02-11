import asyncio
from typing import Annotated

from mcp.server.fastmcp import Context
from pydantic import Field

from blockscout_mcp_server.models import ToolResponse, TransactionInfoData
from blockscout_mcp_server.tools.common import (
    build_tool_response,
    get_blockscout_base_url,
    make_blockscout_request,
    report_and_log_progress,
)
from blockscout_mcp_server.tools.decorators import log_tool_invocation
from blockscout_mcp_server.tools.transaction._shared import (
    _process_and_truncate_tx_info_data,
    _transform_transaction_info,
    _transform_user_ops,
)


@log_tool_invocation
async def get_transaction_info(
    chain_id: Annotated[str, Field(description="The ID of the blockchain")],
    transaction_hash: Annotated[str, Field(description="Transaction hash")],
    ctx: Context,
    include_raw_input: Annotated[
        bool | None, Field(description="If true, includes the raw transaction input data.")
    ] = False,
) -> ToolResponse[TransactionInfoData]:
    """
    Get comprehensive transaction information.
    Unlike standard eth_getTransactionByHash, this tool returns enriched data including decoded input parameters, detailed token transfers with token metadata, transaction fee breakdown (priority fees, burnt fees) and categorized transaction types.
    By default, the raw transaction input is omitted if a decoded version is available to save context; request it with `include_raw_input=True` only when you truly need the raw hex data.
    Essential for transaction analysis, debugging smart contract interactions, tracking DeFi operations.
    """  # noqa: E501
    api_path = f"/api/v2/transactions/{transaction_hash}"

    await report_and_log_progress(
        ctx,
        progress=0.0,
        total=2.0,
        message=f"Starting to fetch transaction info for {transaction_hash} on chain {chain_id}...",
    )

    base_url = await get_blockscout_base_url(chain_id)

    await report_and_log_progress(
        ctx, progress=1.0, total=2.0, message="Resolved Blockscout instance URL. Fetching transaction data..."
    )

    operations_path = "/api/v2/proxy/account-abstraction/operations"

    transaction_result, ops_result = await asyncio.gather(
        make_blockscout_request(base_url=base_url, api_path=api_path),
        make_blockscout_request(
            base_url=base_url,
            api_path=operations_path,
            params={"transaction_hash": transaction_hash},
        ),
        return_exceptions=True,
    )

    if isinstance(transaction_result, Exception):
        raise transaction_result

    response_data = transaction_result
    raw_ops_response = None if isinstance(ops_result, Exception) else ops_result
    ops_error_note = None
    if isinstance(ops_result, Exception):
        ops_error_note = f"Could not retrieve user operations. The 'user_operations' field is null. Error: {ops_result}"

    await report_and_log_progress(ctx, progress=2.0, total=2.0, message="Successfully fetched transaction data.")

    processed_data, was_truncated = _process_and_truncate_tx_info_data(response_data, include_raw_input)

    final_data_dict = _transform_transaction_info(processed_data)

    user_operations = _transform_user_ops(raw_ops_response)
    final_data_dict["user_operations"] = user_operations

    transaction_data = TransactionInfoData(**final_data_dict)

    notes = None
    if was_truncated:
        notes = [
            (
                "One or more large data fields in this response have been truncated "
                '(indicated by "value_truncated": true or "raw_input_truncated": true).'
            ),
            (
                f"To get the full, untruncated data, you can retrieve it programmatically. "
                f'For example, using curl:\n`curl "{str(base_url).rstrip("/")}/api/v2/transactions/{transaction_hash}"`'
            ),
        ]

    if ops_error_note:
        notes = notes or []
        notes.append(ops_error_note)
        notes.append(
            "Since it is not clear if the transaction contains user operations or not, call `direct_api_call` with "
            f"endpoint `/api/v2/proxy/account-abstraction/operations` with "
            f"query_params={{'transaction_hash': '{transaction_hash}'}} to figure this out."
        )

    if user_operations:
        notes = notes or []
        notes.append(
            "⚠️ IMPORTANT: A successful bundle transaction does not guarantee individual user operation success. "
            "ERC-4337 allows operations to fail within a successful bundle."
        )

    if raw_ops_response and isinstance(raw_ops_response, dict) and raw_ops_response.get("next_page_params"):
        pagination_note = (
            "The 'user_operations' list is truncated. Use 'direct_api_call' with "
            f"'/api/v2/proxy/account-abstraction/operations' with query_params={{'transaction_hash': "
            f"'{transaction_hash}'}} to paginate through all operations."
        )
        notes = notes or []
        notes.append(pagination_note)

    instructions = [
        (
            "To get a transaction summary, use `direct_api_call` with "
            f"`endpoint_path='/api/v2/transactions/{transaction_hash}/summary'`."
        ),
        (
            "To get event logs, use `direct_api_call` with "
            f"`endpoint_path='/api/v2/transactions/{transaction_hash}/logs'`."
        ),
    ]
    if user_operations:
        instructions.append(
            "⚠️ USER OPERATIONS REQUIRE EXPANSION: This response shows operation references only. "
            "Use 'direct_api_call' with endpoint `/api/v2/proxy/account-abstraction/operations/{operation_hash}` "
            "for each to get: execution status, decoded calldata, gas breakdown, sponsor type, "
            "paymaster details, smart account type, and revert reasons if failed."
        )
    status_raw = getattr(transaction_data, "status", None)
    status = "successful" if status_raw == "ok" else (status_raw or "unknown status")
    from_address = transaction_data.from_address or "unknown"
    to_address = transaction_data.to_address or "unknown"
    summary = f"Transaction {transaction_hash} on chain {chain_id}: {status}, from {from_address} to {to_address}."
    value = getattr(transaction_data, "value", None)
    if value and str(value) != "0":
        summary = summary[:-1] + f", value {value} wei."
    method_name = transaction_data.decoded_input.method_call if transaction_data.decoded_input else None
    if method_name:
        summary += f" Method: {method_name}."

    return build_tool_response(
        data=transaction_data,
        notes=notes,
        instructions=instructions,
        content_text=summary,
    )
