import base64
import json
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

import anyio
import httpx
from mcp.server.fastmcp import Context

from blockscout_mcp_server.cache import ChainCache, ChainsListCache
from blockscout_mcp_server.config import config
from blockscout_mcp_server.constants import (
    INPUT_DATA_TRUNCATION_LIMIT,
    LOG_DATA_TRUNCATION_LIMIT,
)
from blockscout_mcp_server.models import NextCallInfo, PaginationInfo, ToolResponse

logger = logging.getLogger(__name__)


def _create_httpx_client(*, timeout: float) -> httpx.AsyncClient:
    """Return an AsyncClient pre-configured for Blockscout tooling.

    Args:
        timeout: The timeout value (in seconds) for the HTTP client.

    Returns:
        An instance of httpx.AsyncClient with the specified timeout and
        `follow_redirects` set to ``True``.

    Note:
        The client is created with ``follow_redirects=True`` so all requests
        automatically handle HTTP redirects.
    """

    return httpx.AsyncClient(timeout=timeout, follow_redirects=True)


def find_blockscout_url(chain_data: dict) -> str | None:
    """Return the Blockscout-hosted explorer URL from chain data."""
    for explorer in chain_data.get("explorers", []):
        if isinstance(explorer, dict) and explorer.get("hostedBy") == "blockscout":
            url = explorer.get("url")
            if url:
                return url.rstrip("/")
    return None


class ChainNotFoundError(ValueError):
    """Exception raised when a chain ID cannot be found or resolved to a Blockscout URL."""

    pass


# Shared cache instance for chain data
chain_cache = ChainCache()
chains_list_cache = ChainsListCache()


async def get_blockscout_base_url(chain_id: str) -> str:
    """
    Fetches the Blockscout base URL for a given chain_id from Chainscout,
    caches it, and handles errors.

    Args:
        chain_id: The blockchain chain ID to look up

    Returns:
        The Blockscout instance URL for the chain

    Raises:
        ChainNotFoundError: If no Blockscout instance is found for the chain
    """
    current_time = time.time()
    cached_entry = chain_cache.get(chain_id)

    if cached_entry:
        cached_url, expiry_timestamp = cached_entry
        if current_time < expiry_timestamp:
            if cached_url is None:  # Cached "not found"
                raise ChainNotFoundError(
                    f"Blockscout instance hosted by Blockscout team for chain ID '{chain_id}' is unknown (cached)."
                )
            return cached_url
        else:
            chain_cache.invalidate(chain_id)  # Cache expired

    chain_api_url = f"{config.chainscout_url}/api/chains/{chain_id}"

    # Note: We're not using make_chainscout_request here because we need:
    # 1. Custom error handling for different HTTP status codes (like 404)
    # 2. Special caching behavior for error cases
    # 3. Direct access to handle JSON parsing errors
    # 4. Chain-specific context in error messages
    try:
        async with _create_httpx_client(timeout=config.chainscout_timeout) as client:
            response = await client.get(chain_api_url)
        response.raise_for_status()
        chain_data = response.json()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            chain_cache.set_failure(chain_id)
            raise ChainNotFoundError(f"Chain with ID '{chain_id}' not found on Chainscout.") from e
        raise ChainNotFoundError(f"Error fetching data for chain ID '{chain_id}' from Chainscout: {e}") from e
    except (httpx.RequestError, json.JSONDecodeError) as e:
        raise ChainNotFoundError(f"Could not retrieve or parse data for chain ID '{chain_id}' from Chainscout.") from e

    if not chain_data or "explorers" not in chain_data:
        chain_cache.set_failure(chain_id)
        raise ChainNotFoundError(f"No explorer data found for chain ID '{chain_id}' on Chainscout.")

    blockscout_url = find_blockscout_url(chain_data)
    chain_cache.set(chain_id, blockscout_url)

    if blockscout_url:
        return blockscout_url
    raise ChainNotFoundError(f"Blockscout instance hosted by Blockscout team for chain ID '{chain_id}' is unknown.")


async def make_blockscout_request(base_url: str, api_path: str, params: dict | None = None) -> dict:
    """
    Make a GET request to the Blockscout API.

    Args:
        base_url: The base URL of the Blockscout API instance
        api_path: The API path to request, e.g. '/api/v2/blocks/19000000'
        params: Optional query parameters

    Returns:
        The JSON response as a dictionary

    Raises:
        httpx.HTTPStatusError: If the HTTP request returns an error status code
        httpx.TimeoutException: If the request times out
    """
    async with _create_httpx_client(timeout=config.bs_timeout) as client:
        if params is None:
            params = {}
        if config.bs_api_key:
            params["apikey"] = config.bs_api_key

        url = f"{base_url.rstrip('/')}/{api_path.lstrip('/')}"
        response = await client.get(url, params=params)
        response.raise_for_status()  # Raise an exception for HTTP errors
        return response.json()


