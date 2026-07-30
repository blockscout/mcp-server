# SPDX-License-Identifier: LicenseRef-Blockscout
import asyncio
import re
from unittest.mock import AsyncMock, patch

import httpx
import pytest

import blockscout_mcp_server.tools.common as common_tools
from blockscout_mcp_server.config import config
from blockscout_mcp_server.session_gate import SessionIdMissingError, mint_token, verify_token
from blockscout_mcp_server.session_store import get_store
from blockscout_mcp_server.tools.chains.get_chains_list import get_chains_list
from blockscout_mcp_server.tools.common import ChainsListCache


def test_get_chains_list_description_contains_ethereum_mainnet_chain_id_hint():
    """Guard that the Ethereum Mainnet chain-id hint stays present (regression for #351)."""
    doc = get_chains_list.__doc__ or ""
    assert re.search(r"Ethereum Mainnet.*`chain_id`.*`1`", doc), (
        "Docstring must bind 'Ethereum Mainnet', '`chain_id`', and '`1`' in a single sentence "
        "(regression guard for #351 where this hint was silently removed)"
    )


@pytest.fixture(autouse=True)
def reset_chains_list_cache(monkeypatch):
    new_cache = ChainsListCache()
    monkeypatch.setattr(common_tools, "chains_list_cache", new_cache)
    monkeypatch.setattr("blockscout_mcp_server.tools.chains.get_chains_list.chains_list_cache", new_cache)


@pytest.mark.asyncio
async def test_get_chains_list_join_and_filters(mock_ctx):
    with (
        patch(
            "blockscout_mcp_server.tools.chains.get_chains_list.ensure_pro_api_config",
            new_callable=AsyncMock,
            return_value={"1": "https://eth", "3946": "https://x"},
        ),
        patch(
            "blockscout_mcp_server.tools.chains.get_chains_list.make_chainscout_request",
            new_callable=AsyncMock,
            return_value={"1": {"name": "Ethereum"}, "17000": {"name": "Holesky"}},
        ),
    ):
        res = await get_chains_list(ctx=mock_ctx)
    assert [c.chain_id for c in res.data] == ["1"]


@pytest.mark.asyncio
async def test_get_chains_list_empty_pro_config(mock_ctx):
    with (
        patch(
            "blockscout_mcp_server.tools.chains.get_chains_list.ensure_pro_api_config",
            new_callable=AsyncMock,
            return_value={},
        ),
        patch(
            "blockscout_mcp_server.tools.chains.get_chains_list.make_chainscout_request",
            new_callable=AsyncMock,
            return_value={"1": {"name": "Ethereum"}},
        ),
    ):
        res = await get_chains_list(ctx=mock_ctx)
    assert res.data == []
    assert common_tools.chains_list_cache.get_if_fresh() is None


@pytest.mark.asyncio
async def test_get_chains_list_cache_hit_and_refresh(mock_ctx, monkeypatch):
    t = 0.0
    monkeypatch.setattr("blockscout_mcp_server.cache.time.monotonic", lambda: t)
    monkeypatch.setattr(config, "chains_list_ttl_seconds", 1)
    with (
        patch(
            "blockscout_mcp_server.tools.chains.get_chains_list.ensure_pro_api_config",
            new_callable=AsyncMock,
            side_effect=[{"1": "https://eth"}, {"137": "https://polygon"}],
        ) as pro,
        patch(
            "blockscout_mcp_server.tools.chains.get_chains_list.make_chainscout_request",
            new_callable=AsyncMock,
            side_effect=[{"1": {"name": "Ethereum"}}, {"137": {"name": "Polygon"}}],
        ) as cs,
    ):
        first = await get_chains_list(ctx=mock_ctx)
        second = await get_chains_list(ctx=mock_ctx)
        assert first.data == second.data
        assert pro.await_count == 1
        assert cs.await_count == 1
        t = 2.0
        third = await get_chains_list(ctx=mock_ctx)
        assert [c.chain_id for c in third.data] == ["137"]
        assert pro.await_count == 2
        assert cs.await_count == 2


@pytest.mark.asyncio
async def test_get_chains_list_chainscout_failure_does_not_populate_cache(mock_ctx):
    err = httpx.HTTPStatusError(
        "boom",
        request=httpx.Request("GET", "https://x"),
        response=httpx.Response(503, request=httpx.Request("GET", "https://x")),
    )
    with (
        patch(
            "blockscout_mcp_server.tools.chains.get_chains_list.ensure_pro_api_config",
            new_callable=AsyncMock,
            return_value={"1": "https://eth"},
        ),
        patch(
            "blockscout_mcp_server.tools.chains.get_chains_list.make_chainscout_request",
            new_callable=AsyncMock,
            side_effect=err,
        ),
    ):
        with pytest.raises(httpx.HTTPStatusError):
            await get_chains_list(ctx=mock_ctx)
    assert common_tools.chains_list_cache.get_if_fresh() is None


