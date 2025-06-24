from mcp.server.fastmcp import Context

from blockscout_mcp_server.constants import SERVER_INSTRUCTIONS
from blockscout_mcp_server.tools.common import report_and_log_progress


async def __get_instructions__(ctx: Context) -> str:
    """
    This tool MUST be called BEFORE any other tool.
    Without calling it, the MCP server will not work as expected.
    It MUST be called once in a session.
    """
    # Report start of operation
    await report_and_log_progress(
        ctx,
        progress=0.0,
        total=1.0,
        message="Fetching server instructions...",
    )

    # SERVER_INSTRUCTIONS is a constant, so this is immediate
    await report_and_log_progress(
        ctx,
        progress=1.0,
        total=1.0,
        message="Server instructions ready.",
    )

    return SERVER_INSTRUCTIONS
