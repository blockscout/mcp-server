# SPDX-License-Identifier: LicenseRef-Blockscout
from unittest.mock import AsyncMock, MagicMock, call, patch

import httpx
import pytest

from blockscout_mcp_server.config import config
from blockscout_mcp_server.models import AddressInfoData, ToolResponse
from blockscout_mcp_server.tools.address.get_address_info import get_address_info
from blockscout_mcp_server.tools.common import CreditsExhaustedError


@pytest.mark.asyncio
async def test_get_address_info_success_with_metadata(mock_ctx):
    """
    Verify get_address_info correctly combines data from Blockscout and the Blockscout PRO API metadata endpoint.
    """
    chain_id = "1"
    address = "0x123abc"

    mock_blockscout_response = {
        "hash": address,
        "is_contract": True,
    }
    mock_first_tx_response = {"items": [{"block_number": 100, "timestamp": "2023-01-01T00:00:00Z", "hash": "0xabc"}]}
    mock_metadata_response = {"addresses": {address: {"tags": [{"name": "Test Tag"}]}}}

    with (
        patch(
            "blockscout_mcp_server.tools.address.get_address_info.make_blockscout_request", new_callable=AsyncMock
        ) as mock_bs_request,
        patch(
            "blockscout_mcp_server.tools.address.get_address_info.make_metadata_request", new_callable=AsyncMock
        ) as mock_meta_request,
    ):
        mock_bs_request.side_effect = [mock_blockscout_response, mock_first_tx_response]
        mock_meta_request.return_value = mock_metadata_response

        result = await get_address_info(chain_id=chain_id, address=address, ctx=mock_ctx)

        mock_bs_request.assert_has_calls(
            [
                call(
                    chain_id=chain_id,
                    api_path=f"/api/v2/addresses/{address}",
                    timeout=config.bs_light_timeout,
                ),
                call(
                    chain_id=chain_id,
                    api_path=f"/api/v2/addresses/{address}/transactions",
                    params={"sort": "block_number", "order": "asc"},
                ),
            ]
        )
        assert mock_bs_request.call_count == 2
        mock_meta_request.assert_called_once_with(
            api_path="/services/metadata/api/v1/metadata", params={"addresses": address, "chainId": chain_id}
        )

        assert isinstance(result, ToolResponse)
        assert isinstance(result.data, AddressInfoData)
        assert result.data.basic_info == mock_blockscout_response
        assert result.data.first_transaction_details is not None
        assert result.data.first_transaction_details.block_number == 100
        assert result.data.first_transaction_details.timestamp == "2023-01-01T00:00:00Z"
        assert result.data.metadata == mock_metadata_response["addresses"][address]
        assert result.notes is None
        expected_instructions = [
            (
                "This is only the native coin balance. You MUST also call `get_tokens_by_address` to get the full "
                "portfolio."
            ),
            (
                f"Use `direct_api_call` with endpoint `/api/v2/addresses/{address}/logs`"
                " to get Logs Emitted by Address."
                " Optionally pass query_params={'topic': '<32-byte hex>'} to filter logs by a single topic."
            ),
            (
                f"Use `direct_api_call` with endpoint `/api/v2/addresses/{address}/coin-balance-history-by-day` "
                "to get daily native coin balance history."
            ),
            (
                f"Use `direct_api_call` with endpoint `/api/v2/addresses/{address}/coin-balance-history` "
                "to get native coin balance history."
            ),
            (
                f"Use `direct_api_call` with endpoint `/api/v2/addresses/{address}/blocks-validated` "
                "to get Blocks Validated by this Address."
            ),
            (
                f"Use `direct_api_call` with endpoint `/api/v2/proxy/account-abstraction/accounts/{address}` "
                "to get Account Abstraction info."
            ),
            (
                f"Use `direct_api_call` with endpoint `/api/v2/proxy/account-abstraction/operations` "
                f"and query_params={{'sender': '{address}'}} to get User Operations sent by this Address."
            ),
        ]
        assert result.instructions is not None
        for instr in expected_instructions:
            assert instr in result.instructions

        assert mock_ctx.report_progress.await_count == 3
        assert mock_ctx.info.await_count == 3
        calls = mock_ctx.report_progress.call_args_list
        assert calls[0].kwargs["total"] == 2.0
        assert calls[1].kwargs["total"] == 2.0
        assert calls[2].kwargs["total"] == 2.0


