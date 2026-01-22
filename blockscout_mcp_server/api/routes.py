"""Module for registering all REST API routes with the FastMCP server."""

import json
import pathlib
from collections.abc import Callable
from typing import Any

from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, PlainTextResponse, Response

from blockscout_mcp_server import analytics
from blockscout_mcp_server.analytics import track_event
from blockscout_mcp_server.api.dependencies import get_mock_context
from blockscout_mcp_server.api.helpers import (
    create_deprecation_response,
    extract_and_validate_params,
    handle_rest_errors,
)
from blockscout_mcp_server.models import ToolUsageReport
from blockscout_mcp_server.tools.address.get_address_info import get_address_info
from blockscout_mcp_server.tools.address.get_tokens_by_address import get_tokens_by_address
from blockscout_mcp_server.tools.address.nft_tokens_by_address import nft_tokens_by_address
from blockscout_mcp_server.tools.block.get_block_info import get_block_info
from blockscout_mcp_server.tools.block.get_block_number import get_block_number
from blockscout_mcp_server.tools.chains.get_chains_list import get_chains_list
from blockscout_mcp_server.tools.contract.get_contract_abi import get_contract_abi
from blockscout_mcp_server.tools.contract.inspect_contract_code import inspect_contract_code
from blockscout_mcp_server.tools.contract.read_contract import read_contract
from blockscout_mcp_server.tools.direct_api.direct_api_call import direct_api_call
from blockscout_mcp_server.tools.ens.get_address_by_ens_name import get_address_by_ens_name
from blockscout_mcp_server.tools.initialization.unlock_blockchain_analysis import (
    __unlock_blockchain_analysis__,
)
from blockscout_mcp_server.tools.search.lookup_token_by_symbol import lookup_token_by_symbol
from blockscout_mcp_server.tools.transaction.get_token_transfers_by_address import (
    get_token_transfers_by_address,
)
from blockscout_mcp_server.tools.transaction.get_transaction_info import get_transaction_info
from blockscout_mcp_server.tools.transaction.get_transactions_by_address import (
    get_transactions_by_address,
)
from blockscout_mcp_server.tools.transaction.transaction_summary import transaction_summary

# Define paths to static files relative to this file's location
BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"
LLMS_TXT_PATH = BASE_DIR / "llms.txt"

# Preload static content at module import
try:
    INDEX_HTML_CONTENT = (TEMPLATES_DIR / "index.html").read_text(encoding="utf-8")
except OSError as exc:  # pragma: no cover - test will not cover missing file
    INDEX_HTML_CONTENT = None
    print(f"Warning: Failed to preload landing page content: {exc}")

try:
    LLMS_TXT_CONTENT = LLMS_TXT_PATH.read_text(encoding="utf-8")
except OSError as exc:  # pragma: no cover - test will not cover missing file
    LLMS_TXT_CONTENT = None
    print(f"Warning: Failed to preload llms.txt content: {exc}")


async def health_check(_: Request) -> Response:
    """Return a simple health status."""
    return JSONResponse({"status": "ok"})


async def serve_llms_txt(_: Request) -> Response:
    """Serve the llms.txt file."""
    if LLMS_TXT_CONTENT is None:
        message = "llms.txt content is not available."
        return PlainTextResponse(message, status_code=500)
    return PlainTextResponse(LLMS_TXT_CONTENT)


async def main_page(request: Request) -> Response:
    """Serve the main landing page."""
    track_event(request, "PageView", {"path": "/"})
    if INDEX_HTML_CONTENT is None:
        message = "Landing page content is not available."
        return PlainTextResponse(message, status_code=500)
    return HTMLResponse(INDEX_HTML_CONTENT)


async def report_tool_usage(request: Request) -> Response:
    """Receive and process an anonymous tool usage report from a self-hosted server."""
    try:
        payload = await request.json()
        report = ToolUsageReport.model_validate(payload)
    except Exception:
        return Response(status_code=422)

    user_agent = request.headers.get("user-agent")
    if not user_agent:
        return Response(status_code=400)

    ip = analytics._extract_ip_from_request(request)
    analytics.track_community_usage(report=report, ip=ip, user_agent=user_agent)
    return Response(status_code=202)


