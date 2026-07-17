# SPDX-License-Identifier: LicenseRef-Blockscout
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from web3 import Web3
from web3.exceptions import ContractLogicError

from blockscout_mcp_server.config import config
from blockscout_mcp_server.tools.common import ChainNotFoundError
from blockscout_mcp_server.tools.contract.read_contract import read_contract

# The codec a real AsyncWeb3 instance would carry. Attached to w3 mocks in the
# preflight-focused tests below so `check_if_arguments_can_be_encoded` runs against
# genuine encoders instead of a truthy MagicMock attribute.
REAL_W3_CODEC = Web3().codec


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
        "blockscout_mcp_server.tools.contract.read_contract.WEB3_POOL.get",
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
async def test_read_contract_accepts_dict_form_struct_with_bytes_field(mock_ctx, build_w3_mock):
    """A dict-form struct with a `bytes` field must pass the encodability preflight.

    Regression test: an earlier preflight pre-decoded hex-like strings with a
    type-blind heuristic that recursed into lists but not dicts, so this exact
    input was falsely rejected with a `ValueError` before the call. The preflight
    now checks the raw arguments with the same codec the actual call uses
    (`w3.codec`), which accepts 0x-hex strings for `bytes` fields directly. The
    mocked w3 carries a real codec, so the preflight is genuinely exercised.
    """
    chain_id = "1"
    address = "0x0000000000000000000000000000000000000abc"
    function_name = "echoBytesStruct"
    abi: dict[str, Any] = {
        "name": function_name,
        "type": "function",
        "inputs": [
            {
                "name": "_value",
                "type": "tuple",
                "components": [
                    {"name": "id", "type": "uint256"},
                    {"name": "data", "type": "bytes"},
                ],
            }
        ],
        "outputs": [
            {
                "name": "",
                "type": "tuple",
                "components": [
                    {"name": "id", "type": "uint256"},
                    {"name": "data", "type": "bytes"},
                ],
            }
        ],
    }

    w3_mock = build_w3_mock((7, b"\xde\xad\xbe\xef"), codec=REAL_W3_CODEC)

    with patch(
        "blockscout_mcp_server.tools.contract.read_contract.WEB3_POOL.get",
        new_callable=AsyncMock,
        return_value=w3_mock,
    ):
        result = await read_contract(
            chain_id=chain_id,
            address=address,
            abi=abi,
            function_name=function_name,
            args=json.dumps([{"id": 7, "data": "0xdeadbeef"}]),
            ctx=mock_ctx,
        )

    assert result.data.result == (7, "0xdeadbeef")
    assert mock_ctx.report_progress.await_count == 3
    assert mock_ctx.info.await_count == 3


@pytest.mark.parametrize("name_value", ["0xdeadbeef", "0xData!"])
@pytest.mark.asyncio
async def test_read_contract_accepts_dict_form_struct_with_hexlike_string_field(mock_ctx, build_w3_mock, name_value):
    """A `string` struct field holding "0x"-prefixed text must pass the preflight.

    Regression test: an earlier preflight pre-decoded every hex-like string to
    bytes, which is right for `bytes` fields but wrong for a `string` field whose
    value merely starts with "0x". Two ways it used to break a dict-form struct:
    a valid hex-text value (``0xdeadbeef``) became bytes and failed the
    encodability preflight (false-negative `ValueError`), and a non-hex value
    (``0xData!``) raised a raw `binascii.Error` from `decode_hex`, bypassing the
    tool's error contract. The codec-based preflight checks the raw string
    against the ABI `string` type, which accepts both values. The mocked w3
    carries a real codec, so the preflight is genuinely exercised.
    """
    chain_id = "1"
    address = "0x0000000000000000000000000000000000000abc"
    function_name = "echoNamedStruct"
    abi: dict[str, Any] = {
        "name": function_name,
        "type": "function",
        "inputs": [
            {
                "name": "_value",
                "type": "tuple",
                "components": [
                    {"name": "id", "type": "uint256"},
                    {"name": "name", "type": "string"},
                ],
            }
        ],
        "outputs": [
            {
                "name": "",
                "type": "tuple",
                "components": [
                    {"name": "id", "type": "uint256"},
                    {"name": "name", "type": "string"},
                ],
            }
        ],
    }

    w3_mock = build_w3_mock((7, name_value), codec=REAL_W3_CODEC)

    with patch(
        "blockscout_mcp_server.tools.contract.read_contract.WEB3_POOL.get",
        new_callable=AsyncMock,
        return_value=w3_mock,
    ):
        result = await read_contract(
            chain_id=chain_id,
            address=address,
            abi=abi,
            function_name=function_name,
            args=json.dumps([{"id": 7, "name": name_value}]),
            ctx=mock_ctx,
        )

    assert result.data.result == (7, name_value)
    assert mock_ctx.report_progress.await_count == 3
    assert mock_ctx.info.await_count == 3


