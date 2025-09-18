from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from blockscout_mcp_server.cache import CachedContract
from blockscout_mcp_server.models import ContractMetadata, ContractSourceFile, ToolResponse
from blockscout_mcp_server.tools.contract.inspect_contract_code import inspect_contract_code


@pytest.mark.asyncio
async def test_inspect_contract_metadata_mode_success(mock_ctx):
    contract = CachedContract(
        metadata={
            "name": "Test",
            "language": None,
            "compiler_version": None,
            "verified_at": None,
            "source_code_tree_structure": ["A.sol"],
            "optimization_enabled": None,
            "optimization_runs": None,
            "evm_version": None,
            "license_type": None,
            "proxy_type": None,
            "is_fully_verified": None,
            "constructor_args": None,
            "decoded_constructor_args": None,
            "constructor_args_truncated": False,
        },
        source_files={"A.sol": "code"},
    )
    with patch(
        "blockscout_mcp_server.tools.contract.inspect_contract_code._fetch_and_process_contract",
        new_callable=AsyncMock,
        return_value=contract,
    ) as mock_fetch:
        result = await inspect_contract_code(chain_id="1", address="0xabc", file_name=None, ctx=mock_ctx)
    mock_fetch.assert_awaited_once_with("1", "0xabc", mock_ctx)
    mock_ctx.report_progress.assert_awaited_once()
    assert (
        mock_ctx.report_progress.await_args_list[0].kwargs["message"]
        == "Starting to fetch contract metadata for 0xabc on chain 1..."
    )
    assert isinstance(result, ToolResponse)
    assert isinstance(result.data, ContractMetadata)
    assert result.data.source_code_tree_structure == ["A.sol"]
    assert result.data.decoded_constructor_args is None
    assert result.notes is None
    assert result.instructions == [
        (
            "To retrieve a specific file's contents, call this tool again with the "
            "'file_name' argument using one of the values from 'source_code_tree_structure'."
        )
    ]


@pytest.mark.asyncio
async def test_inspect_contract_file_content_mode_success(mock_ctx):
    contract = CachedContract(metadata={}, source_files={"A.sol": "pragma"})
    with patch(
        "blockscout_mcp_server.tools.contract.inspect_contract_code._fetch_and_process_contract",
        new_callable=AsyncMock,
        return_value=contract,
    ):
        result = await inspect_contract_code(chain_id="1", address="0xabc", file_name="A.sol", ctx=mock_ctx)
    mock_ctx.report_progress.assert_awaited_once()
    assert (
        mock_ctx.report_progress.await_args_list[0].kwargs["message"]
        == "Starting to fetch source code for 'A.sol' of contract 0xabc on chain 1..."
    )
    assert isinstance(result.data, ContractSourceFile)
    assert result.data.file_content == "pragma"


@pytest.mark.asyncio
async def test_inspect_contract_file_not_found_raises_error(mock_ctx):
    contract = CachedContract(metadata={}, source_files={"A.sol": ""})
    with patch(
        "blockscout_mcp_server.tools.contract.inspect_contract_code._fetch_and_process_contract",
        new_callable=AsyncMock,
        return_value=contract,
    ):
        with pytest.raises(ValueError) as exc:
            await inspect_contract_code(chain_id="1", address="0xabc", file_name="B.sol", ctx=mock_ctx)
    mock_ctx.report_progress.assert_awaited_once()
    assert (
        mock_ctx.report_progress.await_args_list[0].kwargs["message"]
        == "Starting to fetch source code for 'B.sol' of contract 0xabc on chain 1..."
    )
    assert "Available files: A.sol" in str(exc.value)


@pytest.mark.asyncio
async def test_inspect_contract_propagates_api_error(mock_ctx):
    error = httpx.HTTPStatusError("err", request=MagicMock(), response=MagicMock(status_code=404))
    with patch(
        "blockscout_mcp_server.tools.contract.inspect_contract_code._fetch_and_process_contract",
        new_callable=AsyncMock,
        side_effect=error,
    ):
        with pytest.raises(httpx.HTTPStatusError):
            await inspect_contract_code(chain_id="1", address="0xabc", file_name=None, ctx=mock_ctx)
    mock_ctx.report_progress.assert_awaited_once()
    assert (
        mock_ctx.report_progress.await_args_list[0].kwargs["message"]
        == "Starting to fetch contract metadata for 0xabc on chain 1..."
    )


@pytest.mark.asyncio
async def test_inspect_contract_metadata_mode_truncated_sets_notes(mock_ctx):
    contract = CachedContract(
        metadata={
            "name": "Test",
            "language": None,
            "compiler_version": None,
            "verified_at": None,
            "source_code_tree_structure": [],
            "optimization_enabled": None,
            "optimization_runs": None,
            "evm_version": None,
            "license_type": None,
            "proxy_type": None,
            "is_fully_verified": None,
            "constructor_args": "0x1234",
            "decoded_constructor_args": ["arg1"],
            "constructor_args_truncated": True,
        },
        source_files={},
    )
    with patch(
        "blockscout_mcp_server.tools.contract.inspect_contract_code._fetch_and_process_contract",
        new_callable=AsyncMock,
        return_value=contract,
    ):
        result = await inspect_contract_code(chain_id="1", address="0xabc", file_name=None, ctx=mock_ctx)
    assert result.notes == ["Constructor arguments were truncated to limit context size."]
    assert result.instructions is None