@handle_rest_errors
async def get_instructions_rest(request: Request) -> Response:
    """REST wrapper for the __unlock_blockchain_analysis__ tool."""
    # NOTE: This endpoint exists solely for backward compatibility. It duplicates
    # ``unlock_blockchain_analysis_rest`` instead of delegating to it because the
    # old route will be removed soon and another wrapper would add needless
    # indirection.
    tool_response = await __unlock_blockchain_analysis__(ctx=get_mock_context(request))
    return JSONResponse(tool_response.model_dump())


@handle_rest_errors
async def unlock_blockchain_analysis_rest(request: Request) -> Response:
    """REST wrapper for the __unlock_blockchain_analysis__ tool."""
    tool_response = await __unlock_blockchain_analysis__(ctx=get_mock_context(request))
    return JSONResponse(tool_response.model_dump())


@handle_rest_errors
async def get_block_info_rest(request: Request) -> Response:
    """REST wrapper for the get_block_info tool."""
    params = extract_and_validate_params(
        request,
        required=["chain_id", "number_or_hash"],
        optional=["include_transactions"],
    )
    tool_response = await get_block_info(**params, ctx=get_mock_context(request))
    return JSONResponse(tool_response.model_dump())


@handle_rest_errors
async def get_latest_block_rest(request: Request) -> Response:
    """REST wrapper for the legacy get_latest_block tool."""
    params = extract_and_validate_params(request, required=["chain_id"], optional=[])
    tool_response = await get_block_number(chain_id=params["chain_id"], datetime=None, ctx=get_mock_context(request))
    return JSONResponse(tool_response.model_dump())


@handle_rest_errors
async def get_block_number_rest(request: Request) -> Response:
    """REST wrapper for the get_block_number tool."""
    params = extract_and_validate_params(request, required=["chain_id"], optional=["datetime"])
    tool_response = await get_block_number(**params, ctx=get_mock_context(request))
    return JSONResponse(tool_response.model_dump())


@handle_rest_errors
async def get_address_by_ens_name_rest(request: Request) -> Response:
    """REST wrapper for the get_address_by_ens_name tool."""
    params = extract_and_validate_params(request, required=["name"], optional=[])
    tool_response = await get_address_by_ens_name(**params, ctx=get_mock_context(request))
    return JSONResponse(tool_response.model_dump())


@handle_rest_errors
async def get_transactions_by_address_rest(request: Request) -> Response:
    """REST wrapper for the get_transactions_by_address tool."""
    params = extract_and_validate_params(
        request,
        required=["chain_id", "address", "age_from"],
        optional=["age_to", "methods", "cursor"],
    )
    tool_response = await get_transactions_by_address(**params, ctx=get_mock_context(request))
    return JSONResponse(tool_response.model_dump())


@handle_rest_errors
async def get_token_transfers_by_address_rest(request: Request) -> Response:
    """REST wrapper for the get_token_transfers_by_address tool."""
    params = extract_and_validate_params(
        request,
        required=["chain_id", "address", "age_from"],
        optional=["age_to", "token", "cursor"],
    )
    tool_response = await get_token_transfers_by_address(**params, ctx=get_mock_context(request))
    return JSONResponse(tool_response.model_dump())


@handle_rest_errors
async def lookup_token_by_symbol_rest(request: Request) -> Response:
    """REST wrapper for the lookup_token_by_symbol tool."""
    params = extract_and_validate_params(request, required=["chain_id", "symbol"], optional=[])
    tool_response = await lookup_token_by_symbol(**params, ctx=get_mock_context(request))
    return JSONResponse(tool_response.model_dump())


@handle_rest_errors
async def get_contract_abi_rest(request: Request) -> Response:
    """REST wrapper for the get_contract_abi tool."""
    params = extract_and_validate_params(request, required=["chain_id", "address"], optional=[])
    tool_response = await get_contract_abi(**params, ctx=get_mock_context(request))
    return JSONResponse(tool_response.model_dump())


@handle_rest_errors
async def inspect_contract_code_rest(request: Request) -> Response:
    """REST wrapper for the inspect_contract_code tool."""
    params = extract_and_validate_params(request, required=["chain_id", "address"], optional=["file_name"])
    tool_response = await inspect_contract_code(**params, ctx=get_mock_context(request))
    return JSONResponse(tool_response.model_dump())


