from types import SimpleNamespace

from blockscout_mcp_server.analytics import _determine_call_source


def test_determine_call_source_explicit_rest():
    ctx = SimpleNamespace(call_source="rest")
    assert _determine_call_source(ctx) == "rest"


def test_determine_call_source_default_mcp_when_no_marker():
    # No explicit marker; defaults to mcp
    ctx = SimpleNamespace()
    assert _determine_call_source(ctx) == "mcp"


def test_determine_call_source_mcp_when_session_present():
    # Even with no explicit marker, presence of client_params should be treated as mcp
    session = SimpleNamespace(client_params=SimpleNamespace())
    ctx = SimpleNamespace(session=session)
    assert _determine_call_source(ctx) == "mcp"
