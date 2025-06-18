import json
from typing import Annotated, Optional, Dict
from pydantic import Field
from blockscout_mcp_server.tools.common import (
    make_blockscout_request,
    get_blockscout_base_url,
    make_request_with_periodic_progress,
    report_and_log_progress,
    decode_cursor,
    encode_cursor,
    InvalidCursorError,
)
from blockscout_mcp_server.config import config
from mcp.server.fastmcp import Context


def _transform_advanced_filter_item(item: dict, fields_to_remove: list[str]) -> dict:
    """Transforms a single item from the advanced filter API response."""
    transformed_item = item.copy()

    if isinstance(transformed_item.get("from"), dict):
        transformed_item["from"] = transformed_item["from"].get("hash")
    if isinstance(transformed_item.get("to"), dict):
        transformed_item["to"] = transformed_item["to"].get("hash")

    for field in fields_to_remove:
        transformed_item.pop(field, None)

    return transformed_item


def _transform_transaction_info(data: dict) -> dict:
    """Transforms the raw transaction info response from Blockscout API
    into a more concise format for the MCP tool.
    """
    # Work on a copy to avoid modifying the original data
    transformed_data = data.copy()

    # 1. Remove redundant top-level hash
    transformed_data.pop("hash", None)

    # 2. Simplify top-level 'from' and 'to' objects
    if isinstance(transformed_data.get("from"), dict):
        transformed_data["from"] = transformed_data["from"].get("hash")
    if isinstance(transformed_data.get("to"), dict):
        transformed_data["to"] = transformed_data["to"].get("hash")

    # 3. Optimize the 'token_transfers' list
    if "token_transfers" in transformed_data and isinstance(
        transformed_data["token_transfers"], list
    ):
        optimized_transfers = []
        for transfer in transformed_data["token_transfers"]:
            if isinstance(transfer.get("from"), dict):
                transfer["from"] = transfer["from"].get("hash")
            if isinstance(transfer.get("to"), dict):
                transfer["to"] = transfer["to"].get("hash")

            transfer.pop("block_hash", None)
            transfer.pop("block_number", None)
            transfer.pop("transaction_hash", None)
            transfer.pop("timestamp", None)

            optimized_transfers.append(transfer)

        transformed_data["token_transfers"] = optimized_transfers

    return transformed_data


async def get_transactions_by_address(
    chain_id: Annotated[str, Field(description="The ID of the blockchain")],
    address: Annotated[str, Field(description="Address which either sender or receiver of the transaction")],
    ctx: Context,
    age_from: Annotated[Optional[str], Field(description="Start date and time (e.g 2025-05-22T23:00:00.00Z).")] = None,
    age_to: Annotated[Optional[str], Field(description="End date and time (e.g 2025-05-22T22:30:00.00Z).")] = None,
    methods: Annotated[Optional[str], Field(description="A method signature to filter transactions by (e.g 0x304e6ade)")] = None,
) -> Dict:
    """
    Get transactions for an address within a specific time range.
    Use cases:
      - `get_transactions_by_address(address, age_from)` - get all transactions to/from the address since the given date up to the current time
      - `get_transactions_by_address(address, age_from, age_to)` - get all transactions to/from the address between the given dates
      - `get_transactions_by_address(address, age_from, age_to, methods)` - get all transactions to/from the address between the given dates and invoking the given method signature
    Manipulating `age_from` and `age_to` allows you to paginate through results by time ranges.
    """
    api_path = "/api/v2/advanced-filters"
    query_params = {
        "to_address_hashes_to_include": address,
        "from_address_hashes_to_include": address
    }
    if age_from:
        query_params["age_from"] = age_from
    if age_to:
        query_params["age_to"] = age_to
    if methods:
        query_params["methods"] = methods

    tool_overall_total_steps = 2.0

    # Report start of operation
    await report_and_log_progress(ctx, 
        progress=0.0, 
        total=tool_overall_total_steps, 
        message=f"Starting to fetch transactions for {address} on chain {chain_id}..."
    )

    base_url = await get_blockscout_base_url(chain_id)
    
    # Report progress after resolving Blockscout URL
    await report_and_log_progress(ctx, 
        progress=1.0, 
        total=tool_overall_total_steps, 
        message="Resolved Blockscout instance URL. Now fetching transactions..."
    )
    
    # Use the periodic progress wrapper for the potentially long-running API call
    response_data = await make_request_with_periodic_progress(
        ctx=ctx,
        request_function=make_blockscout_request,
        request_args={
            "base_url": base_url,
            "api_path": api_path,
            "params": query_params,
        },
        total_duration_hint=config.bs_timeout,  # Use configured timeout
        progress_interval_seconds=config.progress_interval_seconds,  # Use configured interval
        in_progress_message_template="Query in progress... ({elapsed_seconds:.0f}s / {total_hint:.0f}s hint)",
        tool_overall_total_steps=tool_overall_total_steps,
        current_step_number=2.0,  # This is the 2nd step of the tool
        current_step_message_prefix="Fetching transactions"
    )
    
    # The wrapper make_request_with_periodic_progress handles the final progress report for this step.
    # So, no explicit ctx.report_progress(progress=2.0, ...) is needed here.

    original_items = response_data.get("items", [])
    fields_to_remove = [
        "total",
        "token",
        "token_transfer_batch_index",
        "token_transfer_index",
    ]

    transformed_items = [
        _transform_advanced_filter_item(item, fields_to_remove) for item in original_items
    ]

    response_data["items"] = transformed_items
    return response_data

