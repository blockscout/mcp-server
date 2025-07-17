from typing import Annotated

from mcp.server.fastmcp import Context
from pydantic import Field

from blockscout_mcp_server.config import config
from blockscout_mcp_server.constants import INPUT_DATA_TRUNCATION_LIMIT
from blockscout_mcp_server.models import (
    AdvancedFilterItem,
    ToolResponse,
    TransactionInfoData,
    TransactionLogItem,
    TransactionSummaryData,
)
from blockscout_mcp_server.tools.common import (
    _process_and_truncate_log_items,
    _recursively_truncate_and_flag_long_strings,
    apply_cursor_to_params,
    build_tool_response,
    create_items_pagination,
    extract_advanced_filters_cursor_params,
    extract_log_cursor_params,
    get_blockscout_base_url,
    log_tool_invocation,
    make_blockscout_request,
    make_request_with_periodic_progress,
    report_and_log_progress,
)

EXCLUDED_TX_TYPES = {"ERC-20", "ERC-721", "ERC-1155", "ERC-404"}


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


def _process_and_truncate_tx_info_data(data: dict, include_raw_input: bool) -> tuple[dict, bool]:
    """
    Processes transaction data, applying truncation to large fields.

    Returns:
        A tuple containing the processed data and a boolean indicating if truncation occurred.
    """
    transformed_data = data.copy()
    was_truncated = False

    # 1. Handle `raw_input` based on `include_raw_input` flag and presence of `decoded_input`
    raw_input = transformed_data.pop("raw_input", None)
    if include_raw_input or not transformed_data.get("decoded_input"):
        if raw_input and len(raw_input) > INPUT_DATA_TRUNCATION_LIMIT:
            transformed_data["raw_input"] = raw_input[:INPUT_DATA_TRUNCATION_LIMIT]
            transformed_data["raw_input_truncated"] = True
            was_truncated = True
        elif raw_input:
            transformed_data["raw_input"] = raw_input

    # 2. Handle `decoded_input`
    if "decoded_input" in transformed_data and isinstance(transformed_data["decoded_input"], dict):
        decoded_input = transformed_data["decoded_input"]
        if "parameters" in decoded_input:
            processed_params, params_truncated = _recursively_truncate_and_flag_long_strings(
                decoded_input["parameters"]
            )
            decoded_input["parameters"] = processed_params
            if params_truncated:
                was_truncated = True

    return transformed_data, was_truncated


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
    if "token_transfers" in transformed_data and isinstance(transformed_data["token_transfers"], list):
        optimized_transfers = []
        for transfer in transformed_data["token_transfers"]:
            # Copy the nested dictionary to avoid mutating the original response data
            new_transfer = transfer.copy()
            if isinstance(new_transfer.get("from"), dict):
                new_transfer["from"] = new_transfer["from"].get("hash")
            if isinstance(new_transfer.get("to"), dict):
                new_transfer["to"] = new_transfer["to"].get("hash")

            new_transfer.pop("block_hash", None)
            new_transfer.pop("block_number", None)
            new_transfer.pop("transaction_hash", None)
            new_transfer.pop("timestamp", None)

            optimized_transfers.append(new_transfer)

        transformed_data["token_transfers"] = optimized_transfers
    else:
        transformed_data["token_transfers"] = []

    return transformed_data