async def make_bens_request(api_path: str, params: dict | None = None) -> dict:
    """
    Make a GET request to the BENS API.

    Args:
        api_path: The API path to request, e.g. '/api/v1/1/domains/blockscout.eth'
        params: Optional query parameters

    Returns:
        The JSON response as a dictionary

    Raises:
        httpx.HTTPStatusError: If the HTTP request returns an error status code
        httpx.TimeoutException: If the request times out
    """
    async with _create_httpx_client(timeout=config.bens_timeout) as client:
        url = f"{config.bens_url}{api_path}"
        response = await client.get(url, params=params)
        response.raise_for_status()
        return response.json()


async def make_chainscout_request(api_path: str, params: dict | None = None) -> dict:
    """
    Make a GET request to the Chainscout API.

    Args:
        api_path: The API path to request, e.g. '/api/chains/list'
        params: Optional query parameters

    Returns:
        The JSON response as a dictionary

    Raises:
        httpx.HTTPStatusError: If the HTTP request returns an error status code
        httpx.TimeoutException: If the request times out
    """
    async with _create_httpx_client(timeout=config.chainscout_timeout) as client:
        url = f"{config.chainscout_url}{api_path}"
        response = await client.get(url, params=params)
        response.raise_for_status()
        return response.json()


async def make_metadata_request(api_path: str, params: dict | None = None) -> dict:
    """
    Make a GET request to the Metadata API.

    Args:
        api_path: The API path to request
        params: Optional query parameters

    Returns:
        The JSON response as a dictionary

    Raises:
        httpx.HTTPStatusError: If the HTTP request returns an error status code
        httpx.TimeoutException: If the request times out
    """
    async with _create_httpx_client(timeout=config.metadata_timeout) as client:
        url = f"{config.metadata_url}{api_path}"
        response = await client.get(url, params=params)
        response.raise_for_status()
        return response.json()


async def make_request_with_periodic_progress(
    ctx: Context,
    request_function: Callable[..., Awaitable[dict]],  # e.g., make_blockscout_request
    request_args: dict[str, Any],  # Args for request_function
    total_duration_hint: float,  # e.g., config.bs_timeout
    progress_interval_seconds: float = 15.0,
    in_progress_message_template: str = "Query in progress... ({elapsed_seconds:.0f}s / {total_hint:.0f}s)",
    tool_overall_total_steps: float = 2.0,
    current_step_number: float = 2.0,  # 1-indexed
    current_step_message_prefix: str = "Fetching data",
) -> dict:
    """
    Execute a request function with periodic progress updates.

    This wrapper provides periodic progress reports while waiting for potentially long-running
    API calls, helping clients understand that the server is still working.

    Args:
        ctx: MCP Context for progress reporting
        request_function: The async function to call (e.g., make_blockscout_request)
        request_args: Dictionary of arguments to pass to request_function
        total_duration_hint: Expected duration in seconds (for progress calculation)
        progress_interval_seconds: How often to report progress (default 15s)
        in_progress_message_template: Template for progress messages
        tool_overall_total_steps: Total steps in the overall tool (for multi-step tools)
        current_step_number: Which step this request represents (1-indexed)
        current_step_message_prefix: Prefix for progress messages

    Returns:
        The result from request_function

    Raises:
        Any exception raised by request_function
    """
    start_time = time.monotonic()
    api_call_done_event = anyio.Event()
    api_result = None
    api_exception = None

    async def _api_task():
        """Execute the actual API call."""
        nonlocal api_result, api_exception
        try:
            api_result = await request_function(**request_args)
        except Exception as e:
            api_exception = e
        finally:
            api_call_done_event.set()

    async def _progress_task():
        """Periodically report progress while the API call is running."""
        while not api_call_done_event.is_set():
            elapsed_seconds = time.monotonic() - start_time

            # Calculate progress within this step (don't exceed 100% for this step)
            progress_within_step = min(elapsed_seconds / total_duration_hint, 1.0)

            # Calculate overall progress across all tool steps
            overall_progress = (current_step_number - 1) + progress_within_step

            # Round progress to 3 decimal places for cleaner display
            overall_progress_rounded = round(overall_progress, 3)

            # Format the progress message
            formatted_message = f"{current_step_message_prefix}: {in_progress_message_template.format(elapsed_seconds=elapsed_seconds, total_hint=total_duration_hint)}"  # noqa: E501

            # Report progress to client
            await report_and_log_progress(
                ctx,
                progress=overall_progress_rounded,
                total=tool_overall_total_steps,
                message=formatted_message,
            )

            # Wait for the next progress interval or until API call completes
            with anyio.move_on_after(progress_interval_seconds):
                await api_call_done_event.wait()

    # Start both tasks concurrently
    async with anyio.create_task_group() as tg:
        # Start the API call task
        tg.start_soon(_api_task)

        # Start the progress reporting task
        tg.start_soon(_progress_task)

        # Wait for the API call to complete
        await api_call_done_event.wait()

    # Report final progress and handle results
    if api_exception:
        # Report failure
        await ctx.report_progress(
            progress=round(current_step_number, 3),  # Mark this step as complete (even if failed)
            total=tool_overall_total_steps,
            message=f"{current_step_message_prefix}: Failed. Error: {str(api_exception)}",
        )
        raise api_exception
    else:
        # Report success
        await ctx.report_progress(
            progress=round(current_step_number, 3),  # Mark this step as 100% complete
            total=tool_overall_total_steps,
            message=f"{current_step_message_prefix}: Completed.",
        )
        return api_result