@pytest.mark.asyncio
async def test_get_address_info_includes_portfolio_instruction(mock_ctx):
    """Verify get_address_info includes portfolio analysis guidance."""
    chain_id = "1"
    address = "0x123abc"

    mock_blockscout_response = {"hash": address, "is_contract": True}
    mock_metadata_response = {"addresses": {address: {"tags": [{"name": "Test Tag"}]}}}

    with (
        patch(
            "blockscout_mcp_server.tools.address.get_address_info.make_blockscout_request", new_callable=AsyncMock
        ) as mock_bs_request,
        patch(
            "blockscout_mcp_server.tools.address.get_address_info.make_metadata_request", new_callable=AsyncMock
        ) as mock_meta_request,
    ):
        mock_bs_request.return_value = mock_blockscout_response
        mock_meta_request.return_value = mock_metadata_response

        result = await get_address_info(chain_id=chain_id, address=address, ctx=mock_ctx)

        assert result.instructions is not None
        assert (
            "This is only the native coin balance. You MUST also call `get_tokens_by_address` to get the full "
            "portfolio." in result.instructions
        )


@pytest.mark.asyncio
async def test_get_address_info_success_without_metadata(mock_ctx):
    """
    Verify get_address_info correctly omits metadata section when it's not found.
    """
    chain_id = "1"
    address = "0x123abc"

    mock_blockscout_response = {"hash": address, "is_contract": False}
    mock_first_tx_response = {"items": []}
    mock_metadata_response = {"addresses": {}}

    with (
        patch(
            "blockscout_mcp_server.tools.address.get_address_info.make_blockscout_request", new_callable=AsyncMock
        ) as mock_bs_request,
        patch(
            "blockscout_mcp_server.tools.address.get_address_info.make_metadata_request", new_callable=AsyncMock
        ) as mock_meta_request,
    ):
        mock_bs_request.side_effect = [mock_blockscout_response, mock_first_tx_response]
        mock_meta_request.return_value = mock_metadata_response

        result = await get_address_info(chain_id=chain_id, address=address, ctx=mock_ctx)

        mock_bs_request.assert_has_calls(
            [
                call(
                    chain_id=chain_id,
                    api_path=f"/api/v2/addresses/{address}",
                    timeout=config.bs_light_timeout,
                ),
                call(
                    chain_id=chain_id,
                    api_path=f"/api/v2/addresses/{address}/transactions",
                    params={"sort": "block_number", "order": "asc"},
                ),
            ]
        )
        assert mock_bs_request.call_count == 2
        mock_meta_request.assert_called_once_with(
            api_path="/services/metadata/api/v1/metadata", params={"addresses": address, "chainId": chain_id}
        )

        assert isinstance(result, ToolResponse)
        assert isinstance(result.data, AddressInfoData)
        assert result.data.basic_info == mock_blockscout_response
        assert result.data.first_transaction_details is None
        assert result.data.metadata is None
        assert result.notes is None
        assert result.instructions is not None and len(result.instructions) > 0

        assert mock_ctx.report_progress.await_count == 3
        assert mock_ctx.info.await_count == 3
        calls = mock_ctx.report_progress.call_args_list
        assert calls[0].kwargs["total"] == 2.0
        assert calls[1].kwargs["total"] == 2.0
        assert calls[2].kwargs["total"] == 2.0


@pytest.mark.asyncio
async def test_get_address_info_first_transaction_failure(mock_ctx):
    """Return ToolResponse with notes when first transaction fetch fails."""
    chain_id = "1"
    address = "0x123abc"

    mock_blockscout_response = {"hash": address, "is_contract": False}
    first_tx_error = httpx.RequestError("First transaction request failed")
    mock_metadata_response = {"addresses": {}}

    with (
        patch(
            "blockscout_mcp_server.tools.address.get_address_info.make_blockscout_request",
            new_callable=AsyncMock,
        ) as mock_bs_request,
        patch(
            "blockscout_mcp_server.tools.address.get_address_info.make_metadata_request",
            new_callable=AsyncMock,
        ) as mock_meta_request,
    ):
        mock_bs_request.side_effect = [mock_blockscout_response, first_tx_error]
        mock_meta_request.return_value = mock_metadata_response

        result = await get_address_info(chain_id=chain_id, address=address, ctx=mock_ctx)

        mock_bs_request.assert_has_calls(
            [
                call(
                    chain_id=chain_id,
                    api_path=f"/api/v2/addresses/{address}",
                    timeout=config.bs_light_timeout,
                ),
                call(
                    chain_id=chain_id,
                    api_path=f"/api/v2/addresses/{address}/transactions",
                    params={"sort": "block_number", "order": "asc"},
                ),
            ]
        )
        assert mock_bs_request.call_count == 2
        mock_meta_request.assert_called_once_with(
            api_path="/services/metadata/api/v1/metadata", params={"addresses": address, "chainId": chain_id}
        )

        assert isinstance(result, ToolResponse)
        assert isinstance(result.data, AddressInfoData)
        assert result.data.basic_info == mock_blockscout_response
        assert result.data.first_transaction_details is None
        assert result.data.metadata is None
        assert result.notes is not None and len(result.notes) == 1
        assert "Could not retrieve first transaction details" in result.notes[0]

        assert mock_ctx.report_progress.await_count == 3
        assert mock_ctx.info.await_count == 3

        # Verify watershed beat carries the neutral message (honest even when first-tx failed)
        calls = mock_ctx.report_progress.call_args_list
        assert calls[1].kwargs["message"] == "Address data requests completed; processing results."
        assert calls[2].kwargs["message"] == "Successfully fetched all address data."
        assert calls[0].kwargs["total"] == 2.0
        assert calls[1].kwargs["total"] == 2.0
        assert calls[2].kwargs["total"] == 2.0


