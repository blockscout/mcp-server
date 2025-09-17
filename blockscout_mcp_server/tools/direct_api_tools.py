import re
from typing import Annotated, Any

from mcp.server.fastmcp import Context
from pydantic import Field

from blockscout_mcp_server.models import DirectApiData, NextCallInfo, PaginationInfo, ToolResponse
from blockscout_mcp_server.tools.address_tools import get_address_logs
from blockscout_mcp_server.tools.common import (
    apply_cursor_to_params,
    build_tool_response,
    encode_cursor,
    get_blockscout_base_url,
    make_blockscout_request,
    report_and_log_progress,
)
from blockscout_mcp_server.tools.decorators import log_tool_invocation


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
) -> ToolResponse[DirectApiData]:
    """Call a raw Blockscout API endpoint for advanced or chain-specific data.

    Do not include query strings in ``endpoint_path``; pass all query parameters via
    ``query_params`` to avoid double-encoding.

    **SUPPORTS PAGINATION**: If response includes 'pagination' field,
    use the provided next_call to get additional pages.
    """
    logs_match = re.match(r"^/api/v2/addresses/([^/]+)/logs$", endpoint_path)
    if logs_match:
        address = logs_match.group(1)
        return await get_address_logs(
            chain_id=chain_id,
            address=address,
            ctx=ctx,
            cursor=cursor,
        )

    await report_and_log_progress(
        ctx,
        progress=0.0,
        total=2.0,
        message=f"Resolving Blockscout URL for chain {chain_id}...",
    )
    base_url = await get_blockscout_base_url(chain_id)
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
