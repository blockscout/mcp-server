# SPDX-License-Identifier: LicenseRef-Blockscout
"""Unit tests for the PRO-API-key-required notice (issue #425).

Phase 2 covers only ``client_supplied_valid_key()`` — the helper that reports
whether the current request's effective credential is a client-supplied PRO
API key, so response assembly (Phase 3) never has to touch this module's
private state classes directly. Phase 3 extends this file with the
notice-assembly integration tests; keep the whole file under 500 LOC per
rule 210.
"""

from __future__ import annotations

from contextlib import contextmanager

from blockscout_mcp_server.pro_api_key_context import (
    _Absent,
    _client_key_state,
    _Malformed,
    _Valid,
    client_supplied_valid_key,
)


@contextmanager
def _set_client_key_state(state):
    """Context manager that sets _client_key_state and resets it in finally."""
    token = _client_key_state.set(state)
    try:
        yield
    finally:
        _client_key_state.reset(token)


# ===========================================================================
# client_supplied_valid_key() — mapping from every ContextVar state to bool
# ===========================================================================


def test_valid_client_key_state_returns_true():
    with _set_client_key_state(_Valid(value="client-key-123")):
        assert client_supplied_valid_key() is True


def test_absent_state_returns_false():
    with _set_client_key_state(_Absent()):
        assert client_supplied_valid_key() is False


def test_malformed_state_returns_false():
    with _set_client_key_state(_Malformed()):
        assert client_supplied_valid_key() is False


def test_no_state_set_returns_false():
    """Outside any @pro_api_key_scope, the ContextVar reads its _ABSENT default."""
    assert client_supplied_valid_key() is False
