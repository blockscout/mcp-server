from __future__ import annotations

import re
from unittest.mock import patch

import pytest

from blockscout_mcp_server.config import config
from blockscout_mcp_server.models import ToolResponse, TransactionLogItem
from blockscout_mcp_server.tools.common import decode_cursor
from blockscout_mcp_server.tools.direct_api.dispatcher import HANDLER_REGISTRY
from blockscout_mcp_server.tools.direct_api.handlers.transaction_logs_handler import handle_transaction_logs


def _build_match(transaction_hash: str) -> re.Match[str]:
    path = f"/api/v2/transactions/{transaction_hash}/logs"
    pattern = re.compile(r"^/api/v2/transactions/(?P<transaction_hash>0x[a-fA-F0-9]{64})/logs/?$")
    match = pattern.fullmatch(path)
    assert match is not None  # Sanity check for test data
    return match


def test_transaction_logs_handler_regex_match():
    transaction_hash = "0x" + "a" * 64
    path = f"/api/v2/transactions/{transaction_hash}/logs"

    matches_handler = any(
        pattern.fullmatch(path) for pattern, handler in HANDLER_REGISTRY if handler is handle_transaction_logs
    )

    assert matches_handler


@pytest.mark.asyncio
async def test_handle_transaction_logs_success(mock_ctx):
    transaction_hash = "0x" + "b" * 64
    response_json = {
        "items": [
            {
                "address": {"hash": "0x" + "1" * 40},
                "block_number": 19000000,
                "topics": ["0xtopic1"],
                "data": "0xdata",
                "decoded": {"name": "Transfer"},
                "index": 0,
            }
        ]
    }

    result = await handle_transaction_logs(
        match=_build_match(transaction_hash),
        response_json=response_json,
        chain_id="1",
        base_url="https://example.blockscout",
        ctx=mock_ctx,
    )

    assert isinstance(result, ToolResponse)
    assert isinstance(result.data, list)
    assert len(result.data) == 1
    first_item = result.data[0]
    assert isinstance(first_item, TransactionLogItem)
    assert first_item.address == "0x" + "1" * 40
    assert first_item.block_number == 19000000
    assert result.pagination is None
    assert result.notes is None
    assert result.data_description is not None
    assert "Items Structure:" in result.data_description[0]


@pytest.mark.asyncio
async def test_handle_transaction_logs_empty_response(mock_ctx):
    transaction_hash = "0x" + "e" * 64
    result = await handle_transaction_logs(
        match=_build_match(transaction_hash),
        response_json={"items": []},
        chain_id="1",
        base_url="https://example.blockscout",
        ctx=mock_ctx,
    )

    assert result.data == []
    assert result.pagination is None
    assert result.notes is None
    assert result.data_description is not None


@pytest.mark.asyncio
async def test_handle_transaction_logs_complex_item(mock_ctx):
    transaction_hash = "0x" + "f" * 64
    response_json = {
        "items": [
            {
                "address": {"hash": "0xa0b86a33e6dd0ba3c70de3b8e2b9e48cd6efb7b0"},
                "topics": [
                    "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef",
                    "0x000000000000000000000000d8da6bf26964af9d7eed9e03e53415d37aa96045",
                ],
                "data": "0x" + "1" * 64,
                "log_index": "42",
                "transaction_hash": transaction_hash,
                "block_number": 19000000,
                "decoded": {"name": "Transfer"},
                "index": 42,
            }
        ]
    }

    result = await handle_transaction_logs(
        match=_build_match(transaction_hash),
        response_json=response_json,
        chain_id="1",
        base_url="https://example.blockscout",
        ctx=mock_ctx,
    )

    assert len(result.data) == 1
    item = result.data[0]
    assert item.address == "0xa0b86a33e6dd0ba3c70de3b8e2b9e48cd6efb7b0"
    assert item.block_number == 19000000
    assert item.topics == response_json["items"][0]["topics"]
    assert "transaction_hash" not in item.model_dump()


@pytest.mark.asyncio
async def test_handle_transaction_logs_truncation_notes(mock_ctx):
    transaction_hash = "0x" + "c" * 64
    long_data = "0x" + "a" * 600
    long_decoded_value = "b" * 600
    response_json = {
        "items": [
            {
                "address": "0x" + "2" * 40,
                "block_number": 19000002,
                "topics": ["0xtopic"],
                "data": long_data,
                "decoded": {"value": long_decoded_value},
                "index": 0,
            }
        ]
    }

    result = await handle_transaction_logs(
        match=_build_match(transaction_hash),
        response_json=response_json,
        chain_id="1",
        base_url="https://example.blockscout",
        ctx=mock_ctx,
    )

    assert result.notes is not None
    assert any("`data` field" in note for note in result.notes)
    assert any("/api/v2/transactions/" in note for note in result.notes)
    first_item_dump = result.data[0].model_dump()
    assert first_item_dump.get("data_truncated") is True


@pytest.mark.asyncio
async def test_handle_transaction_logs_decoded_truncation_only(mock_ctx):
    transaction_hash = "0x" + "1" * 64
    long_decoded_value = "c" * 600
    response_json = {
        "items": [
            {
                "address": "0x" + "4" * 40,
                "block_number": 19000002,
                "topics": ["0xtopic"],
                "data": "0xdata",
                "decoded": {"value": long_decoded_value},
                "index": 0,
            }
        ]
    }

    result = await handle_transaction_logs(
        match=_build_match(transaction_hash),
        response_json=response_json,
        chain_id="1",
        base_url="https://example.blockscout",
        ctx=mock_ctx,
    )

    assert result.notes is not None
    assert any("One or more log items" in note for note in result.notes)
    first_item_dump = result.data[0].model_dump()
    assert first_item_dump.get("data_truncated") is None
    assert isinstance(first_item_dump["decoded"]["value"], dict)


@pytest.mark.asyncio
async def test_handle_transaction_logs_pagination(mock_ctx):
    transaction_hash = "0x" + "d" * 64
    response_json = {
        "items": [
            {
                "address": "0x" + "3" * 40,
                "block_number": 19000000,
                "topics": ["0xtopic"],
                "data": "0xdata",
                "decoded": None,
                "index": idx,
            }
            for idx in range(50)
        ]
    }

    with patch.object(config, "logs_page_size", 10):
        result = await handle_transaction_logs(
            match=_build_match(transaction_hash),
            response_json=response_json,
            chain_id="10",
            base_url="https://example.blockscout",
            ctx=mock_ctx,
        )

    assert result.pagination is not None
    next_call = result.pagination.next_call
    assert next_call.tool_name == "direct_api_call"
    assert next_call.params["chain_id"] == "10"
    assert next_call.params["endpoint_path"] == f"/api/v2/transactions/{transaction_hash}/logs"
    assert "cursor" in next_call.params
    assert len(result.data) == 10

    decoded_cursor = decode_cursor(next_call.params["cursor"])
    assert decoded_cursor["block_number"] == response_json["items"][9]["block_number"]
    assert decoded_cursor["index"] == response_json["items"][9]["index"]
