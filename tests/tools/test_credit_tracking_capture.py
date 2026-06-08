# SPDX-License-Identifier: LicenseRef-Blockscout
"""Unit tests for x-credits-remaining capture through the HTTP request helpers.

Covers the single capture point reached by make_blockscout_request (GET),
make_blockscout_post_request (POST) and make_metadata_request, plus cross-task
visibility of the shared CreditSink via make_request_with_periodic_progress
and asyncio.gather.
"""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from blockscout_mcp_server.config import config
from blockscout_mcp_server.pro_api_key_context import CreditSink, _credit_sink


@contextmanager
def _set_sink(sink: CreditSink | None):
    """Context manager that sets _credit_sink and resets it in finally."""
    token = _credit_sink.set(sink)
    try:
        yield
    finally:
        _credit_sink.reset(token)


class _MockResponse:
    """Minimal fake httpx response for GET/POST helpers."""

    def __init__(self, json_data=None, status_code=200, headers=None):
        self._json_data = json_data
        self.status_code = status_code
        self.reason_phrase = "OK"
        self.request = httpx.Request("GET", "https://api.blockscout.com/1/x")
        self.text = ""
        self.headers = headers if headers is not None else {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("boom", request=self.request, response=self)

    def json(self):
        return self._json_data


class _SimpleClient:
    """Async context-manager client that returns a fixed response."""

    def __init__(self, response):
        self._response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def get(self, url, **kwargs):
        return self._response

    async def post(self, url, json, params, headers=None, **kwargs):
        return self._response


# ---------------------------------------------------------------------------
# Header capture via make_blockscout_request (GET path)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_request_captures_credits_remaining():
    """A successful GET response whose headers carry x-credits-remaining records the value."""
    from blockscout_mcp_server.tools.common import make_blockscout_request

    sink = CreditSink()
    response = _MockResponse({"data": "ok"}, headers={"x-credits-remaining": "4200"})

    with _set_sink(sink):
        with (
            patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=_SimpleClient(response)),
            patch("blockscout_mcp_server.tools.common.ensure_chain_supported", AsyncMock()),
            patch.object(config, "pro_api_key", "test_key"),
        ):
            await make_blockscout_request("1", "/api/v2/blocks/1")

    assert sink.remaining == 4200.0


@pytest.mark.asyncio
async def test_get_request_missing_header_sink_stays_none():
    """A response without x-credits-remaining leaves the sink at None."""
    from blockscout_mcp_server.tools.common import make_blockscout_request

    sink = CreditSink()
    response = _MockResponse({"data": "ok"}, headers={})

    with _set_sink(sink):
        with (
            patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=_SimpleClient(response)),
            patch("blockscout_mcp_server.tools.common.ensure_chain_supported", AsyncMock()),
            patch.object(config, "pro_api_key", "test_key"),
        ):
            await make_blockscout_request("1", "/api/v2/blocks/1")

    assert sink.remaining is None


@pytest.mark.asyncio
async def test_get_request_unparseable_header_sink_stays_none():
    """A non-numeric x-credits-remaining header leaves the sink at None."""
    from blockscout_mcp_server.tools.common import make_blockscout_request

    sink = CreditSink()
    response = _MockResponse({"data": "ok"}, headers={"x-credits-remaining": "not-a-number"})

    with _set_sink(sink):
        with (
            patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=_SimpleClient(response)),
            patch("blockscout_mcp_server.tools.common.ensure_chain_supported", AsyncMock()),
            patch.object(config, "pro_api_key", "test_key"),
        ):
            await make_blockscout_request("1", "/api/v2/blocks/1")

    assert sink.remaining is None


@pytest.mark.asyncio
async def test_get_request_mock_typed_header_no_capture():
    """A MagicMock headers object must not produce a capture (regression guard).

    Without the isinstance(value, str) guard, float(MagicMock()) returns 1.0
    because MagicMock implements __float__, which would surface a false
    low-credits note.  This test pins the guard in place.
    """
    from blockscout_mcp_server.tools.common import make_blockscout_request

    sink = CreditSink()
    # response.headers is a MagicMock — get_header_case_insensitive will call
    # headers.get(...) which returns a child MagicMock (not a str).
    mock_headers = MagicMock()
    response = _MockResponse({"data": "ok"}, headers={})
    response.headers = mock_headers

    with _set_sink(sink):
        with (
            patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=_SimpleClient(response)),
            patch("blockscout_mcp_server.tools.common.ensure_chain_supported", AsyncMock()),
            patch.object(config, "pro_api_key", "test_key"),
        ):
            await make_blockscout_request("1", "/api/v2/blocks/1")

    # Sink must stay None — no bogus 1.0 capture.
    assert sink.remaining is None


