from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from blockscout_mcp_server.cache import CachedContract
from blockscout_mcp_server.models import ContractMetadata, ContractSourceFile, ToolResponse
from blockscout_mcp_server.tools.contract_tools import (
    _fetch_and_process_contract,
    inspect_contract_code,
)


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
        "blockscout_mcp_server.tools.contract_tools._fetch_and_process_contract",
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
        "blockscout_mcp_server.tools.contract_tools._fetch_and_process_contract",
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
        "blockscout_mcp_server.tools.contract_tools._fetch_and_process_contract",
        new_callable=AsyncMock,
        return_value=contract,
    ):
        with pytest.raises(ValueError):
            await inspect_contract_code(chain_id="1", address="0xabc", file_name="B.sol", ctx=mock_ctx)
    mock_ctx.report_progress.assert_awaited_once()
    assert (
        mock_ctx.report_progress.await_args_list[0].kwargs["message"]
        == "Starting to fetch source code for 'B.sol' of contract 0xabc on chain 1..."
    )


@pytest.mark.asyncio
async def test_fetch_and_process_cache_miss(mock_ctx):
    api_response = {
        "name": "C",
        "language": "Solidity",
        "source_code": "code",
        "file_path": "C.sol",
        "constructor_args": "0x",
    }
    with (
        patch(
            "blockscout_mcp_server.tools.contract_tools.contract_cache.get",
            new_callable=AsyncMock,
            return_value=None,
        ) as mock_get,
        patch(
            "blockscout_mcp_server.tools.contract_tools.make_blockscout_request",
            new_callable=AsyncMock,
            return_value=api_response,
        ) as mock_request,
        patch(
            "blockscout_mcp_server.tools.contract_tools.contract_cache.set",
            new_callable=AsyncMock,
        ) as mock_set,
        patch(
            "blockscout_mcp_server.tools.contract_tools.get_blockscout_base_url",
            new_callable=AsyncMock,
            return_value="https://base",
        ),
    ):
        await _fetch_and_process_contract("1", "0xAbC", mock_ctx)
    mock_get.assert_awaited_once_with("1:0xabc")
    mock_request.assert_awaited_once()
    mock_set.assert_awaited_once()
    assert mock_ctx.report_progress.await_count == 2
    assert mock_ctx.report_progress.await_args_list[0].kwargs["message"] == "Resolved Blockscout instance URL."
    assert mock_ctx.report_progress.await_args_list[1].kwargs["message"] == "Successfully fetched contract data."


@pytest.mark.asyncio
async def test_fetch_and_process_cache_hit(mock_ctx):
    cached = CachedContract(metadata={}, source_files={})
    with (
        patch(
            "blockscout_mcp_server.tools.contract_tools.contract_cache.get",
            new_callable=AsyncMock,
            return_value=cached,
        ) as mock_get,
        patch(
            "blockscout_mcp_server.tools.contract_tools.make_blockscout_request",
            new_callable=AsyncMock,
        ) as mock_request,
    ):
        result = await _fetch_and_process_contract("1", "0xAbC", mock_ctx)
    assert result is cached
    mock_get.assert_awaited_once_with("1:0xabc")
    mock_request.assert_not_called()
    assert mock_ctx.report_progress.await_count == 0


@pytest.mark.asyncio
async def test_process_logic_single_solidity_file(mock_ctx):
    api_response = {
        "name": "MyContract",
        "language": "Solidity",
        "source_code": "code",
        "file_path": ".sol",
        "constructor_args": None,
    }
    with (
        patch(
            "blockscout_mcp_server.tools.contract_tools.contract_cache.get",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "blockscout_mcp_server.tools.contract_tools.make_blockscout_request",
            new_callable=AsyncMock,
            return_value=api_response,
        ),
        patch(
            "blockscout_mcp_server.tools.contract_tools.contract_cache.set",
            new_callable=AsyncMock,
        ) as mock_set,
        patch(
            "blockscout_mcp_server.tools.contract_tools.get_blockscout_base_url",
            new_callable=AsyncMock,
            return_value="https://base",
        ),
    ):
        result = await _fetch_and_process_contract("1", "0xabc", mock_ctx)
    assert result.metadata["source_code_tree_structure"] == ["MyContract.sol"]
    mock_set.assert_awaited_once()
    assert mock_ctx.report_progress.await_count == 2


