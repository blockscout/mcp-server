"""Shared utilities for integration tests."""

from __future__ import annotations


def _find_truncated_call_executed_function_in_logs(data: dict) -> bool:
    """Return True if data contains a truncated 'CallExecuted' log."""
    call_executed_log = next(
        (
            item
            for item in data.get("items", [])
            if isinstance(item.get("decoded"), dict)
            and item["decoded"].get("method_call", "").startswith("CallExecuted")
        ),
        None,
    )
    if not call_executed_log:
        return False

    data_param = next(
        (p for p in call_executed_log["decoded"].get("parameters", []) if p.get("name") == "data"),
        None,
    )
    if not data_param:
        return False

    # Check if value is a dict with truncation info
    value = data_param.get("value")
    if isinstance(value, dict) and value.get("value_truncated"):
        return True

    return False


def _extract_next_cursor(result_str: str) -> str | None:
    """Return cursor from pagination hint if present."""
    if "To get the next page call" in result_str:
        return result_str.split('cursor="')[1].split('"')[0]
    return None