async def _fetch_filtered_transactions_with_smart_pagination(
    base_url: str,
    api_path: str,
    initial_params: dict,
    target_page_size: int,
    ctx: Context,
    max_pages_to_fetch: int = 10,  # Prevent infinite loops
    progress_start_step: float = 2.0,
    total_steps: float = 12.0,
) -> tuple[list[dict], bool]:
    """
    Fetch and accumulate filtered transaction items across multiple pages until we have enough items.

    This function handles the complex case where filtering removes most items from each page,
    requiring us to fetch multiple pages to get enough filtered results.

    The key insight: we accumulate items until we have target_page_size + 1 items (so create_items_pagination
    can detect if pagination is needed) OR until no more API pages are available.

    Returns:
        tuple of (filtered_items, has_more_pages_available)
        - filtered_items: list of raw API data, not transformed
        - has_more_pages_available: True if there are likely more pages with data available
    """
    accumulated_items = []
    current_params = initial_params.copy()
    pages_fetched = 0
    last_page_had_items = False
    api_has_more_pages = False

    while pages_fetched < max_pages_to_fetch:
        current_step = progress_start_step + pages_fetched

        # Fetch current page using periodic progress reporting to provide ability
        # to track progress the page fetch
        response_data = await make_request_with_periodic_progress(
            ctx=ctx,
            request_function=make_blockscout_request,
            request_args={"base_url": base_url, "api_path": api_path, "params": current_params},
            total_duration_hint=config.bs_timeout,
            progress_interval_seconds=config.progress_interval_seconds,
            in_progress_message_template=(
                f"Fetching page {pages_fetched + 1}, accumulated {len(accumulated_items)} items... "
                f"({{elapsed_seconds:.0f}}s / {{total_hint:.0f}}s hint)"
            ),
            tool_overall_total_steps=total_steps,
            current_step_number=current_step,
            current_step_message_prefix=f"Fetching page {pages_fetched + 1}",
        )

        original_items = response_data.get("items", [])
        next_page_params = response_data.get("next_page_params")
        pages_fetched += 1

        # Filter items from current page
        filtered_items = [item for item in original_items if item.get("type") not in EXCLUDED_TX_TYPES]

        # Track if this page had items and if API indicates more pages
        last_page_had_items = len(filtered_items) > 0
        api_has_more_pages = next_page_params is not None

        # Add to accumulated items
        accumulated_items.extend(filtered_items)

        # Check if we have enough items for pagination decision
        # We need target_page_size + 1 so create_items_pagination can detect if pagination is needed
        if len(accumulated_items) > target_page_size:
            # We have more than a page, so there are definitely more items available
            break

        if not next_page_params:
            # No more pages available, return whatever we have
            break

        # Prepare for next page
        current_params.update(next_page_params)

    # Determine if there are more pages available:
    # 1. If we have > target_page_size items, there are definitely more pages
    # 2. If we hit the page limit but the last page had items AND the API says there are more pages,
    #    then there are likely more pages with data
    has_more_pages = len(accumulated_items) > target_page_size or (
        pages_fetched >= max_pages_to_fetch and last_page_had_items and api_has_more_pages
    )

    return accumulated_items, has_more_pages


@log_tool_invocation
async def get_transactions_by_address(
    chain_id: Annotated[str, Field(description="The ID of the blockchain")],
    address: Annotated[str, Field(description="Address which either sender or receiver of the transaction")],
    ctx: Context,
    age_from: Annotated[str | None, Field(description="Start date and time (e.g 2025-05-22T23:00:00.00Z).")] = None,
    age_to: Annotated[str | None, Field(description="End date and time (e.g 2025-05-22T22:30:00.00Z).")] = None,
    methods: Annotated[
        str | None,
        Field(description="A method signature to filter transactions by (e.g 0x304e6ade)"),
    ] = None,
    cursor: Annotated[
        str | None,
        Field(description="The pagination cursor from a previous response to get the next page of results."),
    ] = None,
) -> ToolResponse[list[AdvancedFilterItem]]:
    """
    Retrieves native currency transfers and smart contract interactions (calls, internal txs) for an address.
    **EXCLUDES TOKEN TRANSFERS**: Filters out direct token balance changes (ERC-20, etc.). You'll see calls *to* token contracts, but not the `Transfer` events. For token history, use `get_token_transfers_by_address`.
    A single tx can have multiple records from internal calls; use `internal_transaction_index` for execution order.
    Use cases:
      - `get_transactions_by_address(address, age_from)` - get all txs to/from the address since a given date.
      - `get_transactions_by_address(address, age_from, age_to)` - get all txs to/from the address between given dates.
      - `get_transactions_by_address(address, age_from, age_to, methods)` - get all txs to/from the address between given dates, filtered by method.
    **SUPPORTS PAGINATION**: If response includes 'pagination' field, use the provided next_call to get additional pages.
    """  # noqa: E501
    api_path = "/api/v2/advanced-filters"
    query_params = {
        "to_address_hashes_to_include": address,
        "from_address_hashes_to_include": address,
    }
    if age_from:
        query_params["age_from"] = age_from
    if age_to:
        query_params["age_to"] = age_to
    if methods:
        query_params["methods"] = methods

    apply_cursor_to_params(cursor, query_params)

    # Calculate total steps:
    # 1 (URL resolution) + 10 (max iterations in _fetch_filtered_transactions_with_smart_pagination) + 1 (finalization)
    tool_overall_total_steps = 12.0

    # Report start of operation
    await report_and_log_progress(
        ctx,
        progress=0.0,
        total=tool_overall_total_steps,
        message=f"Starting to fetch transactions for {address} on chain {chain_id}...",
    )

    base_url = await get_blockscout_base_url(chain_id)

    # Report progress after resolving Blockscout URL (step 1 complete)
    await report_and_log_progress(
        ctx,
        progress=1.0,
        total=tool_overall_total_steps,
        message="Resolved Blockscout instance URL. Now fetching transactions...",
    )

    # Use smart pagination that handles filtering across multiple pages (steps 2-11)
    # internally, it uses make_request_with_periodic_progress to report progress for each page fetch
    filtered_items, has_more_pages = await _fetch_filtered_transactions_with_smart_pagination(
        base_url=base_url,
        api_path=api_path,
        initial_params=query_params,
        target_page_size=config.advanced_filters_page_size,
        ctx=ctx,
        progress_start_step=2.0,
        total_steps=tool_overall_total_steps,
    )

    # Report completion after fetching all needed pages (step 12)
    await report_and_log_progress(
        ctx,
        progress=tool_overall_total_steps,
        total=tool_overall_total_steps,
        message="Successfully fetched transaction data.",
    )

    # Transform filtered items (separate responsibility from filtering/pagination)
    fields_to_remove = [
        "total",
        "token",
        "token_transfer_batch_index",
        "token_transfer_index",
    ]
    transformed_items = [_transform_advanced_filter_item(item, fields_to_remove) for item in filtered_items]

    # Use create_items_pagination to handle slicing and pagination logic
    # Force pagination if we know there are more pages available despite having few items
    final_items, pagination = create_items_pagination(
        items=transformed_items,
        page_size=config.advanced_filters_page_size,
        tool_name="get_transactions_by_address",
        next_call_base_params={
            "chain_id": chain_id,
            "address": address,
            "age_from": age_from,
            "age_to": age_to,
            "methods": methods,
        },
        cursor_extractor=extract_advanced_filters_cursor_params,
        force_pagination=has_more_pages and len(transformed_items) <= config.advanced_filters_page_size,
    )

    # Convert to AdvancedFilterItem objects
    validated_items = [AdvancedFilterItem.model_validate(item) for item in final_items]

    return build_tool_response(data=validated_items, pagination=pagination)