@pytest.mark.asyncio
async def test_read_contract_accepts_mixed_bytes_and_hexlike_string_args(mock_ctx, build_w3_mock):
    """A `bytes` arg alongside a `string` arg holding "0x" text must pass the preflight.

    Regression test for the all-or-nothing preflight heuristic: the earlier
    implementation checked either the fully-pre-decoded or the fully-raw argument
    tuple, so a signature mixing a `bytes` field (which had to be decoded for the
    preflight's default codec) with a `string` field holding "0x"-prefixed text
    (which had to stay raw) failed both forms and was falsely rejected with a
    `ValueError`, even though the actual call would have succeeded. The codec-based
    preflight accepts the raw form of both arguments at once. The mocked w3 carries
    a real codec, so the preflight is genuinely exercised.
    """
    chain_id = "1"
    address = "0x0000000000000000000000000000000000000abc"
    function_name = "echoBytesAndLabel"
    abi: dict[str, Any] = {
        "name": function_name,
        "type": "function",
        "inputs": [
            {"name": "data", "type": "bytes"},
            {"name": "label", "type": "string"},
        ],
        "outputs": [
            {"name": "", "type": "bytes"},
            {"name": "", "type": "string"},
        ],
    }

    w3_mock = build_w3_mock((b"\xde\xad\xbe\xef", "0x1234"), codec=REAL_W3_CODEC)
    fn_mock = w3_mock.eth.contract.return_value.get_function_by_name.return_value

    with patch(
        "blockscout_mcp_server.tools.contract.read_contract.WEB3_POOL.get",
        new_callable=AsyncMock,
        return_value=w3_mock,
    ):
        result = await read_contract(
            chain_id=chain_id,
            address=address,
            abi=abi,
            function_name=function_name,
            args=json.dumps(["0xdeadbeef", "0x1234"]),
            ctx=mock_ctx,
        )

    fn_mock.assert_called_once_with("0xdeadbeef", "0x1234")
    assert result.data.result == ("0xdeadbeef", "0x1234")
    assert mock_ctx.report_progress.await_count == 3
    assert mock_ctx.info.await_count == 3


@pytest.mark.asyncio
async def test_read_contract_rejects_unencodable_args(mock_ctx, build_w3_mock):
    """Arguments the call codec cannot encode fail the preflight with a `ValueError`.

    Pins the negative path of the codec-based preflight: a plain non-numeric string
    is not encodable as `uint256`, so the tool must reject it before attempting the
    call. The mocked w3 carries a real codec, so the rejection comes from genuine
    encoders, and the contract object is never even constructed.
    """
    abi: dict[str, Any] = {
        "name": "foo",
        "type": "function",
        "inputs": [{"name": "x", "type": "uint256"}],
        "outputs": [],
    }

    w3_mock = build_w3_mock(None, codec=REAL_W3_CODEC)

    with patch(
        "blockscout_mcp_server.tools.contract.read_contract.WEB3_POOL.get",
        new_callable=AsyncMock,
        return_value=w3_mock,
    ):
        with pytest.raises(ValueError, match="cannot be encoded for function 'foo'"):
            await read_contract(
                chain_id="1",
                address="0x0000000000000000000000000000000000000abc",
                abi=abi,
                function_name="foo",
                args='["notanumber"]',
                ctx=mock_ctx,
            )

    w3_mock.eth.contract.assert_not_called()


