import httpx
import pytest

from blockscout_mcp_server.tools.block.get_block_number import get_block_number


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_block_number_latest_real(mock_ctx):
    """Test that get_block_number returns a latest block number and timestamp."""
    max_retries = 3
    result = None
    last_exc: Exception | None = None
    for attempt in range(max_retries):
        try:
            result = await get_block_number(chain_id="1", ctx=mock_ctx)
            break
        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            last_exc = exc
            if attempt == max_retries - 1:
                pytest.skip(f"Network connectivity issue after {max_retries} attempts: {exc}")
    if result is None:
        message = f"Network connectivity issue after {max_retries} attempts."
        if last_exc is not None:
            message = f"{message} {last_exc}"
        pytest.skip(message)
    assert isinstance(result.data.block_number, int)
    assert result.data.block_number > 0
    assert isinstance(result.data.timestamp, str)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_block_number_by_time_real(mock_ctx):
    """Test that get_block_number resolves a block by datetime."""
    max_retries = 3
    result = None
    last_exc: Exception | None = None
    for attempt in range(max_retries):
        try:
            result = await get_block_number(chain_id="1", ctx=mock_ctx, datetime="2023-01-01T00:00:00Z")
            break
        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            last_exc = exc
            if attempt == max_retries - 1:
                pytest.skip(f"Network connectivity issue after {max_retries} attempts: {exc}")
    if result is None:
        message = f"Network connectivity issue after {max_retries} attempts."
        if last_exc is not None:
            message = f"{message} {last_exc}"
        pytest.skip(message)
    assert isinstance(result.data.block_number, int)
    assert result.data.block_number > 0
    assert isinstance(result.data.timestamp, str)