@log_tool_invocation
async def get_token_transfers_by_address(
    chain_id: Annotated[str, Field(description="The ID of the blockchain")],
    address: Annotated[str, Field(description="Address which either transfer initiator or transfer receiver")],
    ctx: Context,
    age_from: Annotated[
        str | None,
        Field(
            description="Start date and time (e.g 2025-05-22T23:00:00.00Z). This parameter should be provided in most cases to limit transfers and avoid heavy database queries. Omit only if you absolutely need the full history."  # noqa: E501
        ),
    ] = None,
    age_to: Annotated[
        str | None,
        Field(
            description="End date and time (e.g 2025-05-22T22:30:00.00Z). Can be omitted to get all transfers up to the current time."  # noqa: E501
        ),
    ] = None,
    token: Annotated[
        str | None,
        Field(
            description="An ERC-20 token contract address to filter transfers by a specific token. If omitted, returns transfers of all tokens."  # noqa: E501
        ),
    ] = None,
    cursor: Annotated[
        str | None,
        Field(description="The pagination cursor from a previous response to get the next page of results."),
    ] = None,
) -> ToolResponse[list[AdvancedFilterItem]]:
    """
    Get ERC-20 token transfers for an address within a specific time range.
    Use cases:
      - `get_token_transfers_by_address(address, age_from)` - get all transfers of any ERC-20 token to/from the address since the given date up to the current time
      - `get_token_transfers_by_address(address, age_from, age_to)` - get all transfers of any ERC-20 token to/from the address between the given dates
      - `get_token_transfers_by_address(address, age_from, age_to, token)` - get all transfers of the given ERC-20 token to/from the address between the given dates
    **SUPPORTS PAGINATION**: If response includes 'pagination' field, use the provided next_call to get additional pages.
    """  # noqa: E501
    api_path = "/api/v2/advanced-filters"
    query_params = {
        "transaction_types": "ERC-20",
        "to_address_hashes_to_include": address,
        "from_address_hashes_to_include": address,
    }

    if age_from:
        query_params["age_from"] = age_from
    if age_to:
        query_params["age_to"] = age_to
    if token:
        query_params["token_contract_address_hashes_to_include"] = token

    apply_cursor_to_params(cursor, query_params)

    tool_overall_total_steps = 2.0

    # Report start of operation
    await report_and_log_progress(
        ctx,
        progress=0.0,
        total=tool_overall_total_steps,
        message=f"Starting to fetch token transfers for {address} on chain {chain_id}...",
    )

    base_url = await get_blockscout_base_url(chain_id)

    # Report progress after resolving Blockscout URL
    await report_and_log_progress(
        ctx,
        progress=1.0,
        total=tool_overall_total_steps,
        message="Resolved Blockscout instance URL. Now fetching token transfers...",
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
        current_step_message_prefix="Fetching token transfers",
    )

    # The wrapper make_request_with_periodic_progress handles the final progress report for this step.
    # So, no explicit ctx.report_progress(progress=2.0, ...) is needed here.

    original_items = response_data.get("items", [])
    fields_to_remove = ["value", "internal_transaction_index", "created_contract"]

    transformed_items = [_transform_advanced_filter_item(item, fields_to_remove) for item in original_items]

    sliced_items, pagination = create_items_pagination(
        items=transformed_items,
        page_size=config.advanced_filters_page_size,
        tool_name="get_token_transfers_by_address",
        next_call_base_params={
            "chain_id": chain_id,
            "address": address,
            "age_from": age_from,
            "age_to": age_to,
            "token": token,
        },
        cursor_extractor=extract_advanced_filters_cursor_params,
    )
    # All the fields returned by the API except the ones in `fields_to_remove` are added to the response
    sliced_items = [AdvancedFilterItem.model_validate(item) for item in sliced_items]

    return build_tool_response(data=sliced_items, pagination=pagination)


