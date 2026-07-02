# SPDX-License-Identifier: LicenseRef-Blockscout
"""Tests for the `ToolUsageReport` Pydantic model's optional auth-signal fields."""

import pytest
from pydantic import ValidationError

from blockscout_mcp_server.models import ToolUsageReport

VALID_FINGERPRINT = "a" * 64


def _base_payload(**overrides):
    payload = {
        "tool_name": "get_block_info",
        "tool_args": {"chain_id": "1"},
        "client_name": "test-client",
        "client_version": "1.0.0",
        "protocol_version": "2024-11-05",
    }
    payload.update(overrides)
    return payload


def test_legacy_payload_defaults_new_fields_to_none():
    """A payload with only the five original fields validates, and both new fields default to None."""
    report = ToolUsageReport(**_base_payload())

    assert report.auth_origin is None
    assert report.api_key_fingerprint is None


@pytest.mark.parametrize("origin", ["client", "server", "none"])
def test_auth_origin_round_trips_each_valid_value(origin):
    """A payload supplying auth_origin as each of client/server/none validates and round-trips it."""
    report = ToolUsageReport(**_base_payload(auth_origin=origin))

    assert report.auth_origin == origin


def test_auth_origin_rejects_out_of_enum_value():
    """A payload supplying an out-of-enum auth_origin raises a pydantic ValidationError."""
    with pytest.raises(ValidationError):
        ToolUsageReport(**_base_payload(auth_origin="bogus"))


def test_api_key_fingerprint_round_trips_valid_value():
    """A payload supplying a valid 64-char lowercase hex api_key_fingerprint validates and round-trips."""
    report = ToolUsageReport(**_base_payload(api_key_fingerprint=VALID_FINGERPRINT))

    assert report.api_key_fingerprint == VALID_FINGERPRINT


def test_explicit_none_auth_origin_string_with_null_fingerprint_round_trips():
    """Explicitly setting auth_origin="none" and api_key_fingerprint=None round-trips None.

    This is the no-key wire shape an updated reporter actually sends (Phase 4 includes the key
    unconditionally), distinct from omitting the fields. It guards against the `pattern`
    constraint accidentally rejecting an explicit `null`.
    """
    report = ToolUsageReport(**_base_payload(auth_origin="none", api_key_fingerprint=None))

    assert report.auth_origin == "none"
    assert report.api_key_fingerprint is None


def test_explicit_null_auth_origin_with_null_fingerprint_round_trips():
    """Explicitly setting auth_origin=None (Python None / JSON null) round-trips both fields as None.

    This pins the field's typing to `AuthOrigin | None`. A bare `Literal[...]` that merely
    defaults to None would accept an omitted field but reject an explicit null; only this test
    catches that, since the omitted and string-"none" cases pass either way.
    """
    report = ToolUsageReport(**_base_payload(auth_origin=None, api_key_fingerprint=None))

    assert report.auth_origin is None
    assert report.api_key_fingerprint is None


def test_api_key_fingerprint_tolerates_too_short_value():
    """A malformed (too short) api_key_fingerprint is tolerated: coerced to None, not rejected.

    The fingerprint is a not-yet-consumed forward-compat field, so a malformed value must not
    drop the otherwise-valid report.
    """
    report = ToolUsageReport(**_base_payload(api_key_fingerprint="abc"))

    assert report.api_key_fingerprint is None


def test_api_key_fingerprint_tolerates_non_hex_value():
    """A 64-character but non-hex api_key_fingerprint is coerced to None rather than rejected."""
    report = ToolUsageReport(**_base_payload(api_key_fingerprint="z" * 64))

    assert report.api_key_fingerprint is None


def test_api_key_fingerprint_tolerates_uppercase_hex_value():
    """A 64-character uppercase-hex api_key_fingerprint is coerced to None rather than rejected.

    Only lowercase hex is valid (matching the lowercase output of
    `hashlib.sha256(...).hexdigest()`), so uppercase is treated as malformed and tolerated.
    """
    report = ToolUsageReport(**_base_payload(api_key_fingerprint="A" * 64))

    assert report.api_key_fingerprint is None


def test_api_key_fingerprint_tolerates_over_length_value():
    """An over-length api_key_fingerprint is coerced to None rather than rejected."""
    report = ToolUsageReport(**_base_payload(api_key_fingerprint="a" * 65))

    assert report.api_key_fingerprint is None


@pytest.mark.parametrize("junk", [123, ["a" * 64], {"fingerprint": "a" * 64}, 45.6, True])
def test_api_key_fingerprint_tolerates_non_string_junk(junk):
    """A non-string junk api_key_fingerprint (int/list/dict/float/bool) is coerced to None.

    The `mode="before"` validator guards with `isinstance(value, str)` before the regex, so
    non-string input never reaches the pattern and is tolerated as None rather than raising.
    """
    report = ToolUsageReport(**_base_payload(api_key_fingerprint=junk))

    assert report.api_key_fingerprint is None
