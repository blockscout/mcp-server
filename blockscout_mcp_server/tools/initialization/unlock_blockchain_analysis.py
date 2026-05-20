# SPDX-License-Identifier: LicenseRef-Blockscout
from mcp.server.fastmcp import Context

from blockscout_mcp_server.constants import (
    RECOMMENDED_CHAINS,
    SERVER_VERSION,
    SKILL_POINTER_TEXT,
    SKILL_RESOLUTION_RULE_TEXT,
)
from blockscout_mcp_server.models import (
    ChainInfo,
    InstructionsData,
    ToolResponse,
)
from blockscout_mcp_server.tools.common import (
    build_tool_response,
    report_and_log_progress,
)
from blockscout_mcp_server.tools.decorators import log_tool_invocation


# It is very important to keep the tool description in such form to force the LLM to call this tool first
# before calling any other tool. Altering of the description could provide opportunity to LLM to skip this tool.
@log_tool_invocation
async def __unlock_blockchain_analysis__(ctx: Context) -> ToolResponse[InstructionsData]:
    """Mandatory initialization step for any session against the Blockscout MCP server.

    Returns server reference data plus the `blockscout-analysis` skill pointer and URI
    resolution rule.

    MANDATORY FOR AI AGENTS: Call this tool first in every session. The returned payload
    identifies where the operating rules and analysis framework live and how to read
    referenced skill files before executing further tool calls.
    """
    # Report start of operation
    await report_and_log_progress(
        ctx,
        progress=0.0,
        total=1.0,
        message="Fetching server instructions...",
    )

    instructions_data = InstructionsData(
        version=SERVER_VERSION,
        recommended_chains=[ChainInfo(**chain) for chain in RECOMMENDED_CHAINS],
        skill_reference=SKILL_POINTER_TEXT,
        skill_resolution_rule=SKILL_RESOLUTION_RULE_TEXT,
    )

    # Report completion
    await report_and_log_progress(
        ctx,
        progress=1.0,
        total=1.0,
        message="Server instructions ready.",
    )

    return build_tool_response(
        data=instructions_data,
        content_text=(
            f"Session initialized (server v{SERVER_VERSION}). "
            "Consult the `blockscout-analysis` skill referenced in the payload before invoking any other tool."
        ),
    )
