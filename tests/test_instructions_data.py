# SPDX-License-Identifier: LicenseRef-Blockscout
"""Tests for the slim `InstructionsData` model returned by `__unlock_blockchain_analysis__`."""

from blockscout_mcp_server.constants import SKILL_POINTER_TEXT
from blockscout_mcp_server.models import ChainInfo, InstructionsData


def test_instructions_data_constructs_with_three_fields():
    """InstructionsData accepts and exposes its three surviving fields."""
    chains = [
        ChainInfo(
            name="Ethereum",
            chain_id="1",
            is_testnet=False,
            native_currency="ETH",
            ecosystem="Ethereum",
            settlement_layer_chain_id=None,
        ),
        ChainInfo(
            name="Base",
            chain_id="8453",
            is_testnet=False,
            native_currency="ETH",
            ecosystem=["Ethereum", "Superchain"],
            settlement_layer_chain_id="1",
        ),
    ]
    instructions = InstructionsData(
        version="9.9.9",
        recommended_chains=chains,
        skill_reference="See the blockscout-analysis skill.",
    )

    assert instructions.version == "9.9.9"
    assert isinstance(instructions.recommended_chains, list)
    assert len(instructions.recommended_chains) == 2
    assert instructions.recommended_chains[0].name == "Ethereum"
    assert instructions.recommended_chains[1].chain_id == "8453"
    assert instructions.skill_reference == "See the blockscout-analysis skill."


def test_instructions_data_field_set_is_exactly_three():
    """Regression guard: any future field re-introduction must be deliberate."""
    assert set(InstructionsData.model_fields.keys()) == {
        "version",
        "recommended_chains",
        "skill_reference",
    }


def test_instructions_data_recommended_chains_round_trip_as_flat_list():
    """`recommended_chains` is a flat list of ChainInfo (no wrapper model)."""
    chain = ChainInfo(
        name="TestChain",
        chain_id="123",
        is_testnet=False,
        native_currency="TST",
        ecosystem="Test",
    )
    instructions = InstructionsData(
        version="1.0.0",
        recommended_chains=[chain],
        skill_reference="pointer",
    )

    dumped = instructions.model_dump()
    assert dumped["recommended_chains"] == [chain.model_dump()]


def test_skill_reference_matches_constant_when_populated_from_it():
    """When sourced from SKILL_POINTER_TEXT, `skill_reference` equals the constant verbatim."""
    instructions = InstructionsData(
        version="1.0.0",
        recommended_chains=[],
        skill_reference=SKILL_POINTER_TEXT,
    )

    assert instructions.skill_reference == SKILL_POINTER_TEXT
