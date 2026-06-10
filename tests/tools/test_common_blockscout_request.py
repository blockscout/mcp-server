# SPDX-License-Identifier: LicenseRef-Blockscout
"""Focused tests for make_blockscout_request (GET helper) in tools/common.py.

Covers transport/error-parsing behaviour migrated from test_common.py,
plus the new fail-fast (missing PRO API key) and chain-validation guards
introduced when the helper was migrated to the PRO API.
"""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from blockscout_mcp_server.config import config
from blockscout_mcp_server.tools.common import ChainNotFoundError, CreditsExhaustedError, make_blockscout_request

# ---------------------------------------------------------------------------
# Fake httpx.AsyncClient for transport tests
# ---------------------------------------------------------------------------


class MockAsyncClient:
    """Minimal fake AsyncClient; get() accepts any kwargs so header-attaching
    helpers do not raise TypeError."""

    def __init__(self, response: httpx.Response) -> None:
        self._response = response
        self.request_params: dict | None = None
        self.request_url: str | None = None

    async def __aenter__(self) -> "MockAsyncClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def get(self, url: str, params: dict | None = None, **kwargs) -> httpx.Response:
        self.request_url = url
        self.request_params = params
        return self._response


_DEFAULT_URL = "https://api.blockscout.com/1/api/v2/test"


def _make_response(
    status: int,
    body: bytes | None = None,
    json_data: object = None,
    url: str = _DEFAULT_URL,
) -> httpx.Response:
    request = httpx.Request("GET", url)
    if json_data is not None:
        return httpx.Response(status, json=json_data, request=request)
    return httpx.Response(status, content=body or b"", request=request)


def _patch_guards(key: str = "test_pro_key"):
    """Return a pair of context managers: non-empty key + stubbed chain check."""
    patch_key = patch.object(config, "pro_api_key", key)
    stub_chain = patch("blockscout_mcp_server.tools.common.ensure_chain_supported", AsyncMock())
    return patch_key, stub_chain


# ---------------------------------------------------------------------------
# Transport / error-parsing tests (migrated from test_common.py)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_make_blockscout_request_json_api_error_sort():
    """Verify JSON:API errors include title, detail, and pointer."""
    response = _make_response(
        422,
        json_data={
            "errors": [
                {
                    "title": "Invalid value",
                    "source": {"pointer": "/sort"},
                    "detail": "Unexpected field: sort",
                }
            ]
        },
    )
    patch_key, stub_chain = _patch_guards()
    with patch_key, stub_chain:
        with patch(
            "blockscout_mcp_server.tools.common._create_httpx_client",
            return_value=MockAsyncClient(response),
        ):
            with pytest.raises(httpx.HTTPStatusError) as exc_info:
                await make_blockscout_request(chain_id="1", api_path="/api/v2/test")

    assert "422 Unprocessable Entity - Details: Invalid value: Unexpected field: sort (at /sort)" in str(exc_info.value)


@pytest.mark.asyncio
async def test_make_blockscout_request_json_api_error_address_format():
    """Verify JSON:API errors include pointer details for address fields."""
    response = _make_response(
        422,
        json_data={
            "errors": [
                {
                    "title": "Invalid value",
                    "source": {"pointer": "/address_hash_param"},
                    "detail": "Invalid format",
                }
            ]
        },
    )
    patch_key, stub_chain = _patch_guards()
    with patch_key, stub_chain:
        with patch(
            "blockscout_mcp_server.tools.common._create_httpx_client",
            return_value=MockAsyncClient(response),
        ):
            with pytest.raises(httpx.HTTPStatusError) as exc_info:
                await make_blockscout_request(chain_id="1", api_path="/api/v2/test")

    assert "Details: Invalid value: Invalid format (at /address_hash_param)" in str(exc_info.value)


@pytest.mark.asyncio
async def test_make_blockscout_request_simple_json_error_message():
    """Verify message fields are surfaced for generic JSON errors."""
    response = _make_response(400, json_data={"message": "Invalid chain ID"})
    patch_key, stub_chain = _patch_guards()
    with patch_key, stub_chain:
        with patch(
            "blockscout_mcp_server.tools.common._create_httpx_client",
            return_value=MockAsyncClient(response),
        ):
            with pytest.raises(httpx.HTTPStatusError) as exc_info:
                await make_blockscout_request(chain_id="1", api_path="/api/v2/test")

    assert "Details: Invalid chain ID" in str(exc_info.value)