@pytest.mark.asyncio
async def test_get_request_no_sink_in_context_is_silent_noop():
    """With no sink established (_credit_sink is None), the request succeeds without error."""
    from blockscout_mcp_server.tools.common import make_blockscout_request

    response = _MockResponse({"data": "ok"}, headers={"x-credits-remaining": "9999"})

    # _credit_sink is None by default — do not set a sink.
    with (
        patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=_SimpleClient(response)),
        patch("blockscout_mcp_server.tools.common.ensure_chain_supported", AsyncMock()),
        patch.object(config, "pro_api_key", "test_key"),
    ):
        result = await make_blockscout_request("1", "/api/v2/blocks/1")

    assert result == {"data": "ok"}


@pytest.mark.asyncio
async def test_get_request_case_insensitive_header_lookup():
    """x-credits-remaining is captured regardless of the header's casing."""
    from blockscout_mcp_server.tools.common import make_blockscout_request

    sink = CreditSink()
    # Plain dict with a mixed-case key — proves get_header_case_insensitive is used.
    response = _MockResponse({"data": "ok"}, headers={"X-Credits-Remaining": "4200"})

    with _set_sink(sink):
        with (
            patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=_SimpleClient(response)),
            patch("blockscout_mcp_server.tools.common.ensure_chain_supported", AsyncMock()),
            patch.object(config, "pro_api_key", "test_key"),
        ):
            await make_blockscout_request("1", "/api/v2/blocks/1")

    assert sink.remaining == 4200.0


@pytest.mark.asyncio
async def test_get_request_negative_value_captured():
    """A negative x-credits-remaining (overdrawn paid account) is captured as-is."""
    from blockscout_mcp_server.tools.common import make_blockscout_request

    sink = CreditSink()
    response = _MockResponse({"data": "ok"}, headers={"x-credits-remaining": "-12.5"})

    with _set_sink(sink):
        with (
            patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=_SimpleClient(response)),
            patch("blockscout_mcp_server.tools.common.ensure_chain_supported", AsyncMock()),
            patch.object(config, "pro_api_key", "test_key"),
        ):
            await make_blockscout_request("1", "/api/v2/blocks/1")

    assert sink.remaining == -12.5


# ---------------------------------------------------------------------------
# All three public helper surfaces route through the shared capture point
# ---------------------------------------------------------------------------


class _PostClient:
    """Async context-manager client for POST calls."""

    def __init__(self, response):
        self._response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, json, params, headers=None, **kwargs):
        return self._response


class _GetClient:
    """Async context-manager client for GET calls."""

    def __init__(self, response):
        self._response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def get(self, url, **kwargs):
        return self._response


HELPER_IDS = ["make_blockscout_request", "make_blockscout_post_request", "make_metadata_request"]


