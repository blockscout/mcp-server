# SPDX-License-Identifier: LicenseRef-Blockscout
from unittest.mock import AsyncMock, patch

import pytest

from blockscout_mcp_server.tools.common import ChainNotFoundError, ensure_chain_supported

pytestmark = pytest.mark.anyio


async def test_ensure_chain_supported_supported_chain():
    """Supported chain: call completes without raising."""
    with patch(
        "blockscout_mcp_server.tools.common.ensure_pro_api_config",
        AsyncMock(return_value={"1": "https://eth.blockscout.com"}),
    ):
        # Should not raise
        await ensure_chain_supported("1")


async def test_ensure_chain_supported_unsupported_chain():
    """Unsupported chain: raises ChainNotFoundError with correct message."""
    with patch(
        "blockscout_mcp_server.tools.common.ensure_pro_api_config",
        AsyncMock(return_value={"1": "https://eth.blockscout.com"}),
    ):
        with pytest.raises(ChainNotFoundError, match="Chain ID '99999' is not supported by the Blockscout API."):
            await ensure_chain_supported("99999")


async def test_ensure_chain_supported_delegates_to_ensure_pro_api_config():
    """The helper relies on ensure_pro_api_config (it must be awaited)."""
    mock_ensure = AsyncMock(return_value={"1": "https://eth.blockscout.com"})
    with patch(
        "blockscout_mcp_server.tools.common.ensure_pro_api_config",
        mock_ensure,
    ):
        await ensure_chain_supported("1")
        mock_ensure.assert_awaited_once()
