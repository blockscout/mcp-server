# tests/tools/test_contract_tools.py
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import httpx

from blockscout_mcp_server.tools.contract_tools import get_contract_abi

@pytest.mark.asyncio
async def test_get_contract_abi_success(mock_ctx):
    """
    Verify get_contract_abi correctly processes a successful ABI retrieval.
    """
    # ARRANGE
    chain_id = "1"
    address = "0xa0b86a33e6dd0ba3c70de3b8e2b9e48cd6efb7b0"
    mock_base_url = "https://eth.blockscout.com"

    mock_api_response = {
        "abi": [
            {
                "inputs": [],
                "name": "symbol",
                "outputs": [{"internalType": "string", "name": "", "type": "string"}],
                "stateMutability": "view",
                "type": "function"
            },
            {
                "inputs": [],
                "name": "name",
                "outputs": [{"internalType": "string", "name": "", "type": "string"}],
                "stateMutability": "view",
                "type": "function"
            }
        ]
    }

    expected_result = {
        "abi": [
            {
                "inputs": [],
                "name": "symbol",
                "outputs": [{"internalType": "string", "name": "", "type": "string"}],
                "stateMutability": "view",
                "type": "function"
            },
            {
                "inputs": [],
                "name": "name",
                "outputs": [{"internalType": "string", "name": "", "type": "string"}],
                "stateMutability": "view",
                "type": "function"
            }
        ]
    }

    with patch('blockscout_mcp_server.tools.contract_tools.get_blockscout_base_url', new_callable=AsyncMock) as mock_get_url, \
         patch('blockscout_mcp_server.tools.contract_tools.make_blockscout_request', new_callable=AsyncMock) as mock_request:

        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response

        # ACT
        result = await get_contract_abi(chain_id=chain_id, address=address, ctx=mock_ctx)

        # ASSERT
        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(
            base_url=mock_base_url,
            api_path=f"/api/v2/smart-contracts/{address}"
        )
        assert result == expected_result
        assert mock_ctx.report_progress.call_count == 3
        assert mock_ctx.info.call_count == 3

@pytest.mark.asyncio
async def test_get_contract_abi_missing_abi_field(mock_ctx):
    """
    Verify get_contract_abi handles response without abi field.
    """
    # ARRANGE
    chain_id = "1"
    address = "0xa0b86a33e6dd0ba3c70de3b8e2b9e48cd6efb7b0"
    mock_base_url = "https://eth.blockscout.com"

    mock_api_response = {}  # No abi field
    expected_result = {"abi": None}

    with patch('blockscout_mcp_server.tools.contract_tools.get_blockscout_base_url', new_callable=AsyncMock) as mock_get_url, \
         patch('blockscout_mcp_server.tools.contract_tools.make_blockscout_request', new_callable=AsyncMock) as mock_request:

        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response

        # ACT
        result = await get_contract_abi(chain_id=chain_id, address=address, ctx=mock_ctx)

        # ASSERT
        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(
            base_url=mock_base_url,
            api_path=f"/api/v2/smart-contracts/{address}"
        )
        assert result == expected_result
        assert mock_ctx.report_progress.call_count == 3
        assert mock_ctx.info.call_count == 3

@pytest.mark.asyncio
async def test_get_contract_abi_empty_abi(mock_ctx):
    """
    Verify get_contract_abi handles empty abi array.
    """
    # ARRANGE
    chain_id = "1"
    address = "0xa0b86a33e6dd0ba3c70de3b8e2b9e48cd6efb7b0"
    mock_base_url = "https://eth.blockscout.com"

    mock_api_response = {"abi": []}
    expected_result = {"abi": []}

    with patch('blockscout_mcp_server.tools.contract_tools.get_blockscout_base_url', new_callable=AsyncMock) as mock_get_url, \
         patch('blockscout_mcp_server.tools.contract_tools.make_blockscout_request', new_callable=AsyncMock) as mock_request:

        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response

        # ACT
        result = await get_contract_abi(chain_id=chain_id, address=address, ctx=mock_ctx)

        # ASSERT
        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(
            base_url=mock_base_url,
            api_path=f"/api/v2/smart-contracts/{address}"
        )
        assert result == expected_result
        assert mock_ctx.report_progress.call_count == 3

@pytest.mark.asyncio
async def test_get_contract_abi_api_error(mock_ctx):
    """
    Verify get_contract_abi correctly propagates API errors.
    """
    # ARRANGE
    chain_id = "1"
    address = "0xa0b86a33e6dd0ba3c70de3b8e2b9e48cd6efb7b0"
    mock_base_url = "https://eth.blockscout.com"

    api_error = httpx.HTTPStatusError("Not Found", request=MagicMock(), response=MagicMock(status_code=404))

    with patch('blockscout_mcp_server.tools.contract_tools.get_blockscout_base_url', new_callable=AsyncMock) as mock_get_url, \
         patch('blockscout_mcp_server.tools.contract_tools.make_blockscout_request', new_callable=AsyncMock) as mock_request:

        mock_get_url.return_value = mock_base_url
        mock_request.side_effect = api_error

        # ACT & ASSERT
        with pytest.raises(httpx.HTTPStatusError):
            await get_contract_abi(chain_id=chain_id, address=address, ctx=mock_ctx)

        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(
            base_url=mock_base_url,
            api_path=f"/api/v2/smart-contracts/{address}"
        )