@pytest.mark.asyncio
async def test_make_blockscout_request_error_field_fallback():
    """Verify error fields are surfaced when provided."""
    response = _make_response(400, json_data={"error": "Some error text"})
    patch_key, stub_chain = _patch_guards()
    with patch_key, stub_chain:
        with patch(
            "blockscout_mcp_server.tools.common._create_httpx_client",
            return_value=MockAsyncClient(response),
        ):
            with pytest.raises(httpx.HTTPStatusError) as exc_info:
                await make_blockscout_request(chain_id="1", api_path="/api/v2/test")

    assert "Details: Some error text" in str(exc_info.value)


@pytest.mark.asyncio
async def test_make_blockscout_request_errors_string_items():
    """Verify string items in errors array are included."""
    response = _make_response(422, json_data={"errors": ["Simple error message"]})
    patch_key, stub_chain = _patch_guards()
    with patch_key, stub_chain:
        with patch(
            "blockscout_mcp_server.tools.common._create_httpx_client",
            return_value=MockAsyncClient(response),
        ):
            with pytest.raises(httpx.HTTPStatusError) as exc_info:
                await make_blockscout_request(chain_id="1", api_path="/api/v2/test")

    assert "Details: Simple error message" in str(exc_info.value)


@pytest.mark.asyncio
async def test_make_blockscout_request_errors_title_no_detail():
    """Verify errors with title but empty detail are formatted consistently."""
    response = _make_response(
        422,
        json_data={
            "errors": [
                {
                    "title": "Invalid value",
                    "source": {"pointer": "/sort"},
                    "detail": "",
                }
            ]
        },
    )
    patch_key, stub_chain = _patch_guards()
    with patch_key, stub_chain:
        with patch(
            "blockscout_mcp_server.tools.common._create_httpx_client",
            return_value=MockAsyncClient(response),
        ):
            with pytest.raises(httpx.HTTPStatusError) as exc_info:
                await make_blockscout_request(chain_id="1", api_path="/api/v2/test")

    assert "Details: Invalid value (at /sort)" in str(exc_info.value)


@pytest.mark.asyncio
async def test_make_blockscout_request_multiple_errors_joined():
    """Verify multiple errors are joined with semicolons."""
    response = _make_response(
        422,
        json_data={
            "errors": [
                {"title": "First error", "detail": "First detail", "source": {"pointer": "/first"}},
                {"title": "Second error", "detail": "Second detail"},
            ]
        },
    )
    patch_key, stub_chain = _patch_guards()
    with patch_key, stub_chain:
        with patch(
            "blockscout_mcp_server.tools.common._create_httpx_client",
            return_value=MockAsyncClient(response),
        ):
            with pytest.raises(httpx.HTTPStatusError) as exc_info:
                await make_blockscout_request(chain_id="1", api_path="/api/v2/test")

    message = str(exc_info.value)
    assert "First error: First detail (at /first); Second error: Second detail" in message


@pytest.mark.asyncio
async def test_make_blockscout_request_empty_details_message():
    """Verify empty bodies omit the details suffix."""
    response = _make_response(422, body=b"")
    patch_key, stub_chain = _patch_guards()
    with patch_key, stub_chain:
        with patch(
            "blockscout_mcp_server.tools.common._create_httpx_client",
            return_value=MockAsyncClient(response),
        ):
            with pytest.raises(httpx.HTTPStatusError) as exc_info:
                await make_blockscout_request(chain_id="1", api_path="/api/v2/test")

    assert str(exc_info.value).startswith("422 Unprocessable Entity")
    assert "Details:" not in str(exc_info.value)


