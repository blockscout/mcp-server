from types import SimpleNamespace

from blockscout_mcp_server.client_meta import (
    UNDEFINED_CLIENT_NAME,
    UNDEFINED_CLIENT_VERSION,
    UNKNOWN_PROTOCOL_VERSION,
    extract_client_meta_from_ctx,
    get_header_case_insensitive,
)


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
