# SPDX-License-Identifier: LicenseRef-Blockscout
import os

import pytest

import blockscout_mcp_server.config as config_module
from blockscout_mcp_server.config import config


def test_pro_api_key_required_notice_is_pinned_to_default():
    """The exact field whose ambient leakage caused issue #436 must be blank."""
    assert config.pro_api_key_required_notice == ""


def test_pro_api_key_is_pinned_to_default():
    """The server PRO API key must be cleared regardless of the ambient environment.

    We deliberately avoid `assert config.pro_api_key == ""` here: pytest's assertion
    rewriting would print the real ambient key in the failure output on exactly the
    fixture-regression path this test exists to catch.
    """
    if config.pro_api_key:
        pytest.fail("pristine_config did not clear the server PRO API key")


def test_no_blockscout_env_vars_or_port_present_in_environment():
    """Proves the env-var channel is closed for code that builds a fresh ServerConfig.

    The check is case-insensitive because pydantic-settings matches environment
    variables case-insensitively by default, so a lowercase `blockscout_...` (or
    `port`) variable leaks just as well as an uppercase one.
    """
    assert not any(name.upper().startswith("BLOCKSCOUT_") for name in os.environ)
    assert not any(name.upper() == "PORT" for name in os.environ)


def test_local_override_on_top_of_fixture_is_honored(monkeypatch):
    """Tests can still opt in to non-default values on top of the fixture."""
    monkeypatch.setattr(config, "pro_api_key_required_notice", "<marker>")

    assert config.pro_api_key_required_notice == "<marker>"


def test_non_pro_fields_are_pinned_to_their_code_defaults():
    """Spot-check that pinning covers all of `model_fields`, not just PRO settings."""
    assert config.bs_timeout == 120.0
    assert config.port is None


def test_config_singleton_identity_is_preserved():
    """Guards against a reload-based test leaking a replacement singleton (Phase 2)."""
    assert config_module.config is config
