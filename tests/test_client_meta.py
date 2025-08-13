from types import SimpleNamespace

from blockscout_mcp_server.client_meta import (
    UNDEFINED_CLIENT_NAME,
    UNDEFINED_CLIENT_VERSION,
    UNKNOWN_PROTOCOL_VERSION,
    extract_client_meta_from_ctx,
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
