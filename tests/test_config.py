# SPDX-License-Identifier: LicenseRef-Blockscout
from blockscout_mcp_server.config import ServerConfig


def test_server_config_light_timeout_default(monkeypatch):
    monkeypatch.delenv("BLOCKSCOUT_BS_LIGHT_TIMEOUT", raising=False)
    monkeypatch.delenv("BLOCKSCOUT_BS_TIMEOUT", raising=False)

    config = ServerConfig(_env_file=None)

    assert config.bs_light_timeout == 20.0
    assert config.bs_timeout == 120.0


def test_server_config_light_timeout_env_override(monkeypatch):
    monkeypatch.setenv("BLOCKSCOUT_BS_LIGHT_TIMEOUT", "42.0")

    config = ServerConfig(_env_file=None)

    assert config.bs_light_timeout == 42.0