@pytest.mark.asyncio
async def test_get_contract_abi_chain_not_found(mock_ctx):
    """
    Verify get_contract_abi correctly handles chain not found errors.
    """
    # ARRANGE
    chain_id = "999999"
    address = "0xa0b86a33e6dd0ba3c70de3b8e2b9e48cd6efb7b0"

    from blockscout_mcp_server.tools.common import ChainNotFoundError
    chain_error = ChainNotFoundError(f"Chain with ID '{chain_id}' not found on Chainscout.")

    with patch('blockscout_mcp_server.tools.contract_tools.get_blockscout_base_url', new_callable=AsyncMock) as mock_get_url:
        mock_get_url.side_effect = chain_error

        # ACT & ASSERT
        with pytest.raises(ChainNotFoundError):
            await get_contract_abi(chain_id=chain_id, address=address, ctx=mock_ctx)

        mock_get_url.assert_called_once_with(chain_id)

@pytest.mark.asyncio
async def test_get_contract_abi_invalid_address_format(mock_ctx):
    """
    Verify get_contract_abi works with various address formats.
    """
    # ARRANGE
    chain_id = "1"
    address = "invalid-address"  # Invalid format, but should still be passed through
    mock_base_url = "https://eth.blockscout.com"

    # The API might return an error for invalid address, but that's API's responsibility
    api_error = httpx.HTTPStatusError("Bad Request", request=MagicMock(), response=MagicMock(status_code=400))

    with patch('blockscout_mcp_server.tools.contract_tools.get_blockscout_base_url', new_callable=AsyncMock) as mock_get_url, \
         patch('blockscout_mcp_server.tools.contract_tools.make_blockscout_request', new_callable=AsyncMock) as mock_request:

        mock_get_url.return_value = mock_base_url
        mock_request.side_effect = api_error

        # ACT & ASSERT
        with pytest.raises(httpx.HTTPStatusError):
            await get_contract_abi(chain_id=chain_id, address=address, ctx=mock_ctx)

        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(
            base_url=mock_base_url,
            api_path=f"/api/v2/smart-contracts/{address}"
        )

@pytest.mark.asyncio
async def test_get_contract_abi_complex_abi(mock_ctx):
    """
    Verify get_contract_abi handles complex ABI with multiple function types.
    """
    # ARRANGE
    chain_id = "1"
    address = "0xa0b86a33e6dd0ba3c70de3b8e2b9e48cd6efb7b0"
    mock_base_url = "https://eth.blockscout.com"

    mock_api_response = {
        "abi": [
            {
                "inputs": [{"internalType": "string", "name": "_name", "type": "string"}],
                "stateMutability": "nonpayable",
                "type": "constructor"
            },
            {
                "anonymous": False,
                "inputs": [
                    {"indexed": True, "internalType": "address", "name": "from", "type": "address"},
                    {"indexed": True, "internalType": "address", "name": "to", "type": "address"},
                    {"indexed": False, "internalType": "uint256", "name": "value", "type": "uint256"}
                ],
                "name": "Transfer",
                "type": "event"
            },
            {
                "inputs": [
                    {"internalType": "address", "name": "to", "type": "address"},
                    {"internalType": "uint256", "name": "amount", "type": "uint256"}
                ],
                "name": "transfer",
                "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
                "stateMutability": "nonpayable",
                "type": "function"
            }
        ]
    }

    expected_result = {
        "abi": [
            {
                "inputs": [{"internalType": "string", "name": "_name", "type": "string"}],
                "stateMutability": "nonpayable",
                "type": "constructor"
            },
            {
                "anonymous": False,
                "inputs": [
                    {"indexed": True, "internalType": "address", "name": "from", "type": "address"},
                    {"indexed": True, "internalType": "address", "name": "to", "type": "address"},
                    {"indexed": False, "internalType": "uint256", "name": "value", "type": "uint256"}
                ],
                "name": "Transfer",
                "type": "event"
            },
            {
                "inputs": [
                    {"internalType": "address", "name": "to", "type": "address"},
                    {"internalType": "uint256", "name": "amount", "type": "uint256"}
                ],
                "name": "transfer",
                "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
                "stateMutability": "nonpayable",
                "type": "function"
            }
        ]
    }

    with patch('blockscout_mcp_server.tools.contract_tools.get_blockscout_base_url', new_callable=AsyncMock) as mock_get_url, \
         patch('blockscout_mcp_server.tools.contract_tools.make_blockscout_request', new_callable=AsyncMock) as mock_request:

        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response

        # ACT
        result = await get_contract_abi(chain_id=chain_id, address=address, ctx=mock_ctx)

        # ASSERT
        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(
            base_url=mock_base_url,
            api_path=f"/api/v2/smart-contracts/{address}"
        )
        assert result == expected_result
        assert mock_ctx.report_progress.call_count == 3 