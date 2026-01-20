from __future__ import annotations

import re
from unittest.mock import patch

import pytest

from blockscout_mcp_server.config import config
from blockscout_mcp_server.models import ToolResponse, TransactionLogItem
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