@handle_rest_errors
async def read_contract_rest(request: Request) -> Response:
    """REST wrapper for the read_contract tool."""
    params = extract_and_validate_params(
        request,
        required=["chain_id", "address", "abi", "function_name"],
        optional=["args", "block"],
    )
    try:
        params["abi"] = json.loads(params["abi"])
    except json.JSONDecodeError as e:
        raise ValueError("Invalid JSON for 'abi'") from e
    if not isinstance(params["abi"], dict):
        raise ValueError("'abi' must be a JSON object")
    # args parameter is now passed as a JSON string directly to the tool
    if "block" in params and params["block"].isdigit():
        params["block"] = int(params["block"])
    tool_response = await read_contract(**params, ctx=get_mock_context(request))
    return JSONResponse(tool_response.model_dump())


@handle_rest_errors
async def get_address_info_rest(request: Request) -> Response:
    """REST wrapper for the get_address_info tool."""
    params = extract_and_validate_params(request, required=["chain_id", "address"], optional=[])
    tool_response = await get_address_info(**params, ctx=get_mock_context(request))
    return JSONResponse(tool_response.model_dump())


@handle_rest_errors
async def get_tokens_by_address_rest(request: Request) -> Response:
    """REST wrapper for the get_tokens_by_address tool."""
    params = extract_and_validate_params(request, required=["chain_id", "address"], optional=["cursor"])
    tool_response = await get_tokens_by_address(**params, ctx=get_mock_context(request))
    return JSONResponse(tool_response.model_dump())


@handle_rest_errors
async def transaction_summary_rest(request: Request) -> Response:
    """REST wrapper for the transaction_summary tool."""
    params = extract_and_validate_params(request, required=["chain_id", "transaction_hash"], optional=[])
    tool_response = await transaction_summary(**params, ctx=get_mock_context(request))
    return JSONResponse(tool_response.model_dump())


@handle_rest_errors
async def nft_tokens_by_address_rest(request: Request) -> Response:
    """REST wrapper for the nft_tokens_by_address tool."""
    params = extract_and_validate_params(request, required=["chain_id", "address"], optional=["cursor"])
    tool_response = await nft_tokens_by_address(**params, ctx=get_mock_context(request))
    return JSONResponse(tool_response.model_dump())


@handle_rest_errors
async def get_transaction_info_rest(request: Request) -> Response:
    """REST wrapper for the get_transaction_info tool."""
    params = extract_and_validate_params(
        request,
        required=["chain_id", "transaction_hash"],
        optional=["include_raw_input"],
    )
    tool_response = await get_transaction_info(**params, ctx=get_mock_context(request))
    return JSONResponse(tool_response.model_dump())


@handle_rest_errors
async def get_address_logs_rest(request: Request) -> Response:
    """REST wrapper for the get_address_logs tool. This endpoint is deprecated."""
    deprecation_notes = [
        "This endpoint is deprecated and will be removed in a future version.",
        (
            "Please use the recommended workflow: first, call `get_transactions_by_address` "
            "(which supports time filtering), and then use `direct_api_call` with "
            "`endpoint_path='/api/v2/transactions/{transaction_hash}/logs'` for each relevant transaction hash."
        ),
    ]
    return create_deprecation_response(deprecation_notes)


@handle_rest_errors
async def get_transaction_logs_rest(request: Request) -> Response:
    """REST wrapper for the get_transaction_logs tool. This endpoint is deprecated."""
    deprecation_notes = [
        "This endpoint is deprecated and will be removed in a future version.",
        (
            "Please use `direct_api_call` with "
            "`endpoint_path='/api/v2/transactions/{transaction_hash}/logs'` to retrieve logs for a transaction."
        ),
    ]
    return create_deprecation_response(deprecation_notes)


@handle_rest_errors
async def get_chains_list_rest(request: Request) -> Response:
    """REST wrapper for the get_chains_list tool."""
    tool_response = await get_chains_list(ctx=get_mock_context(request))
    return JSONResponse(tool_response.model_dump())


