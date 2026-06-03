# SPDX-License-Identifier: LicenseRef-Blockscout
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from blockscout_mcp_server.config import config
from blockscout_mcp_server.models import ContractAbiData, ToolResponse
from blockscout_mcp_server.tools.common import ChainNotFoundError
from blockscout_mcp_server.tools.contract.get_contract_abi import get_contract_abi


def assert_contract_abi_response(result: ToolResponse, expected_abi) -> None:
    """Verify the wrapper structure and ABI data."""
    assert isinstance(result, ToolResponse)
    assert isinstance(result.data, ContractAbiData)
    assert result.data.abi == expected_abi


@pytest.mark.asyncio
async def test_get_contract_abi_success(mock_ctx):
    """
    Verify get_contract_abi correctly processes a successful ABI retrieval.
    """
    # ARRANGE
    chain_id = "1"
    address = "0xa0b86a33e6dd0ba3c70de3b8e2b9e48cd6efb7b0"

    mock_abi_list = [
        {
            "inputs": [],
            "name": "symbol",
            "outputs": [{"internalType": "string", "name": "", "type": "string"}],
            "stateMutability": "view",
            "type": "function",
        },
        {
            "inputs": [],
            "name": "name",
            "outputs": [{"internalType": "string", "name": "", "type": "string"}],
            "stateMutability": "view",
            "type": "function",
        },
    ]
    mock_api_response = {"abi": mock_abi_list}

    with patch(
        "blockscout_mcp_server.tools.contract.get_contract_abi.make_blockscout_request",
        new_callable=AsyncMock,
    ) as mock_request:
        mock_request.return_value = mock_api_response

        # ACT
        result = await get_contract_abi(chain_id=chain_id, address=address, ctx=mock_ctx)

        # ASSERT
        mock_request.assert_called_once_with(
            chain_id=chain_id,
            api_path=f"/api/v2/smart-contracts/{address}",
            timeout=config.bs_light_timeout,
        )
        assert_contract_abi_response(result, mock_abi_list)
        assert mock_ctx.report_progress.await_count == 2
        assert mock_ctx.info.await_count == 2
        progress_calls = mock_ctx.report_progress.await_args_list
        assert [call.kwargs["progress"] for call in progress_calls] == [0.0, 1.0]
        assert [call.kwargs["total"] for call in progress_calls] == [1.0, 1.0]
        info_messages = [call.args[0] for call in mock_ctx.info.await_args_list]
        assert "Starting to fetch contract ABI for 0xa0b86a33e6dd0ba3c70de3b8e2b9e48cd6efb7b0" in info_messages[0]
        assert "Successfully fetched contract ABI." in info_messages[1]


