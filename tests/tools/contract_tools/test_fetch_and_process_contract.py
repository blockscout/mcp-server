from unittest.mock import AsyncMock, patch

import pytest

from blockscout_mcp_server.cache import CachedContract
from blockscout_mcp_server.tools.contract_tools import _fetch_and_process_contract


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
