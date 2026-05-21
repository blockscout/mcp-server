# SPDX-License-Identifier: LicenseRef-Blockscout
"""Tests for the slim `InstructionsData` model returned by `__unlock_blockchain_analysis__`."""

from blockscout_mcp_server.constants import SKILL_POINTER_TEXT, SKILL_RESOLUTION_RULE_TEXT
from blockscout_mcp_server.models import InstructionsData


def test_instructions_data_constructs_with_three_fields():
    """InstructionsData accepts and exposes its three surviving fields."""
    instructions = InstructionsData(
        version="9.9.9",
        skill_reference="See the blockscout-analysis skill.",
        skill_resolution_rule="Resolve references through the server.",
    )

    assert instructions.version == "9.9.9"
    assert instructions.skill_reference == "See the blockscout-analysis skill."
    assert instructions.skill_resolution_rule == "Resolve references through the server."


def test_instructions_data_field_set_is_exactly_three():
    """Regression guard: any future field re-introduction must be deliberate."""
    assert set(InstructionsData.model_fields.keys()) == {
        "version",
        "skill_reference",
        "skill_resolution_rule",
    }


def test_skill_reference_matches_constant_when_populated_from_it():
    """When sourced from SKILL_POINTER_TEXT, `skill_reference` equals the constant verbatim."""
    instructions = InstructionsData(
        version="1.0.0",
        skill_reference=SKILL_POINTER_TEXT,
        skill_resolution_rule=SKILL_RESOLUTION_RULE_TEXT,
    )

    assert instructions.skill_reference == SKILL_POINTER_TEXT
    assert instructions.skill_resolution_rule == SKILL_RESOLUTION_RULE_TEXT


def test_skill_resolution_rule_round_trips_in_serialization():
    instructions = InstructionsData(
        version="1.0.0",
        skill_reference="pointer",
        skill_resolution_rule=SKILL_RESOLUTION_RULE_TEXT,
    )

    assert instructions.model_dump()["skill_resolution_rule"] == SKILL_RESOLUTION_RULE_TEXT