async def get_token_transfers_by_address(
    chain_id: Annotated[str, Field(description="The ID of the blockchain")],
    address: Annotated[str, Field(description="Address which either transfer initiator or transfer receiver")],
    ctx: Context,
    age_from: Annotated[Optional[str], Field(description="Start date and time (e.g 2025-05-22T23:00:00.00Z). This parameter should be provided in most cases to limit transfers and avoid heavy database queries. Omit only if you absolutely need the full history.")] = None,
    age_to: Annotated[Optional[str], Field(description="End date and time (e.g 2025-05-22T22:30:00.00Z). Can be omitted to get all transfers up to the current time.")] = None,
    token: Annotated[Optional[str], Field(description="An ERC-20 token contract address to filter transfers by a specific token. If omitted, returns transfers of all tokens.")] = None,
) -> Dict:
    """
    Get ERC-20 token transfers for an address within a specific time range.
    Use cases:
      - `get_token_transfers_by_address(address, age_from)` - get all transfers of any ERC-20 token to/from the address since the given date up to the current time
      - `get_token_transfers_by_address(address, age_from, age_to)` - get all transfers of any ERC-20 token to/from the address between the given dates
      - `get_token_transfers_by_address(address, age_from, age_to, token)` - get all transfers of the given ERC-20 token to/from the address between the given dates
    Manipulating `age_from` and `age_to` allows you to paginate through results by time ranges. For example, after getting transfers up to a certain timestamp, you can use that timestamp as `age_to` in the next query to get the next page of older transfers.
    """
    api_path = "/api/v2/advanced-filters"
    query_params = {
        "transaction_types": "ERC-20",
        "to_address_hashes_to_include": address,
        "from_address_hashes_to_include": address
    }
    
    if age_from:
        query_params["age_from"] = age_from
    if age_to:
        query_params["age_to"] = age_to
    if token:
        query_params["token_contract_address_hashes_to_include"] = token

    tool_overall_total_steps = 2.0

    # Report start of operation
    await report_and_log_progress(ctx, 
        progress=0.0,
        total=tool_overall_total_steps,
        message=f"Starting to fetch token transfers for {address} on chain {chain_id}..."
    )

    base_url = await get_blockscout_base_url(chain_id)
    
    # Report progress after resolving Blockscout URL
    await report_and_log_progress(ctx, 
        progress=1.0,
        total=tool_overall_total_steps,
        message="Resolved Blockscout instance URL. Now fetching token transfers..."
    )
    
    # Use the periodic progress wrapper for the potentially long-running API call
    response_data = await make_request_with_periodic_progress(
        ctx=ctx,
        request_function=make_blockscout_request,
        request_args={
            "base_url": base_url,
            "api_path": api_path,
            "params": query_params,
        },
        total_duration_hint=config.bs_timeout,  # Use configured timeout
        progress_interval_seconds=config.progress_interval_seconds,  # Use configured interval
        in_progress_message_template="Query in progress... ({elapsed_seconds:.0f}s / {total_hint:.0f}s hint)",
        tool_overall_total_steps=tool_overall_total_steps,
        current_step_number=2.0,  # This is the 2nd step of the tool
        current_step_message_prefix="Fetching token transfers"
    )
    
    # The wrapper make_request_with_periodic_progress handles the final progress report for this step.
    # So, no explicit ctx.report_progress(progress=2.0, ...) is needed here.

    original_items = response_data.get("items", [])
    fields_to_remove = ["value", "internal_transaction_index", "created_contract"]

    transformed_items = [
        _transform_advanced_filter_item(item, fields_to_remove) for item in original_items
    ]

    response_data["items"] = transformed_items
    return response_data

