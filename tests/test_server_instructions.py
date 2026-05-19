# SPDX-License-Identifier: LicenseRef-Blockscout
"""Regression tests for the slim `composed_instructions` string in server.py."""

from blockscout_mcp_server.constants import SERVER_VERSION, SKILL_POINTER_TEXT
from blockscout_mcp_server.server import composed_instructions

REMOVED_TAGS = (
    "<error_handling_rules>",
    "<pagination_rules>",
    "<time_based_query_rules>",
    "<binary_search_rules>",
    "<portfolio_analysis_rules>",
    "<funds_movement_rules>",
    "<data_ordering_and_resumption_rules>",
    "<direct_call_endpoint_list>",
    "<chain_id_guidance>",
    "<rules>",
)


def test_composed_instructions_drops_all_removed_rule_blocks():
    """None of the legacy rule-block tags survive after the shrink refactor."""
    present = [tag for tag in REMOVED_TAGS if tag in composed_instructions]
    assert present == [], f"Legacy tag(s) still present in composed_instructions: {present}"


def test_composed_instructions_contains_required_structural_pieces():
    """Version line, recommended_chains block, and skill pointer prose all appear."""
    assert f"Blockscout MCP server version: {SERVER_VERSION}" in composed_instructions
    assert "<recommended_chains>" in composed_instructions
    assert "blockscout-analysis" in composed_instructions


def test_skill_pointer_text_is_identical_between_server_surfaces():
    """The skill-pointer sentence emitted by the server matches SKILL_POINTER_TEXT verbatim."""
    assert composed_instructions.rstrip().endswith(SKILL_POINTER_TEXT)
    assert composed_instructions.count(SKILL_POINTER_TEXT) == 1
