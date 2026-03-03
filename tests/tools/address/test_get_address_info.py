from unittest.mock import AsyncMock, MagicMock, call, patch

import httpx
import pytest

from blockscout_mcp_server.config import config
from blockscout_mcp_server.constants import INPUT_DATA_TRUNCATION_LIMIT
from blockscout_mcp_server.models import AddressInfoData, ToolResponse
from blockscout_mcp_server.tools.address.get_address_info import _process_metadata_tags, get_address_info


def _long_string() -> str:
    return "x" * (INPUT_DATA_TRUNCATION_LIMIT + 20)


@pytest.mark.asyncio
async def test_get_address_info_success_with_metadata(mock_ctx):
    """
    Verify get_address_info correctly combines data from Blockscout and Metadata APIs.
    """
    chain_id = "1"
    address = "0x123abc"
    mock_base_url = "https://eth.blockscout.com"

    mock_blockscout_response = {
        "hash": address,
        "is_contract": True,
    }
    mock_first_tx_response = {"items": [{"block_number": 100, "timestamp": "2023-01-01T00:00:00Z", "hash": "0xabc"}]}
    mock_metadata_response = {"addresses": {address: {"tags": [{"name": "Test Tag"}]}}}

    with (
        patch(
            "blockscout_mcp_server.tools.address.get_address_info.get_blockscout_base_url", new_callable=AsyncMock
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.address.get_address_info.make_blockscout_request", new_callable=AsyncMock
        ) as mock_bs_request,
        patch(
            "blockscout_mcp_server.tools.address.get_address_info.make_metadata_request", new_callable=AsyncMock
        ) as mock_meta_request,
    ):
        mock_get_url.return_value = mock_base_url
        mock_bs_request.side_effect = [mock_blockscout_response, mock_first_tx_response]
        mock_meta_request.return_value = mock_metadata_response

        result = await get_address_info(chain_id=chain_id, address=address, ctx=mock_ctx)

        mock_get_url.assert_called_once_with(chain_id)
        mock_bs_request.assert_has_calls(
            [
                call(base_url=mock_base_url, api_path=f"/api/v2/addresses/{address}"),
                call(
                    base_url=mock_base_url,
                    api_path=f"/api/v2/addresses/{address}/transactions",
                    params={"sort": "block_number", "order": "asc"},
                ),
            ]
        )
        assert mock_bs_request.call_count == 2
        mock_meta_request.assert_called_once_with(
            api_path="/api/v1/metadata", params={"addresses": address, "chainId": chain_id}
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
            (f"Use `direct_api_call` with endpoint `/api/v2/addresses/{address}/logs` to get Logs Emitted by Address."),
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

        assert mock_ctx.report_progress.await_count == 4
        assert mock_ctx.info.await_count == 4


@pytest.mark.asyncio
async def test_get_address_info_includes_portfolio_instruction(mock_ctx):
    """Verify get_address_info includes portfolio analysis guidance."""
    chain_id = "1"
    address = "0x123abc"
    mock_base_url = "https://eth.blockscout.com"

    mock_blockscout_response = {"hash": address, "is_contract": True}
    mock_metadata_response = {"addresses": {address: {"tags": [{"name": "Test Tag"}]}}}

    with (
        patch(
            "blockscout_mcp_server.tools.address.get_address_info.get_blockscout_base_url", new_callable=AsyncMock
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.address.get_address_info.make_blockscout_request", new_callable=AsyncMock
        ) as mock_bs_request,
        patch(
            "blockscout_mcp_server.tools.address.get_address_info.make_metadata_request", new_callable=AsyncMock
        ) as mock_meta_request,
    ):
        mock_get_url.return_value = mock_base_url
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
    mock_base_url = "https://eth.blockscout.com"

    mock_blockscout_response = {"hash": address, "is_contract": False}
    mock_first_tx_response = {"items": []}
    mock_metadata_response = {"addresses": {}}

    with (
        patch(
            "blockscout_mcp_server.tools.address.get_address_info.get_blockscout_base_url", new_callable=AsyncMock
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.address.get_address_info.make_blockscout_request", new_callable=AsyncMock
        ) as mock_bs_request,
        patch(
            "blockscout_mcp_server.tools.address.get_address_info.make_metadata_request", new_callable=AsyncMock
        ) as mock_meta_request,
    ):
        mock_get_url.return_value = mock_base_url
        mock_bs_request.side_effect = [mock_blockscout_response, mock_first_tx_response]
        mock_meta_request.return_value = mock_metadata_response

        result = await get_address_info(chain_id=chain_id, address=address, ctx=mock_ctx)

        mock_get_url.assert_called_once_with(chain_id)
        mock_bs_request.assert_has_calls(
            [
                call(base_url=mock_base_url, api_path=f"/api/v2/addresses/{address}"),
                call(
                    base_url=mock_base_url,
                    api_path=f"/api/v2/addresses/{address}/transactions",
                    params={"sort": "block_number", "order": "asc"},
                ),
            ]
        )
        assert mock_bs_request.call_count == 2
        mock_meta_request.assert_called_once_with(
            api_path="/api/v1/metadata", params={"addresses": address, "chainId": chain_id}
        )

        assert isinstance(result, ToolResponse)
        assert isinstance(result.data, AddressInfoData)
        assert result.data.basic_info == mock_blockscout_response
        assert result.data.first_transaction_details is None
        assert result.data.metadata is None
        assert result.notes is None
        assert result.instructions is not None and len(result.instructions) > 0

        assert mock_ctx.report_progress.await_count == 4
        assert mock_ctx.info.await_count == 4


@pytest.mark.asyncio
async def test_get_address_info_metadata_failure(mock_ctx):
    """Return ToolResponse with notes when metadata API fails."""
    chain_id = "1"
    address = "0x123abc"
    mock_base_url = "https://eth.blockscout.com"

    mock_blockscout_response = {"hash": address, "is_contract": False}
    mock_first_tx_response = {"items": []}
    metadata_error = httpx.RequestError("Network error")

    with (
        patch(
            "blockscout_mcp_server.tools.address.get_address_info.get_blockscout_base_url",
            new_callable=AsyncMock,
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.address.get_address_info.make_blockscout_request",
            new_callable=AsyncMock,
        ) as mock_bs_request,
        patch(
            "blockscout_mcp_server.tools.address.get_address_info.make_metadata_request",
            new_callable=AsyncMock,
        ) as mock_meta_request,
    ):
        mock_get_url.return_value = mock_base_url
        mock_bs_request.side_effect = [mock_blockscout_response, mock_first_tx_response]
        mock_meta_request.side_effect = metadata_error

        result = await get_address_info(chain_id=chain_id, address=address, ctx=mock_ctx)

        mock_get_url.assert_called_once_with(chain_id)
        mock_bs_request.assert_has_calls(
            [
                call(base_url=mock_base_url, api_path=f"/api/v2/addresses/{address}"),
                call(
                    base_url=mock_base_url,
                    api_path=f"/api/v2/addresses/{address}/transactions",
                    params={"sort": "block_number", "order": "asc"},
                ),
            ]
        )
        assert mock_bs_request.call_count == 2
        mock_meta_request.assert_called_once_with(
            api_path="/api/v1/metadata", params={"addresses": address, "chainId": chain_id}
        )

        assert isinstance(result, ToolResponse)
        assert isinstance(result.data, AddressInfoData)
        assert result.data.basic_info == mock_blockscout_response
        assert result.data.first_transaction_details is None
        assert result.data.metadata is None
        assert result.notes is not None and len(result.notes) == 1
        assert "Could not retrieve address metadata" in result.notes[0]

        assert mock_ctx.report_progress.await_count == 4
        assert mock_ctx.info.await_count == 4


@pytest.mark.asyncio
async def test_get_address_info_first_transaction_failure(mock_ctx):
    """Return ToolResponse with notes when first transaction fetch fails."""
    chain_id = "1"
    address = "0x123abc"
    mock_base_url = "https://eth.blockscout.com"

    mock_blockscout_response = {"hash": address, "is_contract": False}
    first_tx_error = httpx.RequestError("First transaction request failed")
    mock_metadata_response = {"addresses": {}}

    with (
        patch(
            "blockscout_mcp_server.tools.address.get_address_info.get_blockscout_base_url",
            new_callable=AsyncMock,
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.address.get_address_info.make_blockscout_request",
            new_callable=AsyncMock,
        ) as mock_bs_request,
        patch(
            "blockscout_mcp_server.tools.address.get_address_info.make_metadata_request",
            new_callable=AsyncMock,
        ) as mock_meta_request,
    ):
        mock_get_url.return_value = mock_base_url
        mock_bs_request.side_effect = [mock_blockscout_response, first_tx_error]
        mock_meta_request.return_value = mock_metadata_response

        result = await get_address_info(chain_id=chain_id, address=address, ctx=mock_ctx)

        mock_get_url.assert_called_once_with(chain_id)
        mock_bs_request.assert_has_calls(
            [
                call(base_url=mock_base_url, api_path=f"/api/v2/addresses/{address}"),
                call(
                    base_url=mock_base_url,
                    api_path=f"/api/v2/addresses/{address}/transactions",
                    params={"sort": "block_number", "order": "asc"},
                ),
            ]
        )
        assert mock_bs_request.call_count == 2
        mock_meta_request.assert_called_once_with(
            api_path="/api/v1/metadata", params={"addresses": address, "chainId": chain_id}
        )

        assert isinstance(result, ToolResponse)
        assert isinstance(result.data, AddressInfoData)
        assert result.data.basic_info == mock_blockscout_response
        assert result.data.first_transaction_details is None
        assert result.data.metadata is None
        assert result.notes is not None and len(result.notes) == 1
        assert "Could not retrieve first transaction details" in result.notes[0]

        assert mock_ctx.report_progress.await_count == 4
        assert mock_ctx.info.await_count == 4


@pytest.mark.asyncio
async def test_get_address_info_blockscout_failure(mock_ctx):
    """Ensure exception is raised when primary Blockscout call fails."""
    chain_id = "1"
    address = "0x123abc"
    mock_base_url = "https://eth.blockscout.com"

    api_error = httpx.HTTPStatusError("Not Found", request=MagicMock(), response=MagicMock(status_code=404))

    with (
        patch(
            "blockscout_mcp_server.tools.address.get_address_info.get_blockscout_base_url",
            new_callable=AsyncMock,
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.address.get_address_info.make_blockscout_request",
            new_callable=AsyncMock,
        ) as mock_bs_request,
        patch(
            "blockscout_mcp_server.tools.address.get_address_info.make_metadata_request",
            new_callable=AsyncMock,
        ) as mock_meta_request,
    ):
        mock_get_url.return_value = mock_base_url
        mock_bs_request.side_effect = [api_error, {"items": []}]
        mock_meta_request.return_value = {}

        with pytest.raises(httpx.HTTPStatusError):
            await get_address_info(chain_id=chain_id, address=address, ctx=mock_ctx)

        mock_get_url.assert_called_once_with(chain_id)
        mock_bs_request.assert_has_calls(
            [
                call(base_url=mock_base_url, api_path=f"/api/v2/addresses/{address}"),
                call(
                    base_url=mock_base_url,
                    api_path=f"/api/v2/addresses/{address}/transactions",
                    params={"sort": "block_number", "order": "asc"},
                ),
            ]
        )
        assert mock_bs_request.call_count == 2
        mock_meta_request.assert_called_once_with(
            api_path="/api/v1/metadata", params={"addresses": address, "chainId": chain_id}
        )

        assert mock_ctx.report_progress.await_count == 2
        assert mock_ctx.info.await_count == 2


def test_process_metadata_tags_truncates_oversized_meta_values():
    metadata_data = {
        "tags": [
            {
                "slug": "warpcast-account",
                "meta": ('{"tagUrl":"https://example.com/user","tagIcon":"' + _long_string() + '"}'),
            }
        ]
    }

    processed, truncated = _process_metadata_tags(metadata_data)

    assert truncated is True
    assert processed is not None
    meta = processed["tags"][0]["meta"]
    assert meta["tagUrl"] == "https://example.com/user"
    assert meta["tagIcon"]["value_truncated"] is True


def test_process_metadata_tags_preserves_small_meta_values():
    metadata_data = {"tags": [{"meta": '{"tagUrl":"https://example.com/user","tagName":"Alice"}'}]}

    processed, truncated = _process_metadata_tags(metadata_data)

    assert truncated is False
    assert processed == {"tags": [{"meta": {"tagUrl": "https://example.com/user", "tagName": "Alice"}}]}


def test_process_metadata_tags_invalid_json_short_string_is_preserved():
    metadata_data = {"tags": [{"meta": "not json"}]}

    processed, truncated = _process_metadata_tags(metadata_data)

    assert truncated is False
    assert processed == metadata_data


def test_process_metadata_tags_invalid_json_oversized_string_is_truncated():
    metadata_data = {"tags": [{"meta": _long_string()}]}

    processed, truncated = _process_metadata_tags(metadata_data)

    assert truncated is True
    assert processed is not None
    assert processed["tags"][0]["meta"]["value_truncated"] is True


def test_process_metadata_tags_truncates_when_meta_is_dict():
    metadata_data = {"tags": [{"meta": {"icon": _long_string(), "label": "ok"}}]}

    processed, truncated = _process_metadata_tags(metadata_data)

    assert truncated is True
    assert processed is not None
    assert processed["tags"][0]["meta"]["icon"]["value_truncated"] is True
    assert processed["tags"][0]["meta"]["label"] == "ok"


def test_process_metadata_tags_truncates_when_meta_parses_to_array():
    metadata_data = {"tags": [{"meta": '[{"k":"' + _long_string() + '"}]'}]}

    processed, truncated = _process_metadata_tags(metadata_data)

    assert truncated is True
    assert processed is not None
    assert processed["tags"][0]["meta"][0]["k"]["value_truncated"] is True


def test_process_metadata_tags_parses_json_primitives():
    metadata_data = {"tags": [{"meta": "null"}, {"meta": "true"}]}

    processed, truncated = _process_metadata_tags(metadata_data)

    assert truncated is False
    assert processed == {"tags": [{"meta": None}, {"meta": True}]}


def test_process_metadata_tags_truncates_long_json_string_primitive():
    metadata_data = {"tags": [{"meta": '"' + _long_string() + '"'}]}

    processed, truncated = _process_metadata_tags(metadata_data)

    assert truncated is True
    assert processed is not None
    assert processed["tags"][0]["meta"]["value_truncated"] is True


def test_process_metadata_tags_handles_missing_tags_key():
    metadata_data = {"name": "metadata without tags"}

    processed, truncated = _process_metadata_tags(metadata_data)

    assert processed == metadata_data
    assert truncated is False


def test_process_metadata_tags_handles_none_metadata():
    processed, truncated = _process_metadata_tags(None)

    assert processed is None
    assert truncated is False


@pytest.mark.asyncio
async def test_get_address_info_adds_note_when_metadata_meta_is_truncated(mock_ctx):
    chain_id = "1"
    address = "0x123abc"
    mock_base_url = "https://eth.blockscout.com"
    mock_blockscout_response = {"hash": address, "is_contract": True}
    mock_first_tx_response = {"items": []}
    mock_metadata_response = {
        "addresses": {
            address: {"tags": [{"meta": ('{"tagUrl":"https://example.com/user","tagIcon":"' + _long_string() + '"}')}]}
        }
    }

    with (
        patch(
            "blockscout_mcp_server.tools.address.get_address_info.get_blockscout_base_url", new_callable=AsyncMock
        ) as mock_get_url,
        patch(
            "blockscout_mcp_server.tools.address.get_address_info.make_blockscout_request", new_callable=AsyncMock
        ) as mock_bs_request,
        patch(
            "blockscout_mcp_server.tools.address.get_address_info.make_metadata_request", new_callable=AsyncMock
        ) as mock_meta_request,
    ):
        mock_get_url.return_value = mock_base_url
        mock_bs_request.side_effect = [mock_blockscout_response, mock_first_tx_response]
        mock_meta_request.return_value = mock_metadata_response

        result = await get_address_info(chain_id=chain_id, address=address, ctx=mock_ctx)

    assert result.notes is not None
    assert any("Some metadata tag fields were truncated" in note for note in result.notes)
    expected_metadata_prefix = f'`curl "{str(config.metadata_url).rstrip("/")}/api/v1/metadata?addresses={address}'
    assert any(expected_metadata_prefix in note for note in result.notes)
    assert any(f"chainId={chain_id}" in note for note in result.notes)
    assert result.data.metadata is not None
    assert result.data.metadata["tags"][0]["meta"]["tagIcon"]["value_truncated"] is True
