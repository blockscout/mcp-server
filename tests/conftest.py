# SPDX-License-Identifier: LicenseRef-Blockscout
# tests/conftest.py
import os
from unittest.mock import AsyncMock, MagicMock

import pytest

from blockscout_mcp_server.config import ServerConfig, config


@pytest.fixture
def mock_ctx():
    """Provides a mock MCP Context object for tests."""
    ctx = MagicMock()
    ctx.report_progress = AsyncMock()
    ctx.info = AsyncMock()
    return ctx


@pytest.fixture(autouse=True)
def pristine_config(request, monkeypatch):
    """Pin every field of the `config` singleton to its code default for unit tests.

    A plain `pytest` run must be deterministic regardless of the developer's exported
    environment variables or local `.env` file. Without this fixture, ambient values
    (e.g. a non-empty `BLOCKSCOUT_PRO_API_KEY_REQUIRED_NOTICE`) leak into the `config`
    singleton at import time and make otherwise-passing tests fail on some machines
    but not others (see issue #436).

    Known limitation: tests in `tests/test_server.py` that rebuild the config module
    via `importlib.reload` re-execute `config = ServerConfig()`, rebinding the module
    attribute to a brand-new object this fixture never touched. That reload path is
    handled separately (see Phase 2 of the issue #436 implementation plan), which is
    why `tests/test_server.py` carries its own additional isolation fixture.
    """
    if "integration" in request.keywords:
        # Integration tests deliberately rely on ambient configuration (e.g. a real
        # BLOCKSCOUT_PRO_API_KEY), so leave the environment and singleton untouched.
        return

    # Close the env-var channel: any code that constructs a fresh ServerConfig during
    # the test must not see ambient BLOCKSCOUT_* variables or the unprefixed PORT
    # variable (the `port` field is aliased to read PORT directly). The comparison is
    # case-insensitive because pydantic-settings matches environment variables
    # case-insensitively by default, so e.g. a lowercase `blockscout_bs_timeout` would
    # otherwise leak into the pristine instance built below.
    for name in list(os.environ):
        upper_name = name.upper()
        if upper_name.startswith("BLOCKSCOUT_") or upper_name == "PORT":
            monkeypatch.delenv(name, raising=False)

    # Pin the singleton: build a pristine instance (bypassing the local .env file)
    # and copy every declared field onto the module-level singleton so production
    # code importing `config` sees code defaults only.
    pristine = ServerConfig(_env_file=None)
    for field_name in type(config).model_fields:
        monkeypatch.setattr(config, field_name, getattr(pristine, field_name))
