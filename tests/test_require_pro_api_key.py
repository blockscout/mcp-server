# SPDX-License-Identifier: LicenseRef-Blockscout
"""Direct unit tests for the require_pro_api_key() chokepoint message contract.

Kept in a new focused module because tests/test_pro_api_key_context.py (466 LOC)
does not import require_pro_api_key and is already near the 500 LOC ceiling.
"""

from __future__ import annotations

from contextlib import contextmanager

import pytest

from blockscout_mcp_server.config import config
from blockscout_mcp_server.pro_api_key_context import (
    _Absent,
    _client_key_state,
    _Valid,
    require_pro_api_key,
)

# ---------------------------------------------------------------------------
# ContextVar isolation helper (mirrored from tests/test_pro_api_key_context.py)
# ---------------------------------------------------------------------------


@contextmanager
def _set_key_state(state):
    """Context manager that sets _client_key_state and resets it in finally."""
    token = _client_key_state.set(state)
    try:
        yield
    finally:
        _client_key_state.reset(token)


# ---------------------------------------------------------------------------
# Exact-message contract (primary lock)
# ---------------------------------------------------------------------------


def test_require_pro_api_key_exact_message_data_access(monkeypatch):
    """Full-string equality: label 'data access' produces the exact new terse message."""
    monkeypatch.setattr(config, "pro_api_key", "", raising=False)
    with _set_key_state(_Absent()):
        with pytest.raises(ValueError) as exc_info:
            require_pro_api_key("data access")
    assert str(exc_info.value) == "PRO API key required for data access; not configured."


def test_require_pro_api_key_exact_message_contract_reads(monkeypatch):
    """Full-string equality: label 'contract reads via the PRO API gateway' produces the exact new terse message."""
    monkeypatch.setattr(config, "pro_api_key", "", raising=False)
    with _set_key_state(_Absent()):
        with pytest.raises(ValueError) as exc_info:
            require_pro_api_key("contract reads via the PRO API gateway")
    assert str(exc_info.value) == "PRO API key required for contract reads via the PRO API gateway; not configured."


# ---------------------------------------------------------------------------
# Negative guard (defense in depth)
# ---------------------------------------------------------------------------


def test_require_pro_api_key_message_excludes_env_var_name(monkeypatch):
    """The error message must not contain the environment variable name."""
    monkeypatch.setattr(config, "pro_api_key", "", raising=False)
    monkeypatch.setattr(config, "pro_api_key_header", "Blockscout-MCP-Pro-Api-Key", raising=False)
    with _set_key_state(_Absent()):
        with pytest.raises(ValueError) as exc_info:
            require_pro_api_key("data access")
    message = str(exc_info.value)
    assert "BLOCKSCOUT_PRO_API_KEY" not in message
    assert "on the server" not in message
    assert "Blockscout-MCP-Pro-Api-Key" not in message


# ---------------------------------------------------------------------------
# Happy path guard
# ---------------------------------------------------------------------------


def test_require_pro_api_key_returns_key_when_present(monkeypatch):
    """When a non-empty server key is configured, require_pro_api_key returns it without raising."""
    monkeypatch.setattr(config, "pro_api_key", "my-server-key", raising=False)
    with _set_key_state(_Absent()):
        result = require_pro_api_key("data access")
    assert result == "my-server-key"


def test_require_pro_api_key_returns_client_key_when_valid(monkeypatch):
    """When a valid client key is in the ContextVar, require_pro_api_key returns it without raising."""
    monkeypatch.setattr(config, "pro_api_key", "", raising=False)
    with _set_key_state(_Valid(value="client-supplied-key")):
        result = require_pro_api_key("data access")
    assert result == "client-supplied-key"
