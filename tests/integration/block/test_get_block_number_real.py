# SPDX-License-Identifier: LicenseRef-Blockscout
"""Integration tests for get_block_number.

test_get_block_number_by_time_real is an exception to the convention used
elsewhere in tests/integration/ (stable deep-historical data on chain_id=1):
it queries "5 minutes ago" against Gnosis Chain (chain_id=100) to verify
datetime → block resolution on a fast-block-time chain. The other test in
this module follows the usual pattern.

If the by-time test fails intermittently, the indexer may briefly lag tip;
widen the offset (e.g. 5 → 30 minutes) before suspecting a real regression.
"""

from datetime import UTC, datetime, timedelta

import pytest

from blockscout_mcp_server.config import config
from blockscout_mcp_server.tools.block.get_block_number import get_block_number
from tests.integration.helpers import retry_on_network_error


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.skipif(not config.pro_api_key, reason="BLOCKSCOUT_PRO_API_KEY not configured")
async def test_get_block_number_latest_real(mock_ctx):
    """Test that get_block_number returns a latest block number and timestamp."""
    result = await retry_on_network_error(
        lambda: get_block_number(chain_id="1", ctx=mock_ctx),
        action_description="get_block_number latest request",
    )
    assert isinstance(result.data.block_number, int)
    assert result.data.block_number > 0
    assert isinstance(result.data.timestamp, str)


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.skipif(not config.pro_api_key, reason="BLOCKSCOUT_PRO_API_KEY not configured")
async def test_get_block_number_by_time_real(mock_ctx):
    """Test that get_block_number resolves a block by datetime."""
    target_datetime = (datetime.now(UTC) - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%S.00Z")
    result = await retry_on_network_error(
        lambda: get_block_number(chain_id="100", ctx=mock_ctx, datetime=target_datetime),
        action_description="get_block_number by datetime request",
    )
    assert isinstance(result.data.block_number, int)
    assert result.data.block_number > 0
    assert isinstance(result.data.timestamp, str)