async def transaction_summary(
    chain_id: Annotated[str, Field(description="The ID of the blockchain")],
    hash: Annotated[str, Field(description="Transaction hash")],
    ctx: Context
) -> str:
    """
    Get human-readable transaction summaries from Blockscout Transaction Interpreter.
    Automatically classifies transactions into natural language descriptions (transfers, swaps, NFT sales, DeFi operations)
    Essential for rapid transaction comprehension, dashboard displays, and initial analysis.
    Note: Not all transactions can be summarized and accuracy is not guaranteed for complex patterns.
    """
    api_path = f"/api/v2/transactions/{hash}/summary"

    # Report start of operation
    await report_and_log_progress(ctx, progress=0.0, total=2.0, message=f"Starting to fetch transaction summary for {hash} on chain {chain_id}...")

    base_url = await get_blockscout_base_url(chain_id)
    
    # Report progress after resolving Blockscout URL
    await report_and_log_progress(ctx, progress=1.0, total=2.0, message="Resolved Blockscout instance URL. Fetching transaction summary...")
    
    response_data = await make_blockscout_request(base_url=base_url, api_path=api_path)
    
    # Report completion
    await report_and_log_progress(ctx, progress=2.0, total=2.0, message="Successfully fetched transaction summary.")
    
    summary = response_data.get("data", {}).get("summaries")
    if summary:
        return f"# Transaction Summary from Blockscout Transaction Interpreter\n{summary}"
    else:
        return "No summary available."

async def get_transaction_info(
    chain_id: Annotated[str, Field(description="The ID of the blockchain")],
    hash: Annotated[str, Field(description="Transaction hash")],
    ctx: Context,
    include_raw_input: Annotated[Optional[bool], Field(description="If true, includes the raw transaction input data.")] = False
) -> Dict:
    """
    Get comprehensive transaction information. 
    Unlike standard eth_getTransactionByHash, this tool returns enriched data including decoded input parameters, detailed token transfers with token metadata, transaction fee breakdown (priority fees, burnt fees) and categorized transaction types.
    By default, the raw transaction input is omitted if a decoded version is available to save context; request it with `include_raw_input=True` only when you truly need the raw hex data.
    Essential for transaction analysis, debugging smart contract interactions, tracking DeFi operations.
    """
    api_path = f"/api/v2/transactions/{hash}"
    
    # Report start of operation
    await report_and_log_progress(ctx, progress=0.0, total=2.0, message=f"Starting to fetch transaction info for {hash} on chain {chain_id}...")
    
    base_url = await get_blockscout_base_url(chain_id)
    
    # Report progress after resolving Blockscout URL
    await report_and_log_progress(ctx, progress=1.0, total=2.0, message="Resolved Blockscout instance URL. Fetching transaction data...")
    
    response_data = await make_blockscout_request(base_url=base_url, api_path=api_path)

    # Report completion
    await report_and_log_progress(ctx, progress=2.0, total=2.0, message="Successfully fetched transaction data.")

    # Conditionally remove raw_input to save context if decoded_input is present
    if not include_raw_input and response_data.get("decoded_input"):
        response_data.pop("raw_input", None)

    # Apply our new transformation logic before returning
    transformed_data = _transform_transaction_info(response_data)

    return transformed_data

