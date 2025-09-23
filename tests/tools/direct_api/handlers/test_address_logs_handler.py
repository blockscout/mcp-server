from __future__ import annotations

import re
from unittest.mock import patch

import pytest

from blockscout_mcp_server.config import config
from blockscout_mcp_server.models import AddressLogItem, ToolResponse
from blockscout_mcp_server.tools.direct_api.handlers.address_logs_handler import handle_address_logs


def _build_match(address: str) -> re.Match[str]:
    path = f"/api/v2/addresses/{address}/logs"
    pattern = re.compile(r"^/api/v2/addresses/(?P<address>0x[a-fA-F0-9]{40})/logs/?$")
    match = pattern.fullmatch(path)
    assert match is not None  # Sanity check for test data
    return match


@pytest.mark.asyncio
async def test_handle_address_logs_success(mock_ctx):
    address = "0x" + "1" * 40
    response_json = {
        "items": [
            {
                "block_number": 19000000,
                "transaction_hash": "0xtx123",
                "topics": ["0xtopic1"],
                "data": "0xdata",
                "decoded": None,
                "index": 0,
            }
        ]
    }

    result = await handle_address_logs(
        match=_build_match(address),
        response_json=response_json,
        chain_id="1",
        base_url="https://example.blockscout",
        ctx=mock_ctx,
        query_params=None,
    )

    assert isinstance(result, ToolResponse)
    assert isinstance(result.data, list)
    assert len(result.data) == 1
    first_item = result.data[0]
    assert isinstance(first_item, AddressLogItem)
    assert first_item.transaction_hash == "0xtx123"
    assert first_item.block_number == 19000000
    assert result.pagination is None
    assert result.notes is None
    assert result.data_description is not None
    assert "Items Structure:" in result.data_description[0]


@pytest.mark.asyncio
async def test_handle_address_logs_pagination(mock_ctx):
    address = "0x" + "2" * 40
    response_json = {
        "items": [
            {
                "block_number": 19000001,
                "transaction_hash": "0xtxA",
                "topics": ["0xtopic"],
                "data": "0xdata",
                "decoded": None,
                "index": 0,
            },
            {
                "block_number": 19000000,
                "transaction_hash": "0xtxB",
                "topics": ["0xtopic"],
                "data": "0xdata",
                "decoded": None,
                "index": 1,
            },
        ]
    }

    with patch.object(config, "logs_page_size", 1):
        result = await handle_address_logs(
            match=_build_match(address),
            response_json=response_json,
            chain_id="10",
            base_url="https://example.blockscout",
            ctx=mock_ctx,
            query_params=None,
        )

    assert result.pagination is not None
    next_call = result.pagination.next_call
    assert next_call.tool_name == "direct_api_call"
    assert next_call.params["chain_id"] == "10"
    assert next_call.params["endpoint_path"] == f"/api/v2/addresses/{address}/logs"
    assert "cursor" in next_call.params
    assert len(result.data) == 1
    assert result.data[0].transaction_hash == "0xtxA"


@pytest.mark.asyncio
async def test_handle_address_logs_truncation_notes(mock_ctx):
    address = "0x" + "3" * 40
    long_data = "0x" + "a" * 600
    long_decoded_value = "b" * 600
    response_json = {
        "items": [
            {
                "block_number": 19000002,
                "transaction_hash": "0xtxC",
                "topics": ["0xtopic"],
                "data": long_data,
                "decoded": {"value": long_decoded_value},
                "index": 0,
            }
        ]
    }

    result = await handle_address_logs(
        match=_build_match(address),
        response_json=response_json,
        chain_id="1",
        base_url="https://example.blockscout",
        ctx=mock_ctx,
        query_params=None,
    )

    assert result.notes is not None
    assert any("`data` field" in note for note in result.notes)
    assert "transactions/{THE_TRANSACTION_HASH}/logs" in result.notes[-1]
    first_item_dump = result.data[0].model_dump()
    assert first_item_dump.get("data_truncated") is True


@pytest.mark.asyncio
async def test_handle_address_logs_empty_items(mock_ctx):
    address = "0x" + "4" * 40
    response_json = {"items": []}

    result = await handle_address_logs(
        match=_build_match(address),
        response_json=response_json,
        chain_id="1",
        base_url="https://example.blockscout",
        ctx=mock_ctx,
        query_params=None,
    )

    assert isinstance(result, ToolResponse)
    assert result.data == []
    assert result.notes is None
    assert result.pagination is None
