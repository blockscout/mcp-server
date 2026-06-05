# SPDX-License-Identifier: LicenseRef-Blockscout
"""Unit tests for the handle_rest_errors decorator in blockscout_mcp_server.api.helpers."""

import json

import pytest
from starlette.requests import Request

from blockscout_mcp_server.api.helpers import handle_rest_errors
from blockscout_mcp_server.tools.common import CreditsExhaustedError


def _make_request() -> Request:
    """Create a minimal Starlette Request for use in decorator tests."""
    scope = {"type": "http", "method": "GET", "path": "/", "query_string": b"", "headers": []}
    return Request(scope)


@pytest.mark.asyncio
async def test_handle_rest_errors_credits_exhausted_returns_402():
    """handle_rest_errors converts CreditsExhaustedError into an HTTP 402 response."""
    message = "Out of credits"

    @handle_rest_errors
    async def handler(request: Request):
        raise CreditsExhaustedError(message)

    response = await handler(_make_request())

    assert response.status_code == 402
    body = json.loads(response.body)
    assert body["error"] == message


@pytest.mark.asyncio
async def test_handle_rest_errors_value_error_still_returns_400():
    """CreditsExhaustedError branch does not intercept ValueError; it still maps to 400."""

    @handle_rest_errors
    async def handler(request: Request):
        raise ValueError("bad input")

    response = await handler(_make_request())

    assert response.status_code == 400
    body = json.loads(response.body)
    assert body["error"] == "bad input"