@pytest.mark.asyncio
async def test_get_address_info_blockscout_failure(mock_ctx):
    """Ensure exception is raised when primary Blockscout call fails."""
    chain_id = "1"
    address = "0x123abc"

    api_error = httpx.HTTPStatusError("Not Found", request=MagicMock(), response=MagicMock(status_code=404))

    with (
        patch(
            "blockscout_mcp_server.tools.address.get_address_info.make_blockscout_request",
            new_callable=AsyncMock,
        ) as mock_bs_request,
        patch(
            "blockscout_mcp_server.tools.address.get_address_info.make_metadata_request",
            new_callable=AsyncMock,
        ) as mock_meta_request,
    ):
        mock_bs_request.side_effect = [api_error, {"items": []}]
        mock_meta_request.return_value = {}

        with pytest.raises(httpx.HTTPStatusError):
            await get_address_info(chain_id=chain_id, address=address, ctx=mock_ctx)

        mock_bs_request.assert_has_calls(
            [
                call(
                    chain_id=chain_id,
                    api_path=f"/api/v2/addresses/{address}",
                    timeout=config.bs_light_timeout,
                ),
                call(
                    chain_id=chain_id,
                    api_path=f"/api/v2/addresses/{address}/transactions",
                    params={"sort": "block_number", "order": "asc"},
                ),
            ]
        )
        assert mock_bs_request.call_count == 2
        mock_meta_request.assert_called_once_with(
            api_path="/services/metadata/api/v1/metadata", params={"addresses": address, "chainId": chain_id}
        )

        assert mock_ctx.report_progress.await_count == 1
        assert mock_ctx.info.await_count == 1


# ---------------------------------------------------------------------------
# CreditsExhaustedError composite-tool tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_address_info_first_transaction_credits_exhausted_degrades_gracefully(mock_ctx):
    """CreditsExhaustedError on the first-transaction side request degrades softly.

    Mirrors test_get_address_info_first_transaction_failure but with the new
    exception type to prove the composite-tool soft-fail path handles it.
    """
    chain_id = "1"
    address = "0x123abc"

    mock_blockscout_response = {"hash": address, "is_contract": False}
    first_tx_error = CreditsExhaustedError(
        "Blockscout PRO API credits exhausted (HTTP 402): the API key's credit allowance is depleted."
    )
    mock_metadata_response = {"addresses": {}}

    with (
        patch(
            "blockscout_mcp_server.tools.address.get_address_info.make_blockscout_request",
            new_callable=AsyncMock,
        ) as mock_bs_request,
        patch(
            "blockscout_mcp_server.tools.address.get_address_info.make_metadata_request",
            new_callable=AsyncMock,
        ) as mock_meta_request,
    ):
        mock_bs_request.side_effect = [mock_blockscout_response, first_tx_error]
        mock_meta_request.return_value = mock_metadata_response

        result = await get_address_info(chain_id=chain_id, address=address, ctx=mock_ctx)

        assert isinstance(result, ToolResponse)
        assert isinstance(result.data, AddressInfoData)
        assert result.data.basic_info == mock_blockscout_response
        assert result.data.first_transaction_details is None
        assert result.notes is not None and len(result.notes) >= 1
        assert any("Could not retrieve first transaction details" in note for note in result.notes)


@pytest.mark.asyncio
async def test_get_address_info_primary_credits_exhausted_raises(mock_ctx):
    """CreditsExhaustedError on the primary address-info request is re-raised unchanged.

    Mirrors test_get_address_info_blockscout_failure but with CreditsExhaustedError
    to prove the tool surfaces the distinct error rather than swallowing it.
    """
    chain_id = "1"
    address = "0x123abc"

    primary_error = CreditsExhaustedError(
        "Blockscout PRO API credits exhausted (HTTP 402): the API key's credit allowance is depleted."
    )

    with (
        patch(
            "blockscout_mcp_server.tools.address.get_address_info.make_blockscout_request",
            new_callable=AsyncMock,
        ) as mock_bs_request,
        patch(
            "blockscout_mcp_server.tools.address.get_address_info.make_metadata_request",
            new_callable=AsyncMock,
        ) as mock_meta_request,
    ):
        mock_bs_request.side_effect = [primary_error, {"items": []}]
        mock_meta_request.return_value = {}

        with pytest.raises(CreditsExhaustedError):
            await get_address_info(chain_id=chain_id, address=address, ctx=mock_ctx)