async def get_transaction_logs(
    chain_id: Annotated[str, Field(description="The ID of the blockchain")],
    hash: Annotated[str, Field(description="Transaction hash")],
    ctx: Context,
    cursor: Annotated[
        Optional[str],
        Field(
            description="The pagination cursor from a previous response to get the next page of results."
        ),
    ] = None,
) -> str:
    """
    Get comprehensive transaction logs.
    Unlike standard eth_getLogs, this tool returns enriched logs, primarily focusing on decoded event parameters with their types and values (if event decoding is applicable).
    Essential for analyzing smart contract events, tracking token transfers, monitoring DeFi protocol interactions, debugging event emissions, and understanding complex multi-contract transaction flows.
    """
    api_path = f"/api/v2/transactions/{hash}/logs"
    params = {}

    if cursor:
        try:
            decoded_params = decode_cursor(cursor)
            params.update(decoded_params)
        except InvalidCursorError:
            return (
                "Error: Invalid or expired pagination cursor. Please make a new request without the cursor to start over."
            )
    
    # Report start of operation
    await report_and_log_progress(ctx, progress=0.0, total=2.0, message=f"Starting to fetch transaction logs for {hash} on chain {chain_id}...")
    
    base_url = await get_blockscout_base_url(chain_id)
    
    # Report progress after resolving Blockscout URL
    await report_and_log_progress(ctx, progress=1.0, total=2.0, message="Resolved Blockscout instance URL. Fetching transaction logs...")
    
    response_data = await make_blockscout_request(
        base_url=base_url, api_path=api_path, params=params
    )

    original_items = response_data.get("items", [])

    transformed_items = [
        {
            "address": item.get("address", {}).get("hash"),
            "block_number": item.get("block_number"),
            "data": item.get("data"),
            "decoded": item.get("decoded"),
            "index": item.get("index"),
            "topics": item.get("topics"),
        }
        for item in original_items
    ]

    transformed_response = {
        "items": transformed_items,
    }

    # Report completion
    await report_and_log_progress(ctx, progress=2.0, total=2.0, message="Successfully fetched transaction logs.")

    logs_json_str = json.dumps(transformed_response)  # Compact JSON

    prefix = """**Items Structure:**
- `address`: The contract address that emitted the log (string)
- `block_number`: Block where the event was emitted
- `index`: Log position within the block
- `topics`: Raw indexed event parameters (first topic is event signature hash)
- `data`: Raw non-indexed event parameters (hex encoded)
- `decoded`: If available, the decoded event with its name and parameters

**Event Decoding in `decoded` field:**
- `method_call`: **Actually the event signature** (e.g., "Transfer(address indexed from, address indexed to, uint256 value)")
- `method_id`: **Actually the event signature hash** (first 4 bytes of keccak256 hash)
- `parameters`: Decoded event parameters with names, types, values, and indexing status

**Transaction logs JSON:**
"""

    output = f"{prefix}{logs_json_str}"

    next_page_params = response_data.get("next_page_params")
    if next_page_params:
        next_cursor = encode_cursor(next_page_params)
        pagination_hint = f"""

----
To get the next page call get_transaction_logs(chain_id=\"{chain_id}\", hash=\"{hash}\", cursor=\"{next_cursor}\")"""
        output += pagination_hint

    return output
