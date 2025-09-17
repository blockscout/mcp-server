from typing import Any

from mcp.server.fastmcp import Context

from blockscout_mcp_server.config import config
from blockscout_mcp_server.constants import INPUT_DATA_TRUNCATION_LIMIT
from blockscout_mcp_server.tools.common import (
    _process_and_truncate_log_items,
    _recursively_truncate_and_flag_long_strings,
    create_items_pagination,
    extract_advanced_filters_cursor_params,
    extract_log_cursor_params,
    make_blockscout_request,
    make_request_with_periodic_progress,
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
    *,
    max_pages_to_fetch: int = 10,
    progress_start_step: float = 2.0,
    total_steps: float = 12.0,
) -> tuple[list[dict], bool]:
    """
    Fetch and accumulate filtered transaction items across multiple pages until we have enough items.

    Returns a tuple of (filtered_items, has_more_pages_available).
    """
    accumulated_items = []
    current_params = initial_params.copy()
    pages_fetched = 0
    last_page_had_items = False
    api_has_more_pages = False

    while pages_fetched < max_pages_to_fetch:
        current_step = progress_start_step + pages_fetched

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

        filtered_items = [item for item in original_items if item.get("type") not in EXCLUDED_TX_TYPES]

        last_page_had_items = len(filtered_items) > 0
        api_has_more_pages = next_page_params is not None

        accumulated_items.extend(filtered_items)

        if len(accumulated_items) > target_page_size:
            break

        if not next_page_params:
            break

        current_params.update(next_page_params)

    has_more_pages = len(accumulated_items) > target_page_size or (
        pages_fetched >= max_pages_to_fetch and last_page_had_items and api_has_more_pages
    )

    return accumulated_items, has_more_pages


__all__ = [
    "EXCLUDED_TX_TYPES",
    "_fetch_filtered_transactions_with_smart_pagination",
    "_process_and_truncate_log_items",
    "_process_and_truncate_tx_info_data",
    "_recursively_truncate_and_flag_long_strings",
    "_transform_advanced_filter_item",
    "_transform_transaction_info",
    "create_items_pagination",
    "extract_advanced_filters_cursor_params",
    "extract_log_cursor_params",
]
