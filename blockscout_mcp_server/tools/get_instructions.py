from mcp.server.fastmcp import Context

from blockscout_mcp_server.constants import (
    GENERAL_RULES,
    RECOMMENDED_CHAINS,
    SERVER_VERSION,
)
from blockscout_mcp_server.models import (
    ChainInfo,
    InstructionsData,
    ToolResponse,
)
from blockscout_mcp_server.tools.common import build_tool_response, report_and_log_progress


# It is very important to keep the tool description in such form to force the LLM to call this tool first
# before calling any other tool. Altering of the description could provide opportunity to LLM to skip this tool.
async def __get_instructions__(ctx: Context) -> ToolResponse[InstructionsData]:
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

    # Construct the structured data payload
    instructions_data = InstructionsData(
        version=SERVER_VERSION,
        general_rules=GENERAL_RULES,
        recommended_chains=[ChainInfo(**chain) for chain in RECOMMENDED_CHAINS],
    )

    # Report completion
    await report_and_log_progress(
        ctx,
        progress=1.0,
        total=1.0,
        message="Server instructions ready.",
    )

    return build_tool_response(data=instructions_data)
