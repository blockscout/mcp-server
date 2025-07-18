from datetime import datetime

from mcp.server.fastmcp import Context

from blockscout_mcp_server.constants import (
    BLOCK_TIME_ESTIMATION_RULES,
    CHAIN_ID_RULES,
    EFFICIENCY_OPTIMIZATION_RULES,
    ERROR_HANDLING_RULES,
    MODERN_PROTOCOL_VERSION_THRESHOLD,
    PAGINATION_RULES,
    RECOMMENDED_CHAINS,
    SERVER_VERSION,
    TIME_BASED_QUERY_RULES,
)
from blockscout_mcp_server.models import (
    ChainIdGuidance,
    ChainInfo,
    EmptyData,
    InstructionsData,
    ToolResponse,
)
from blockscout_mcp_server.tools.common import (
    build_tool_response,
    report_and_log_progress,
)
from blockscout_mcp_server.tools.decorators import log_tool_invocation


def is_modern_protocol_version(version: str | None) -> bool:
    """Return True if protocol version meets modern threshold."""
    if not isinstance(version, str) or not version:
        return False
    try:
        return datetime.fromisoformat(version) >= datetime.fromisoformat(MODERN_PROTOCOL_VERSION_THRESHOLD)
    except ValueError:
        return False


# It is very important to keep the tool description in such form to force the LLM to call this tool first
# before calling any other tool. Altering of the description could provide opportunity to LLM to skip this tool.
@log_tool_invocation
async def __get_instructions__(ctx: Context) -> ToolResponse[EmptyData]:
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

    # Determine client protocol version
    protocol_version = None
    try:
        if hasattr(ctx, "session") and ctx.session and ctx.session.client_params:
            protocol_version = ctx.session.client_params.protocolVersion
    except AttributeError:
        protocol_version = None

    if is_modern_protocol_version(protocol_version):
        instructions_content = instructions_data
    else:
        from blockscout_mcp_server.formatting.instruction_formatters import (
            format_all_instructions_as_xml_strings,
        )

        instructions_content = format_all_instructions_as_xml_strings()

    # Report completion
    await report_and_log_progress(
        ctx,
        progress=1.0,
        total=1.0,
        message="Server instructions ready.",
    )

    return build_tool_response(data=EmptyData(), instructions=instructions_content)
