from __future__ import annotations

import re

import pytest

from blockscout_mcp_server.models import ToolResponse, TransactionSummaryData
from blockscout_mcp_server.tools.direct_api.dispatcher import HANDLER_REGISTRY
from blockscout_mcp_server.tools.direct_api.handlers.transaction_summary_handler import handle_transaction_summary

PATTERN = r"^/api/v2/transactions/(?P<transaction_hash>0x[a-fA-F0-9]{64})/summary/?$"


def _build_match(transaction_hash: str) -> re.Match[str]:
    path = f"/api/v2/transactions/{transaction_hash}/summary"
    match = re.compile(PATTERN).fullmatch(path)
    assert match is not None
    return match


def test_transaction_summary_handler_regex_match():
    transaction_hash = "0x" + "a" * 64
    path = f"/api/v2/transactions/{transaction_hash}/summary"
    matches_handler = any(
        pattern.fullmatch(path) for pattern, handler in HANDLER_REGISTRY if handler is handle_transaction_summary
    )
    assert matches_handler


@pytest.mark.asyncio
async def test_handle_transaction_summary_success(mock_ctx):
    transaction_hash = "0x" + "b" * 64
    response_json = {"data": {"summaries": [{"template": "Transfer", "vars": {"amount": "1"}}]}}

    result = await handle_transaction_summary(
        match=_build_match(transaction_hash),
        response_json=response_json,
        chain_id="1",
        base_url="https://example.blockscout",
        ctx=mock_ctx,
    )

    assert isinstance(result, ToolResponse)
    assert isinstance(result.data, TransactionSummaryData)
    assert result.data.summary == response_json["data"]["summaries"]
    assert result.notes is None


@pytest.mark.asyncio
async def test_handle_transaction_summary_empty_response_dict(mock_ctx):
    transaction_hash = "0x" + "c" * 64

    result = await handle_transaction_summary(
        match=_build_match(transaction_hash),
        response_json={},
        chain_id="1",
        base_url="https://example.blockscout",
        ctx=mock_ctx,
    )

    assert isinstance(result, ToolResponse)
    assert isinstance(result.data, TransactionSummaryData)
    assert result.data.summary is None
    assert result.notes == ["No summary available. This usually indicates the transaction failed."]


@pytest.mark.asyncio
async def test_handle_transaction_summary_empty_response_none(mock_ctx):
    transaction_hash = "0x" + "d" * 64

    result = await handle_transaction_summary(
        match=_build_match(transaction_hash),
        response_json=None,
        chain_id="1",
        base_url="https://example.blockscout",
        ctx=mock_ctx,
    )

    assert isinstance(result, ToolResponse)
    assert isinstance(result.data, TransactionSummaryData)
    assert result.data.summary is None
    assert result.notes == ["No summary available. This usually indicates the transaction failed."]


@pytest.mark.asyncio
async def test_handle_transaction_summary_missing_data_key(mock_ctx):
    transaction_hash = "0x" + "e" * 64
    response_json = {"foo": "bar"}

    with pytest.raises(RuntimeError, match="unexpected format"):
        await handle_transaction_summary(
            match=_build_match(transaction_hash),
            response_json=response_json,
            chain_id="1",
            base_url="https://example.blockscout",
            ctx=mock_ctx,
        )


@pytest.mark.asyncio
async def test_handle_transaction_summary_missing_summaries_key(mock_ctx):
    transaction_hash = "0x" + "f" * 64
    response_json = {"data": {"foo": "bar"}}

    with pytest.raises(RuntimeError, match="unexpected format"):
        await handle_transaction_summary(
            match=_build_match(transaction_hash),
            response_json=response_json,
            chain_id="1",
            base_url="https://example.blockscout",
            ctx=mock_ctx,
        )


@pytest.mark.asyncio
async def test_handle_transaction_summary_summaries_none(mock_ctx):
    transaction_hash = "0x" + "1" * 64
    response_json = {"data": {"summaries": None}}

    with pytest.raises(RuntimeError, match="unexpected format"):
        await handle_transaction_summary(
            match=_build_match(transaction_hash),
            response_json=response_json,
            chain_id="1",
            base_url="https://example.blockscout",
            ctx=mock_ctx,
        )


@pytest.mark.asyncio
async def test_handle_transaction_summary_summaries_not_list(mock_ctx):
    transaction_hash = "0x" + "2" * 64
    response_json = {"data": {"summaries": "unexpected"}}

    with pytest.raises(RuntimeError, match="unexpected format"):
        await handle_transaction_summary(
            match=_build_match(transaction_hash),
            response_json=response_json,
            chain_id="1",
            base_url="https://example.blockscout",
            ctx=mock_ctx,
        )


@pytest.mark.asyncio
async def test_handle_transaction_summary_empty_list(mock_ctx):
    transaction_hash = "0x" + "3" * 64
    response_json = {"data": {"summaries": []}}

    result = await handle_transaction_summary(
        match=_build_match(transaction_hash),
        response_json=response_json,
        chain_id="1",
        base_url="https://example.blockscout",
        ctx=mock_ctx,
    )

    assert isinstance(result, ToolResponse)
    assert isinstance(result.data, TransactionSummaryData)
    assert result.data.summary == []


@pytest.mark.asyncio
async def test_handle_transaction_summary_multiple_summaries(mock_ctx):
    transaction_hash = "0x" + "4" * 64
    response_json = {
        "data": {
            "summaries": [
                {"template": "Summary 1", "vars": {"a": 1}},
                {"template": "Summary 2", "vars": {"b": 2}},
            ]
        }
    }

    result = await handle_transaction_summary(
        match=_build_match(transaction_hash),
        response_json=response_json,
        chain_id="1",
        base_url="https://example.blockscout",
        ctx=mock_ctx,
    )

    assert result.data.summary == response_json["data"]["summaries"]
