"""Module for registering all REST API routes with the FastMCP server."""

import json
import pathlib
from collections.abc import Callable
from typing import Any

from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, PlainTextResponse, Response

from blockscout_mcp_server.api.dependencies import get_mock_context
from blockscout_mcp_server.api.helpers import (
    create_deprecation_response,
    extract_and_validate_params,
    handle_rest_errors,
)
from blockscout_mcp_server.tools.address_tools import (
    get_address_info,
    get_tokens_by_address,
    nft_tokens_by_address,
)
from blockscout_mcp_server.tools.block_tools import get_block_info, get_latest_block
from blockscout_mcp_server.tools.chains_tools import get_chains_list
from blockscout_mcp_server.tools.contract_tools import get_contract_abi, read_contract
from blockscout_mcp_server.tools.ens_tools import get_address_by_ens_name
from blockscout_mcp_server.tools.initialization_tools import __unlock_blockchain_analysis__
from blockscout_mcp_server.tools.search_tools import lookup_token_by_symbol
from blockscout_mcp_server.tools.transaction_tools import (
    get_token_transfers_by_address,
    get_transaction_info,
    get_transaction_logs,
    get_transactions_by_address,
    transaction_summary,
)

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


async def main_page(_: Request) -> Response:
    """Serve the main landing page."""
    if INDEX_HTML_CONTENT is None:
        message = "Landing page content is not available."
        return PlainTextResponse(message, status_code=500)
    return HTMLResponse(INDEX_HTML_CONTENT)


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
    """REST wrapper for the get_latest_block tool."""
    params = extract_and_validate_params(request, required=["chain_id"], optional=[])
    tool_response = await get_latest_block(**params, ctx=get_mock_context(request))
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
        required=["chain_id", "address"],
        optional=["age_from", "age_to", "methods", "cursor"],
    )
    tool_response = await get_transactions_by_address(**params, ctx=get_mock_context(request))
    return JSONResponse(tool_response.model_dump())


@handle_rest_errors
async def get_token_transfers_by_address_rest(request: Request) -> Response:
    """REST wrapper for the get_token_transfers_by_address tool."""
    params = extract_and_validate_params(
        request,
        required=["chain_id", "address"],
        optional=["age_from", "age_to", "token", "cursor"],
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
    if "args" in params:
        try:
            params["args"] = json.loads(params["args"])
        except json.JSONDecodeError as e:
            raise ValueError("Invalid JSON for 'args'") from e
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
async def get_transaction_logs_rest(request: Request) -> Response:
    """REST wrapper for the get_transaction_logs tool."""
    params = extract_and_validate_params(request, required=["chain_id", "transaction_hash"], optional=["cursor"])
    tool_response = await get_transaction_logs(**params, ctx=get_mock_context(request))
    return JSONResponse(tool_response.model_dump())


@handle_rest_errors
async def get_address_logs_rest(request: Request) -> Response:
    """REST wrapper for the get_address_logs tool. This endpoint is deprecated."""
    return create_deprecation_response()


@handle_rest_errors
async def get_chains_list_rest(request: Request) -> Response:
    """REST wrapper for the get_chains_list tool."""
    tool_response = await get_chains_list(ctx=get_mock_context(request))
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

    # Version 1 of the REST API
    _add_v1_tool_route(mcp, "/tools", list_tools_rest)
    _add_v1_tool_route(mcp, "/get_instructions", get_instructions_rest)
    _add_v1_tool_route(mcp, "/unlock_blockchain_analysis", unlock_blockchain_analysis_rest)
    _add_v1_tool_route(mcp, "/get_block_info", get_block_info_rest)
    _add_v1_tool_route(mcp, "/get_latest_block", get_latest_block_rest)
    _add_v1_tool_route(mcp, "/get_address_by_ens_name", get_address_by_ens_name_rest)
    _add_v1_tool_route(mcp, "/get_transactions_by_address", get_transactions_by_address_rest)
    _add_v1_tool_route(mcp, "/get_token_transfers_by_address", get_token_transfers_by_address_rest)
    _add_v1_tool_route(mcp, "/lookup_token_by_symbol", lookup_token_by_symbol_rest)
    _add_v1_tool_route(mcp, "/get_contract_abi", get_contract_abi_rest)
    _add_v1_tool_route(mcp, "/read_contract", read_contract_rest)
    _add_v1_tool_route(mcp, "/get_address_info", get_address_info_rest)
    _add_v1_tool_route(mcp, "/get_tokens_by_address", get_tokens_by_address_rest)
    _add_v1_tool_route(mcp, "/transaction_summary", transaction_summary_rest)
    _add_v1_tool_route(mcp, "/nft_tokens_by_address", nft_tokens_by_address_rest)
    _add_v1_tool_route(mcp, "/get_transaction_info", get_transaction_info_rest)
    _add_v1_tool_route(mcp, "/get_transaction_logs", get_transaction_logs_rest)
    _add_v1_tool_route(mcp, "/get_address_logs", get_address_logs_rest)
    _add_v1_tool_route(mcp, "/get_chains_list", get_chains_list_rest)
