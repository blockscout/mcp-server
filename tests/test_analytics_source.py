# SPDX-License-Identifier: LicenseRef-Blockscout
from types import SimpleNamespace

from blockscout_mcp_server.analytics import get_call_source


def test_get_call_source_explicit_rest():
    ctx = SimpleNamespace(call_source="rest")
    assert get_call_source(ctx) == "rest"


def test_get_call_source_default_mcp_when_no_marker():
    # No explicit marker; defaults to mcp
    ctx = SimpleNamespace()
    assert get_call_source(ctx) == "mcp"


def test_get_call_source_mcp_when_session_present():
    # No explicit marker still defaults to 'mcp' regardless of session presence
    session = SimpleNamespace(client_params=SimpleNamespace())
    ctx = SimpleNamespace(session=session)
    assert get_call_source(ctx) == "mcp"


def test_get_call_source_empty_string_defaults_to_mcp():
    ctx = SimpleNamespace(call_source="")
    assert get_call_source(ctx) == "mcp"


def test_get_call_source_raising_attribute_returns_unknown():
    # getattr(..., None) only swallows AttributeError; any other exception raised
    # while reading `call_source` must reach the defensive except branch.
    class RaisingCallSource:
        @property
        def call_source(self):
            raise RuntimeError("boom")

    assert get_call_source(RaisingCallSource()) == "unknown"