class InvalidCursorError(ValueError):
    """Raised when a pagination cursor is malformed or invalid."""

    pass


def encode_cursor(params: dict) -> str:
    """JSON-serializes and Base64URL-encodes pagination parameters."""
    if not params:
        return ""
    json_string = json.dumps(params, separators=(",", ":"))
    return base64.urlsafe_b64encode(json_string.encode("utf-8")).decode("utf-8")


def decode_cursor(cursor: str) -> dict:
    """Decodes and JSON-deserializes a cursor string."""
    if not cursor:
        raise InvalidCursorError("Cursor cannot be empty.")
    try:
        padded_cursor = cursor + "=" * (-len(cursor) % 4)
        json_string = base64.urlsafe_b64decode(padded_cursor.encode("utf-8")).decode("utf-8")
        return json.loads(json_string)
    except (TypeError, ValueError, json.JSONDecodeError, base64.binascii.Error) as e:
        raise InvalidCursorError("Invalid or expired cursor provided.") from e


def _recursively_truncate_and_flag_long_strings(data: Any) -> tuple[Any, bool]:
    """
    Recursively traverses a data structure to find and truncate long strings.

    This function handles nested lists, tuples, and dictionaries. When a string
    exceeds INPUT_DATA_TRUNCATION_LIMIT, it's replaced with a dictionary
    indicating that truncation occurred.

    Args:
        data: The data to process (can be any type).

    Returns:
        A tuple containing:
        - The processed data with long strings replaced.
        - A boolean flag `was_truncated`, which is True if any string was truncated.
    """  # noqa: E501
    if isinstance(data, str):
        if len(data) > INPUT_DATA_TRUNCATION_LIMIT:
            return {
                "value_sample": data[:INPUT_DATA_TRUNCATION_LIMIT],
                "value_truncated": True,
            }, True
        return data, False

    if isinstance(data, list):
        processed_list = []
        list_truncated = False
        for item in data:
            processed_item, item_truncated = _recursively_truncate_and_flag_long_strings(item)
            processed_list.append(processed_item)
            if item_truncated:
                list_truncated = True
        return processed_list, list_truncated

    if isinstance(data, tuple):
        processed_list = []
        tuple_truncated = False
        for item in data:
            processed_item, item_truncated = _recursively_truncate_and_flag_long_strings(item)
            processed_list.append(processed_item)
            if item_truncated:
                tuple_truncated = True
        return tuple(processed_list), tuple_truncated

    if isinstance(data, dict):
        processed_dict = {}
        dict_truncated = False
        for key, value in data.items():
            processed_value, value_truncated = _recursively_truncate_and_flag_long_strings(value)
            processed_dict[key] = processed_value
            if value_truncated:
                dict_truncated = True
        return processed_dict, dict_truncated

    # For any other data type (int, bool, None, etc.), return it as is.
    return data, False


def _process_and_truncate_log_items(items: list) -> tuple[list, bool]:
    """Truncate large log values.

    Shortens the raw ``data`` field and recursively trims long strings within
    the ``decoded`` dictionary of each item. Returns the processed list and a
    flag indicating whether any truncation occurred.
    """
    processed_items = []
    was_truncated = False
    for item in items:
        item_copy = item.copy()
        data = item_copy.get("data")
        if isinstance(data, str) and len(data) > LOG_DATA_TRUNCATION_LIMIT:
            item_copy["data"] = data[:LOG_DATA_TRUNCATION_LIMIT]
            item_copy["data_truncated"] = True
            was_truncated = True

        decoded = item_copy.get("decoded")
        if isinstance(decoded, dict):
            processed_decoded, decoded_was_truncated = _recursively_truncate_and_flag_long_strings(decoded)
            item_copy["decoded"] = processed_decoded
            if decoded_was_truncated:
                was_truncated = True
        processed_items.append(item_copy)
    return processed_items, was_truncated


