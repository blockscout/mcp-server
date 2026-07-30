# SPDX-License-Identifier: LicenseRef-Blockscout
"""Status-code mapping tests for the session-gate error branches in `handle_rest_errors`.

Patches one wrapped tool with an `AsyncMock` that raises each of the five typed
gate errors, and asserts the mapped HTTP status code and the verbatim JSON
`error` body (the exact Phase 3 messages must flow through unchanged). Also
confirms a plain `ValueError` still maps to `400` (no regression in the
generic branch, which sits after the new gate-error branches).
"""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from blockscout_mcp_server.constants import (
    SESSION_ID_REQUIRED_MESSAGE,
    SESSION_OVER_MESSAGE,
    SESSION_STORE_UNAVAILABLE_MESSAGE,
)
from blockscout_mcp_server.session_gate import (
    SessionBudgetExhaustedError,
    SessionExpiredError,
    SessionIdInvalidError,
    SessionIdMissingError,
    SessionStoreUnavailableError,
)

_URL = "/v1/get_block_number?chain_id=1"


@pytest.mark.asyncio
async def test_session_id_missing_maps_to_401(client: AsyncClient):
    with patch(
        "blockscout_mcp_server.api.routes.get_block_number",
        new_callable=AsyncMock,
        side_effect=SessionIdMissingError(),
    ):
        response = await client.get(_URL)
    assert response.status_code == 401
    assert response.json() == {"error": SESSION_ID_REQUIRED_MESSAGE}


@pytest.mark.asyncio
async def test_session_id_invalid_maps_to_401(client: AsyncClient):
    with patch(
        "blockscout_mcp_server.api.routes.get_block_number",
        new_callable=AsyncMock,
        side_effect=SessionIdInvalidError(),
    ):
        response = await client.get(_URL)
    assert response.status_code == 401
    assert response.json() == {"error": SESSION_ID_REQUIRED_MESSAGE}


@pytest.mark.asyncio
async def test_session_expired_maps_to_429(client: AsyncClient):
    with patch(
        "blockscout_mcp_server.api.routes.get_block_number",
        new_callable=AsyncMock,
        side_effect=SessionExpiredError(),
    ):
        response = await client.get(_URL)
    assert response.status_code == 429
    assert response.json() == {"error": SESSION_OVER_MESSAGE}


@pytest.mark.asyncio
async def test_session_budget_exhausted_maps_to_429(client: AsyncClient):
    with patch(
        "blockscout_mcp_server.api.routes.get_block_number",
        new_callable=AsyncMock,
        side_effect=SessionBudgetExhaustedError(),
    ):
        response = await client.get(_URL)
    assert response.status_code == 429
    assert response.json() == {"error": SESSION_OVER_MESSAGE}


@pytest.mark.asyncio
async def test_expired_and_exhausted_bodies_are_identical(client: AsyncClient):
    """Both 429 causes must be textually indistinguishable to the agent."""
    with patch(
        "blockscout_mcp_server.api.routes.get_block_number",
        new_callable=AsyncMock,
        side_effect=SessionExpiredError(),
    ):
        expired_response = await client.get(_URL)
    with patch(
        "blockscout_mcp_server.api.routes.get_block_number",
        new_callable=AsyncMock,
        side_effect=SessionBudgetExhaustedError(),
    ):
        exhausted_response = await client.get(_URL)

    assert expired_response.json() == exhausted_response.json()


@pytest.mark.asyncio
async def test_session_store_unavailable_maps_to_503(client: AsyncClient):
    with patch(
        "blockscout_mcp_server.api.routes.get_block_number",
        new_callable=AsyncMock,
        side_effect=SessionStoreUnavailableError(),
    ):
        response = await client.get(_URL)
    assert response.status_code == 503
    assert response.json() == {"error": SESSION_STORE_UNAVAILABLE_MESSAGE}


@pytest.mark.asyncio
async def test_plain_value_error_still_maps_to_400(client: AsyncClient):
    """No regression: a generic `ValueError` from the tool body still maps to 400."""
    with patch(
        "blockscout_mcp_server.api.routes.get_block_number",
        new_callable=AsyncMock,
        side_effect=ValueError("boom"),
    ):
        response = await client.get(_URL)
    assert response.status_code == 400
    assert response.json() == {"error": "boom"}