@handle_rest_errors
async def direct_api_call_rest(request: Request) -> Response:
    """REST wrapper for the direct_api_call tool."""
    params = extract_and_validate_params(request, required=["chain_id", "endpoint_path"], optional=["cursor"])
    extra: dict[str, str] = {}
    for key, value in request.query_params.items():
        if key in {"chain_id", "endpoint_path", "cursor"}:
            continue
        if key.startswith("query_params[") and key.endswith("]"):
            extra[key[13:-1]] = value
        else:
            extra[key] = value
    if extra:
        params["query_params"] = extra
    tool_response = await direct_api_call(**params, ctx=get_mock_context(request))
    return JSONResponse(tool_response.model_dump())


def _add_v1_tool_route(mcp: FastMCP, path: str, handler: Callable[..., Any]) -> None:
    """Register a tool route under the /v1/ prefix."""
    mcp.custom_route(f"/v1{path}", methods=["GET"])(handler)


def register_api_routes(mcp: FastMCP) -> None:
    """Registers all REST API routes."""

    async def list_tools_rest(_: Request) -> Response:
        """Return a list of all available tools and their schemas."""
        # The FastMCP instance is needed to query registered tools. Defining this
        # handler inside ``register_api_routes`` allows it to close over the
        # specific ``mcp`` object instead of accessing ``request.app.state``.
        # This reduces coupling to the underlying ASGI app and makes unit tests
        # simpler because no custom state injection is required.
        tools_list = await mcp.list_tools()
        return JSONResponse([tool.model_dump() for tool in tools_list])

    # These routes are not part of the OpenAPI schema for tools.
    mcp.custom_route("/health", methods=["GET"], include_in_schema=False)(health_check)
    mcp.custom_route("/llms.txt", methods=["GET"], include_in_schema=False)(serve_llms_txt)
    mcp.custom_route("/", methods=["GET"], include_in_schema=False)(main_page)
    mcp.custom_route("/v1/report_tool_usage", methods=["POST"])(report_tool_usage)

    # Version 1 of the REST API
    _add_v1_tool_route(mcp, "/tools", list_tools_rest)
    _add_v1_tool_route(mcp, "/get_instructions", get_instructions_rest)
    _add_v1_tool_route(mcp, "/unlock_blockchain_analysis", unlock_blockchain_analysis_rest)
    _add_v1_tool_route(mcp, "/get_block_info", get_block_info_rest)
    _add_v1_tool_route(mcp, "/get_block_number", get_block_number_rest)
    _add_v1_tool_route(mcp, "/get_latest_block", get_latest_block_rest)
    _add_v1_tool_route(mcp, "/get_address_by_ens_name", get_address_by_ens_name_rest)
    _add_v1_tool_route(mcp, "/get_transactions_by_address", get_transactions_by_address_rest)
    _add_v1_tool_route(mcp, "/get_token_transfers_by_address", get_token_transfers_by_address_rest)
    _add_v1_tool_route(mcp, "/lookup_token_by_symbol", lookup_token_by_symbol_rest)
    _add_v1_tool_route(mcp, "/get_contract_abi", get_contract_abi_rest)
    _add_v1_tool_route(mcp, "/inspect_contract_code", inspect_contract_code_rest)
    _add_v1_tool_route(mcp, "/read_contract", read_contract_rest)
    _add_v1_tool_route(mcp, "/get_address_info", get_address_info_rest)
    _add_v1_tool_route(mcp, "/get_tokens_by_address", get_tokens_by_address_rest)
    _add_v1_tool_route(mcp, "/transaction_summary", transaction_summary_rest)
    _add_v1_tool_route(mcp, "/nft_tokens_by_address", nft_tokens_by_address_rest)
    _add_v1_tool_route(mcp, "/get_transaction_info", get_transaction_info_rest)
    _add_v1_tool_route(mcp, "/get_address_logs", get_address_logs_rest)
    _add_v1_tool_route(mcp, "/get_transaction_logs", get_transaction_logs_rest)
    _add_v1_tool_route(mcp, "/get_chains_list", get_chains_list_rest)
    _add_v1_tool_route(mcp, "/direct_api_call", direct_api_call_rest)