async def report_and_log_progress(
    ctx: Context,
    progress: float,
    total: float | None,
    message: str | None,
) -> None:
    """Reports progress to the client and logs it as an info message."""
    await ctx.report_progress(progress=progress, total=total, message=message)
    log_message = f"Progress: {progress}/{total} - {message}"
    await ctx.info(log_message)


def build_tool_response(
    data: Any,
    data_description: list[str] | None = None,
    notes: list[str] | None = None,
    instructions: list[str] | None = None,
    pagination: PaginationInfo | None = None,
) -> ToolResponse[Any]:
    """
    Construct a standardized ToolResponse object.

    Args:
        data: The main data payload for the response.
        data_description: Optional list of strings describing the data structure.
        notes: Optional list of strings for warnings or contextual notes.
        instructions: Optional list of strings for follow-up actions.
        pagination: Optional PaginationInfo object if the data is paginated.

    Returns:
        A ToolResponse instance.
    """
    # Automatically add pagination instructions when pagination is present
    final_instructions = list(instructions) if instructions is not None else []

    if pagination:
        pagination_instructions = [
            "⚠️ MORE DATA AVAILABLE: Use pagination.next_call to get the next page.",
            "Continue calling subsequent pages if you need comprehensive results.",
        ]
        final_instructions.extend(pagination_instructions)

    # Return instructions if they were explicitly provided (even if empty) or if pagination added some
    final_instructions_output = None
    if instructions is not None or pagination is not None:
        final_instructions_output = final_instructions

    return ToolResponse(
        data=data,
        data_description=data_description,
        notes=notes,
        instructions=final_instructions_output,
        pagination=pagination,
    )


def apply_cursor_to_params(cursor: str | None, params: dict) -> None:
    """Decodes a pagination cursor and updates the params dictionary in-place.

    Args:
        cursor: The opaque cursor string from a previous tool response.
        params: The dictionary of query parameters to be updated.

    Raises:
        ValueError: If the cursor is invalid or expired.
    """
    if cursor:
        try:
            decoded_params = decode_cursor(cursor)
            params.update(decoded_params)
        except InvalidCursorError:
            raise ValueError(
                "Invalid or expired pagination cursor. Please make a new request without the cursor to start over."
            )


def create_items_pagination(
    *,
    items: list[dict],
    page_size: int,
    tool_name: str,
    next_call_base_params: dict,
    cursor_extractor: Callable[[dict], dict],
    force_pagination: bool = False,
) -> tuple[list[dict], PaginationInfo | None]:
    """
    Slice items list and generate pagination info if needed.

    Args:
        force_pagination: If True, creates pagination even when items <= page_size,
                         using the last item for cursor generation. Useful when the caller
                         knows there are more pages available despite having few items.
    """
    if len(items) <= page_size and not force_pagination:
        return items, None

    # Determine pagination behavior
    if len(items) > page_size:
        # Normal case: slice items and use item at page_size - 1 for cursor
        sliced_items = items[:page_size]
        last_item_for_cursor = items[page_size - 1]
    else:
        # Force pagination case: use all items and last item for cursor
        sliced_items = items
        last_item_for_cursor = items[-1] if items else None

    # Only create pagination if we have an item to generate cursor from
    if not last_item_for_cursor:
        return sliced_items, None

    next_page_params = cursor_extractor(last_item_for_cursor)
    next_cursor = encode_cursor(next_page_params)

    final_params = next_call_base_params.copy()
    final_params["cursor"] = next_cursor

    pagination = PaginationInfo(
        next_call=NextCallInfo(
            tool_name=tool_name,
            params=final_params,
        )
    )

    return sliced_items, pagination


def extract_log_cursor_params(item: dict) -> dict:
    """Return cursor parameters extracted from a log item."""

    return {
        "block_number": item.get("block_number"),
        "index": item.get("index"),
    }


def extract_advanced_filters_cursor_params(item: dict) -> dict:
    """Return cursor parameters extracted from an advanced-filters item."""

    return {
        "block_number": item.get("block_number"),
        "transaction_index": item.get("transaction_index"),
        "internal_transaction_index": item.get("internal_transaction_index"),
        "token_transfer_batch_index": item.get("token_transfer_batch_index"),
        "token_transfer_index": item.get("token_transfer_index"),
    }
