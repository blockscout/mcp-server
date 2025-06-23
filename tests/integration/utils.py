"""Shared utilities for integration tests."""

from __future__ import annotations


def _find_truncated_scope_function_in_logs(data: dict) -> bool:
    """Return True if data contains a truncated 'ScopeFunction' log."""
    scope_function_log = next(
        (
            item
            for item in data.get("items", [])
            if isinstance(item.get("decoded"), dict)
            and item["decoded"].get("method_call", "").startswith("ScopeFunction")
        ),
        None,
    )
    if not scope_function_log:
        return False

    conditions_param = next(
        (
            p
            for p in scope_function_log["decoded"].get("parameters", [])
            if p.get("name") == "conditions"
        ),
        None,
    )
    if not conditions_param:
        return False

    for condition_tuple in conditions_param.get("value", []):
        if isinstance(condition_tuple[-1], dict) and condition_tuple[-1].get("value_truncated"):
            return True

    return False


def _extract_next_cursor(result_str: str) -> str | None:
    """Return cursor from pagination hint if present."""
    if "To get the next page call" in result_str:
        return result_str.split('cursor="')[1].split('"')[0]
    return None
