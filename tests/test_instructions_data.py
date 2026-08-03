# SPDX-License-Identifier: LicenseRef-Blockscout
"""Tests for the slim `InstructionsData` model returned by `__unlock_blockchain_analysis__`."""

from blockscout_mcp_server.constants import SKILL_RESOLUTION_RULE_TEXT
from blockscout_mcp_server.models import InstructionsData
from blockscout_mcp_server.resources import skill_resources


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


def test_instructions_data_field_set_is_exactly_four():
    """Regression guard: any future field re-introduction must be deliberate.

    Phase 6 (issue #442) adds `session_id` to the surviving three fields, moving the
    exact-field-set contract from three to four.
    """
    assert set(InstructionsData.model_fields.keys()) == {
        "version",
        "skill_reference",
        "skill_resolution_rule",
        "session_id",
    }


def test_instructions_data_session_id_defaults_to_none():
    """Constructing without `session_id` leaves it `None`."""
    instructions = InstructionsData(
        version="1.0.0",
        skill_reference="pointer",
        skill_resolution_rule=SKILL_RESOLUTION_RULE_TEXT,
    )

    assert instructions.session_id is None


def test_instructions_data_serialization_omits_session_id_when_none():
    """Serialization must omit the `session_id` key entirely when unset, not emit `null`."""
    instructions = InstructionsData(
        version="1.0.0",
        skill_reference="pointer",
        skill_resolution_rule=SKILL_RESOLUTION_RULE_TEXT,
    )

    dumped = instructions.model_dump(mode="json", by_alias=True)

    assert "session_id" not in dumped


def test_instructions_data_serialization_includes_session_id_when_set():
    """Serialization must include the `session_id` key with its value when set."""
    instructions = InstructionsData(
        version="1.0.0",
        skill_reference="pointer",
        skill_resolution_rule=SKILL_RESOLUTION_RULE_TEXT,
        session_id="abc.123.def",
    )

    dumped = instructions.model_dump(mode="json", by_alias=True)

    assert dumped["session_id"] == "abc.123.def"


def test_skill_reference_matches_rendered_pointer_when_populated_from_it():
    """When sourced from skill_pointer_text(), `skill_reference` equals the rendered pointer verbatim."""
    rendered_pointer = skill_resources.skill_pointer_text()
    instructions = InstructionsData(
        version="1.0.0",
        skill_reference=rendered_pointer,
        skill_resolution_rule=SKILL_RESOLUTION_RULE_TEXT,
    )

    assert instructions.skill_reference == rendered_pointer
    assert instructions.skill_resolution_rule == SKILL_RESOLUTION_RULE_TEXT


def test_skill_resolution_rule_round_trips_in_serialization():
    instructions = InstructionsData(
        version="1.0.0",
        skill_reference="pointer",
        skill_resolution_rule=SKILL_RESOLUTION_RULE_TEXT,
    )

    assert instructions.model_dump()["skill_resolution_rule"] == SKILL_RESOLUTION_RULE_TEXT