@log_tool_invocation
async def transaction_summary(
    chain_id: Annotated[str, Field(description="The ID of the blockchain")],
    transaction_hash: Annotated[str, Field(description="Transaction hash")],
    ctx: Context,
) -> ToolResponse[TransactionSummaryData]:
    """
    Get human-readable transaction summaries from Blockscout Transaction Interpreter.
    Automatically classifies transactions into natural language descriptions (transfers, swaps, NFT sales, DeFi operations)
    Essential for rapid transaction comprehension, dashboard displays, and initial analysis.
    Note: Not all transactions can be summarized and accuracy is not guaranteed for complex patterns.
    """  # noqa: E501
    api_path = f"/api/v2/transactions/{transaction_hash}/summary"

    # Report start of operation
    await report_and_log_progress(
        ctx,
        progress=0.0,
        total=2.0,
        message=f"Starting to fetch transaction summary for {transaction_hash} on chain {chain_id}...",
    )

    base_url = await get_blockscout_base_url(chain_id)

    # Report progress after resolving Blockscout URL
    await report_and_log_progress(
        ctx, progress=1.0, total=2.0, message="Resolved Blockscout instance URL. Fetching transaction summary..."
    )

    response_data = await make_blockscout_request(base_url=base_url, api_path=api_path)

    # Report completion
    await report_and_log_progress(ctx, progress=2.0, total=2.0, message="Successfully fetched transaction summary.")

    # Only the summary is extracted from the API response since only this field contains
    # information that could be handled by the LLM without additional interpretation instructions
    summary = response_data.get("data", {}).get("summaries")

    if summary is not None and not isinstance(summary, list):
        raise RuntimeError("Blockscout API returned an unexpected format for transaction summary")

    summary_data = TransactionSummaryData(summary=summary)

    return build_tool_response(data=summary_data)


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

    # Report start of operation
    await report_and_log_progress(
        ctx,
        progress=0.0,
        total=2.0,
        message=f"Starting to fetch transaction info for {transaction_hash} on chain {chain_id}...",
    )

    base_url = await get_blockscout_base_url(chain_id)

    # Report progress after resolving Blockscout URL
    await report_and_log_progress(
        ctx, progress=1.0, total=2.0, message="Resolved Blockscout instance URL. Fetching transaction data..."
    )

    response_data = await make_blockscout_request(base_url=base_url, api_path=api_path)

    # Report completion
    await report_and_log_progress(ctx, progress=2.0, total=2.0, message="Successfully fetched transaction data.")

    # Process data for truncation
    processed_data, was_truncated = _process_and_truncate_tx_info_data(response_data, include_raw_input)

    # Apply transformations to the data to preserve the LLM context:
    # 1. Remove redundant top-level hash
    # 2. Simplify top-level 'from' and 'to' objects
    # 3. Optimize the 'token_transfers' list to remove fields duplicated in the top-level objects
    final_data_dict = _transform_transaction_info(processed_data)

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

    return build_tool_response(data=transaction_data, notes=notes)


