from blockscout_mcp_server.models import AddressLogItem, TransactionLogItem


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
