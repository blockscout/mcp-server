from __future__ import annotations

import re

import pytest

from blockscout_mcp_server.constants import INPUT_DATA_TRUNCATION_LIMIT
from blockscout_mcp_server.models import ToolResponse, UserOperationData
from blockscout_mcp_server.tools.direct_api.handlers.user_operation_handler import PATTERN, handle_user_operation


def _build_match(user_operation_hash: str, *, trailing_slash: bool = False) -> re.Match[str]:
    suffix = "/" if trailing_slash else ""
    path = f"/api/v2/proxy/account-abstraction/operations/{user_operation_hash}{suffix}"
    match = re.compile(PATTERN).fullmatch(path)
    assert match is not None
    return match


def test_user_operation_handler_regex_match():
    valid_hash = "0x" + "a" * 64
    valid_path = f"/api/v2/proxy/account-abstraction/operations/{valid_hash}"
    valid_path_trailing = f"/api/v2/proxy/account-abstraction/operations/{valid_hash}/"
    invalid_length = "/api/v2/proxy/account-abstraction/operations/0x" + "a" * 63
    missing_hash = "/api/v2/proxy/account-abstraction/operations/"

    pattern = re.compile(PATTERN)

    assert pattern.fullmatch(valid_path)
    assert pattern.fullmatch(valid_path_trailing)
    assert pattern.fullmatch(invalid_length) is None
    assert pattern.fullmatch(missing_hash) is None


@pytest.mark.asyncio
async def test_user_operation_handler_success(mock_ctx):
    user_operation_hash = "0x" + "b" * 64
    response_json = {
        "hash": user_operation_hash,
        "sender": "0x" + "1" * 40,
        "entry_point": "0x" + "2" * 40,
        "call_data": "0x1234",
        "execute_call_data": "0x5678",
        "signature": "0xabcdef",
        "aggregator_signature": "0xdeadbeef",
        "decoded_call_data": {"parameters": [{"name": "amount", "value": "1"}]},
        "decoded_execute_call_data": {"parameters": [{"name": "target", "value": "0x1"}]},
        "raw": {"call_data": "0x01", "paymaster_and_data": "0x02", "signature": "0x03"},
    }

    result = await handle_user_operation(
        match=_build_match(user_operation_hash),
        response_json=response_json,
        chain_id="1",
        base_url="https://example.blockscout",
        ctx=mock_ctx,
    )

    assert isinstance(result, ToolResponse)
    assert isinstance(result.data, UserOperationData)
    assert result.data.sender == "0x" + "1" * 40
    assert result.data.entry_point == "0x" + "2" * 40
    assert result.data.call_data_truncated is None
    assert result.data.raw is not None
    assert result.data.raw.call_data_truncated is None
    assert result.notes is None


@pytest.mark.asyncio
async def test_user_operation_handler_with_nulls(mock_ctx):
    user_operation_hash = "0x" + "c" * 64
    response_json = {
        "hash": user_operation_hash,
        "sender": None,
        "factory": None,
        "paymaster": None,
        "entry_point": None,
        "bundler": None,
        "execute_target": None,
        "decoded_call_data": None,
        "decoded_execute_call_data": None,
        "raw": None,
    }

    result = await handle_user_operation(
        match=_build_match(user_operation_hash),
        response_json=response_json,
        chain_id="1",
        base_url="https://example.blockscout",
        ctx=mock_ctx,
    )

    assert result.data.sender is None
    assert result.data.factory is None
    assert result.data.paymaster is None
    assert result.data.entry_point is None
    assert result.data.bundler is None
    assert result.data.execute_target is None
    assert result.data.call_data_truncated is None
    assert result.notes is None


@pytest.mark.asyncio
async def test_user_operation_handler_address_optimization(mock_ctx):
    user_operation_hash = "0x" + "d" * 64
    response_json = {
        "hash": user_operation_hash,
        "sender": {"hash": "0x" + "1" * 40, "name": "Sender"},
        "factory": {"hash": "0x" + "2" * 40, "is_contract": True},
        "paymaster": {"hash": "0x" + "3" * 40, "reputation": "ok"},
        "entry_point": {"hash": "0x" + "4" * 40},
        "bundler": {"hash": "0x" + "5" * 40},
        "execute_target": {"hash": "0x" + "6" * 40},
    }

    result = await handle_user_operation(
        match=_build_match(user_operation_hash),
        response_json=response_json,
        chain_id="1",
        base_url="https://example.blockscout",
        ctx=mock_ctx,
    )

    assert result.data.sender == "0x" + "1" * 40
    assert result.data.factory == "0x" + "2" * 40
    assert result.data.paymaster == "0x" + "3" * 40
    assert result.data.entry_point == "0x" + "4" * 40
    assert result.data.bundler == "0x" + "5" * 40
    assert result.data.execute_target == "0x" + "6" * 40


@pytest.mark.asyncio
async def test_user_operation_handler_truncation(mock_ctx):
    user_operation_hash = "0x" + "e" * 64
    long_data = "0x" + "a" * (INPUT_DATA_TRUNCATION_LIMIT + 10)
    response_json = {
        "hash": user_operation_hash,
        "call_data": long_data,
        "execute_call_data": long_data,
        "signature": long_data,
        "aggregator_signature": long_data,
    }

    result = await handle_user_operation(
        match=_build_match(user_operation_hash),
        response_json=response_json,
        chain_id="1",
        base_url="https://example.blockscout",
        ctx=mock_ctx,
    )

    data_dump = result.data.model_dump()
    assert len(data_dump["call_data"]) == INPUT_DATA_TRUNCATION_LIMIT
    assert len(data_dump["execute_call_data"]) == INPUT_DATA_TRUNCATION_LIMIT
    assert len(data_dump["signature"]) == INPUT_DATA_TRUNCATION_LIMIT
    assert len(data_dump["aggregator_signature"]) == INPUT_DATA_TRUNCATION_LIMIT
    assert result.data.call_data_truncated is True
    assert result.data.execute_call_data_truncated is True
    assert result.data.signature_truncated is True
    assert result.data.aggregator_signature_truncated is True
    assert result.notes is not None
    assert any("account-abstraction/operations" in note for note in result.notes)


