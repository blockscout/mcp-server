# SPDX-License-Identifier: LicenseRef-Blockscout
import json
from typing import Annotated, Any, Literal

from mcp.server.fastmcp import Context
from pydantic import Field

from blockscout_mcp_server.config import config
from blockscout_mcp_server.constants import ALLOW_LARGE_RESPONSE_HEADER
from blockscout_mcp_server.models import DirectApiData, NextCallInfo, PaginationInfo, ToolResponse
from blockscout_mcp_server.tools.common import (
    ResponseTooLargeError,
    apply_cursor_to_params,
    build_tool_response,
    encode_cursor,
    get_blockscout_base_url,
    make_blockscout_post_request,
    make_blockscout_request,
    report_and_log_progress,
)
from blockscout_mcp_server.tools.decorators import log_tool_invocation
from blockscout_mcp_server.tools.direct_api import dispatcher
from blockscout_mcp_server.tools.direct_api import handlers as _handlers  # noqa: F401  # Ensure handler registration


@log_tool_invocation
async def direct_api_call(
    chain_id: Annotated[str, Field(description="The ID of the blockchain")],
    endpoint_path: Annotated[
        str,
        Field(
            description="The Blockscout API path to call (e.g., '/api/v2/stats'); do not include query strings.",
        ),
    ],
    ctx: Context,
    query_params: Annotated[
        dict[str, Any] | None,
        Field(description="Optional query parameters forwarded to the Blockscout API."),
    ] = None,
    cursor: Annotated[
        str | None,
        Field(description="The pagination cursor from a previous response to get the next page of results."),
    ] = None,
    method: Annotated[
        Literal["GET", "POST"],
        Field(description="HTTP method used for the upstream call. Use POST with json_body."),
    ] = "GET",
    json_body: Annotated[
        dict[str, Any] | None,
        Field(description="JSON request body for POST requests."),
    ] = None,
) -> ToolResponse[Any]:
    """Call a raw Blockscout API endpoint for advanced or chain-specific data.

    Do not include query strings in ``endpoint_path``; pass all query parameters via
    ``query_params`` to avoid double-encoding.

    **SUPPORTS PAGINATION**: If response includes 'pagination' field,
    use the provided next_call to get additional pages (GET only).

    Supports POST requests with a JSON body for endpoints like ``/api/eth-rpc``.

    Returns:
        ToolResponse[Any]: Must return ToolResponse[Any] (not ToolResponse[BaseModel])
        because specialized handlers can return lists or other types that don't inherit
        from BaseModel. The dispatcher system supports flexible data structures.
    """
    await report_and_log_progress(
        ctx,
        progress=0.0,
        total=2.0,
        message=f"Resolving Blockscout URL for chain {chain_id}...",
    )
    if method not in ("GET", "POST"):
        raise ValueError("method must be 'GET' or 'POST'.")
    if method == "GET" and json_body is not None:
        raise ValueError("json_body is only allowed with method='POST'.")
    if method == "POST" and json_body is None:
        raise ValueError("json_body is required when method='POST'.")
    if method == "POST" and json_body is not None and not isinstance(json_body, dict):
        raise ValueError("json_body must be a JSON object (dict).")
    if method == "POST" and cursor is not None:
        raise ValueError("Pagination (cursor) is not supported for POST requests.")

    base_url = await get_blockscout_base_url(chain_id)
    if endpoint_path != "/" and endpoint_path.endswith("/"):
        endpoint_path = endpoint_path.rstrip("/")
    if "?" in endpoint_path:
        raise ValueError("Do not include query parameters in endpoint_path. Use query_params instead.")

    params = dict(query_params) if query_params else {}
    if method == "GET":
        apply_cursor_to_params(cursor, params)

    await report_and_log_progress(
        ctx,
        progress=1.0,
        total=2.0,
        message="Fetching data from Blockscout API...",
    )
    if method == "GET":
        response_json = await make_blockscout_request(base_url=base_url, api_path=endpoint_path, params=params)
    else:
        response_json = await make_blockscout_post_request(
            base_url=base_url,
            api_path=endpoint_path,
            json_body=json_body,
            params=params,
        )

    handler_response = await dispatcher.dispatch(
        endpoint_path=endpoint_path,
        query_params=query_params,
        response_json=response_json,
        chain_id=chain_id,
        base_url=base_url,
        ctx=ctx,
        method=method,
        json_body=json_body,
    )
    if handler_response is not None:
        await report_and_log_progress(
            ctx,
            progress=2.0,
            total=2.0,
            message="Successfully fetched data.",
        )
        return handler_response

    pagination = None
    if method == "GET":
        next_page_params = response_json.get("next_page_params")
        if next_page_params:
            next_cursor = encode_cursor(next_page_params)
            next_call_params = {
                "chain_id": chain_id,
                "endpoint_path": endpoint_path,
                "cursor": next_cursor,
            }
            if query_params:
                next_call_params["query_params"] = query_params
            pagination = PaginationInfo(next_call=NextCallInfo(tool_name="direct_api_call", params=next_call_params))

    await report_and_log_progress(
        ctx,
        progress=2.0,
        total=2.0,
        message="Successfully fetched data.",
    )

    response_str = json.dumps(response_json)
    response_len = len(response_str)
    response_limit = config.direct_api_response_size_limit
    if response_len > response_limit:
        is_rest_call = getattr(ctx, "call_source", None) == "rest"
        if is_rest_call:
            request_context = getattr(ctx, "request_context", None)
            request = getattr(request_context, "request", None) if request_context else None
            headers = getattr(request, "headers", {}) if request is not None else {}
            if not (
                isinstance(headers.get(ALLOW_LARGE_RESPONSE_HEADER), str)
                and headers.get(ALLOW_LARGE_RESPONSE_HEADER).lower() == "true"
            ):
                message = (
                    f"Response size ({response_len} chars) exceeds the safety limit. "
                    f"To bypass, add the header '{ALLOW_LARGE_RESPONSE_HEADER}: true' to your request."
                )
                raise ResponseTooLargeError(message)
        else:
            message = (
                f"Response size ({response_len} chars) exceeds the safety limit of {response_limit}. "
                "Use query parameters to filter the result or try a more specific tool."
            )
            raise ResponseTooLargeError(message)

    data = DirectApiData.model_validate(response_json)

    if pagination is not None and isinstance(response_json, dict) and isinstance(response_json.get("items"), list):
        content_text = (
            f"Called {endpoint_path} on chain {chain_id}. Returned {len(response_json.get('items', []))} items. "
            "More pages available."
        )
    elif isinstance(response_json, dict):
        content_text = (
            f"Called {endpoint_path} on chain {chain_id}. Response type: object with {len(response_json)} keys."
        )
    elif isinstance(response_json, list):
        content_text = f"Called {endpoint_path} on chain {chain_id}. Response type: list of {len(response_json)} items."
    else:
        content_text = f"Called {endpoint_path} on chain {chain_id}. Response type: {type(response_json).__name__}."

    return build_tool_response(data=data, pagination=pagination, content_text=content_text)
