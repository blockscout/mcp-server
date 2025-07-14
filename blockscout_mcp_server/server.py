from typing import Annotated

import typer
import uvicorn
from mcp.server.fastmcp import FastMCP

from blockscout_mcp_server.constants import (
    BLOCK_TIME_ESTIMATION_RULES,
    CHAIN_ID_RULES,
    EFFICIENCY_OPTIMIZATION_RULES,
    ERROR_HANDLING_RULES,
    PAGINATION_RULES,
    RECOMMENDED_CHAINS,
    SERVER_NAME,
    SERVER_VERSION,
    TIME_BASED_QUERY_RULES,
)
from blockscout_mcp_server.tools.address_tools import (
    get_address_info,
    get_address_logs,
    get_tokens_by_address,
    nft_tokens_by_address,
)
from blockscout_mcp_server.tools.block_tools import get_block_info, get_latest_block
from blockscout_mcp_server.tools.chains_tools import get_chains_list
from blockscout_mcp_server.tools.contract_tools import get_contract_abi
from blockscout_mcp_server.tools.ens_tools import get_address_by_ens_name
from blockscout_mcp_server.tools.get_instructions import __get_instructions__
from blockscout_mcp_server.tools.search_tools import lookup_token_by_symbol
from blockscout_mcp_server.tools.transaction_tools import (
    get_token_transfers_by_address,
    get_transaction_info,
    get_transaction_logs,
    get_transactions_by_address,
    transaction_summary,
)

# Compose the instructions string for the MCP server constructor
chains_list_str = "\n".join([f"  * {chain['name']}: {chain['chain_id']}" for chain in RECOMMENDED_CHAINS])
composed_instructions = f"""
Blockscout MCP server version: {SERVER_VERSION}

<error_handling_rules>
{ERROR_HANDLING_RULES.strip()}
</error_handling_rules>

<chain_id_guidance>
<rules>
{CHAIN_ID_RULES.strip()}
</rules>
<recommended_chains>
Here is the list of IDs of most popular chains:
{chains_list_str}
</recommended_chains>
</chain_id_guidance>

<pagination_rules>
{PAGINATION_RULES.strip()}
</pagination_rules>

<time_based_query_rules>
{TIME_BASED_QUERY_RULES.strip()}
</time_based_query_rules>

<block_time_estimation_rules>
{BLOCK_TIME_ESTIMATION_RULES.strip()}
</block_time_estimation_rules>

<efficiency_optimization_rules>
{EFFICIENCY_OPTIMIZATION_RULES.strip()}
</efficiency_optimization_rules>
"""

mcp = FastMCP(name=SERVER_NAME, instructions=composed_instructions)

# Register the tools
# The name of each tool will be its function name
# The description will be taken from the function's docstring
# The arguments (name, type, description) will be inferred from type hints
# TODO: structured_output is disabled for all tools so far to preserve the LLM context since it adds to the `list/tools` response ~20K tokens.  # noqa: E501
mcp.tool(structured_output=False)(__get_instructions__)
mcp.tool(structured_output=False)(get_block_info)
mcp.tool(structured_output=False)(get_latest_block)
mcp.tool(structured_output=False)(get_address_by_ens_name)
mcp.tool(structured_output=False)(get_transactions_by_address)
mcp.tool(structured_output=False)(get_token_transfers_by_address)
mcp.tool(structured_output=False)(lookup_token_by_symbol)
mcp.tool(structured_output=False)(get_contract_abi)
mcp.tool(structured_output=False)(get_address_info)
mcp.tool(structured_output=False)(get_tokens_by_address)
mcp.tool(structured_output=False)(transaction_summary)
mcp.tool(structured_output=False)(nft_tokens_by_address)
mcp.tool(structured_output=False)(get_transaction_info)
mcp.tool(structured_output=False)(get_transaction_logs)
mcp.tool(structured_output=False)(get_address_logs)
mcp.tool(structured_output=False)(get_chains_list)

# Create a Typer application for our CLI
cli_app = typer.Typer()


@cli_app.command()
def main_command(
    http: Annotated[bool, typer.Option("--http", help="Run server in HTTP Streamable mode.")] = False,
    rest: Annotated[bool, typer.Option("--rest", help="Enable REST API (requires --http).")] = False,
    http_host: Annotated[
        str, typer.Option("--http-host", help="Host for HTTP server if --http is used.")
    ] = "127.0.0.1",
    http_port: Annotated[int, typer.Option("--http-port", help="Port for HTTP server if --http is used.")] = 8000,
):
    """Blockscout MCP Server. Runs in stdio mode by default.
    Use --http to enable HTTP Streamable mode.
    Use --http and --rest to enable the REST API.
    """
    if http:
        if rest:
            print(f"Starting Blockscout MCP Server with REST API on {http_host}:{http_port}")
            from blockscout_mcp_server.api.routes import register_api_routes

            register_api_routes(mcp)
        else:
            print(f"Starting Blockscout MCP Server in HTTP Streamable mode on {http_host}:{http_port}")

        # Configure the existing 'mcp' instance for stateless HTTP with JSON responses
        mcp.settings.stateless_http = True  # Enable stateless mode
        mcp.settings.json_response = True  # Enable JSON responses instead of SSE for tool calls
        asgi_app = mcp.streamable_http_app()
        uvicorn.run(asgi_app, host=http_host, port=http_port)
    elif rest:
        raise typer.BadParameter("The --rest flag can only be used with the --http flag.")
    else:
        # This is the original behavior: run in stdio mode
        mcp.run()


def run_server_cli():
    """This function will be called by the script defined in pyproject.toml"""
    cli_app()


if __name__ == "__main__":
    # This allows running the server directly with `python blockscout_mcp_server/server.py`
    run_server_cli()