@pytest.mark.asyncio
async def test_get_contract_abi_missing_abi_field(mock_ctx):
    """
    Verify get_contract_abi handles response without abi field.
    """
    # ARRANGE
    chain_id = "1"
    address = "0xa0b86a33e6dd0ba3c70de3b8e2b9e48cd6efb7b0"

    mock_api_response = {}  # No abi field

    with patch(
        "blockscout_mcp_server.tools.contract.get_contract_abi.make_blockscout_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = mock_api_response

        # ACT
        result = await get_contract_abi(chain_id=chain_id, address=address, ctx=mock_ctx)

        # ASSERT
        mock_request.assert_called_once_with(
            chain_id=chain_id,
            api_path=f"/api/v2/smart-contracts/{address}",
            timeout=config.bs_light_timeout,
        )
        assert_contract_abi_response(result, None)
        assert mock_ctx.report_progress.await_count == 2
        assert mock_ctx.info.await_count == 2
        progress_calls = mock_ctx.report_progress.await_args_list
        assert [call.kwargs["progress"] for call in progress_calls] == [0.0, 1.0]
        assert [call.kwargs["total"] for call in progress_calls] == [1.0, 1.0]
        info_messages = [call.args[0] for call in mock_ctx.info.await_args_list]
        assert "Starting to fetch contract ABI for 0xa0b86a33e6dd0ba3c70de3b8e2b9e48cd6efb7b0" in info_messages[0]
        assert "Successfully fetched contract ABI." in info_messages[1]


@pytest.mark.asyncio
async def test_get_contract_abi_empty_abi(mock_ctx):
    """
    Verify get_contract_abi handles empty abi array.
    """
    # ARRANGE
    chain_id = "1"
    address = "0xa0b86a33e6dd0ba3c70de3b8e2b9e48cd6efb7b0"

    mock_api_response = {"abi": []}

    with patch(
        "blockscout_mcp_server.tools.contract.get_contract_abi.make_blockscout_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = mock_api_response

        # ACT
        result = await get_contract_abi(chain_id=chain_id, address=address, ctx=mock_ctx)

        # ASSERT
        mock_request.assert_called_once_with(
            chain_id=chain_id,
            api_path=f"/api/v2/smart-contracts/{address}",
            timeout=config.bs_light_timeout,
        )
        assert_contract_abi_response(result, [])
        assert mock_ctx.report_progress.await_count == 2
        assert mock_ctx.info.await_count == 2
        progress_calls = mock_ctx.report_progress.await_args_list
        assert [call.kwargs["progress"] for call in progress_calls] == [0.0, 1.0]
        assert [call.kwargs["total"] for call in progress_calls] == [1.0, 1.0]
        info_messages = [call.args[0] for call in mock_ctx.info.await_args_list]
        assert "Starting to fetch contract ABI for 0xa0b86a33e6dd0ba3c70de3b8e2b9e48cd6efb7b0" in info_messages[0]
        assert "Successfully fetched contract ABI." in info_messages[1]


@pytest.mark.asyncio
async def test_get_contract_abi_api_error(mock_ctx):
    """
    Verify get_contract_abi correctly propagates API errors.
    """
    # ARRANGE
    chain_id = "1"
    address = "0xa0b86a33e6dd0ba3c70de3b8e2b9e48cd6efb7b0"

    api_error = httpx.HTTPStatusError("Not Found", request=MagicMock(), response=MagicMock(status_code=404))

    with patch(
        "blockscout_mcp_server.tools.contract.get_contract_abi.make_blockscout_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = api_error

        # ACT & ASSERT
        with pytest.raises(httpx.HTTPStatusError):
            await get_contract_abi(chain_id=chain_id, address=address, ctx=mock_ctx)

        mock_request.assert_called_once_with(
            chain_id=chain_id,
            api_path=f"/api/v2/smart-contracts/{address}",
            timeout=config.bs_light_timeout,
        )
        assert mock_ctx.report_progress.await_count == 1  # 0.0 only
        infos = [c.args[0] for c in mock_ctx.info.await_args_list]
        assert any("Starting to fetch contract ABI" in message for message in infos)
        assert not any("Successfully fetched contract ABI." in message for message in infos)


@pytest.mark.asyncio
async def test_get_contract_abi_chain_not_found(mock_ctx):
    """
    Verify get_contract_abi correctly handles chain not found errors.
    """
    # ARRANGE
    chain_id = "999999"
    address = "0xa0b86a33e6dd0ba3c70de3b8e2b9e48cd6efb7b0"

    chain_error = ChainNotFoundError(f"Chain with ID '{chain_id}' not found on Chainscout.")

    with patch(
        "blockscout_mcp_server.tools.contract.get_contract_abi.make_blockscout_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = chain_error

        # ACT & ASSERT
        with pytest.raises(ChainNotFoundError):
            await get_contract_abi(chain_id=chain_id, address=address, ctx=mock_ctx)

        mock_request.assert_called_once_with(
            chain_id=chain_id,
            api_path=f"/api/v2/smart-contracts/{address}",
            timeout=config.bs_light_timeout,
        )
        assert mock_ctx.report_progress.await_count == 1
        assert mock_ctx.report_progress.await_args_list[0].kwargs["progress"] == 0.0


@pytest.mark.asyncio
async def test_get_contract_abi_invalid_address_format(mock_ctx):
    """
    Verify get_contract_abi works with various address formats.
    """
    # ARRANGE
    chain_id = "1"
    address = "invalid-address"  # Invalid format, but should still be passed through

    # The API might return an error for invalid address, but that's API's responsibility
    api_error = httpx.HTTPStatusError("Bad Request", request=MagicMock(), response=MagicMock(status_code=400))

    with patch(
        "blockscout_mcp_server.tools.contract.get_contract_abi.make_blockscout_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = api_error

        # ACT & ASSERT
        with pytest.raises(httpx.HTTPStatusError):
            await get_contract_abi(chain_id=chain_id, address=address, ctx=mock_ctx)

        mock_request.assert_called_once_with(
            chain_id=chain_id,
            api_path=f"/api/v2/smart-contracts/{address}",
            timeout=config.bs_light_timeout,
        )
        assert mock_ctx.report_progress.await_count == 1


@pytest.mark.asyncio
async def test_get_contract_abi_complex_abi(mock_ctx):
    """
    Verify get_contract_abi handles complex ABI with multiple function types.
    """
    # ARRANGE
    chain_id = "1"
    address = "0xa0b86a33e6dd0ba3c70de3b8e2b9e48cd6efb7b0"

    mock_api_response = {
        "abi": [
            {
                "inputs": [{"internalType": "string", "name": "_name", "type": "string"}],
                "stateMutability": "nonpayable",
                "type": "constructor",
            },
            {
                "anonymous": False,
                "inputs": [
                    {"indexed": True, "internalType": "address", "name": "from", "type": "address"},
                    {"indexed": True, "internalType": "address", "name": "to", "type": "address"},
                    {"indexed": False, "internalType": "uint256", "name": "value", "type": "uint256"},
                ],
                "name": "Transfer",
                "type": "event",
            },
            {
                "inputs": [
                    {"internalType": "address", "name": "to", "type": "address"},
                    {"internalType": "uint256", "name": "amount", "type": "uint256"},
                ],
                "name": "transfer",
                "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
                "stateMutability": "nonpayable",
                "type": "function",
            },
        ]
    }

    mock_abi_list = mock_api_response["abi"]

    with patch(
        "blockscout_mcp_server.tools.contract.get_contract_abi.make_blockscout_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = mock_api_response

        # ACT
        result = await get_contract_abi(chain_id=chain_id, address=address, ctx=mock_ctx)

        # ASSERT
        mock_request.assert_called_once_with(
            chain_id=chain_id,
            api_path=f"/api/v2/smart-contracts/{address}",
            timeout=config.bs_light_timeout,
        )
        assert_contract_abi_response(result, mock_abi_list)
        assert mock_ctx.report_progress.await_count == 2
        assert mock_ctx.info.await_count == 2
        progress_calls = mock_ctx.report_progress.await_args_list
        assert [call.kwargs["progress"] for call in progress_calls] == [0.0, 1.0]
        info_messages = [call.args[0] for call in mock_ctx.info.await_args_list]
        assert "Starting to fetch contract ABI for 0xa0b86a33e6dd0ba3c70de3b8e2b9e48cd6efb7b0" in info_messages[0]
        assert "Successfully fetched contract ABI." in info_messages[1]
