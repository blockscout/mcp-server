import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

import httpx
import pytest

from blockscout_mcp_server.models import AddressLogItem, TransactionLogItem

T = TypeVar("T")


async def retry_on_network_error(
    action: Callable[[], Awaitable[T]],
    *,
    action_description: str,
    max_retries: int = 3,
    delay_seconds: float = 0.5,
) -> T:
    for attempt in range(1, max_retries + 1):
        try:
            return await action()
        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            if attempt == max_retries:
                pytest.skip(
                    f"Network connectivity issue after {max_retries} attempts while {action_description}: {exc}"
                )
            await asyncio.sleep(delay_seconds)
    raise AssertionError("retry_on_network_error exhausted without returning.")


def is_log_a_truncated_call_executed(log: TransactionLogItem | AddressLogItem) -> bool:
    """Checks if a log item is a 'CallExecuted' event with a truncated 'data' parameter."""
    if not (isinstance(log.decoded, dict) and log.decoded.get("method_call", "").startswith("CallExecuted")):
        return False

    data_param = next(
        (p for p in log.decoded.get("parameters", []) if p.get("name") == "data"),
        None,
    )
    if not data_param:
        return False

    value = data_param.get("value")
    return isinstance(value, dict) and value.get("value_truncated") is True
