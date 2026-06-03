# SPDX-License-Identifier: LicenseRef-Blockscout
"""Metadata-focused unit tests for get_address_info.

Covers: metadata failure degradation (RequestError and HTTPStatusError),
_process_metadata_tags behaviour, and the truncation-note content.
"""

from unittest.mock import AsyncMock, MagicMock, call, patch

import httpx
import pytest

from blockscout_mcp_server.config import config
from blockscout_mcp_server.constants import INPUT_DATA_TRUNCATION_LIMIT
from blockscout_mcp_server.models import AddressInfoData, ToolResponse
from blockscout_mcp_server.tools.address.get_address_info import _process_metadata_tags, get_address_info


def _long_string() -> str:
    return "x" * (INPUT_DATA_TRUNCATION_LIMIT + 20)


# ---------------------------------------------------------------------------
# Metadata failure — RequestError (network-level)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_address_info_metadata_failure(mock_ctx):
    """Return ToolResponse with notes when metadata API fails."""
    chain_id = "1"
    address = "0x123abc"

    mock_blockscout_response = {"hash": address, "is_contract": False}
    mock_first_tx_response = {"items": []}
    metadata_error = httpx.RequestError("Network error")

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
        mock_bs_request.side_effect = [mock_blockscout_response, mock_first_tx_response]
        mock_meta_request.side_effect = metadata_error

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
        assert "Could not retrieve address metadata" in result.notes[0]

        assert mock_ctx.report_progress.await_count == 3
        assert mock_ctx.info.await_count == 3


# ---------------------------------------------------------------------------
# Metadata failure — HTTPStatusError (PRO API auth/quota/rate-limit)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [401, 402, 429])
async def test_get_address_info_metadata_http_status_error_degrades_gracefully(status_code, mock_ctx):
    """A rejected PRO API call (401/402/429) degrades softly — primary data is still returned."""
    chain_id = "1"
    address = "0x123abc"

    mock_blockscout_response = {"hash": address, "is_contract": False}
    mock_first_tx_response = {"items": []}

    mock_request = MagicMock()
    mock_response = MagicMock(status_code=status_code)
    metadata_error = httpx.HTTPStatusError(f"HTTP {status_code}", request=mock_request, response=mock_response)

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
        mock_bs_request.side_effect = [mock_blockscout_response, mock_first_tx_response]
        mock_meta_request.side_effect = metadata_error

        result = await get_address_info(chain_id=chain_id, address=address, ctx=mock_ctx)

        mock_meta_request.assert_called_once_with(
            api_path="/services/metadata/api/v1/metadata", params={"addresses": address, "chainId": chain_id}
        )

        assert isinstance(result, ToolResponse)
        assert isinstance(result.data, AddressInfoData)
        assert result.data.basic_info == mock_blockscout_response
        assert result.data.metadata is None
        assert result.notes is not None and len(result.notes) >= 1
        assert any("Could not retrieve address metadata" in note for note in result.notes)


# ---------------------------------------------------------------------------
# Primary request fails fast — no PRO API key configured
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_address_info_fails_fast_when_no_key(mock_ctx, monkeypatch):
    """With no PRO API key, the primary make_blockscout_request fails fast and get_address_info raises the error."""
    monkeypatch.setattr(config, "pro_api_key", "")
    chain_id = "1"
    address = "0x123abc"

    missing_key_error = ValueError("BLOCKSCOUT_PRO_API_KEY is not set")

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
        mock_bs_request.side_effect = missing_key_error
        mock_meta_request.return_value = {}

        with pytest.raises(ValueError, match="BLOCKSCOUT_PRO_API_KEY"):
            await get_address_info(chain_id=chain_id, address=address, ctx=mock_ctx)


# ---------------------------------------------------------------------------
# _process_metadata_tags unit tests
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Truncation note content
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_address_info_adds_note_when_metadata_meta_is_truncated(mock_ctx):
    chain_id = "1"
    address = "0x123abc"
    mock_blockscout_response = {"hash": address, "is_contract": True}
    mock_first_tx_response = {"items": []}
    mock_metadata_response = {
        "addresses": {
            address: {"tags": [{"meta": ('{"tagUrl":"https://example.com/user","tagIcon":"' + _long_string() + '"}')}]}
        }
    }

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

    assert result.notes is not None
    assert any("Some metadata tag fields were truncated" in note for note in result.notes)
    expected_metadata_prefix = f"`{config.pro_api_base_url}/services/metadata/api/v1/metadata?addresses={address}"
    assert any(expected_metadata_prefix in note for note in result.notes)
    assert any(f"chainId={chain_id}" in note for note in result.notes)
    assert all("curl" not in note for note in result.notes)
    assert all("metadata.services.blockscout.com" not in note for note in result.notes)
    assert any("`web3-dev` skill" in note for note in result.notes)
    assert result.data.metadata is not None
    assert result.data.metadata["tags"][0]["meta"]["tagIcon"]["value_truncated"] is True
