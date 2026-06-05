# SPDX-License-Identifier: LicenseRef-Blockscout
from unittest.mock import AsyncMock, patch

import pytest

from blockscout_mcp_server.cache import CachedContract
from blockscout_mcp_server.config import config
from blockscout_mcp_server.pro_api_key_context import _client_key_state, _Malformed, _Valid
from blockscout_mcp_server.tools.contract._shared import _fetch_and_process_contract


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
        patch.object(config, "pro_api_key", "test_key"),
        patch(
            "blockscout_mcp_server.tools.contract._shared.contract_cache.get",
            new_callable=AsyncMock,
            return_value=None,
        ) as mock_get,
        patch(
            "blockscout_mcp_server.tools.contract._shared.make_blockscout_request",
            new_callable=AsyncMock,
            return_value=api_response,
        ) as mock_request,
        patch(
            "blockscout_mcp_server.tools.contract._shared.contract_cache.set",
            new_callable=AsyncMock,
        ) as mock_set,
    ):
        await _fetch_and_process_contract("1", "0xAbC")
    mock_get.assert_awaited_once_with("1:0xabc")
    mock_request.assert_awaited_once_with(
        chain_id="1",
        api_path="/api/v2/smart-contracts/0xabc",
        timeout=config.bs_light_timeout,
    )
    mock_set.assert_awaited_once()
    key_arg, value_arg = mock_set.await_args.args
    assert key_arg == "1:0xabc"
    assert isinstance(value_arg, CachedContract)
    assert mock_ctx.report_progress.await_count == 0


@pytest.mark.asyncio
async def test_fetch_and_process_cache_hit(mock_ctx):
    cached = CachedContract(metadata={}, source_files={})
    with (
        patch.object(config, "pro_api_key", "test_key"),
        patch(
            "blockscout_mcp_server.tools.contract._shared.contract_cache.get",
            new_callable=AsyncMock,
            return_value=cached,
        ) as mock_get,
        patch(
            "blockscout_mcp_server.tools.contract._shared.make_blockscout_request",
            new_callable=AsyncMock,
        ) as mock_request,
    ):
        result = await _fetch_and_process_contract("1", "0xAbC")
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
        patch.object(config, "pro_api_key", "test_key"),
        patch(
            "blockscout_mcp_server.tools.contract._shared.contract_cache.get",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "blockscout_mcp_server.tools.contract._shared.make_blockscout_request",
            new_callable=AsyncMock,
            return_value=api_response,
        ),
        patch(
            "blockscout_mcp_server.tools.contract._shared.contract_cache.set",
            new_callable=AsyncMock,
        ) as mock_set,
    ):
        result = await _fetch_and_process_contract("1", "0xabc")
    assert result.metadata["source_code_tree_structure"] == ["MyContract.sol"]
    assert set(result.source_files.keys()) == {"MyContract.sol"}
    mock_set.assert_awaited_once()
    assert mock_ctx.report_progress.await_count == 0


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
        patch.object(config, "pro_api_key", "test_key"),
        patch(
            "blockscout_mcp_server.tools.contract._shared.contract_cache.get",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "blockscout_mcp_server.tools.contract._shared.make_blockscout_request",
            new_callable=AsyncMock,
            return_value=api_response,
        ),
        patch(
            "blockscout_mcp_server.tools.contract._shared.contract_cache.set",
            new_callable=AsyncMock,
        ),
    ):
        result = await _fetch_and_process_contract("1", "0xabc")
    assert set(result.metadata["source_code_tree_structure"]) == {"Main.sol", "B.sol"}
    assert set(result.source_files.keys()) == {"Main.sol", "B.sol"}
    assert result.source_files["Main.sol"] == "a"
    assert result.source_files["B.sol"] == "b"
    assert mock_ctx.report_progress.await_count == 0


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
        patch.object(config, "pro_api_key", "test_key"),
        patch(
            "blockscout_mcp_server.tools.contract._shared.contract_cache.get",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "blockscout_mcp_server.tools.contract._shared.contract_cache.set",
            new_callable=AsyncMock,
        ) as mock_set,
    ):
        with patch(
            "blockscout_mcp_server.tools.contract._shared.make_blockscout_request",
            new_callable=AsyncMock,
            return_value=multi_resp,
        ):
            multi = await _fetch_and_process_contract("1", "0x1")
        with patch(
            "blockscout_mcp_server.tools.contract._shared.make_blockscout_request",
            new_callable=AsyncMock,
            return_value=vyper_resp,
        ):
            vyper = await _fetch_and_process_contract("1", "0x2")
    assert set(multi.metadata["source_code_tree_structure"]) == {"A.sol", "B.sol"}
    assert vyper.metadata["source_code_tree_structure"] == ["VyperC.vy"]
    assert mock_ctx.report_progress.await_count == 0
    assert mock_set.await_count == 2


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
        patch.object(config, "pro_api_key", "test_key"),
        patch(
            "blockscout_mcp_server.tools.contract._shared.contract_cache.get",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "blockscout_mcp_server.tools.contract._shared.make_blockscout_request",
            new_callable=AsyncMock,
            return_value=api_response,
        ),
        patch(
            "blockscout_mcp_server.tools.contract._shared.contract_cache.set",
            new_callable=AsyncMock,
        ),
    ):
        result = await _fetch_and_process_contract("1", "0xAbC")
    assert result.source_files == {}
    assert result.metadata["source_code_tree_structure"] == []
    assert result.metadata["name"] == "0xabc"
    # Heavy/raw fields should be stripped from metadata
    assert "creation_bytecode" not in result.metadata
    assert "deployed_bytecode" not in result.metadata
    assert "source_code" not in result.metadata
    assert "additional_sources" not in result.metadata
    assert mock_ctx.report_progress.await_count == 0


