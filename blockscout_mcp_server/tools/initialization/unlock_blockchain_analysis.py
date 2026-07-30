# SPDX-License-Identifier: LicenseRef-Blockscout
from mcp.server.fastmcp import Context

from blockscout_mcp_server.constants import (
    SERVER_VERSION,
    SKILL_RESOLUTION_RULE_TEXT,
)
from blockscout_mcp_server.models import (
    InstructionsData,
    ToolResponse,
)
from blockscout_mcp_server.pro_api_key_context import pro_api_credit_scope, pro_api_key_scope
from blockscout_mcp_server.resources import skill_resources
from blockscout_mcp_server.session_gate import gate_enabled, mint_token
from blockscout_mcp_server.tools.common import (
    build_tool_response,
    report_and_log_progress,
)
from blockscout_mcp_server.tools.decorators import log_tool_invocation


@log_tool_invocation
@pro_api_key_scope
@pro_api_credit_scope
async def __unlock_blockchain_analysis__(ctx: Context) -> ToolResponse[InstructionsData]:
    """Initializes a Blockscout MCP session: returns server reference data, the
    `blockscout-analysis` skill pointer, and the URI resolution rule. When the response
    payload includes a `session_id`, pass it with every subsequent tool call. Call this
    tool exactly once per session, before any other tool, and reuse its payload for the
    rest of the session; do not call it again.
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
        skill_reference=skill_resources.skill_pointer_text(),
        skill_resolution_rule=SKILL_RESOLUTION_RULE_TEXT,
    )

    content_text = (
        f"Session initialized (server v{SERVER_VERSION}). "
        "Consult the `blockscout-analysis` skill referenced in the payload before invoking any other tool."
    )

    if gate_enabled():
        # Lazy creation: minting writes no store row, so an identifier that is never
        # used leaves nothing behind. Unlock stays a pure function.
        instructions_data.session_id = mint_token()
        content_text = (
            f"Session initialized (server v{SERVER_VERSION}). Consult the `blockscout-analysis` skill "
            "referenced in the payload before invoking any other tool. Your `session_id` is in the "
            "payload — pass it with every subsequent tool call. A session is this entire conversation, "
            "including all tool loops and sub-agents; reconnections and context compaction do not start "
            "a new one. Do not initialize this session again."
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
        content_text=content_text,
    )