@pytest.mark.asyncio
@pytest.mark.parametrize("helper_name", HELPER_IDS)
async def test_all_helper_surfaces_capture_credits_remaining(helper_name):
    """GET, POST, and metadata helpers all record x-credits-remaining into the sink.

    This pins the 'single capture point covers all helpers' guarantee: because
    make_blockscout_request, make_blockscout_post_request, and make_metadata_request
    all delegate to _make_blockscout_http_request, a single capture call there
    covers all three surfaces without per-helper logic.
    """
    from blockscout_mcp_server.tools import common as common_module

    credits_header = {"x-credits-remaining": "7777"}

    if helper_name == "make_blockscout_request":
        response = _MockResponse({"ok": True}, headers=credits_header)
        client = _GetClient(response)
        call_kwargs = {
            "request_function": common_module.make_blockscout_request,
            "call_args": {"chain_id": "1", "api_path": "/api/v2/blocks/1"},
            "client_patch": client,
            "method": "get",
        }
    elif helper_name == "make_blockscout_post_request":
        response = _MockResponse({"ok": True}, headers=credits_header)
        client = _PostClient(response)
        call_kwargs = {
            "request_function": common_module.make_blockscout_post_request,
            "call_args": {"chain_id": "1", "api_path": "/json-rpc", "json_body": {"x": 1}},
            "client_patch": client,
            "method": "post",
        }
    else:  # make_metadata_request
        request = httpx.Request("GET", "https://api.blockscout.com/metadata")
        real_response = httpx.Response(200, json={"ok": True}, request=request, headers=credits_header)

        class _MetaClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return None

            async def get(self, url, **kwargs):
                return real_response

        client = _MetaClient()
        call_kwargs = {
            "request_function": common_module.make_metadata_request,
            "call_args": {"api_path": "/api/v1/metadata/address"},
            "client_patch": client,
            "method": "get",
        }

    sink = CreditSink()

    with _set_sink(sink):
        with (
            patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=call_kwargs["client_patch"]),
            patch("blockscout_mcp_server.tools.common.ensure_chain_supported", AsyncMock()),
            patch.object(config, "pro_api_key", "test_key"),
        ):
            await call_kwargs["request_function"](**call_kwargs["call_args"])

    assert sink.remaining == 7777.0, f"{helper_name} did not capture credits"


# ---------------------------------------------------------------------------
# Cross-task visibility: make_request_with_periodic_progress
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cross_task_visibility_via_periodic_progress(mock_ctx):
    """Credit captured in a child task spawned by make_request_with_periodic_progress is visible to the parent.

    make_request_with_periodic_progress uses an anyio task group internally.
    The child task runs in a copied context, but shares the same CreditSink
    object reference, so mutations are visible to the parent.
    """
    from blockscout_mcp_server.tools.common import make_blockscout_request, make_request_with_periodic_progress

    sink = CreditSink()
    response = _MockResponse({"data": "ok"}, headers={"x-credits-remaining": "3333"})

    with _set_sink(sink):
        with (
            patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=_SimpleClient(response)),
            patch("blockscout_mcp_server.tools.common.ensure_chain_supported", AsyncMock()),
            patch.object(config, "pro_api_key", "test_key"),
        ):
            result = await make_request_with_periodic_progress(
                ctx=mock_ctx,
                request_function=make_blockscout_request,
                request_args={"chain_id": "1", "api_path": "/api/v2/blocks/1"},
                total_duration_hint=30.0,
            )

    assert result == {"data": "ok"}
    # The value written by the child task must be visible on the parent's sink.
    assert sink.remaining == 3333.0
    # Progress must be reported via the periodic-progress helper.
    assert mock_ctx.report_progress.call_count > 0


# ---------------------------------------------------------------------------
# Cross-task visibility: asyncio.gather (two concurrent requests)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cross_task_visibility_via_asyncio_gather():
    """Concurrent requests via asyncio.gather both write to the shared sink; minimum is recorded.

    Two concurrent GET requests return different x-credits-remaining values.
    The sink must end up with the minimum of the two.
    """
    from blockscout_mcp_server.tools.common import make_blockscout_request

    sink = CreditSink()

    response_high = _MockResponse({"seq": "high"}, headers={"x-credits-remaining": "9000"})
    response_low = _MockResponse({"seq": "low"}, headers={"x-credits-remaining": "2000"})
    responses = [response_high, response_low]
    call_count = {"n": 0}

    class _AlternatingClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, **kwargs):
            idx = call_count["n"]
            call_count["n"] += 1
            return responses[idx % len(responses)]

    with _set_sink(sink):
        with (
            patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=_AlternatingClient()),
            patch("blockscout_mcp_server.tools.common.ensure_chain_supported", AsyncMock()),
            patch.object(config, "pro_api_key", "test_key"),
        ):
            results = await asyncio.gather(
                make_blockscout_request("1", "/api/v2/blocks/1"),
                make_blockscout_request("1", "/api/v2/blocks/2"),
            )

    assert len(results) == 2
    # Minimum of 9000 and 2000 must be recorded.
    assert sink.remaining == 2000.0