@pytest.mark.asyncio
async def test_process_logic_multi_file_missing_main_path(mock_ctx):
    api_response = {
        "name": "Main",
        "language": "Solidity",
        "source_code": "a",
        "file_path": "",
        "additional_sources": [{"file_path": "B.sol", "source_code": "b"}],
        "constructor_args": None,
    }
    with (
        patch(
            "blockscout_mcp_server.tools.contract_tools.contract_cache.get",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "blockscout_mcp_server.tools.contract_tools.make_blockscout_request",
            new_callable=AsyncMock,
            return_value=api_response,
        ),
        patch(
            "blockscout_mcp_server.tools.contract_tools.contract_cache.set",
            new_callable=AsyncMock,
        ),
        patch(
            "blockscout_mcp_server.tools.contract_tools.get_blockscout_base_url",
            new_callable=AsyncMock,
            return_value="https://base",
        ),
    ):
        result = await _fetch_and_process_contract("1", "0xabc", mock_ctx)
    assert set(result.metadata["source_code_tree_structure"]) == {"Main.sol", "B.sol"}
    assert mock_ctx.report_progress.await_count == 2


@pytest.mark.asyncio
async def test_process_logic_multi_file_and_vyper(mock_ctx):
    multi_resp = {
        "name": "Multi",
        "language": "Solidity",
        "source_code": "a",
        "file_path": "A.sol",
        "additional_sources": [{"file_path": "B.sol", "source_code": "b"}],
        "constructor_args": None,
    }
    vyper_resp = {
        "name": "VyperC",
        "language": "Vyper",
        "source_code": "# vyper",
        "file_path": "",
        "constructor_args": None,
    }
    with (
        patch(
            "blockscout_mcp_server.tools.contract_tools.contract_cache.get",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "blockscout_mcp_server.tools.contract_tools.contract_cache.set",
            new_callable=AsyncMock,
        ),
        patch(
            "blockscout_mcp_server.tools.contract_tools.get_blockscout_base_url",
            new_callable=AsyncMock,
            return_value="https://base",
        ),
    ):
        with patch(
            "blockscout_mcp_server.tools.contract_tools.make_blockscout_request",
            new_callable=AsyncMock,
            return_value=multi_resp,
        ):
            multi = await _fetch_and_process_contract("1", "0x1", mock_ctx)
        with patch(
            "blockscout_mcp_server.tools.contract_tools.make_blockscout_request",
            new_callable=AsyncMock,
            return_value=vyper_resp,
        ):
            vyper = await _fetch_and_process_contract("1", "0x2", mock_ctx)
    assert set(multi.metadata["source_code_tree_structure"]) == {"A.sol", "B.sol"}
    assert vyper.metadata["source_code_tree_structure"] == ["VyperC.vy"]
    assert mock_ctx.report_progress.await_count == 4


@pytest.mark.asyncio
async def test_process_logic_unverified_contract(mock_ctx):
    api_response = {
        "creation_bytecode": "0x",
        "creation_status": "success",
        "deployed_bytecode": "0x",
        "implementations": [],
        "proxy_type": "unknown",
    }
    with (
        patch(
            "blockscout_mcp_server.tools.contract_tools.contract_cache.get",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "blockscout_mcp_server.tools.contract_tools.make_blockscout_request",
            new_callable=AsyncMock,
            return_value=api_response,
        ),
        patch(
            "blockscout_mcp_server.tools.contract_tools.contract_cache.set",
            new_callable=AsyncMock,
        ),
        patch(
            "blockscout_mcp_server.tools.contract_tools.get_blockscout_base_url",
            new_callable=AsyncMock,
            return_value="https://base",
        ),
    ):
        result = await _fetch_and_process_contract("1", "0xAbC", mock_ctx)
    assert result.source_files == {}
    assert result.metadata["source_code_tree_structure"] == []
    assert result.metadata["name"] == "0xabc"
    assert mock_ctx.report_progress.await_count == 2


@pytest.mark.asyncio
async def test_inspect_contract_propagates_api_error(mock_ctx):
    error = httpx.HTTPStatusError("err", request=MagicMock(), response=MagicMock(status_code=404))
    with patch(
        "blockscout_mcp_server.tools.contract_tools._fetch_and_process_contract",
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
        "blockscout_mcp_server.tools.contract_tools._fetch_and_process_contract",
        new_callable=AsyncMock,
        return_value=contract,
    ):
        result = await inspect_contract_code(chain_id="1", address="0xabc", file_name=None, ctx=mock_ctx)
    assert result.notes == ["Constructor arguments were truncated to limit context size."]
