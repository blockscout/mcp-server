from unittest.mock import AsyncMock, MagicMock, call, patch

import httpx
import pytest

from blockscout_mcp_server.constants import INPUT_DATA_TRUNCATION_LIMIT
from blockscout_mcp_server.models import TokenTransfer, ToolResponse, TransactionInfoData
from blockscout_mcp_server.tools.common import ChainNotFoundError
from blockscout_mcp_server.tools.transaction.get_transaction_info import get_transaction_info


@pytest.mark.asyncio
async def test_get_transaction_info_success(mock_ctx):
    """
    Verify get_transaction_info correctly processes a successful transaction lookup.
    """
    # ARRANGE
    chain_id = "1"
    tx_hash = "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
    mock_base_url = "https://eth.blockscout.com"

    mock_api_response = {
        "hash": tx_hash,
        "block_number": 19000000,
        "block_hash": "0xblock123...",
        "from": {"hash": "0xfrom123..."},
        "to": {"hash": "0xto123..."},
        "value": "1000000000000000000",
        "gas_limit": "21000",
        "gas_used": "21000",
        "gas_price": "20000000000",
        "status": "ok",
        "timestamp": "2024-01-01T12:00:00.000000Z",
        "transaction_index": 42,
        "nonce": 123,
    }

    expected_transformed_result = {
        "block_number": 19000000,
        "block_hash": "0xblock123...",
        "from": "0xfrom123...",
        "to": "0xto123...",
        "value": "1000000000000000000",
        "gas_limit": "21000",
        "gas_used": "21000",
        "gas_price": "20000000000",
        "status": "ok",
        "timestamp": "2024-01-01T12:00:00.000000Z",
        "transaction_index": 42,
        "nonce": 123,
    }

    ops_response = {"items": []}

    with (
        patch(
            "blockscout_mcp_server.tools.transaction.get_transaction_info.get_blockscout_base_url",
            new_callable=AsyncMock,
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.transaction.get_transaction_info.make_blockscout_request",
            new_callable=AsyncMock,
        ) as mock_request,
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.side_effect = [mock_api_response, ops_response]

        # ACT
        result = await get_transaction_info(chain_id=chain_id, transaction_hash=tx_hash, ctx=mock_ctx)

        # ASSERT
        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_has_calls(
            [
                call(base_url=mock_base_url, api_path=f"/api/v2/transactions/{tx_hash}"),
                call(
                    base_url=mock_base_url,
                    api_path="/api/v2/proxy/account-abstraction/operations",
                    params={"transaction_hash": tx_hash},
                ),
            ]
        )
        assert isinstance(result, ToolResponse)
        assert isinstance(result.data, TransactionInfoData)
        data = result.data.model_dump(by_alias=True)
        for key, value in expected_transformed_result.items():
            assert data[key] == value
        assert mock_ctx.report_progress.await_count == 3
        assert mock_ctx.info.await_count == 3
        assert result.instructions is not None
        assert all("/api/v2/proxy/account-abstraction/operations" not in instr for instr in result.instructions)


@pytest.mark.asyncio
async def test_get_transaction_info_with_user_ops(mock_ctx):
    """Verify get_transaction_info includes user operations when present."""
    chain_id = "1"
    tx_hash = "0xabc123"
    mock_base_url = "https://eth.blockscout.com"

    mock_api_response = {"hash": tx_hash, "status": "ok"}
    ops_response = {
        "items": [
            {"hash": "0xop1", "address": {"hash": "0xsender1"}},
            {"hash": "0xop2", "address": {"hash": "0xsender2"}},
        ]
    }

    with (
        patch(
            "blockscout_mcp_server.tools.transaction.get_transaction_info.get_blockscout_base_url",
            new_callable=AsyncMock,
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.transaction.get_transaction_info.make_blockscout_request",
            new_callable=AsyncMock,
        ) as mock_request,
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.side_effect = [mock_api_response, ops_response]

        result = await get_transaction_info(chain_id=chain_id, transaction_hash=tx_hash, ctx=mock_ctx)

        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_has_calls(
            [
                call(base_url=mock_base_url, api_path=f"/api/v2/transactions/{tx_hash}"),
                call(
                    base_url=mock_base_url,
                    api_path="/api/v2/proxy/account-abstraction/operations",
                    params={"transaction_hash": tx_hash},
                ),
            ]
        )
        assert mock_ctx.report_progress.await_count == 3
        assert mock_ctx.info.await_count == 3
        assert any(
            "Starting to fetch transaction info" in call.kwargs.get("message", "")
            for call in mock_ctx.report_progress.await_args_list
        )
        assert any(
            "Resolved Blockscout instance URL" in call.kwargs.get("message", "")
            for call in mock_ctx.report_progress.await_args_list
        )
        assert result.data.user_operations is not None
        assert len(result.data.user_operations) == 2
        assert result.data.user_operations[0].sender == "0xsender1"
        assert result.data.user_operations[0].operation_hash == "0xop1"
        assert result.instructions is not None
        assert "endpoint_path" in result.instructions[0]
        assert "VERIFY OPERATION STATUS" in result.instructions[1]


@pytest.mark.asyncio
async def test_get_transaction_info_with_user_ops_includes_warning_note(mock_ctx):
    """Verify get_transaction_info adds warning notes and instructions for user ops."""
    chain_id = "1"
    tx_hash = "0xabc123"
    mock_base_url = "https://eth.blockscout.com"

    mock_api_response = {"hash": tx_hash, "status": "ok"}
    ops_response = {
        "items": [
            {"hash": "0xop1", "address": {"hash": "0xsender1"}},
        ]
    }

    with (
        patch(
            "blockscout_mcp_server.tools.transaction.get_transaction_info.get_blockscout_base_url",
            new_callable=AsyncMock,
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.transaction.get_transaction_info.make_blockscout_request",
            new_callable=AsyncMock,
        ) as mock_request,
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.side_effect = [mock_api_response, ops_response]

        result = await get_transaction_info(chain_id=chain_id, transaction_hash=tx_hash, ctx=mock_ctx)

        assert result.notes is not None
        assert any("successful bundle transaction" in note for note in result.notes)
        assert result.instructions is not None
        assert any("VERIFY OPERATION STATUS" in instr for instr in result.instructions)
        assert any(
            "/api/v2/proxy/account-abstraction/operations/{operation_hash}" in instr for instr in result.instructions
        )


@pytest.mark.asyncio
async def test_get_transaction_info_no_user_ops(mock_ctx):
    """Verify get_transaction_info omits user operations when none exist."""
    chain_id = "1"
    tx_hash = "0xabc123"
    mock_base_url = "https://eth.blockscout.com"

    mock_api_response = {"hash": tx_hash, "status": "ok"}
    ops_response = {"items": []}

    with (
        patch(
            "blockscout_mcp_server.tools.transaction.get_transaction_info.get_blockscout_base_url",
            new_callable=AsyncMock,
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.transaction.get_transaction_info.make_blockscout_request",
            new_callable=AsyncMock,
        ) as mock_request,
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.side_effect = [mock_api_response, ops_response]

        result = await get_transaction_info(chain_id=chain_id, transaction_hash=tx_hash, ctx=mock_ctx)

        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_has_calls(
            [
                call(base_url=mock_base_url, api_path=f"/api/v2/transactions/{tx_hash}"),
                call(
                    base_url=mock_base_url,
                    api_path="/api/v2/proxy/account-abstraction/operations",
                    params={"transaction_hash": tx_hash},
                ),
            ]
        )
        assert mock_ctx.report_progress.await_count == 3
        assert mock_ctx.info.await_count == 3
        assert any(
            "Starting to fetch transaction info" in call.kwargs.get("message", "")
            for call in mock_ctx.report_progress.await_args_list
        )
        assert any(
            "Resolved Blockscout instance URL" in call.kwargs.get("message", "")
            for call in mock_ctx.report_progress.await_args_list
        )
        assert result.data.user_operations is None
        assert all("VERIFY OPERATION STATUS" not in instr for instr in result.instructions)


@pytest.mark.asyncio
async def test_get_transaction_info_ops_api_failure(mock_ctx):
    """Verify get_transaction_info succeeds when user ops API fails."""
    chain_id = "1"
    tx_hash = "0xabc123"
    mock_base_url = "https://eth.blockscout.com"

    mock_api_response = {"hash": tx_hash, "status": "ok"}
    ops_error = httpx.HTTPStatusError("Server Error", request=MagicMock(), response=MagicMock(status_code=500))

    with (
        patch(
            "blockscout_mcp_server.tools.transaction.get_transaction_info.get_blockscout_base_url",
            new_callable=AsyncMock,
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.transaction.get_transaction_info.make_blockscout_request",
            new_callable=AsyncMock,
        ) as mock_request,
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.side_effect = [mock_api_response, ops_error]

        result = await get_transaction_info(chain_id=chain_id, transaction_hash=tx_hash, ctx=mock_ctx)

        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_has_calls(
            [
                call(base_url=mock_base_url, api_path=f"/api/v2/transactions/{tx_hash}"),
                call(
                    base_url=mock_base_url,
                    api_path="/api/v2/proxy/account-abstraction/operations",
                    params={"transaction_hash": tx_hash},
                ),
            ]
        )
        assert mock_ctx.report_progress.await_count == 3
        assert mock_ctx.info.await_count == 3
        assert any(
            "Starting to fetch transaction info" in call.kwargs.get("message", "")
            for call in mock_ctx.report_progress.await_args_list
        )
        assert any(
            "Resolved Blockscout instance URL" in call.kwargs.get("message", "")
            for call in mock_ctx.report_progress.await_args_list
        )
        assert result.data.user_operations is None
        assert result.notes is not None
        assert any("Could not retrieve user operations" in note for note in result.notes)
        assert any("Since it is not clear if the transaction contains user operations" in note for note in result.notes)
        assert all("VERIFY OPERATION STATUS" not in instr for instr in result.instructions)


@pytest.mark.asyncio
async def test_get_transaction_info_pagination_note(mock_ctx):
    """Verify get_transaction_info adds a pagination note for user ops."""
    chain_id = "1"
    tx_hash = "0xabc123"
    mock_base_url = "https://eth.blockscout.com"

    mock_api_response = {"hash": tx_hash, "status": "ok"}
    ops_response = {
        "items": [{"hash": "0xop1", "address": {"hash": "0xsender1"}}],
        "next_page_params": {"page": 2},
    }

    with (
        patch(
            "blockscout_mcp_server.tools.transaction.get_transaction_info.get_blockscout_base_url",
            new_callable=AsyncMock,
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.transaction.get_transaction_info.make_blockscout_request",
            new_callable=AsyncMock,
        ) as mock_request,
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.side_effect = [mock_api_response, ops_response]

        result = await get_transaction_info(chain_id=chain_id, transaction_hash=tx_hash, ctx=mock_ctx)

        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_has_calls(
            [
                call(base_url=mock_base_url, api_path=f"/api/v2/transactions/{tx_hash}"),
                call(
                    base_url=mock_base_url,
                    api_path="/api/v2/proxy/account-abstraction/operations",
                    params={"transaction_hash": tx_hash},
                ),
            ]
        )
        assert mock_ctx.report_progress.await_count == 3
        assert mock_ctx.info.await_count == 3
        assert any(
            "Starting to fetch transaction info" in call.kwargs.get("message", "")
            for call in mock_ctx.report_progress.await_args_list
        )
        assert any(
            "Resolved Blockscout instance URL" in call.kwargs.get("message", "")
            for call in mock_ctx.report_progress.await_args_list
        )
        assert result.notes is not None
        assert any("user_operations" in note for note in result.notes)


@pytest.mark.asyncio
async def test_get_transaction_info_no_truncation(mock_ctx):
    """Verify behavior when no data is large enough to be truncated."""
    chain_id = "1"
    tx_hash = "0x123"
    mock_base_url = "https://eth.blockscout.com"
    mock_api_response = {
        "hash": tx_hash,
        "decoded_input": {
            "method_call": "test()",
            "method_id": "0xabc",
            "parameters": ["short_string"],
        },
        "raw_input": "0xshort",
    }
    ops_response = {"items": []}

    with (
        patch(
            "blockscout_mcp_server.tools.transaction.get_transaction_info.get_blockscout_base_url",
            new_callable=AsyncMock,
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.transaction.get_transaction_info.make_blockscout_request",
            new_callable=AsyncMock,
        ) as mock_request,
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.side_effect = [mock_api_response, ops_response]

        result = await get_transaction_info(chain_id=chain_id, transaction_hash=tx_hash, ctx=mock_ctx)

        assert isinstance(result, ToolResponse)
        assert isinstance(result.data, TransactionInfoData)
        assert result.data.raw_input is None
        assert result.data.raw_input_truncated is None
        assert result.data.decoded_input.parameters[0] == "short_string"


@pytest.mark.asyncio
async def test_get_transaction_info_truncates_raw_input(mock_ctx):
    """Verify raw_input is truncated when it's too long and there's no decoded_input."""
    chain_id = "1"
    tx_hash = "0x123"
    mock_base_url = "https://eth.blockscout.com"
    long_raw_input = "0x" + "a" * INPUT_DATA_TRUNCATION_LIMIT
    mock_api_response = {"hash": tx_hash, "decoded_input": None, "raw_input": long_raw_input}
    ops_response = {"items": []}

    with (
        patch(
            "blockscout_mcp_server.tools.transaction.get_transaction_info.get_blockscout_base_url",
            new_callable=AsyncMock,
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.transaction.get_transaction_info.make_blockscout_request",
            new_callable=AsyncMock,
        ) as mock_request,
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.side_effect = [mock_api_response, ops_response]

        result = await get_transaction_info(chain_id=chain_id, transaction_hash=tx_hash, ctx=mock_ctx)

        assert isinstance(result, ToolResponse)
        assert isinstance(result.data, TransactionInfoData)
        assert result.notes is not None
        assert result.data.raw_input_truncated is True
        assert len(result.data.raw_input) <= INPUT_DATA_TRUNCATION_LIMIT


@pytest.mark.asyncio
async def test_get_transaction_info_truncates_decoded_input(mock_ctx):
    """Verify a parameter in decoded_input is truncated."""
    chain_id = "1"
    tx_hash = "0x123"
    mock_base_url = "https://eth.blockscout.com"
    long_param = "0x" + "a" * INPUT_DATA_TRUNCATION_LIMIT
    mock_api_response = {
        "hash": tx_hash,
        "decoded_input": {
            "method_call": "test()",
            "method_id": "0xabc",
            "parameters": [long_param],
        },
        "raw_input": "0xshort",
    }
    ops_response = {"items": []}

    with (
        patch(
            "blockscout_mcp_server.tools.transaction.get_transaction_info.get_blockscout_base_url",
            new_callable=AsyncMock,
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.transaction.get_transaction_info.make_blockscout_request",
            new_callable=AsyncMock,
        ) as mock_request,
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.side_effect = [mock_api_response, ops_response]

        result = await get_transaction_info(chain_id=chain_id, transaction_hash=tx_hash, ctx=mock_ctx)

        assert isinstance(result, ToolResponse)
        assert isinstance(result.data, TransactionInfoData)
        assert result.notes is not None
        param = result.data.decoded_input.parameters[0]
        assert param["value_truncated"] is True
        assert len(param["value_sample"]) <= INPUT_DATA_TRUNCATION_LIMIT


@pytest.mark.asyncio
async def test_get_transaction_info_keeps_and_truncates_raw_input_when_flagged(mock_ctx):
    """Verify raw_input is kept but truncated when include_raw_input is True."""
    chain_id = "1"
    tx_hash = "0x123"
    mock_base_url = "https://eth.blockscout.com"
    long_raw_input = "0x" + "a" * INPUT_DATA_TRUNCATION_LIMIT
    mock_api_response = {
        "hash": tx_hash,
        "decoded_input": {
            "method_call": "test()",
            "method_id": "0xabc",
            "parameters": ["short"],
        },
        "raw_input": long_raw_input,
    }
    ops_response = {"items": []}

    with (
        patch(
            "blockscout_mcp_server.tools.transaction.get_transaction_info.get_blockscout_base_url",
            new_callable=AsyncMock,
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.transaction.get_transaction_info.make_blockscout_request",
            new_callable=AsyncMock,
        ) as mock_request,
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.side_effect = [mock_api_response, ops_response]

        result = await get_transaction_info(
            chain_id=chain_id, transaction_hash=tx_hash, ctx=mock_ctx, include_raw_input=True
        )

        assert isinstance(result, ToolResponse)
        assert isinstance(result.data, TransactionInfoData)
        assert result.notes is not None
        assert result.data.raw_input is not None
        assert result.data.raw_input_truncated is True
        assert len(result.data.raw_input) <= INPUT_DATA_TRUNCATION_LIMIT


@pytest.mark.asyncio
async def test_get_transaction_info_not_found(mock_ctx):
    """
    Verify get_transaction_info correctly handles transaction not found errors.
    """
    # ARRANGE
    chain_id = "1"
    tx_hash = "0xnonexistent1234567890abcdef1234567890abcdef1234567890abcdef123456"
    mock_base_url = "https://eth.blockscout.com"

    api_error = httpx.HTTPStatusError("Not Found", request=MagicMock(), response=MagicMock(status_code=404))
    ops_response = {"items": []}

    with (
        patch(
            "blockscout_mcp_server.tools.transaction.get_transaction_info.get_blockscout_base_url",
            new_callable=AsyncMock,
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.transaction.get_transaction_info.make_blockscout_request",
            new_callable=AsyncMock,
        ) as mock_request,
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.side_effect = [api_error, ops_response]

        # ACT & ASSERT
        with pytest.raises(httpx.HTTPStatusError):
            await get_transaction_info(chain_id=chain_id, transaction_hash=tx_hash, ctx=mock_ctx)

        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_has_calls(
            [
                call(base_url=mock_base_url, api_path=f"/api/v2/transactions/{tx_hash}"),
                call(
                    base_url=mock_base_url,
                    api_path="/api/v2/proxy/account-abstraction/operations",
                    params={"transaction_hash": tx_hash},
                ),
            ]
        )
        assert mock_ctx.report_progress.await_count == 2
        assert mock_ctx.info.await_count == 2


@pytest.mark.asyncio
async def test_get_transaction_info_chain_not_found(mock_ctx):
    """
    Verify get_transaction_info correctly handles chain not found errors.
    """
    # ARRANGE
    chain_id = "999999"
    tx_hash = "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"

    chain_error = ChainNotFoundError(f"Chain with ID '{chain_id}' not found on Blockscout.")

    with patch(
        "blockscout_mcp_server.tools.transaction.get_transaction_info.get_blockscout_base_url", new_callable=AsyncMock
    ) as mock_get_url:
        mock_get_url.side_effect = chain_error

        # ACT & ASSERT
        with pytest.raises(ChainNotFoundError):
            await get_transaction_info(chain_id=chain_id, transaction_hash=tx_hash, ctx=mock_ctx)

        mock_get_url.assert_called_once_with(chain_id)
        assert mock_ctx.report_progress.await_count == 1
        assert mock_ctx.info.await_count == 1


@pytest.mark.asyncio
async def test_get_transaction_info_minimal_response(mock_ctx):
    """
    Verify get_transaction_info handles minimal transaction response.
    """
    # ARRANGE
    chain_id = "1"
    tx_hash = "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
    mock_base_url = "https://eth.blockscout.com"

    mock_api_response = {
        "hash": tx_hash,
        "status": "pending",
        # Minimal response with most fields missing
    }
    ops_response = {"items": []}

    with (
        patch(
            "blockscout_mcp_server.tools.transaction.get_transaction_info.get_blockscout_base_url",
            new_callable=AsyncMock,
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.transaction.get_transaction_info.make_blockscout_request",
            new_callable=AsyncMock,
        ) as mock_request,
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.side_effect = [mock_api_response, ops_response]

        # ACT
        result = await get_transaction_info(chain_id=chain_id, transaction_hash=tx_hash, ctx=mock_ctx)

        # ASSERT
        mock_get_url.assert_called_once_with(chain_id)
        mock_request.assert_has_calls(
            [
                call(base_url=mock_base_url, api_path=f"/api/v2/transactions/{tx_hash}"),
                call(
                    base_url=mock_base_url,
                    api_path="/api/v2/proxy/account-abstraction/operations",
                    params={"transaction_hash": tx_hash},
                ),
            ]
        )
        expected_result = {"status": "pending", "token_transfers": []}
        assert isinstance(result, ToolResponse)
        assert isinstance(result.data, TransactionInfoData)
        data = result.data.model_dump(by_alias=True)
        for key, value in expected_result.items():
            assert data[key] == value
        assert mock_ctx.report_progress.await_count == 3
        assert mock_ctx.info.await_count == 3


@pytest.mark.asyncio
async def test_get_transaction_info_with_token_transfers_transformation(mock_ctx):
    """
    Verify get_transaction_info correctly transforms the token_transfers list.
    """
    # ARRANGE
    chain_id = "1"
    tx_hash = "0xd4df84bf9e45af2aa8310f74a2577a28b420c59f2e3da02c52b6d39dc83ef10f"
    mock_base_url = "https://eth.blockscout.com"

    mock_api_response = {
        "hash": tx_hash,
        "from": {"hash": "0xe725..."},
        "to": {"hash": "0x3328..."},
        "token_transfers": [
            {
                "block_hash": "0x841ad...",
                "block_number": 22697200,
                "from": {"hash": "0x000..."},
                "to": {"hash": "0x3328..."},
                "token": {"name": "WETH", "symbol": "WETH"},
                "total": {"value": "2046..."},
                "transaction_hash": tx_hash,
                "timestamp": "2025-06-13T17:42:23.000000Z",
                "type": "token_minting",
                "log_index": 13,
            }
        ],
    }
    ops_response = {"items": []}

    with (
        patch(
            "blockscout_mcp_server.tools.transaction.get_transaction_info.get_blockscout_base_url",
            new_callable=AsyncMock,
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.transaction.get_transaction_info.make_blockscout_request",
            new_callable=AsyncMock,
        ) as mock_request,
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.side_effect = [mock_api_response, ops_response]

        # ACT
        result = await get_transaction_info(chain_id=chain_id, transaction_hash=tx_hash, ctx=mock_ctx)

        # ASSERT
        assert isinstance(result, ToolResponse)
        assert isinstance(result.data, TransactionInfoData)
        assert result.data.from_address == "0xe725..."
        assert result.data.to_address == "0x3328..."
        assert isinstance(result.data.token_transfers[0], TokenTransfer)
        assert result.data.token_transfers[0].transfer_type == "token_minting"
        assert mock_ctx.report_progress.await_count == 3
        assert mock_ctx.info.await_count == 3


@pytest.mark.asyncio
async def test_get_transaction_info_handles_null_token_transfer_metadata(mock_ctx):
    """Verify get_transaction_info accepts token transfers with null token metadata."""
    # ARRANGE
    chain_id = "1"
    tx_hash = "0x9d4df84bf9e45af2aa8310f74a2577a28b420c59f2e3da02c52b6d39dc83ef10f"
    mock_base_url = "https://eth.blockscout.com"

    mock_api_response = {
        "hash": tx_hash,
        "from": {"hash": "0xe725..."},
        "to": {"hash": "0x3328..."},
        "token_transfers": [
            {
                "block_hash": "0x841ad...",
                "block_number": 22697200,
                "from": {"hash": "0x000..."},
                "to": {"hash": "0x3328..."},
                "token": None,
                "total": {"value": "2046..."},
                "transaction_hash": tx_hash,
                "timestamp": "2025-06-13T17:42:23.000000Z",
                "type": "token_minting",
                "log_index": 13,
            }
        ],
    }
    ops_response = {"items": []}

    with (
        patch(
            "blockscout_mcp_server.tools.transaction.get_transaction_info.get_blockscout_base_url",
            new_callable=AsyncMock,
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.transaction.get_transaction_info.make_blockscout_request",
            new_callable=AsyncMock,
        ) as mock_request,
    ):
        mock_get_url.return_value = mock_base_url
        mock_request.side_effect = [mock_api_response, ops_response]

        # ACT
        result = await get_transaction_info(chain_id=chain_id, transaction_hash=tx_hash, ctx=mock_ctx)

        # ASSERT
        assert isinstance(result, ToolResponse)
        assert isinstance(result.data, TransactionInfoData)
        assert isinstance(result.data.token_transfers[0], TokenTransfer)
        assert result.data.token_transfers[0].token is None
        assert mock_ctx.report_progress.await_count == 3
        assert mock_ctx.info.await_count == 3