@pytest.mark.asyncio
async def test_user_operation_handler_raw_truncation(mock_ctx):
    user_operation_hash = "0x" + "f" * 64
    long_data = "0x" + "b" * (INPUT_DATA_TRUNCATION_LIMIT + 10)
    response_json = {
        "hash": user_operation_hash,
        "raw": {
            "call_data": long_data,
            "init_code": long_data,
            "paymaster_and_data": long_data,
            "signature": long_data,
        },
    }

    result = await handle_user_operation(
        match=_build_match(user_operation_hash),
        response_json=response_json,
        chain_id="1",
        base_url="https://example.blockscout",
        ctx=mock_ctx,
    )

    data_dump = result.data.model_dump()
    raw = data_dump["raw"]
    assert len(raw["call_data"]) == INPUT_DATA_TRUNCATION_LIMIT
    assert len(raw["init_code"]) == INPUT_DATA_TRUNCATION_LIMIT
    assert len(raw["paymaster_and_data"]) == INPUT_DATA_TRUNCATION_LIMIT
    assert len(raw["signature"]) == INPUT_DATA_TRUNCATION_LIMIT
    assert result.data.raw is not None
    raw_flags = result.data.raw.model_dump()
    assert raw_flags.get("call_data_truncated") is True
    assert raw_flags.get("init_code_truncated") is True
    assert raw_flags.get("paymaster_and_data_truncated") is True
    assert raw_flags.get("signature_truncated") is True


@pytest.mark.asyncio
async def test_user_operation_handler_decoded_truncation(mock_ctx):
    user_operation_hash = "0x" + "1" * 64
    long_value = "0x" + "c" * (INPUT_DATA_TRUNCATION_LIMIT + 10)
    response_json = {
        "hash": user_operation_hash,
        "decoded_call_data": {
            "method_call": "executeBatch(address[] dest, bytes[] func)",
            "method_id": "18dfb3c7",
            "parameters": [
                {
                    "name": "dest",
                    "type": "address[]",
                    "value": [
                        "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
                        "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
                    ],
                },
                {
                    "name": "func",
                    "type": "bytes[]",
                    "value": [long_value, long_value],
                },
            ],
        },
    }

    result = await handle_user_operation(
        match=_build_match(user_operation_hash),
        response_json=response_json,
        chain_id="1",
        base_url="https://example.blockscout",
        ctx=mock_ctx,
    )

    decoded = result.data.model_dump()["decoded_call_data"]
    truncated_values = decoded["parameters"][1]["value"]
    assert all(isinstance(item, dict) for item in truncated_values)
    assert all(item["value_truncated"] is True for item in truncated_values)


@pytest.mark.asyncio
async def test_user_operation_handler_decoded_execute_truncation(mock_ctx):
    user_operation_hash = "0x" + "3" * 64
    long_value = "0x" + "e" * (INPUT_DATA_TRUNCATION_LIMIT + 10)
    response_json = {
        "hash": user_operation_hash,
        "decoded_execute_call_data": {
            "method_call": "executeBatch(address[] dest, bytes[] func)",
            "method_id": "18dfb3c7",
            "parameters": [
                {
                    "name": "dest",
                    "type": "address[]",
                    "value": [
                        "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
                        "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
                    ],
                },
                {
                    "name": "func",
                    "type": "bytes[]",
                    "value": [long_value, long_value],
                },
            ],
        },
    }

    result = await handle_user_operation(
        match=_build_match(user_operation_hash),
        response_json=response_json,
        chain_id="1",
        base_url="https://example.blockscout",
        ctx=mock_ctx,
    )

    decoded = result.data.model_dump()["decoded_execute_call_data"]
    truncated_values = decoded["parameters"][1]["value"]
    assert all(isinstance(item, dict) for item in truncated_values)
    assert all(item["value_truncated"] is True for item in truncated_values)


@pytest.mark.asyncio
async def test_user_operation_handler_complex(mock_ctx):
    user_operation_hash = "0x" + "2" * 64
    long_data = "0x" + "d" * (INPUT_DATA_TRUNCATION_LIMIT + 10)
    response_json = {
        "hash": user_operation_hash,
        "sender": {"hash": "0x" + "a" * 40},
        "entry_point": {"hash": "0x" + "b" * 40},
        "call_data": long_data,
        "decoded_call_data": {"parameters": [{"name": "value", "value": long_data}]},
        "raw": {"call_data": long_data},
    }

    result = await handle_user_operation(
        match=_build_match(user_operation_hash, trailing_slash=True),
        response_json=response_json,
        chain_id="1",
        base_url="https://example.blockscout",
        ctx=mock_ctx,
    )

    assert result.data.sender == "0x" + "a" * 40
    assert result.data.entry_point == "0x" + "b" * 40
    assert result.data.call_data_truncated is True
    assert result.data.raw is not None
    assert result.data.raw.call_data_truncated is True
    assert result.notes is not None
