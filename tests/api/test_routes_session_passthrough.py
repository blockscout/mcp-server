# SPDX-License-Identifier: LicenseRef-Blockscout
"""Passthrough coverage for the `session_id` query parameter on REST tool wrappers.

Phase 8 adds `"session_id"` to the `optional` list of every REST wrapper that
invokes a tool function (rule 230's "success including optional parameters"
slot), except the two unlock wrappers (which take no `session_id`) and the
deprecated endpoints (which invoke no tool). This module proves the plumbing:
a request with `session_id=<value>` reaches the (mocked) tool as a
`session_id=<value>` kwarg, and a request without it reaches the tool with no
`session_id` kwarg at all (mirroring the existing optional-parameter contract
in `tests/api/test_routes.py`).

Not merged into `tests/api/test_routes.py`: that file is already 1,027 lines,
exceeding the file-size guideline, and is not to be grown by this plan.
"""

from unittest.mock import ANY, AsyncMock, patch

import pytest
from httpx import AsyncClient

from blockscout_mcp_server.models import ToolResponse

_SESSION_ID = "test-session-id-value"

# (query suffix without session_id, patch target name in routes module, expected
# base kwargs the tool receives when session_id is absent)
ENDPOINTS = [
    (
        "/v1/get_block_info",
        "chain_id=1&number_or_hash=latest",
        "get_block_info",
        {"chain_id": "1", "number_or_hash": "latest"},
    ),
    ("/v1/get_block_number", "chain_id=1", "get_block_number", {"chain_id": "1"}),
    (
        "/v1/get_address_by_ens_name",
        "name=foo.eth",
        "get_address_by_ens_name",
        {"name": "foo.eth"},
    ),
    (
        "/v1/get_transactions_by_address",
        "chain_id=1&address=0xabc&age_from=2023-01-01",
        "get_transactions_by_address",
        {"chain_id": "1", "address": "0xabc", "age_from": "2023-01-01"},
    ),
    (
        "/v1/get_token_transfers_by_address",
        "chain_id=1&address=0xabc&age_from=2023-01-01",
        "get_token_transfers_by_address",
        {"chain_id": "1", "address": "0xabc", "age_from": "2023-01-01"},
    ),
    (
        "/v1/lookup_token_by_symbol",
        "chain_id=1&symbol=USDC",
        "lookup_token_by_symbol",
        {"chain_id": "1", "symbol": "USDC"},
    ),
    (
        "/v1/get_contract_abi",
        "chain_id=1&address=0xabc",
        "get_contract_abi",
        {"chain_id": "1", "address": "0xabc"},
    ),
    (
        "/v1/inspect_contract_code",
        "chain_id=1&address=0xabc",
        "inspect_contract_code",
        {"chain_id": "1", "address": "0xabc"},
    ),
    (
        "/v1/get_address_info",
        "chain_id=1&address=0xabc",
        "get_address_info",
        {"chain_id": "1", "address": "0xabc"},
    ),
    (
        "/v1/get_tokens_by_address",
        "chain_id=1&address=0xabc",
        "get_tokens_by_address",
        {"chain_id": "1", "address": "0xabc"},
    ),
    (
        "/v1/nft_tokens_by_address",
        "chain_id=1&address=0xabc",
        "nft_tokens_by_address",
        {"chain_id": "1", "address": "0xabc"},
    ),
    (
        "/v1/get_transaction_info",
        "chain_id=1&transaction_hash=0xdead",
        "get_transaction_info",
        {"chain_id": "1", "transaction_hash": "0xdead"},
    ),
    ("/v1/get_chains_list", "", "get_chains_list", {}),
]


def _assert_rest_marked_ctx(mock_tool: AsyncMock) -> None:
    """Assert the ctx the tool was actually called with is REST-marked.

    `ctx=ANY` in `assert_called_once_with` only proves *some* ctx arrived; it
    says nothing about which surface it claims. Pulling the captured ctx out of
    `call_args.kwargs` and checking `call_source == "rest"` is what turns this
    module into a structural guard: a future REST wrapper that forgets
    `get_mock_context` (and would therefore silently meter at the MCP ceiling
    instead of the REST one) fails here by name.
    """
    captured_ctx = mock_tool.call_args.kwargs["ctx"]
    assert captured_ctx.call_source == "rest"


