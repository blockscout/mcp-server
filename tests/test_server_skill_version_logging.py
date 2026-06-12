# SPDX-License-Identifier: LicenseRef-Blockscout
"""Unit tests for the bundled skill version startup diagnostic in server.py."""


def test_missing_version_logs_warning(caplog, monkeypatch):
    """When the bundled version is unavailable, the diagnostic logs at WARNING level."""
    from blockscout_mcp_server import server

    monkeypatch.setattr(server.skill_resources, "get_bundled_skill_version", lambda: None)

    with caplog.at_level("INFO", logger="blockscout_mcp_server.server"):
        server._log_bundled_skill_version_status()

    matching = [r for r in caplog.records if "skill version" in r.message]
    assert matching, "Expected a log record about the bundled skill version"
    assert all(r.levelname == "WARNING" for r in matching)


def test_present_version_logs_info_with_value(caplog, monkeypatch):
    """When the bundled version is available, the diagnostic logs it at INFO level."""
    from blockscout_mcp_server import server

    monkeypatch.setattr(server.skill_resources, "get_bundled_skill_version", lambda: "0.5.0")

    with caplog.at_level("INFO", logger="blockscout_mcp_server.server"):
        server._log_bundled_skill_version_status()

    matching = [r for r in caplog.records if "skill version" in r.message]
    assert matching, "Expected a log record about the bundled skill version"
    assert all(r.levelname == "INFO" for r in matching)
    assert any("0.5.0" in r.message for r in matching)
