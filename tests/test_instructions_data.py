# SPDX-License-Identifier: LicenseRef-Blockscout
"""Tests for the slim `InstructionsData` model returned by `__unlock_blockchain_analysis__`."""

from blockscout_mcp_server.models import InstructionsData


def test_instructions_data_constructs_with_server_version_only():
    """Constructing with only `server_version` exposes that value and leaves `session_id` as `None`."""
    instructions = InstructionsData(server_version="9.9.9")

    assert instructions.server_version == "9.9.9"
    assert instructions.session_id is None


def test_instructions_data_field_set_is_exactly_two():
    """Regression guard: any future field re-introduction must be deliberate.

    The model carries exactly two reference scalars: `session_id` and `server_version`.
    The skill pointer and its reference-path resolution rule are delivered via the
    response envelope's `instructions` list instead (see issue #450).
    """
    assert set(InstructionsData.model_fields.keys()) == {"session_id", "server_version"}


def test_instructions_data_serialization_omits_session_id_when_none():
    """Serialization must omit the `session_id` key entirely when unset, not emit `null`."""
    instructions = InstructionsData(server_version="1.0.0")

    dumped = instructions.model_dump(mode="json", by_alias=True)

    assert "session_id" not in dumped


def test_instructions_data_serialization_includes_session_id_when_set():
    """Serialization must include the `session_id` key with its value when set."""
    instructions = InstructionsData(server_version="1.0.0", session_id="abc.123.def")

    dumped = instructions.model_dump(mode="json", by_alias=True)

    assert dumped["session_id"] == "abc.123.def"


def test_instructions_data_session_id_is_first_key_when_set():
    """When `session_id` is set, it is the first key of the serialized dict.

    The ordering is a stated goal of issue #450: agents reliably overlook a
    trailing scalar, so `session_id` must lead the serialized payload.
    """
    instructions = InstructionsData(server_version="1.0.0", session_id="abc.123.def")

    dumped = instructions.model_dump(mode="json", by_alias=True)

    assert list(dumped.keys())[0] == "session_id"
