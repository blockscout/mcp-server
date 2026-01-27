from unittest.mock import AsyncMock

import httpx
import pytest

from tests.integration.helpers import retry_on_network_error


def make_request() -> httpx.Request:
    return httpx.Request("GET", "https://example.com")


def make_http_status_error(status_code: int) -> httpx.HTTPStatusError:
    request = make_request()
    response = httpx.Response(status_code=status_code, request=request)
    return httpx.HTTPStatusError("status error", request=request, response=response)


@pytest.mark.asyncio
async def test_retry_on_network_error_success_first_attempt():
    action = AsyncMock(return_value="ok")

    result = await retry_on_network_error(
        action,
        action_description="successful request",
    )

    assert result == "ok"
    assert action.call_count == 1


@pytest.mark.asyncio
async def test_retry_on_network_error_retries_request_errors_then_succeeds():
    request = make_request()
    action = AsyncMock(
        side_effect=[
            httpx.RequestError("boom", request=request),
            httpx.RequestError("boom", request=request),
            "ok",
        ]
    )

    result = await retry_on_network_error(
        action,
        action_description="request with retries",
        delay_seconds=0,
    )

    assert result == "ok"
    assert action.call_count == 3


@pytest.mark.asyncio
async def test_retry_on_network_error_skips_after_request_errors_exhausted():
    request = make_request()
    action = AsyncMock(
        side_effect=[
            httpx.RequestError("boom", request=request),
            httpx.RequestError("boom", request=request),
            httpx.RequestError("boom", request=request),
        ]
    )

    with pytest.raises(pytest.skip.Exception):
        await retry_on_network_error(
            action,
            action_description="request with retries",
            delay_seconds=0,
        )

    assert action.call_count == 3


@pytest.mark.asyncio
async def test_retry_on_network_error_retries_server_errors_then_succeeds():
    action = AsyncMock(
        side_effect=[
            make_http_status_error(500),
            make_http_status_error(500),
            "ok",
        ]
    )

    result = await retry_on_network_error(
        action,
        action_description="server errors",
        delay_seconds=0,
    )

    assert result == "ok"
    assert action.call_count == 3


@pytest.mark.asyncio
async def test_retry_on_network_error_skips_after_server_errors_exhausted():
    action = AsyncMock(
        side_effect=[
            make_http_status_error(503),
            make_http_status_error(503),
            make_http_status_error(503),
        ]
    )

    with pytest.raises(pytest.skip.Exception):
        await retry_on_network_error(
            action,
            action_description="server errors",
            delay_seconds=0,
        )

    assert action.call_count == 3


@pytest.mark.asyncio
async def test_retry_on_network_error_raises_on_client_error():
    action = AsyncMock(side_effect=[make_http_status_error(404)])

    with pytest.raises(httpx.HTTPStatusError):
        await retry_on_network_error(
            action,
            action_description="client error",
        )

    assert action.call_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [500, 502, 503, 504])
async def test_retry_on_network_error_retries_each_retryable_status(status_code):
    action = AsyncMock(
        side_effect=[
            make_http_status_error(status_code),
            make_http_status_error(status_code),
            make_http_status_error(status_code),
        ]
    )

    with pytest.raises(pytest.skip.Exception):
        await retry_on_network_error(
            action,
            action_description="server errors",
            delay_seconds=0,
        )

    assert action.call_count == 3
