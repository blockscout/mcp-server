from mcp.server.fastmcp import Context

from blockscout_mcp_server.constants import (
    BINARY_SEARCH_RULES,
    CHAIN_ID_RULES,
    DATA_ORDERING_AND_RESUMPTION_RULES,
    DIRECT_API_CALL_ENDPOINT_LIST,
    DIRECT_API_CALL_RULES,
    ERROR_HANDLING_RULES,
    FUNDS_MOVEMENT_RULES,
    PAGINATION_RULES,
    PORTFOLIO_ANALYSIS_RULES,
    RECOMMENDED_CHAINS,
    SERVER_VERSION,
    TIME_BASED_QUERY_RULES,
)
from blockscout_mcp_server.models import (
    ChainIdGuidance,
    ChainInfo,
    DirectApiCommonGroup,
    DirectApiEndpoint,
    DirectApiEndpointList,
    DirectApiSpecificGroup,
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

    COMPREHENSIVE DATA SOURCES: Provides an extensive catalog of specialized
    blockchain endpoints to unlock sophisticated, multi-dimensional blockchain
    investigations across all supported networks.
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

    common_groups = []
    for group_data in DIRECT_API_CALL_ENDPOINT_LIST["common"]:
        endpoints = [DirectApiEndpoint(**endpoint) for endpoint in group_data["endpoints"]]
        common_groups.append(DirectApiCommonGroup(group=group_data["group"], endpoints=endpoints))

    specific_groups = []
    for group_data in DIRECT_API_CALL_ENDPOINT_LIST["specific"]:
        endpoints = [DirectApiEndpoint(**endpoint) for endpoint in group_data["endpoints"]]
        specific_groups.append(DirectApiSpecificGroup(chain_family=group_data["chain_family"], endpoints=endpoints))

    direct_api_endpoints = DirectApiEndpointList(common=common_groups, specific=specific_groups)

    instructions_data = InstructionsData(
        version=SERVER_VERSION,
        error_handling_rules=ERROR_HANDLING_RULES,
        chain_id_guidance=chain_id_guidance,
        pagination_rules=PAGINATION_RULES,
        time_based_query_rules=TIME_BASED_QUERY_RULES,
        binary_search_rules=BINARY_SEARCH_RULES,
        portfolio_analysis_rules=PORTFOLIO_ANALYSIS_RULES,
        funds_movement_rules=FUNDS_MOVEMENT_RULES,
        data_ordering_and_resumption_rules=DATA_ORDERING_AND_RESUMPTION_RULES,
        direct_api_call_rules=DIRECT_API_CALL_RULES,
        direct_api_endpoints=direct_api_endpoints,
    )

    # Report completion
    await report_and_log_progress(
        ctx,
        progress=1.0,
        total=1.0,
        message="Server instructions ready.",
    )

    return build_tool_response(data=instructions_data)
