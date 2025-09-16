from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from web3.exceptions import ContractLogicError

from blockscout_mcp_server.tools.common import ChainNotFoundError
from blockscout_mcp_server.tools.contract_tools import read_contract


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
    assert mock_ctx.report_progress.await_count == 3
    assert mock_ctx.info.await_count == 3


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
    assert mock_ctx.report_progress.await_count == 1
    assert mock_ctx.info.await_count == 1


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
    assert mock_ctx.report_progress.await_count == 2
    assert mock_ctx.info.await_count == 2


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
    assert mock_ctx.report_progress.await_count == 3
    assert mock_ctx.info.await_count == 3


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
    assert mock_ctx.report_progress.await_count == 3
    assert mock_ctx.info.await_count == 3


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
    assert mock_ctx.report_progress.await_count == 3
    assert mock_ctx.info.await_count == 3


@pytest.mark.asyncio
async def test_read_contract_function_not_in_abi(mock_ctx):
    abi = {"name": "foo", "type": "function", "inputs": [], "outputs": []}
    w3 = MagicMock()
    contract = MagicMock()
    contract.get_function_by_name.side_effect = ValueError("not found")
    w3.eth.contract.return_value = contract

    with patch(
        "blockscout_mcp_server.tools.contract_tools.WEB3_POOL.get",
        new_callable=AsyncMock,
        return_value=w3,
    ):
        with pytest.raises(ValueError, match="Function name 'bar' is not found in provided ABI"):
            await read_contract(
                chain_id="1",
                address="0x0000000000000000000000000000000000000abc",
                abi=abi,
                function_name="bar",
                ctx=mock_ctx,
            )


@pytest.mark.asyncio
async def test_read_contract_block_string_normalization(mock_ctx):
    abi = {"name": "foo", "type": "function", "inputs": [], "outputs": []}
    fn_result = MagicMock()
    fn_result.call = AsyncMock(return_value=0)
    fn = MagicMock(return_value=fn_result)
    contract = MagicMock()
    contract.get_function_by_name.return_value = fn
    w3 = MagicMock()
    w3.eth.contract.return_value = contract

    with patch(
        "blockscout_mcp_server.tools.contract_tools.WEB3_POOL.get",
        new_callable=AsyncMock,
        return_value=w3,
    ):
        await read_contract(
            chain_id="1",
            address="0x0000000000000000000000000000000000000abc",
            abi=abi,
            function_name="foo",
            block="19000000",
            ctx=mock_ctx,
        )

    fn_result.call.assert_awaited_once_with(block_identifier=19000000)
