# SPDX-License-Identifier: LicenseRef-Blockscout
"""Unit tests for blockscout_mcp_server.session_gate.

Covers token integrity, TTL semantics, predicate logic, and the message
contracts — with no per-request store I/O (a throwaway `tmp_path` store, or a
patched generation accessor, supplies the generation).
"""

from __future__ import annotations

import time

import pytest

from blockscout_mcp_server import analytics
from blockscout_mcp_server.config import config
from blockscout_mcp_server.constants import (
    SESSION_ID_REQUIRED_MESSAGE,
    SESSION_OVER_MESSAGE,
    SESSION_STORE_UNAVAILABLE_MESSAGE,
)
from blockscout_mcp_server.session_gate import (
    SessionBudgetExhaustedError,
    SessionExpiredError,
    SessionGateError,
    SessionIdInvalidError,
    SessionIdMissingError,
    SessionStoreUnavailableError,
    gate_enabled,
    mint_token,
    verify_token,
)
from blockscout_mcp_server.session_store import close_store, initialize_store


@pytest.fixture(autouse=True)
def _clear_store_singleton():
    """Ensure the module-level store singleton never leaks between tests."""
    close_store()
    yield
    close_store()


@pytest.fixture
def store(tmp_path, monkeypatch):
    """Initialize a throwaway store and point config.session_secret at a test value."""
    monkeypatch.setattr(config, "session_secret", "test-secret")
    db_path = tmp_path / "sessions.db"
    return initialize_store(str(db_path))


# ---------------------------------------------------------------------------
# Mint / verify round-trip
# ---------------------------------------------------------------------------


def test_mint_verify_round_trip_returns_random_part_and_issued_at(store):
    before = int(time.time())
    token = mint_token()
    random_part, issued_at = verify_token(token)

    assert random_part
    assert issued_at >= before


def test_mint_token_raises_when_secret_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "session_secret", "")
    initialize_store(str(tmp_path / "sessions.db"))

    with pytest.raises(SessionGateError):
        mint_token()


# ---------------------------------------------------------------------------
# Tampering
# ---------------------------------------------------------------------------


def test_tampered_random_part_is_mac_invalid(store):
    token = mint_token()
    random_part, issued_at, mac = token.split(".")
    tampered = f"{random_part}x.{issued_at}.{mac}"

    with pytest.raises(SessionIdInvalidError):
        verify_token(tampered)


def test_tampered_issued_at_is_mac_invalid(store):
    token = mint_token()
    random_part, issued_at, mac = token.split(".")
    tampered = f"{random_part}.{int(issued_at) + 100}.{mac}"

    with pytest.raises(SessionIdInvalidError):
        verify_token(tampered)


def test_truncated_mac_is_mac_invalid(store):
    token = mint_token()
    random_part, issued_at, mac = token.split(".")
    tampered = f"{random_part}.{issued_at}.{mac[:8]}"

    with pytest.raises(SessionIdInvalidError):
        verify_token(tampered)


def test_wrong_separator_count_is_mac_invalid(store):
    token = mint_token()
    with pytest.raises(SessionIdInvalidError):
        verify_token(token + ".extra")

    random_part, issued_at, _mac = token.split(".")
    with pytest.raises(SessionIdInvalidError):
        verify_token(f"{random_part}.{issued_at}")


def test_empty_string_is_mac_invalid(store):
    with pytest.raises(SessionIdInvalidError):
        verify_token("")


def test_token_minted_under_one_secret_does_not_verify_under_another(store, monkeypatch):
    token = mint_token()
    monkeypatch.setattr(config, "session_secret", "a-different-secret")

    with pytest.raises(SessionIdInvalidError):
        verify_token(token)


def test_token_minted_under_one_store_generation_does_not_verify_under_another(store, tmp_path):
    token = mint_token()

    # Re-initialize on a fresh file: a new generation is minted.
    close_store()
    initialize_store(str(tmp_path / "sessions2.db"))

    with pytest.raises(SessionIdInvalidError):
        verify_token(token)


# ---------------------------------------------------------------------------
# TTL semantics
# ---------------------------------------------------------------------------


def test_ttl_expiry_with_non_default_ttl(store, monkeypatch):
    monkeypatch.setattr(config, "session_ttl_seconds", 100)
    now = 1_000_000
    monkeypatch.setattr(time, "time", lambda: now)
    token = mint_token()

    monkeypatch.setattr(time, "time", lambda: now + 101)
    with pytest.raises(SessionExpiredError):
        verify_token(token)


def test_retroactive_ttl_raise_revives_expired_token(store, monkeypatch):
    monkeypatch.setattr(config, "session_ttl_seconds", 100)
    now = 1_000_000
    monkeypatch.setattr(time, "time", lambda: now)
    token = mint_token()

    monkeypatch.setattr(time, "time", lambda: now + 101)
    with pytest.raises(SessionExpiredError):
        verify_token(token)

    monkeypatch.setattr(config, "session_ttl_seconds", 1000)
    random_part, issued_at = verify_token(token)
    assert random_part
    assert issued_at == now


def test_future_issued_at_is_rejected(store, monkeypatch):
    now = 1_000_000
    monkeypatch.setattr(time, "time", lambda: now)
    token = mint_token()

    monkeypatch.setattr(time, "time", lambda: now - 100)
    with pytest.raises(SessionExpiredError):
        verify_token(token)


# ---------------------------------------------------------------------------
# gate_enabled matrix
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("_reset_http_mode")
class TestGateEnabledMatrix:
    @pytest.mark.parametrize(
        ("secret", "http_mode", "expected"),
        [
            ("a-secret", True, True),
            ("a-secret", False, False),
            ("", True, False),
            ("", False, False),
        ],
    )
    def test_gate_enabled_matrix(self, monkeypatch, secret, http_mode, expected):
        monkeypatch.setattr(config, "session_secret", secret)
        analytics.set_http_mode(http_mode)

        assert gate_enabled() is expected


@pytest.fixture
def _reset_http_mode():
    analytics.set_http_mode(False)
    yield
    analytics.set_http_mode(False)


# ---------------------------------------------------------------------------
# Message contracts
# ---------------------------------------------------------------------------


def test_missing_and_invalid_errors_carry_required_message_verbatim():
    assert str(SessionIdMissingError()) == SESSION_ID_REQUIRED_MESSAGE
    assert str(SessionIdInvalidError()) == SESSION_ID_REQUIRED_MESSAGE


def test_expired_and_exhausted_errors_carry_over_message_verbatim_and_equal():
    expired_message = str(SessionExpiredError())
    exhausted_message = str(SessionBudgetExhaustedError())

    assert expired_message == SESSION_OVER_MESSAGE
    assert exhausted_message == SESSION_OVER_MESSAGE
    assert expired_message == exhausted_message


def test_store_unavailable_message_contains_no_terminal_markers():
    assert "do not retry" not in SESSION_STORE_UNAVAILABLE_MESSAGE.lower()
    assert "do not initialize" not in SESSION_STORE_UNAVAILABLE_MESSAGE.lower()
    assert str(SessionStoreUnavailableError()) == SESSION_STORE_UNAVAILABLE_MESSAGE