@pytest.mark.asyncio
@pytest.mark.parametrize("path, query, tool_name, base_kwargs", ENDPOINTS, ids=[e[2] for e in ENDPOINTS])
async def test_session_id_passed_through_when_present(path, query, tool_name, base_kwargs, client: AsyncClient):
    """A request with `session_id=<value>` reaches the tool as a `session_id` kwarg."""
    with patch(f"blockscout_mcp_server.api.routes.{tool_name}", new_callable=AsyncMock) as mock_tool:
        mock_tool.return_value = ToolResponse(data={"ok": True})
        full_query = f"{query}&session_id={_SESSION_ID}" if query else f"session_id={_SESSION_ID}"
        response = await client.get(f"{path}?{full_query}")

    assert response.status_code == 200
    mock_tool.assert_called_once_with(**base_kwargs, session_id=_SESSION_ID, ctx=ANY)
    _assert_rest_marked_ctx(mock_tool)


@pytest.mark.asyncio
@pytest.mark.parametrize("path, query, tool_name, base_kwargs", ENDPOINTS, ids=[e[2] for e in ENDPOINTS])
async def test_session_id_absent_when_not_supplied(path, query, tool_name, base_kwargs, client: AsyncClient):
    """A request without `session_id` reaches the tool with no `session_id` kwarg at all."""
    with patch(f"blockscout_mcp_server.api.routes.{tool_name}", new_callable=AsyncMock) as mock_tool:
        mock_tool.return_value = ToolResponse(data={"ok": True})
        url = f"{path}?{query}" if query else path
        response = await client.get(url)

    assert response.status_code == 200
    mock_tool.assert_called_once_with(**base_kwargs, ctx=ANY)
    _assert_rest_marked_ctx(mock_tool)


@pytest.mark.asyncio
@patch("blockscout_mcp_server.api.routes.read_contract", new_callable=AsyncMock)
async def test_read_contract_session_id_passthrough(mock_tool, client: AsyncClient):
    """`read_contract`'s extra `abi` JSON-parsing step does not disturb `session_id` passthrough."""
    mock_tool.return_value = ToolResponse(data={"ok": True})
    response = await client.get(
        f"/v1/read_contract?chain_id=1&address=0xabc&abi=%7B%7D&function_name=foo&session_id={_SESSION_ID}"
    )
    assert response.status_code == 200
    mock_tool.assert_called_once_with(
        chain_id="1",
        address="0xabc",
        abi={},
        function_name="foo",
        session_id=_SESSION_ID,
        ctx=ANY,
    )
    _assert_rest_marked_ctx(mock_tool)


@pytest.mark.asyncio
@patch("blockscout_mcp_server.api.routes.read_contract", new_callable=AsyncMock)
async def test_read_contract_no_session_id_when_absent(mock_tool, client: AsyncClient):
    """`read_contract` receives no `session_id` kwarg when the query omits it."""
    mock_tool.return_value = ToolResponse(data={"ok": True})
    response = await client.get("/v1/read_contract?chain_id=1&address=0xabc&abi=%7B%7D&function_name=foo")
    assert response.status_code == 200
    mock_tool.assert_called_once_with(
        chain_id="1",
        address="0xabc",
        abi={},
        function_name="foo",
        ctx=ANY,
    )
    _assert_rest_marked_ctx(mock_tool)


@pytest.mark.asyncio
@patch("blockscout_mcp_server.api.routes.get_block_number", new_callable=AsyncMock)
async def test_get_latest_block_session_id_passthrough(mock_tool, client: AsyncClient):
    """The legacy `get_latest_block` wrapper explicitly forwards `session_id` alongside `datetime=None`."""
    mock_tool.return_value = ToolResponse(data={"block_number": 1})
    response = await client.get(f"/v1/get_latest_block?chain_id=1&session_id={_SESSION_ID}")
    assert response.status_code == 200
    mock_tool.assert_called_once_with(chain_id="1", datetime=None, session_id=_SESSION_ID, ctx=ANY)
    _assert_rest_marked_ctx(mock_tool)


