from __future__ import annotations

import re

import pytest

from blockscout_mcp_server.tools.direct_api import dispatcher
from blockscout_mcp_server.tools.direct_api.handlers import address_logs_handler  # noqa: F401


def test_handler_registration():
    """Verify that the address logs handler is registered."""
    assert dispatcher.HANDLER_REGISTRY, "No handlers registered with dispatcher"
    log_handler_registered = any(
        handler.__name__ == "handle_address_logs" for _, handler in dispatcher.HANDLER_REGISTRY
    )
    assert log_handler_registered, "address_logs_handler was not registered"


@pytest.mark.asyncio
async def test_dispatch_routes_to_correct_handler(mock_ctx):
    """Dispatch should call the address logs handler when the pattern matches."""
    endpoint_path = "/api/v2/addresses/0x1234567890123456789012345678901234567890/logs"
    response = await dispatcher.dispatch(
        endpoint_path=endpoint_path,
        response_json={"items": []},
        chain_id="1",
        base_url="https://example.blockscout",
        ctx=mock_ctx,
    )
    assert response is not None, "Dispatcher did not invoke the handler"
    assert hasattr(response, "data"), "Handler did not return a ToolResponse-like object"
    assert isinstance(response.data, list)
    assert response.data == []


@pytest.mark.asyncio
async def test_dispatch_passes_query_params(monkeypatch):
    """Dispatch should forward query params to the resolved handler."""
    captured: dict[str, object] = {}

    async def dummy_handler(*, match: re.Match[str], query_params: dict[str, str] | None, **kwargs: object) -> object:
        captured["match"] = match
        captured["query_params"] = query_params
        return {"data": []}

    monkeypatch.setattr(
        dispatcher,
        "HANDLER_REGISTRY",
        [(re.compile(r"^/dummy$"), dummy_handler)],
        raising=False,
    )

    query_params = {"foo": "bar"}
    response = await dispatcher.dispatch(endpoint_path="/dummy", query_params=query_params, response_json={})

    assert response == {"data": []}
    assert "match" in captured and captured["match"].group(0) == "/dummy"
    assert captured["query_params"] is query_params