@pytest.mark.asyncio
async def test_read_contract_rejects_dict_form_struct_with_missing_field(mock_ctx, build_w3_mock):
    """A dict-form struct missing an ABI component key fails the preflight with a `ValueError`.

    web3's `check_if_arguments_can_be_encoded` does not return False for this shape:
    its input alignment raises a raw `KeyError` for the absent component name. The
    tool must fold that into its normal rejection contract instead of leaking the
    bare `KeyError` to the caller. The mocked w3 carries a real codec, so the
    preflight is genuinely exercised, and the contract object is never constructed.
    """
    function_name = "echoBytesStruct"
    abi: dict[str, Any] = {
        "name": function_name,
        "type": "function",
        "inputs": [
            {
                "name": "_value",
                "type": "tuple",
                "components": [
                    {"name": "id", "type": "uint256"},
                    {"name": "data", "type": "bytes"},
                ],
            }
        ],
        "outputs": [],
    }

    w3_mock = build_w3_mock(None, codec=REAL_W3_CODEC)

    with patch(
        "blockscout_mcp_server.tools.contract.read_contract.WEB3_POOL.get",
        new_callable=AsyncMock,
        return_value=w3_mock,
    ):
        with pytest.raises(ValueError, match=f"cannot be encoded for function '{function_name}'"):
            await read_contract(
                chain_id="1",
                address="0x0000000000000000000000000000000000000abc",
                abi=abi,
                function_name=function_name,
                args=json.dumps([{"id": 7, "datta": "0xdeadbeef"}]),
                ctx=mock_ctx,
            )

    w3_mock.eth.contract.assert_not_called()


@pytest.mark.asyncio
async def test_read_contract_chain_not_found(mock_ctx):
    chain_id = "999"
    abi = {"name": "foo", "type": "function", "inputs": [], "outputs": []}
    with patch(
        "blockscout_mcp_server.tools.contract.read_contract.WEB3_POOL.get",
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
async def test_read_contract_missing_pro_api_key_propagates_value_error(mock_ctx):
    """Without a PRO API key, the real pool's ValueError must surface unchanged.

    Unlike the other tests, this one does NOT mock ``WEB3_POOL.get`` — it drives
    the real pool with an empty key so the tool's wiring (the ``WEB3_POOL.get``
    call sits outside any try/except) is exercised end to end. This locks in the
    user-facing contract: the minimal "PRO API key required for …; not configured."
    message is not swallowed or rewrapped into a generic error.
    """
    abi = {"name": "foo", "type": "function", "inputs": [], "outputs": []}
    with patch.object(config, "pro_api_key", ""):
        with pytest.raises(ValueError, match="PRO API key required"):
            await read_contract(
                chain_id="1",
                address="0x0000000000000000000000000000000000000abc",
                abi=abi,
                function_name="foo",
                ctx=mock_ctx,
            )
    # The fail-fast raise happens after the initial progress report but before
    # any network/session work.
    assert mock_ctx.report_progress.await_count == 1


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
        "blockscout_mcp_server.tools.contract.read_contract.WEB3_POOL.get",
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
        "blockscout_mcp_server.tools.contract.read_contract.WEB3_POOL.get",
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
        "blockscout_mcp_server.tools.contract.read_contract.WEB3_POOL.get",
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
        "blockscout_mcp_server.tools.contract.read_contract.WEB3_POOL.get",
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
        "blockscout_mcp_server.tools.contract.read_contract.WEB3_POOL.get",
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
        "blockscout_mcp_server.tools.contract.read_contract.WEB3_POOL.get",
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