@pytest.mark.asyncio
@patch("blockscout_mcp_server.api.routes.get_block_number", new_callable=AsyncMock)
async def test_get_latest_block_session_id_none_when_absent(mock_tool, client: AsyncClient):
    """The legacy `get_latest_block` wrapper still forwards `session_id=None` when the query omits it."""
    mock_tool.return_value = ToolResponse(data={"block_number": 1})
    response = await client.get("/v1/get_latest_block?chain_id=1")
    assert response.status_code == 200
    mock_tool.assert_called_once_with(chain_id="1", datetime=None, session_id=None, ctx=ANY)
    _assert_rest_marked_ctx(mock_tool)


@pytest.mark.asyncio
@patch("blockscout_mcp_server.api.routes.__unlock_blockchain_analysis__", new_callable=AsyncMock)
async def test_unlock_endpoints_reject_and_pass_nothing(mock_tool, client: AsyncClient):
    """The two unlock endpoints accept no `session_id` and pass none to the tool."""
    mock_tool.return_value = ToolResponse(data={"version": "1.0"})

    response = await client.get(f"/v1/get_instructions?session_id={_SESSION_ID}")
    assert response.status_code == 200
    mock_tool.assert_called_once_with(ctx=ANY)
    _assert_rest_marked_ctx(mock_tool)

    mock_tool.reset_mock()
    response = await client.get(f"/v1/unlock_blockchain_analysis?session_id={_SESSION_ID}")
    assert response.status_code == 200
    mock_tool.assert_called_once_with(ctx=ANY)
    _assert_rest_marked_ctx(mock_tool)


@pytest.mark.asyncio
@patch("blockscout_mcp_server.api.routes.direct_api_call", new_callable=AsyncMock)
async def test_direct_api_call_sweep_guard_get(mock_tool, client: AsyncClient):
    """A bare `session_id` plus an ordinary filter: `session_id` is the top-level kwarg,
    `query_params` carries the filter but not `session_id`."""
    mock_tool.return_value = ToolResponse(data={"items": []})
    response = await client.get(
        f"/v1/direct_api_call?chain_id=1&endpoint_path=/api/v2/stats&session_id={_SESSION_ID}&status=ok"
    )
    assert response.status_code == 200
    mock_tool.assert_called_once_with(
        chain_id="1",
        endpoint_path="/api/v2/stats",
        session_id=_SESSION_ID,
        query_params={"status": "ok"},
        ctx=ANY,
    )
    _assert_rest_marked_ctx(mock_tool)


@pytest.mark.asyncio
@patch("blockscout_mcp_server.api.routes.direct_api_call", new_callable=AsyncMock)
async def test_direct_api_call_sweep_guard_post(mock_tool, client: AsyncClient):
    """Same sweep guard on the POST path."""
    mock_tool.return_value = ToolResponse(data={"ok": True})
    response = await client.post(
        f"/v1/direct_api_call?chain_id=1&endpoint_path=/api/v2/stats&session_id={_SESSION_ID}&status=ok",
        json={"foo": "bar"},
    )
    assert response.status_code == 200
    mock_tool.assert_called_once_with(
        chain_id="1",
        endpoint_path="/api/v2/stats",
        session_id=_SESSION_ID,
        json_body={"foo": "bar"},
        method="POST",
        query_params={"status": "ok"},
        ctx=ANY,
    )
    _assert_rest_marked_ctx(mock_tool)


@pytest.mark.asyncio
@patch("blockscout_mcp_server.api.routes.direct_api_call", new_callable=AsyncMock)
async def test_direct_api_call_bracketed_query_params_session_id_escape_hatch(mock_tool, client: AsyncClient):
    """A `query_params[session_id]=...` spelling is a deliberate upstream filter,
    untouched by the sweep guard, and still arrives inside `query_params`."""
    mock_tool.return_value = ToolResponse(data={"items": []})
    response = await client.get(
        "/v1/direct_api_call?chain_id=1&endpoint_path=/api/v2/stats&query_params%5Bsession_id%5D=upstream-value"
    )
    assert response.status_code == 200
    mock_tool.assert_called_once_with(
        chain_id="1",
        endpoint_path="/api/v2/stats",
        query_params={"session_id": "upstream-value"},
        ctx=ANY,
    )
    _assert_rest_marked_ctx(mock_tool)
