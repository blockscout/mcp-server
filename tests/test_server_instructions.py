# SPDX-License-Identifier: LicenseRef-Blockscout
"""Regression tests for the slim `composed_instructions` string in server.py."""

from blockscout_mcp_server.constants import SERVER_VERSION, SKILL_RESOLUTION_RULE_TEXT
from blockscout_mcp_server.resources import skill_resources
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
    "<recommended_chains>",
)


def test_composed_instructions_drops_all_removed_rule_blocks():
    """None of the legacy rule-block tags survive after the shrink refactor."""
    present = [tag for tag in REMOVED_TAGS if tag in composed_instructions]
    assert present == [], f"Legacy tag(s) still present in composed_instructions: {present}"


def test_composed_instructions_contains_required_structural_pieces():
    """Version line and skill pointer prose appear."""
    assert f"Blockscout MCP server version: {SERVER_VERSION}" in composed_instructions
    assert "blockscout-analysis" in composed_instructions


def test_skill_pointer_text_is_identical_between_server_surfaces():
    """The skill-pointer sentence emitted by the server matches skill_pointer_text() verbatim."""
    rendered_pointer = skill_resources.skill_pointer_text()
    combined_skill_text = f"{rendered_pointer}\n\n{SKILL_RESOLUTION_RULE_TEXT}"

    assert composed_instructions.rstrip().endswith(combined_skill_text)
    assert composed_instructions.count(rendered_pointer) == 1
    assert composed_instructions.count(SKILL_RESOLUTION_RULE_TEXT) == 1


def test_skill_pointer_precedes_resolution_rule_and_names_fetch_surfaces():
    rendered_pointer = skill_resources.skill_pointer_text()
    assert composed_instructions.index(rendered_pointer) < composed_instructions.index(SKILL_RESOLUTION_RULE_TEXT)
    assert "blockscout-mcp://skill/SKILL.md" in composed_instructions
    assert "GET /skill/SKILL.md" in composed_instructions


def test_composed_instructions_contains_skill_version():
    """The bundled skill version appears in composed_instructions (issue #410)."""
    version = skill_resources.get_bundled_skill_version()
    assert version is not None, "Bundled skill version must be available for this assertion to be meaningful"
    assert f"(version {version})" in composed_instructions
