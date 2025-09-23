from typing import Annotated, Any

from mcp.server.fastmcp import Context
from pydantic import Field

from blockscout_mcp_server.models import DirectApiData, NextCallInfo, PaginationInfo, ToolResponse
from blockscout_mcp_server.tools.common import (
    apply_cursor_to_params,
    build_tool_response,
    encode_cursor,
    get_blockscout_base_url,
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
) -> ToolResponse[Any]:
    """Call a raw Blockscout API endpoint for advanced or chain-specific data.

    Do not include query strings in ``endpoint_path``; pass all query parameters via
    ``query_params`` to avoid double-encoding.

    **SUPPORTS PAGINATION**: If response includes 'pagination' field,
    use the provided next_call to get additional pages.
    
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
    base_url = await get_blockscout_base_url(chain_id)
    if endpoint_path != "/" and endpoint_path.endswith("/"):
        endpoint_path = endpoint_path.rstrip("/")
    if "?" in endpoint_path:
        raise ValueError("Do not include query parameters in endpoint_path. Use query_params instead.")

    params = dict(query_params) if query_params else {}
    apply_cursor_to_params(cursor, params)

    await report_and_log_progress(
        ctx,
        progress=1.0,
        total=2.0,
        message="Fetching data from Blockscout API...",
    )
    response_json = await make_blockscout_request(base_url=base_url, api_path=endpoint_path, params=params)

    handler_response = await dispatcher.dispatch(
        endpoint_path=endpoint_path,
        query_params=query_params,
        response_json=response_json,
        chain_id=chain_id,
        base_url=base_url,
        ctx=ctx,
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

    data = DirectApiData.model_validate(response_json)
    return build_tool_response(data=data, pagination=pagination)
