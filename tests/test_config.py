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


def test_server_config_does_not_expose_bs_api_key():
    config = ServerConfig(_env_file=None)

    assert not hasattr(config, "bs_api_key")


def test_pro_api_config_defaults(monkeypatch):
    monkeypatch.delenv("BLOCKSCOUT_PRO_API_BASE_URL", raising=False)
    monkeypatch.delenv("BLOCKSCOUT_PRO_API_CONFIG_TIMEOUT", raising=False)
    cfg = ServerConfig(_env_file=None)
    assert cfg.pro_api_base_url == "https://api.blockscout.com"
    assert cfg.pro_api_config_timeout == 15.0


def test_pro_api_config_env_overrides(monkeypatch):
    monkeypatch.setenv("BLOCKSCOUT_PRO_API_BASE_URL", "https://example.com/")
    monkeypatch.setenv("BLOCKSCOUT_PRO_API_CONFIG_TIMEOUT", "9.5")
    cfg = ServerConfig(_env_file=None)
    assert cfg.pro_api_base_url == "https://example.com"
    assert cfg.pro_api_config_timeout == 9.5


def test_pro_api_config_ttl_default(monkeypatch):
    monkeypatch.delenv("BLOCKSCOUT_PRO_API_CONFIG_TTL_SECONDS", raising=False)
    cfg = ServerConfig(_env_file=None)
    assert cfg.pro_api_config_ttl_seconds == 300


def test_pro_api_config_ttl_env_override(monkeypatch):
    monkeypatch.setenv("BLOCKSCOUT_PRO_API_CONFIG_TTL_SECONDS", "123")
    cfg = ServerConfig(_env_file=None)
    assert cfg.pro_api_config_ttl_seconds == 123


def test_pro_api_config_refresh_retry_default(monkeypatch):
    monkeypatch.delenv("BLOCKSCOUT_PRO_API_CONFIG_REFRESH_RETRY_SECONDS", raising=False)
    cfg = ServerConfig(_env_file=None)
    assert cfg.pro_api_config_refresh_retry_seconds == 30


def test_pro_api_config_refresh_retry_env_override(monkeypatch):
    monkeypatch.setenv("BLOCKSCOUT_PRO_API_CONFIG_REFRESH_RETRY_SECONDS", "7")
    cfg = ServerConfig(_env_file=None)
    assert cfg.pro_api_config_refresh_retry_seconds == 7