# ---------------------------------------------------------------------------
# Phase 4: contract-metadata cache short-circuit gate tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_and_process_cache_hit_serverless_valid_client_key(mock_ctx):
    """Cache hit with empty server key and valid client key: gate passes, cache serves data, no HTTP call."""
    cached = CachedContract(metadata={}, source_files={})
    token = _client_key_state.set(_Valid(value="client-key-xyz"))
    try:
        with (
            patch.object(config, "pro_api_key", ""),
            patch(
                "blockscout_mcp_server.tools.contract._shared.contract_cache.get",
                new_callable=AsyncMock,
                return_value=cached,
            ) as mock_get,
            patch(
                "blockscout_mcp_server.tools.contract._shared.make_blockscout_request",
                new_callable=AsyncMock,
            ) as mock_request,
        ):
            result = await _fetch_and_process_contract("1", "0xAbC")
    finally:
        _client_key_state.reset(token)

    assert result is cached
    mock_get.assert_awaited_once_with("1:0xabc")
    mock_request.assert_not_called()


@pytest.mark.asyncio
async def test_fetch_and_process_cache_hit_malformed_key_fails_closed(mock_ctx):
    """Cache hit with malformed client key: gate raises ValueError before cache is consulted."""
    cached = CachedContract(metadata={}, source_files={})
    token = _client_key_state.set(_Malformed())
    try:
        with (
            patch.object(config, "pro_api_key", "server-key"),
            patch(
                "blockscout_mcp_server.tools.contract._shared.contract_cache.get",
                new_callable=AsyncMock,
                return_value=cached,
            ) as mock_get,
        ):
            with pytest.raises(ValueError, match="malformed"):
                await _fetch_and_process_contract("1", "0xAbC")
    finally:
        _client_key_state.reset(token)

    mock_get.assert_not_called()


@pytest.mark.asyncio
async def test_fetch_and_process_cache_hit_no_key_fails_closed(mock_ctx):
    """Cache hit with empty server key and absent client key: gate raises not-configured error."""
    cached = CachedContract(metadata={}, source_files={})
    with (
        patch.object(config, "pro_api_key", ""),
        patch(
            "blockscout_mcp_server.tools.contract._shared.contract_cache.get",
            new_callable=AsyncMock,
            return_value=cached,
        ) as mock_get,
    ):
        with pytest.raises(ValueError, match="BLOCKSCOUT_PRO_API_KEY"):
            await _fetch_and_process_contract("1", "0xAbC")

    mock_get.assert_not_called()


@pytest.mark.asyncio
async def test_fetch_and_process_cache_key_stays_credential_free(mock_ctx):
    """The cache key must remain '{chain_id}:{address}' — no key material mixed in."""
    api_response = {
        "name": "C",
        "language": "Solidity",
        "source_code": "code",
        "file_path": "C.sol",
        "constructor_args": None,
    }
    token = _client_key_state.set(_Valid(value="super-secret-client-key"))
    try:
        with (
            patch.object(config, "pro_api_key", ""),
            patch(
                "blockscout_mcp_server.tools.contract._shared.contract_cache.get",
                new_callable=AsyncMock,
                return_value=None,
            ) as mock_get,
            patch(
                "blockscout_mcp_server.tools.contract._shared.make_blockscout_request",
                new_callable=AsyncMock,
                return_value=api_response,
            ),
            patch(
                "blockscout_mcp_server.tools.contract._shared.contract_cache.set",
                new_callable=AsyncMock,
            ) as mock_set,
        ):
            await _fetch_and_process_contract("1", "0xAbC")
    finally:
        _client_key_state.reset(token)

    # cache.get and cache.set must be called with the plain "{chain_id}:{address}" key
    mock_get.assert_awaited_once_with("1:0xabc")
    set_key_arg = mock_set.await_args.args[0]
    assert set_key_arg == "1:0xabc"
    # Must not contain any key material
    assert "super-secret-client-key" not in set_key_arg
    assert "super-secret-client-key" not in mock_get.await_args.args[0]