@log_tool_invocation
async def get_transaction_logs(
    chain_id: Annotated[str, Field(description="The ID of the blockchain")],
    transaction_hash: Annotated[str, Field(description="Transaction hash")],
    ctx: Context,
    cursor: Annotated[
        str | None,
        Field(description="The pagination cursor from a previous response to get the next page of results."),
    ] = None,
) -> ToolResponse[list[TransactionLogItem]]:
    """
    Get comprehensive transaction logs.
    Unlike standard eth_getLogs, this tool returns enriched logs, primarily focusing on decoded event parameters with their types and values (if event decoding is applicable).
    Essential for analyzing smart contract events, tracking token transfers, monitoring DeFi protocol interactions, debugging event emissions, and understanding complex multi-contract transaction flows.
    **SUPPORTS PAGINATION**: If response includes 'pagination' field, use the provided next_call to get additional pages.
    """  # noqa: E501
    api_path = f"/api/v2/transactions/{transaction_hash}/logs"
    params = {}

    apply_cursor_to_params(cursor, params)

    # Report start of operation
    await report_and_log_progress(
        ctx,
        progress=0.0,
        total=2.0,
        message=f"Starting to fetch transaction logs for {transaction_hash} on chain {chain_id}...",
    )

    base_url = await get_blockscout_base_url(chain_id)

    # Report progress after resolving Blockscout URL
    await report_and_log_progress(
        ctx, progress=1.0, total=2.0, message="Resolved Blockscout instance URL. Fetching transaction logs..."
    )

    response_data = await make_blockscout_request(base_url=base_url, api_path=api_path, params=params)

    original_items, was_truncated = _process_and_truncate_log_items(response_data.get("items", []))

    log_items_dicts: list[dict] = []
    # To preserve the LLM context, only specific fields are added to the response
    for item in original_items:
        address_value = (
            item.get("address", {}).get("hash") if isinstance(item.get("address"), dict) else item.get("address")
        )
        curated_item = {
            "address": address_value,
            "block_number": item.get("block_number"),
            "topics": item.get("topics"),
            "data": item.get("data"),
            "decoded": item.get("decoded"),
            "index": item.get("index"),
        }
        if item.get("data_truncated"):
            curated_item["data_truncated"] = True
        log_items_dicts.append(curated_item)

    data_description = [
        "Items Structure:",
        "- `address`: The contract address that emitted the log (string)",
        "- `block_number`: Block where the event was emitted",
        "- `index`: Log position within the block",
        "- `topics`: Raw indexed event parameters (first topic is event signature hash)",
        "- `data`: Raw non-indexed event parameters (hex encoded). **May be truncated.**",
        "- `decoded`: If available, the decoded event with its name and parameters",
        "- `data_truncated`: (Optional) `true` if the `data` or `decoded` field was shortened.",
        "Event Decoding in `decoded` field:",
        (
            "- `method_call`: **Actually the event signature** "
            '(e.g., "Transfer(address indexed from, address indexed to, uint256 value)")'
        ),
        "- `method_id`: **Actually the event signature hash** (first 4 bytes of keccak256 hash)",
        "- `parameters`: Decoded event parameters with names, types, values, and indexing status",
    ]

    notes = None
    if was_truncated:
        notes = [
            (
                "One or more log items in this response had a `data` field that was "
                'too large and has been truncated (indicated by `"data_truncated": true`).'
            ),
            (
                "If the full log data is crucial for your analysis, you can retrieve the complete, "
                "untruncated logs for this transaction programmatically. For example, using curl:"
            ),
            f'`curl "{base_url}/api/v2/transactions/{transaction_hash}/logs"`',
            "You would then need to parse the JSON response and find the specific log by its index.",
        ]

    sliced_items, pagination = create_items_pagination(
        items=log_items_dicts,
        page_size=config.logs_page_size,
        tool_name="get_transaction_logs",
        next_call_base_params={"chain_id": chain_id, "transaction_hash": transaction_hash},
        cursor_extractor=extract_log_cursor_params,
    )

    log_items = [TransactionLogItem(**item) for item in sliced_items]

    await report_and_log_progress(ctx, progress=2.0, total=2.0, message="Successfully fetched transaction logs.")

    return build_tool_response(
        data=log_items,
        data_description=data_description,
        notes=notes,
        pagination=pagination,
    )
