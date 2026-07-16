# SPDX-License-Identifier: LicenseRef-Blockscout
"""Unit tests for read_contract's bytes-normalization behavior (issue #428).

web3 decodes ABI `bytes`/`bytesN` outputs into Python `bytes`. Pydantic v2's default
JSON serialization tries to decode `bytes` as UTF-8 text, which crashes for arbitrary
binary payloads (and silently mangles the rare byte string that happens to be valid
UTF-8). `read_contract` normalizes every bytes-like leaf in the decoded call result
into a canonical `0x`-prefixed hex string before building the response. These tests
cover that normalization at the top level, inside structs/arrays, at nested depth,
and confirm the fixed response actually survives `model_dump(mode="json")`.
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from blockscout_mcp_server.tools.contract.read_contract import read_contract

CHAIN_ID = "1"
ADDRESS = "0x0000000000000000000000000000000000000abc"
FUNCTION_NAME = "foo"
ABI: dict[str, Any] = {"name": FUNCTION_NAME, "type": "function", "inputs": [], "outputs": []}

# 32 bytes starting with 0x8e: not valid UTF-8, reproduces the issue's crash directly.
NON_UTF8_BYTES32 = bytes([0x8E]) + bytes(31)
NON_UTF8_BYTES32_HEX = "0x8e" + "00" * 31

# A second, distinct non-UTF-8 bytes32 payload, for scenarios needing two values.
NON_UTF8_BYTES32_B = bytes([0x9F]) + bytes(31)
NON_UTF8_BYTES32_B_HEX = "0x9f" + "00" * 31


def _build_w3_mock(call_return_value: Any) -> MagicMock:
    """Build the WEB3_POOL.get()-shaped mock chain returning call_return_value from .call()."""
    fn_result = MagicMock()
    fn_result.call = AsyncMock(return_value=call_return_value)
    fn_mock = MagicMock(return_value=fn_result)
    contract_mock = MagicMock()
    contract_mock.get_function_by_name.return_value = fn_mock
    w3_mock = MagicMock()
    w3_mock.eth.contract.return_value = contract_mock
    return w3_mock


async def _call_read_contract(mock_ctx: Any, call_return_value: Any):
    w3_mock = _build_w3_mock(call_return_value)
    with patch(
        "blockscout_mcp_server.tools.contract.read_contract.WEB3_POOL.get",
        new_callable=AsyncMock,
        return_value=w3_mock,
    ):
        return await read_contract(
            chain_id=CHAIN_ID,
            address=ADDRESS,
            abi=ABI,
            function_name=FUNCTION_NAME,
            ctx=mock_ctx,
        )


@pytest.mark.asyncio
async def test_read_contract_normalizes_non_utf8_bytes32(mock_ctx):
    """Direct reproduction of the issue: a non-UTF-8 bytes32 return must not crash and must be hex."""
    result = await _call_read_contract(mock_ctx, NON_UTF8_BYTES32)

    assert result.data.result == NON_UTF8_BYTES32_HEX
    assert mock_ctx.report_progress.await_count == 3
    assert mock_ctx.info.await_count == 3


@pytest.mark.asyncio
async def test_read_contract_normalizes_utf8_decodable_bytes_to_hex(mock_ctx):
    """b"data" is valid UTF-8 text but must still become hex, not "data" (silent-corruption guard)."""
    result = await _call_read_contract(mock_ctx, b"data")

    assert result.data.result == "0x64617461"
    assert result.data.result != "data"
    assert mock_ctx.report_progress.await_count == 3
    assert mock_ctx.info.await_count == 3


@pytest.mark.asyncio
async def test_read_contract_normalizes_bytearray_to_hex(mock_ctx):
    """A bytearray return must be normalized the same way as a bytes return."""
    result = await _call_read_contract(mock_ctx, bytearray(NON_UTF8_BYTES32))

    assert result.data.result == NON_UTF8_BYTES32_HEX
    assert mock_ctx.report_progress.await_count == 3
    assert mock_ctx.info.await_count == 3


@pytest.mark.asyncio
async def test_read_contract_normalizes_struct_tuple_preserving_siblings(mock_ctx):
    """A struct (tuple) mixing int/bool/bytes32 stays a tuple; only the bytes leaf becomes hex."""
    call_return_value = (1, True, NON_UTF8_BYTES32)

    result = await _call_read_contract(mock_ctx, call_return_value)

    assert result.data.result == (1, True, NON_UTF8_BYTES32_HEX)
    assert isinstance(result.data.result, tuple)
    assert mock_ctx.report_progress.await_count == 3
    assert mock_ctx.info.await_count == 3


@pytest.mark.asyncio
async def test_read_contract_normalizes_nested_struct(mock_ctx):
    """A tuple containing an inner tuple with a bytes leaf is normalized at depth."""
    call_return_value = (1, (2, NON_UTF8_BYTES32))

    result = await _call_read_contract(mock_ctx, call_return_value)

    assert result.data.result == (1, (2, NON_UTF8_BYTES32_HEX))
    assert mock_ctx.report_progress.await_count == 3
    assert mock_ctx.info.await_count == 3


@pytest.mark.asyncio
async def test_read_contract_normalizes_array_of_bytes32(mock_ctx):
    """An ABI array return (a Python list, not a tuple) of bytes32 values becomes a list of hex strings."""
    call_return_value = [NON_UTF8_BYTES32, NON_UTF8_BYTES32_B]

    result = await _call_read_contract(mock_ctx, call_return_value)

    assert result.data.result == [NON_UTF8_BYTES32_HEX, NON_UTF8_BYTES32_B_HEX]
    assert isinstance(result.data.result, list)
    assert mock_ctx.report_progress.await_count == 3
    assert mock_ctx.info.await_count == 3


@pytest.mark.asyncio
async def test_read_contract_passthrough_for_plain_str(mock_ctx):
    """A plain str return (e.g. a checksummed address) passes through byte-for-byte unchanged."""
    checksummed_address = "0xF977814e90dA44bFA03b6295A0616a897441aceC"

    result = await _call_read_contract(mock_ctx, checksummed_address)

    assert result.data.result == checksummed_address
    assert mock_ctx.report_progress.await_count == 3
    assert mock_ctx.info.await_count == 3


@pytest.mark.asyncio
async def test_read_contract_bytes_result_survives_json_serialization(mock_ctx):
    """The regression assertion that would have caught the original crash.

    Before the fix, calling model_dump(mode="json") on a ToolResponse wrapping a raw,
    non-UTF-8 bytes32 result raised a UnicodeDecodeError from Pydantic's default
    ser_json_bytes="utf8" bytes serializer.
    """
    result = await _call_read_contract(mock_ctx, NON_UTF8_BYTES32)

    dumped = result.model_dump(mode="json")

    assert dumped["data"]["result"] == NON_UTF8_BYTES32_HEX
    assert mock_ctx.report_progress.await_count == 3
    assert mock_ctx.info.await_count == 3