@pytest.mark.asyncio
async def test_make_blockscout_request_raw_text_error_truncation():
    """Verify raw text errors are truncated to 200 characters."""
    html_body = "<html><body><h1>502 Bad Gateway</h1>" + ("a" * 250) + "</body></html>"
    response = _make_response(502, body=html_body.encode())
    patch_key, stub_chain = _patch_guards()
    with patch_key, stub_chain:
        with patch(
            "blockscout_mcp_server.tools.common._create_httpx_client",
            return_value=MockAsyncClient(response),
        ):
            with pytest.raises(httpx.HTTPStatusError) as exc_info:
                await make_blockscout_request(chain_id="1", api_path="/api/v2/test")

    assert html_body[:200] in str(exc_info.value)


@pytest.mark.asyncio
async def test_make_blockscout_request_success():
    """Verify successful responses return JSON payloads."""
    response = _make_response(200, json_data={"result": "success"})
    patch_key, stub_chain = _patch_guards()
    with patch_key, stub_chain:
        with patch(
            "blockscout_mcp_server.tools.common._create_httpx_client",
            return_value=MockAsyncClient(response),
        ):
            result = await make_blockscout_request(chain_id="1", api_path="/api/v2/test")

    assert result == {"result": "success"}


@pytest.mark.asyncio
async def test_make_blockscout_request_returns_empty_dict_on_null_response():
    """Verify null JSON bodies return an empty dictionary."""
    request = httpx.Request("GET", "https://api.blockscout.com/1/api/v2/test")
    response = httpx.Response(200, content=b"null", request=request)
    patch_key, stub_chain = _patch_guards()
    with patch_key, stub_chain:
        with patch(
            "blockscout_mcp_server.tools.common._create_httpx_client",
            return_value=MockAsyncClient(response),
        ):
            result = await make_blockscout_request(chain_id="1", api_path="/api/v2/test")

    assert result == {}


# ---------------------------------------------------------------------------
# Fail-fast: missing PRO API key
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_make_blockscout_request_raises_when_no_pro_api_key(monkeypatch):
    """With no PRO API key, make_blockscout_request raises ValueError before any network call."""
    monkeypatch.setattr(config, "pro_api_key", "")

    def _fail(*args, **kwargs):
        raise AssertionError("No HTTP client should be created when PRO API key is absent")

    with patch("blockscout_mcp_server.tools.common._create_httpx_client", _fail):
        with pytest.raises(ValueError, match="PRO API key required"):
            await make_blockscout_request(chain_id="1", api_path="/api/v2/test")


@pytest.mark.asyncio
async def test_make_blockscout_post_request_raises_when_no_pro_api_key(monkeypatch):
    """With no PRO API key, make_blockscout_post_request raises ValueError before any network call."""
    from blockscout_mcp_server.tools.common import make_blockscout_post_request

    monkeypatch.setattr(config, "pro_api_key", "")

    def _fail(*args, **kwargs):
        raise AssertionError("No HTTP client should be created when PRO API key is absent")

    with patch("blockscout_mcp_server.tools.common._create_httpx_client", _fail):
        with pytest.raises(ValueError, match="PRO API key required"):
            await make_blockscout_post_request(chain_id="1", api_path="/json-rpc", json_body={})


# ---------------------------------------------------------------------------
# Chain validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_make_blockscout_request_raises_for_unsupported_chain(monkeypatch):
    """An unsupported chain_id raises ChainNotFoundError."""
    monkeypatch.setattr(config, "pro_api_key", "test_key")

    # Patch ensure_pro_api_config to return a map without the requested chain
    async def _fake_pro_api_config():
        return {"1": "https://api.blockscout.com/1"}

    def _fail(*args, **kwargs):
        raise AssertionError("No HTTP client should be created for unsupported chain")

    with (
        patch("blockscout_mcp_server.tools.common.ensure_pro_api_config", _fake_pro_api_config),
        patch("blockscout_mcp_server.tools.common._create_httpx_client", _fail),
    ):
        with pytest.raises(ChainNotFoundError):
            await make_blockscout_request(chain_id="99999", api_path="/api/v2/test")