@pytest.mark.asyncio
async def test_get_chains_list_true_concurrent_calls_single_refresh(mock_ctx):
    call_count = 0
    first_call_started = asyncio.Event()
    first_call_can_complete = asyncio.Event()

    async def controlled_chainscout(*, api_path: str):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            first_call_started.set()
            await first_call_can_complete.wait()
        return {"1": {"name": "Ethereum"}}

    with (
        patch(
            "blockscout_mcp_server.tools.chains.get_chains_list.ensure_pro_api_config",
            new_callable=AsyncMock,
            return_value={"1": "https://eth"},
        ),
        patch(
            "blockscout_mcp_server.tools.chains.get_chains_list.make_chainscout_request",
            new_callable=AsyncMock,
            side_effect=controlled_chainscout,
        ),
    ):
        t1 = asyncio.create_task(get_chains_list(ctx=mock_ctx))
        t2 = asyncio.create_task(get_chains_list(ctx=mock_ctx))
        await first_call_started.wait()
        first_call_can_complete.set()
        r1, r2 = await asyncio.gather(t1, t2)
    assert call_count == 1
    assert r1.data == r2.data


@pytest.mark.asyncio
async def test_get_chains_list_chainscout_returns_non_dict(mock_ctx):
    with (
        patch(
            "blockscout_mcp_server.tools.chains.get_chains_list.ensure_pro_api_config",
            new_callable=AsyncMock,
            return_value={"1": "https://eth"},
        ),
        patch(
            "blockscout_mcp_server.tools.chains.get_chains_list.make_chainscout_request",
            new_callable=AsyncMock,
            return_value="oops",
        ),
    ):
        res = await get_chains_list(ctx=mock_ctx)
    assert res.data == []
    assert common_tools.chains_list_cache.get_if_fresh() is None


@pytest.mark.asyncio
async def test_get_chains_list_rebuilds_after_pro_api_refresh_invalidates_cache(mock_ctx):
    common_tools.chains_list_cache.store_snapshot([])
    common_tools.chains_list_cache.invalidate()
    with (
        patch(
            "blockscout_mcp_server.tools.chains.get_chains_list.ensure_pro_api_config",
            new_callable=AsyncMock,
            return_value={"2": "https://new"},
        ),
        patch(
            "blockscout_mcp_server.tools.chains.get_chains_list.make_chainscout_request",
            new_callable=AsyncMock,
            return_value={"2": {"name": "Two"}},
        ) as cs,
    ):
        res = await get_chains_list(ctx=mock_ctx)
    assert [c.chain_id for c in res.data] == ["2"]
    assert cs.await_count == 1


# ---------------------------------------------------------------------------
# Session-gated behavior (issue #442, Phase 7): get_chains_list is gated but
# not metered — a valid identifier navigates without incrementing its counter.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_chains_list_gated_valid_token_succeeds_without_metering(mock_ctx, enabled_session_gate):
    token = mint_token()
    random_part, _issued_at = verify_token(token)

    with (
        patch(
            "blockscout_mcp_server.tools.chains.get_chains_list.ensure_pro_api_config",
            new_callable=AsyncMock,
            return_value={"1": "https://eth"},
        ),
        patch(
            "blockscout_mcp_server.tools.chains.get_chains_list.make_chainscout_request",
            new_callable=AsyncMock,
            return_value={"1": {"name": "Ethereum"}},
        ),
    ):
        res = await get_chains_list(ctx=mock_ctx, session_id=token)

    assert [c.chain_id for c in res.data] == ["1"]
    assert res.notes is not None
    assert f"{config.session_max_calls} of {config.session_max_calls}" in res.notes[-1]
    # Read-only: no row created for a fresh identifier, so the counter stays at 0.
    assert get_store().get_calls(random_part) == 0


@pytest.mark.asyncio
async def test_get_chains_list_gated_missing_session_id_raises(mock_ctx, enabled_session_gate):
    with pytest.raises(SessionIdMissingError):
        await get_chains_list(ctx=mock_ctx)


@pytest.mark.asyncio
async def test_get_chains_list_ungated_behaves_as_today(mock_ctx):
    """Without the `enabled_session_gate` fixture, the gate is disabled by default
    (`pristine_config`) and the tool behaves exactly as before: no session_id
    required, no budget note appended."""
    with (
        patch(
            "blockscout_mcp_server.tools.chains.get_chains_list.ensure_pro_api_config",
            new_callable=AsyncMock,
            return_value={"1": "https://eth"},
        ),
        patch(
            "blockscout_mcp_server.tools.chains.get_chains_list.make_chainscout_request",
            new_callable=AsyncMock,
            return_value={"1": {"name": "Ethereum"}},
        ),
    ):
        res = await get_chains_list(ctx=mock_ctx)

    assert [c.chain_id for c in res.data] == ["1"]
    assert res.notes is None
