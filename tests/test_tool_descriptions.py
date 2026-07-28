# SPDX-License-Identifier: LicenseRef-Blockscout
"""
Schema-level regression tests for the client-visible MCP tools/list surface.

These tests assert on ``await server.mcp.list_tools()`` — the exact data a client
receives — for every tool touched in Phases 1–5 of issue #420.  They catch
botched parameter relocations, leaked "Use cases" / "Returns:" / placeholder
text, and missing chain-id hints that the per-tool __doc__ smoke tests would
miss because those tests never inspect inputSchema.properties[*].description.

No network calls or mock_ctx are needed: listing tools is a pure
registration-surface read.
"""

import re

import pytest

from blockscout_mcp_server import server
from blockscout_mcp_server.tools.search.lookup_token_by_symbol import TOKEN_RESULTS_LIMIT


@pytest.mark.asyncio
async def test_get_transactions_by_address_description_excludes_banned_phrases():
    """Description must not contain 'Use cases' or the execution-order instruction."""
    tools = {t.name: t for t in await server.mcp.list_tools()}
    tool = tools["get_transactions_by_address"]

    assert "Use cases" not in tool.description
    assert "internal_transaction_index" not in tool.description


@pytest.mark.asyncio
async def test_get_transactions_by_address_description_length_budget():
    """Client-visible description must stay within the Phase 1 exception budget (≤ 600 chars)."""
    tools = {t.name: t for t in await server.mcp.list_tools()}
    tool = tools["get_transactions_by_address"]

    assert len(tool.description.strip()) <= 600


@pytest.mark.asyncio
async def test_get_transactions_by_address_parameter_descriptions_carry_usage_cues():
    """age_from, age_to, and methods parameter descriptions must each carry their relocated usage cue."""
    tools = {t.name: t for t in await server.mcp.list_tools()}
    tool = tools["get_transactions_by_address"]
    properties = tool.inputSchema.get("properties", {})

    assert "age_from" in properties
    assert properties["age_from"]["description"]

    assert "age_to" in properties
    assert properties["age_to"]["description"]

    assert "methods" in properties
    assert properties["methods"]["description"]

    # Each parameter description must carry its relocated usage cue, not merely be non-empty
    assert "Alone" in properties["age_from"]["description"]
    assert "bounds the upper end" in properties["age_to"]["description"]
    assert "method signature" in properties["methods"]["description"]


@pytest.mark.asyncio
async def test_get_token_transfers_by_address_description_excludes_use_cases():
    """Description must not contain 'Use cases'."""
    tools = {t.name: t for t in await server.mcp.list_tools()}
    tool = tools["get_token_transfers_by_address"]

    assert "Use cases" not in tool.description


@pytest.mark.asyncio
async def test_get_token_transfers_by_address_parameter_descriptions_carry_usage_cues():
    """age_from, age_to, and token parameter descriptions must each carry their relocated usage cue."""
    tools = {t.name: t for t in await server.mcp.list_tools()}
    tool = tools["get_token_transfers_by_address"]
    properties = tool.inputSchema.get("properties", {})

    assert "age_from" in properties
    assert properties["age_from"]["description"]

    assert "age_to" in properties
    assert properties["age_to"]["description"]

    assert "token" in properties
    assert properties["token"]["description"]

    # Each parameter description must carry its relocated usage cue, not merely be non-empty
    assert "Alone" in properties["age_from"]["description"]
    assert "bounds the upper end" in properties["age_to"]["description"]
    assert "single token" in properties["token"]["description"]


@pytest.mark.asyncio
async def test_lookup_token_by_symbol_description_resolves_placeholder():
    """Description must not contain 'TOKEN_RESULTS_LIMIT' and must contain the concrete limit value."""
    tools = {t.name: t for t in await server.mcp.list_tools()}
    tool = tools["lookup_token_by_symbol"]

    assert "TOKEN_RESULTS_LIMIT" not in tool.description
    assert re.search(rf"first\s+{TOKEN_RESULTS_LIMIT}\s+matches", tool.description), (
        "Description must state the concrete result limit (e.g. 'first 7 matches'), "
        "not the TOKEN_RESULTS_LIMIT placeholder."
    )


@pytest.mark.asyncio
async def test_get_chains_list_description_contains_ethereum_mainnet_chain_id_hint():
    """Description must bind 'Ethereum Mainnet', 'chain_id', and '1' in one sentence."""
    tools = {t.name: t for t in await server.mcp.list_tools()}
    tool = tools["get_chains_list"]

    assert re.search(r"Ethereum Mainnet.*`chain_id`.*`1`", tool.description), (
        "Description must bind 'Ethereum Mainnet', 'chain_id', and '1' in a single sentence "
        "(regression guard for the chain-id hint restored in Phase 4)."
    )


