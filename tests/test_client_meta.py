from types import SimpleNamespace

from blockscout_mcp_server.client_meta import (
    UNDEFINED_CLIENT_NAME,
    UNDEFINED_CLIENT_VERSION,
    UNKNOWN_PROTOCOL_VERSION,
    _parse_intermediary_header,
    extract_client_meta_from_ctx,
    get_header_case_insensitive,
)
from blockscout_mcp_server.config import config


def test_extract_client_meta_full():
    client_info = SimpleNamespace(name="clientX", version="2.3.4")
    client_params = SimpleNamespace(clientInfo=client_info, protocolVersion="2024-11-05")
    ctx = SimpleNamespace(session=SimpleNamespace(client_params=client_params))

    meta = extract_client_meta_from_ctx(ctx)
    assert meta.name == "clientX"
    assert meta.version == "2.3.4"
    assert meta.protocol == "2024-11-05"


def test_extract_client_meta_missing_everything():
    ctx = SimpleNamespace()
    meta = extract_client_meta_from_ctx(ctx)
    assert meta.name == UNDEFINED_CLIENT_NAME
    assert meta.version == UNDEFINED_CLIENT_VERSION
    assert meta.protocol == UNKNOWN_PROTOCOL_VERSION


def test_extract_client_meta_partial():
    client_info = SimpleNamespace(name=None, version="0.1.0")
    client_params = SimpleNamespace(clientInfo=client_info)  # no protocolVersion
    ctx = SimpleNamespace(session=SimpleNamespace(client_params=client_params))

    meta = extract_client_meta_from_ctx(ctx)
    assert meta.name == UNDEFINED_CLIENT_NAME
    assert meta.version == "0.1.0"
    assert meta.protocol == UNKNOWN_PROTOCOL_VERSION


def test_extract_client_meta_uses_user_agent_when_name_missing():
    # No clientInfo; user agent present in HTTP request
    headers = {"User-Agent": "ua-test/9.9.9"}
    request = SimpleNamespace(headers=headers)
    ctx = SimpleNamespace(request_context=SimpleNamespace(request=request))

    meta = extract_client_meta_from_ctx(ctx)
    assert meta.name == "ua-test/9.9.9"
    assert meta.version == UNDEFINED_CLIENT_VERSION
    assert meta.protocol == UNKNOWN_PROTOCOL_VERSION


def test_get_header_case_insensitive_with_dict():
    headers = {"User-Agent": "ua-test/1.0", "X-Real-IP": "1.2.3.4"}
    assert get_header_case_insensitive(headers, "user-agent") == "ua-test/1.0"
    assert get_header_case_insensitive(headers, "USER-AGENT") == "ua-test/1.0"
    assert get_header_case_insensitive(headers, "x-real-ip") == "1.2.3.4"
    assert get_header_case_insensitive(headers, "missing", "default") == "default"


def _ctx_with_intermediary(value: str) -> SimpleNamespace:
    headers = {"Blockscout-MCP-Intermediary": value}
    request = SimpleNamespace(headers=headers)
    client_info = SimpleNamespace(name="node", version="1.0.0")
    client_params = SimpleNamespace(clientInfo=client_info, protocolVersion="2024-11-05")
    return SimpleNamespace(
        session=SimpleNamespace(client_params=client_params),
        request_context=SimpleNamespace(request=request),
    )


def test_intermediary_header_merged(monkeypatch):
    monkeypatch.setattr(
        config,
        "intermediary_allowlist",
        "ClaudeDesktop,HigressPlugin",
        raising=False,
    )
    ctx = _ctx_with_intermediary(" claudeDESKTOP ")
    meta = extract_client_meta_from_ctx(ctx)
    assert meta.name == "node/claudeDESKTOP"


def test_intermediary_header_uses_user_agent_when_client_missing(monkeypatch):
    monkeypatch.setattr(
        config,
        "intermediary_allowlist",
        "ClaudeDesktop,HigressPlugin",
        raising=False,
    )
    headers = {
        "User-Agent": "ua-test/9.9.9",
        "Blockscout-MCP-Intermediary": "HigressPlugin",
    }
    request = SimpleNamespace(headers=headers)
    ctx = SimpleNamespace(request_context=SimpleNamespace(request=request))

    meta = extract_client_meta_from_ctx(ctx)
    assert meta.name == "ua-test/9.9.9/HigressPlugin"


def test_intermediary_header_appends_when_no_client_and_no_user_agent(monkeypatch):
    monkeypatch.setattr(
        config,
        "intermediary_allowlist",
        "ClaudeDesktop,HigressPlugin",
        raising=False,
    )
    ctx = _ctx_with_intermediary("HigressPlugin")
    ctx.session.client_params.clientInfo.name = ""  # type: ignore[attr-defined]
    ctx.session.client_params.clientInfo.version = ""  # type: ignore[attr-defined]
    ctx.session.client_params.protocolVersion = None  # type: ignore[attr-defined]
    ctx.request_context.request.headers.pop("Blockscout-MCP-Intermediary", None)
    ctx.request_context.request.headers["Blockscout-MCP-Intermediary"] = "HigressPlugin"
    ctx.request_context.request.headers.pop("User-Agent", None)

    meta = extract_client_meta_from_ctx(ctx)
    assert meta.name == "N/A/HigressPlugin"


def test_parse_intermediary_header_allowlisted():
    allowlist = "ClaudeDesktop,HigressPlugin"
    assert _parse_intermediary_header(" claudeDESKTOP ", allowlist) == "claudeDESKTOP"


def test_parse_intermediary_header_not_allowlisted():
    allowlist = "ClaudeDesktop,HigressPlugin"
    assert _parse_intermediary_header("Unknown", allowlist) == ""


def test_parse_intermediary_header_invalid_char():
    allowlist = "BadValue"
    assert _parse_intermediary_header("Bad/Value", allowlist) == ""


def test_parse_intermediary_header_too_long():
    allowlist = "X" * 17
    assert _parse_intermediary_header("X" * 17, allowlist) == ""


def test_parse_intermediary_header_multiple_values():
    allowlist = "ClaudeDesktop,HigressPlugin"
    assert _parse_intermediary_header(" ,HigressPlugin,Other", allowlist) == "HigressPlugin"