@pytest.mark.asyncio
async def test_make_blockscout_post_request_raises_for_unsupported_chain(monkeypatch):
    """An unsupported chain_id raises ChainNotFoundError for POST requests."""
    from blockscout_mcp_server.tools.common import make_blockscout_post_request

    monkeypatch.setattr(config, "pro_api_key", "test_key")

    async def _fake_pro_api_config():
        return {"1": "https://api.blockscout.com/1"}

    def _fail(*args, **kwargs):
        raise AssertionError("No HTTP client should be created for unsupported chain")

    with (
        patch("blockscout_mcp_server.tools.common.ensure_pro_api_config", _fake_pro_api_config),
        patch("blockscout_mcp_server.tools.common._create_httpx_client", _fail),
    ):
        with pytest.raises(ChainNotFoundError):
            await make_blockscout_post_request(chain_id="99999", api_path="/json-rpc", json_body={})


# ---------------------------------------------------------------------------
# Authenticated-transport test for GET
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_make_blockscout_request_sends_auth_headers_to_pro_api(monkeypatch):
    """GET requests must carry auth headers and target the PRO API host.

    Mirrors the POST-side test in test_common_post_request.py. The other GET
    transport tests here use a header-swallowing client, so without this an
    implementation could build the wrong URL or drop the Bearer token on GET
    and still pass the unit suite.
    """
    monkeypatch.setattr(config, "pro_api_key", "get_test_key")
    chain_id = "1"
    api_path = "/api/v2/test"
    pro_base = config.pro_api_base_url

    captured: dict = {}

    class CapturingClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, params=None, headers=None, **kwargs):
            captured["url"] = url
            captured["headers"] = headers or {}
            request = httpx.Request("GET", url)
            return httpx.Response(200, json={"result": "ok"}, request=request)

    stub_ensure_chain_supported = AsyncMock()

    with (
        patch("blockscout_mcp_server.tools.common._create_httpx_client", return_value=CapturingClient()),
        patch("blockscout_mcp_server.tools.common.ensure_chain_supported", stub_ensure_chain_supported),
    ):
        result = await make_blockscout_request(chain_id=chain_id, api_path=api_path)

    assert result == {"result": "ok"}
    stub_ensure_chain_supported.assert_awaited_once_with(chain_id)
    assert captured["url"] == f"{pro_base}/{chain_id}{api_path}"
    assert captured["headers"].get("Authorization") == "Bearer get_test_key"
    assert "User-Agent" in captured["headers"]
    assert captured["headers"].get("Accept") == "application/json"


# ---------------------------------------------------------------------------
# CreditsExhaustedError: 402 → distinct error, no retry
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_make_blockscout_request_402_raises_credits_exhausted_error():
    """A 402 response raises CreditsExhaustedError (not HTTPStatusError) exactly once — no retry."""
    response = _make_response(402, json_data={"error": "Out of credits"})

    call_count = {"n": 0}

    class CountingClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url, params=None, **kwargs):
            call_count["n"] += 1
            return response

    patch_key, stub_chain = _patch_guards()
    with patch_key, stub_chain:
        with patch(
            "blockscout_mcp_server.tools.common._create_httpx_client",
            return_value=CountingClient(),
        ):
            with patch("blockscout_mcp_server.tools.common.anyio.sleep") as mock_sleep:
                with pytest.raises(CreditsExhaustedError) as excinfo:
                    await make_blockscout_request(chain_id="1", api_path="/api/v2/test")

    # Must NOT be an HTTPStatusError (wrong base class would silently mis-route in Phase 2)
    assert not isinstance(excinfo.value, httpx.HTTPStatusError)
    # Message must carry the actionable signals the MCP agent needs
    message = str(excinfo.value).lower()
    assert "credits" in message
    assert "402" in message
    assert "retry" in message
    # Must not retry: exactly one HTTP call, sleep never called
    assert call_count["n"] == 1
    mock_sleep.assert_not_called()


def test_credits_exhausted_error_is_exception_not_value_error():
    """CreditsExhaustedError must subclass Exception but NOT ValueError.

    This guards the Phase 2 design: handle_rest_errors has an `except ValueError → 400`
    branch; if CreditsExhaustedError were a ValueError subclass it would be mis-routed
    to 400 instead of 402.
    """
    assert issubclass(CreditsExhaustedError, Exception)
    assert not issubclass(CreditsExhaustedError, ValueError)