@pytest.mark.asyncio
async def test_direct_api_call_description_excludes_banned_phrases():
    """Description must not contain 'Returns:' or the standalone query-string sentence."""
    tools = {t.name: t for t in await server.mcp.list_tools()}
    tool = tools["direct_api_call"]

    assert "Returns:" not in tool.description
    # The standalone query-string sentence was relocated to the endpoint_path parameter
    # in Phase 5; it must not linger in the tool-level description.
    assert "query string" not in tool.description.lower()


@pytest.mark.asyncio
async def test_direct_api_call_description_contains_skill_entrypoint_uri():
    """Description must contain the literal SKILL.md skill resource URI."""
    tools = {t.name: t for t in await server.mcp.list_tools()}
    tool = tools["direct_api_call"]

    assert "blockscout-mcp://skill/SKILL.md" in tool.description


@pytest.mark.asyncio
async def test_direct_api_call_description_contains_api_index_uri():
    """Description must contain the literal blockscout-api-index.md skill resource URI."""
    tools = {t.name: t for t in await server.mcp.list_tools()}
    tool = tools["direct_api_call"]

    assert "blockscout-mcp://skill/references/blockscout-api-index.md" in tool.description


@pytest.mark.asyncio
async def test_direct_api_call_description_orders_skill_entrypoint_before_api_index():
    """SKILL.md must be read before the endpoint index: its URI occurs earlier in the text."""
    tools = {t.name: t for t in await server.mcp.list_tools()}
    tool = tools["direct_api_call"]

    skill_index = tool.description.find("blockscout-mcp://skill/SKILL.md")
    api_index_index = tool.description.find("blockscout-mcp://skill/references/blockscout-api-index.md")

    assert skill_index != -1
    assert api_index_index != -1
    assert skill_index < api_index_index


@pytest.mark.asyncio
async def test_direct_api_call_description_binds_first_call_to_session_scope():
    """'Before the first ... call ... session' must appear as a single bound clause."""
    tools = {t.name: t for t in await server.mcp.list_tools()}
    tool = tools["direct_api_call"]

    assert re.search(r"before the first\b.{0,30}call\b.{0,40}\bsession", tool.description, re.IGNORECASE | re.DOTALL)


@pytest.mark.asyncio
async def test_direct_api_call_description_binds_skip_to_already_in_context():
    """'Skip ... already in context' must appear as a single bound clause (preload exemption)."""
    tools = {t.name: t for t in await server.mcp.list_tools()}
    tool = tools["direct_api_call"]

    assert re.search(r"skip\b.{0,60}\balready in context", tool.description, re.IGNORECASE | re.DOTALL)


@pytest.mark.asyncio
async def test_direct_api_call_description_warns_recalled_knowledge_not_a_substitute():
    """The recalled-knowledge warning and its rationale must both be present and bound."""
    tools = {t.name: t for t in await server.mcp.list_tools()}
    tool = tools["direct_api_call"]
    description = tool.description

    assert "not a substitute" in description.lower()
    assert re.search(
        r"(?:paths|parameters|response shapes).{0,80}vary across.{0,40}(?:version|chain)",
        description,
        re.IGNORECASE | re.DOTALL,
    )
    # The relation regex above is satisfied by a single member of each alternation group;
    # these literal checks guard against dropping any of the other varying things or
    # deployment dimensions while the regex stays green.
    for literal in ("paths", "parameters", "response shapes", "version", "chain"):
        assert literal in description.lower()


@pytest.mark.asyncio
async def test_direct_api_call_description_binds_authoritative_to_index():
    """The endpoint index must be described as authoritative, bound in one clause."""
    tools = {t.name: t for t in await server.mcp.list_tools()}
    tool = tools["direct_api_call"]

    assert re.search(
        r"authoritative.{0,60}index|index.{0,60}authoritative", tool.description, re.IGNORECASE | re.DOTALL
    )


@pytest.mark.asyncio
async def test_direct_api_call_description_length_budget():
    """Client-visible description must stay within the Phase 2 exception budget (<= 900 chars)."""
    tools = {t.name: t for t in await server.mcp.list_tools()}
    tool = tools["direct_api_call"]

    assert len(tool.description.strip()) <= 900


@pytest.mark.asyncio
async def test_direct_api_call_endpoint_path_param_mentions_query_params():
    """endpoint_path parameter description must mention passing query parameters via query_params."""
    tools = {t.name: t for t in await server.mcp.list_tools()}
    tool = tools["direct_api_call"]
    properties = tool.inputSchema.get("properties", {})

    assert "endpoint_path" in properties
    param_desc = properties["endpoint_path"]["description"]
    assert "query_params" in param_desc, (
        "endpoint_path parameter description must mention 'query_params' "
        "to guide users away from double-encoding (Phase 5 relocation)."
    )
