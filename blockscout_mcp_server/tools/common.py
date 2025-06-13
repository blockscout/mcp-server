import httpx
import time
import json
import base64
import anyio
from typing import Optional, Callable, Awaitable, Any, Dict
from blockscout_mcp_server.config import config
from mcp.server.fastmcp import Context

class ChainNotFoundError(ValueError):
    """Exception raised when a chain ID cannot be found or resolved to a Blockscout URL."""
    pass

# Cache: chain_id -> (blockscout_url_or_none, expiry_timestamp)
# Note: This cache is simple and not thread-safe for concurrent writes for the same new key.
# This is acceptable for the typical MCP server use case (local, one server per client).
_chain_cache: dict[str, tuple[Optional[str], float]] = {}

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
    cached_entry = _chain_cache.get(chain_id)

    if cached_entry:
        cached_url, expiry_timestamp = cached_entry
        if current_time < expiry_timestamp:
            if cached_url is None:  # Cached "not found"
                raise ChainNotFoundError(
                    f"Blockscout instance hosted by Blockscout team for chain ID '{chain_id}' is unknown (cached)."
                )
            return cached_url
        else:
            _chain_cache.pop(chain_id, None)  # Cache expired

    chain_api_url = f"{config.chainscout_url}/api/chains/{chain_id}"
    
    # Note: We're not using make_chainscout_request here because we need:
    # 1. Custom error handling for different HTTP status codes (like 404)
    # 2. Special caching behavior for error cases
    # 3. Direct access to handle JSON parsing errors
    # 4. Chain-specific context in error messages
    try:
        async with httpx.AsyncClient(timeout=config.chainscout_timeout) as client:
            response = await client.get(chain_api_url)
        response.raise_for_status()
        chain_data = response.json()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            _chain_cache[chain_id] = (None, current_time + config.chain_cache_ttl_seconds)
            raise ChainNotFoundError(f"Chain with ID '{chain_id}' not found on Chainscout.") from e
        raise ChainNotFoundError(f"Error fetching data for chain ID '{chain_id}' from Chainscout: {e}") from e
    except (httpx.RequestError, json.JSONDecodeError) as e:
        raise ChainNotFoundError(f"Could not retrieve or parse data for chain ID '{chain_id}' from Chainscout.") from e

    if not chain_data or "explorers" not in chain_data:
        _chain_cache[chain_id] = (None, current_time + config.chain_cache_ttl_seconds)
        raise ChainNotFoundError(f"No explorer data found for chain ID '{chain_id}' on Chainscout.")

    blockscout_url = None
    for explorer in chain_data.get("explorers", []):
        if isinstance(explorer, dict) and explorer.get("hostedBy") == "blockscout":
            blockscout_url = explorer.get("url")
            if blockscout_url:
                break
    
    expiry = current_time + config.chain_cache_ttl_seconds
    if blockscout_url:
        _chain_cache[chain_id] = (blockscout_url, expiry)
        return blockscout_url.rstrip('/')
    else:
        _chain_cache[chain_id] = (None, expiry)
        raise ChainNotFoundError(
            f"Blockscout instance hosted by Blockscout team for chain ID '{chain_id}' is unknown."
        )

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
    async with httpx.AsyncClient(timeout=config.bs_timeout) as client:
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
    async with httpx.AsyncClient(timeout=config.bens_timeout) as client:
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
    async with httpx.AsyncClient(timeout=config.chainscout_timeout) as client:
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
    async with httpx.AsyncClient(timeout=config.metadata_timeout) as client:
        url = f"{config.metadata_url}{api_path}"
        response = await client.get(url, params=params)
        response.raise_for_status()
        return response.json()

async def make_request_with_periodic_progress(
    ctx: Context,
    request_function: Callable[..., Awaitable[Dict]],  # e.g., make_blockscout_request
    request_args: Dict[str, Any],                      # Args for request_function
    total_duration_hint: float,                        # e.g., config.bs_timeout
    progress_interval_seconds: float = 15.0,
    in_progress_message_template: str = "Query in progress... ({elapsed_seconds:.0f}s / {total_hint:.0f}s)",
    tool_overall_total_steps: float = 2.0,
    current_step_number: float = 2.0,  # 1-indexed
    current_step_message_prefix: str = "Fetching data"
) -> Dict:
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
            formatted_message = f"{current_step_message_prefix}: {in_progress_message_template.format(elapsed_seconds=elapsed_seconds, total_hint=total_duration_hint)}"
            
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
            message=f"{current_step_message_prefix}: Failed. Error: {str(api_exception)}"
        )
        raise api_exception
    else:
        # Report success
        await ctx.report_progress(
            progress=round(current_step_number, 3),  # Mark this step as 100% complete
            total=tool_overall_total_steps,
            message=f"{current_step_message_prefix}: Completed."
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
        json_string = base64.urlsafe_b64decode(padded_cursor.encode("utf-8")).decode(
            "utf-8"
        )
        return json.loads(json_string)
    except (TypeError, ValueError, json.JSONDecodeError, base64.binascii.Error) as e:
        raise InvalidCursorError("Invalid or expired cursor provided.") from e


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
