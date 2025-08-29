# tests/tools/test_contract_tools.py
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from web3.exceptions import ContractLogicError

from blockscout_mcp_server.models import ContractAbiData, ToolResponse
from blockscout_mcp_server.tools.common import ChainNotFoundError
from blockscout_mcp_server.tools.contract_tools import get_contract_abi, read_contract


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
    mock_base_url = "https://eth.blockscout.com"

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

    with (
        patch(
            "blockscout_mcp_server.tools.contract_tools.get_blockscout_base_url",
            new_callable=AsyncMock,
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.contract_tools.make_blockscout_request",
            new_callable=AsyncMock,
        ) as mock_request,
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response

        # ACT
        result = await get_contract_abi(chain_id=chain_id, address=address, ctx=mock_ctx)

        # ASSERT
        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(base_url=mock_base_url, api_path=f"/api/v2/smart-contracts/{address}")
        assert_contract_abi_response(result, mock_abi_list)
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

    with (
        patch(
            "blockscout_mcp_server.tools.contract_tools.get_blockscout_base_url", new_callable=AsyncMock
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.contract_tools.make_blockscout_request", new_callable=AsyncMock
        ) as mock_request,
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response

        # ACT
        result = await get_contract_abi(chain_id=chain_id, address=address, ctx=mock_ctx)

        # ASSERT
        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(base_url=mock_base_url, api_path=f"/api/v2/smart-contracts/{address}")
        assert_contract_abi_response(result, None)
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

    with (
        patch(
            "blockscout_mcp_server.tools.contract_tools.get_blockscout_base_url", new_callable=AsyncMock
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.contract_tools.make_blockscout_request", new_callable=AsyncMock
        ) as mock_request,
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response

        # ACT
        result = await get_contract_abi(chain_id=chain_id, address=address, ctx=mock_ctx)

        # ASSERT
        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(base_url=mock_base_url, api_path=f"/api/v2/smart-contracts/{address}")
        assert_contract_abi_response(result, [])
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

    with (
        patch(
            "blockscout_mcp_server.tools.contract_tools.get_blockscout_base_url", new_callable=AsyncMock
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.contract_tools.make_blockscout_request", new_callable=AsyncMock
        ) as mock_request,
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.side_effect = api_error

        # ACT & ASSERT
        with pytest.raises(httpx.HTTPStatusError):
            await get_contract_abi(chain_id=chain_id, address=address, ctx=mock_ctx)

        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(base_url=mock_base_url, api_path=f"/api/v2/smart-contracts/{address}")


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

    with patch(
        "blockscout_mcp_server.tools.contract_tools.get_blockscout_base_url", new_callable=AsyncMock
    ) as mock_get_url:
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

    with (
        patch(
            "blockscout_mcp_server.tools.contract_tools.get_blockscout_base_url", new_callable=AsyncMock
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.contract_tools.make_blockscout_request", new_callable=AsyncMock
        ) as mock_request,
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.side_effect = api_error

        # ACT & ASSERT
        with pytest.raises(httpx.HTTPStatusError):
            await get_contract_abi(chain_id=chain_id, address=address, ctx=mock_ctx)

        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(base_url=mock_base_url, api_path=f"/api/v2/smart-contracts/{address}")


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

    with (
        patch(
            "blockscout_mcp_server.tools.contract_tools.get_blockscout_base_url", new_callable=AsyncMock
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.contract_tools.make_blockscout_request", new_callable=AsyncMock
        ) as mock_request,
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.return_value = mock_api_response

        # ACT
        result = await get_contract_abi(chain_id=chain_id, address=address, ctx=mock_ctx)

        # ASSERT
        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_called_once_with(base_url=mock_base_url, api_path=f"/api/v2/smart-contracts/{address}")
        assert_contract_abi_response(result, mock_abi_list)
        assert mock_ctx.report_progress.call_count == 3


@pytest.mark.asyncio
async def test_read_contract_success(mock_ctx):
    chain_id = "1"
    address = "0x0000000000000000000000000000000000000abc"
    function_name = "balanceOf"
    abi: dict[str, Any] = {
        "name": function_name,
        "type": "function",
        "inputs": [{"name": "owner", "type": "uint256"}],
        "outputs": [],
    }
    expected = 123

    fn_result = MagicMock()
    fn_result.call = AsyncMock(return_value=expected)
    fn_mock = MagicMock(return_value=fn_result)
    contract_mock = MagicMock()
    contract_mock.get_function_by_name.return_value = fn_mock
    w3_mock = MagicMock()
    w3_mock.eth.contract.return_value = contract_mock

    with patch(
        "blockscout_mcp_server.tools.contract_tools.WEB3_POOL.get",
        new_callable=AsyncMock,
        return_value=w3_mock,
    ) as mock_get:
        result = await read_contract(
            chain_id=chain_id,
            address=address,
            abi=abi,
            function_name=function_name,
            args='["1"]',
            block="latest",
            ctx=mock_ctx,
        )

    mock_get.assert_called_once_with(chain_id)
    contract_mock.get_function_by_name.assert_called_once_with(function_name)
    fn_mock.assert_called_once_with(1)
    fn_result.call.assert_awaited_once_with(block_identifier="latest")
    assert result.data.result == expected
    assert mock_ctx.report_progress.call_count == 3
    assert mock_ctx.info.call_count == 3


@pytest.mark.asyncio
async def test_read_contract_chain_not_found(mock_ctx):
    chain_id = "999"
    abi = {"name": "foo", "type": "function", "inputs": [], "outputs": []}
    with patch(
        "blockscout_mcp_server.tools.contract_tools.WEB3_POOL.get",
        new_callable=AsyncMock,
        side_effect=ChainNotFoundError("not found"),
    ) as mock_get:
        with pytest.raises(ChainNotFoundError):
            await read_contract(
                chain_id=chain_id,
                address="0x0000000000000000000000000000000000000abc",
                abi=abi,
                function_name="foo",
                ctx=mock_ctx,
            )
    mock_get.assert_called_once_with(chain_id)
    assert mock_ctx.report_progress.call_count == 1


@pytest.mark.asyncio
async def test_read_contract_contract_error(mock_ctx):
    abi = {"name": "foo", "type": "function", "inputs": [], "outputs": []}
    fn_result = MagicMock()
    fn_result.call = AsyncMock(side_effect=ContractLogicError("boom"))
    fn_mock = MagicMock(return_value=fn_result)
    contract_mock = MagicMock()
    contract_mock.get_function_by_name.return_value = fn_mock
    w3_mock = MagicMock()
    w3_mock.eth.contract.return_value = contract_mock

    with patch(
        "blockscout_mcp_server.tools.contract_tools.WEB3_POOL.get",
        new_callable=AsyncMock,
        return_value=w3_mock,
    ):
        with pytest.raises(RuntimeError):
            await read_contract(
                chain_id="1",
                address="0x0000000000000000000000000000000000000abc",
                abi=abi,
                function_name="foo",
                ctx=mock_ctx,
            )
    assert mock_ctx.report_progress.call_count == 2


@pytest.mark.asyncio
async def test_read_contract_default_args(mock_ctx):
    abi = {"name": "foo", "type": "function", "inputs": [], "outputs": []}
    fn_result = MagicMock()
    fn_result.call = AsyncMock(return_value=0)
    fn_mock = MagicMock(return_value=fn_result)
    contract_mock = MagicMock()
    contract_mock.get_function_by_name.return_value = fn_mock
    w3_mock = MagicMock()
    w3_mock.eth.contract.return_value = contract_mock

    with patch(
        "blockscout_mcp_server.tools.contract_tools.WEB3_POOL.get",
        new_callable=AsyncMock,
        return_value=w3_mock,
    ):
        await read_contract(
            chain_id="1",
            address="0x0000000000000000000000000000000000000abc",
            abi=abi,
            function_name="foo",
            ctx=mock_ctx,
        )

    fn_mock.assert_called_once_with()
    fn_result.call.assert_awaited_once_with(block_identifier="latest")
    assert mock_ctx.report_progress.call_count == 3


@pytest.mark.asyncio
async def test_read_contract_whitespace_args(mock_ctx):
    abi = {"name": "foo", "type": "function", "inputs": [], "outputs": []}
    fn_result = MagicMock()
    fn_result.call = AsyncMock(return_value=0)
    fn_mock = MagicMock(return_value=fn_result)
    contract_mock = MagicMock()
    contract_mock.get_function_by_name.return_value = fn_mock
    w3_mock = MagicMock()
    w3_mock.eth.contract.return_value = contract_mock

    with patch(
        "blockscout_mcp_server.tools.contract_tools.WEB3_POOL.get",
        new_callable=AsyncMock,
        return_value=w3_mock,
    ):
        await read_contract(
            chain_id="1",
            address="0x0000000000000000000000000000000000000abc",
            abi=abi,
            function_name="foo",
            args="   ",
            ctx=mock_ctx,
        )

    fn_mock.assert_called_once_with()
    fn_result.call.assert_awaited_once_with(block_identifier="latest")
    assert mock_ctx.report_progress.call_count == 3


@pytest.mark.asyncio
async def test_read_contract_invalid_args_json(mock_ctx):
    with pytest.raises(ValueError):
        await read_contract(
            chain_id="1",
            address="0x0000000000000000000000000000000000000abc",
            abi={"name": "foo", "type": "function", "inputs": [], "outputs": []},
            function_name="foo",
            args="[",  # invalid JSON
            ctx=mock_ctx,
        )


@pytest.mark.asyncio
async def test_read_contract_args_not_array(mock_ctx):
    with pytest.raises(ValueError) as exc_info:
        await read_contract(
            chain_id="1",
            address="0x0000000000000000000000000000000000000abc",
            abi={"name": "foo", "type": "function", "inputs": [], "outputs": []},
            function_name="foo",
            args='{"x":1}',  # JSON object instead of array
            ctx=mock_ctx,
        )
    assert "`args` must be a JSON array string representing a list; got dict." in str(exc_info.value)


@pytest.mark.asyncio
async def test_read_contract_arity_mismatch(mock_ctx):
    """Test that argument count mismatch gives clear error message."""
    with pytest.raises(ValueError) as exc_info:
        await read_contract(
            chain_id="1",
            address="0x0000000000000000000000000000000000000abc",
            abi={"name": "foo", "type": "function", "inputs": [{"type": "uint256"}], "outputs": []},
            function_name="foo",
            args="[]",  # Empty args but ABI expects 1 input
            ctx=mock_ctx,
        )
    assert "Argument count mismatch: expected 1 per ABI, got 0" in str(exc_info.value)


@pytest.mark.asyncio
async def test_read_contract_negative_numbers(mock_ctx):
    """Test that negative numeric strings are properly converted to integers."""
    chain_id = "1"
    address = "0x0000000000000000000000000000000000000abc"
    function_name = "testNegative"
    abi: dict[str, Any] = {
        "name": function_name,
        "type": "function",
        "inputs": [{"name": "value", "type": "int256"}],
        "outputs": [],
    }
    expected = -42

    fn_result = MagicMock()
    fn_result.call = AsyncMock(return_value=expected)
    fn_mock = MagicMock(return_value=fn_result)
    contract_mock = MagicMock()
    contract_mock.get_function_by_name.return_value = fn_mock
    w3_mock = MagicMock()
    w3_mock.eth.contract.return_value = contract_mock

    with patch(
        "blockscout_mcp_server.tools.contract_tools.WEB3_POOL.get",
        new_callable=AsyncMock,
        return_value=w3_mock,
    ) as mock_get:
        result = await read_contract(
            chain_id=chain_id,
            address=address,
            abi=abi,
            function_name=function_name,
            args='["-42"]',  # Negative number as string
            block="latest",
            ctx=mock_ctx,
        )

    mock_get.assert_called_once_with(chain_id)
    contract_mock.get_function_by_name.assert_called_once_with(function_name)
    fn_mock.assert_called_once_with(-42)  # Should be converted to integer
    fn_result.call.assert_awaited_once_with(block_identifier="latest")
    assert result.data.result == expected
