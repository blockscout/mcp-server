# SPDX-License-Identifier: LicenseRef-Blockscout
# tests/conftest.py
import os
from unittest.mock import AsyncMock, MagicMock

import pytest

from blockscout_mcp_server import analytics
from blockscout_mcp_server.config import ServerConfig, config
from blockscout_mcp_server.session_store import close_store, initialize_store


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
    handled separately by the `_isolate_dotenv_and_singleton` fixture that
    `tests/test_server.py` carries for its own additional isolation.
    """
    if request.node.get_closest_marker("integration") is not None:
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


@pytest.fixture
def reset_analytics_state(monkeypatch):
    """Reset the analytics module's private state around a test.

    Shared by the analytics test modules, which opt in module-wide via
    ``pytestmark = pytest.mark.usefixtures("reset_analytics_state")``. Deliberately
    not autouse: unrelated test modules must not have analytics state silently
    reset under them. The memoized Mixpanel client is cleared via ``monkeypatch``
    (whose teardown restores the pre-test value); the HTTP-mode flag is reset
    directly on both sides of the test.
    """
    analytics.set_http_mode(False)
    monkeypatch.setattr(analytics, "_mp_client", None, raising=False)  # type: ignore[attr-defined]
    yield
    analytics.set_http_mode(False)


@pytest.fixture
def enabled_session_gate(tmp_path, monkeypatch):
    """Turn the session gate on against a temporary SQLite store.

    Not autouse: tests opt in explicitly (Phases 4-9 reuse this fixture). Sets
    `config.session_secret` and `config.session_db_path` via `monkeypatch`, flips
    HTTP mode on, and initializes the store singleton — mirroring the discipline of
    `reset_analytics_state` above. Everything else keeps running ungated
    automatically thanks to `pristine_config`.

    Safe for direct decorator tests and for the Phase 8 REST tests because both run
    the store's SQL on the pytest thread's own event loop
    (`httpx.AsyncClient(ASGITransport)` involves no second thread). Do **not** use
    this fixture in the `TestClient`-driven transport and lifespan tests
    (`tests/test_session_gate_http_transport.py`, `tests/test_server_session_gate.py`):
    Starlette's `TestClient` runs the ASGI app in an AnyIO portal thread, and the
    store keeps `check_same_thread=True`, so a store initialized here on the pytest
    thread would make every SQL-touching scenario there die with a cross-thread
    `ProgrammingError`. Those files own the store on the portal thread instead.
    """
    db_path = tmp_path / "sessions.db"
    monkeypatch.setattr(config, "session_secret", "test-session-secret")
    monkeypatch.setattr(config, "session_db_path", str(db_path))
    analytics.set_http_mode(True)
    initialize_store(str(db_path))
    yield
    close_store()
    analytics.set_http_mode(False)
