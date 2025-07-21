from mcp.server.fastmcp import Context

from blockscout_mcp_server.constants import (
    BLOCK_TIME_ESTIMATION_RULES,
    CHAIN_ID_RULES,
    EFFICIENCY_OPTIMIZATION_RULES,
    ERROR_HANDLING_RULES,
    PAGINATION_RULES,
    RECOMMENDED_CHAINS,
    SERVER_VERSION,
    TIME_BASED_QUERY_RULES,
)
from blockscout_mcp_server.models import (
    ChainIdGuidance,
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
    """Unlocks access to other MCP tools.

    All tools remain locked with a "Session Not Initialized" error until this
    function is successfully called. Skipping this explicit initialization step
    will cause all subsequent tool calls to fail.

    MANDATORY FOR AI AGENTS: The returned instructions contain ESSENTIAL rules
    that MUST govern ALL blockchain data interactions. Failure to integrate these
    rules will result in incorrect data retrieval, tool failures and invalid
    responses. Always apply these guidelines when planning queries, processing
    responses or recommending blockchain actions.
    """
    # Report start of operation
    await report_and_log_progress(
        ctx,
        progress=0.0,
        total=1.0,
        message="Fetching server instructions...",
    )

    # Construct the structured data payload
    chain_id_guidance = ChainIdGuidance(
        rules=CHAIN_ID_RULES,
        recommended_chains=[ChainInfo(**chain) for chain in RECOMMENDED_CHAINS],
    )

    instructions_data = InstructionsData(
        version=SERVER_VERSION,
        error_handling_rules=ERROR_HANDLING_RULES,
        chain_id_guidance=chain_id_guidance,
        pagination_rules=PAGINATION_RULES,
        time_based_query_rules=TIME_BASED_QUERY_RULES,
        block_time_estimation_rules=BLOCK_TIME_ESTIMATION_RULES,
        efficiency_optimization_rules=EFFICIENCY_OPTIMIZATION_RULES,
    )

    # Report completion
    await report_and_log_progress(
        ctx,
        progress=1.0,
        total=1.0,
        message="Server instructions ready.",
    )

    return build_tool_response(data=instructions_data)
