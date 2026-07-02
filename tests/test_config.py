# SPDX-License-Identifier: LicenseRef-Blockscout
import pytest
from pydantic import ValidationError

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


def test_pro_api_config_url_default(monkeypatch):
    monkeypatch.delenv("BLOCKSCOUT_PRO_API_BASE_URL", raising=False)
    cfg = ServerConfig(_env_file=None)
    assert cfg.pro_api_config_url == "https://api.blockscout.com/api/json/config"


def test_pro_api_config_url_env_override(monkeypatch):
    monkeypatch.setenv("BLOCKSCOUT_PRO_API_BASE_URL", "https://custom.api.com/")
    cfg = ServerConfig(_env_file=None)
    assert cfg.pro_api_config_url == "https://custom.api.com/api/json/config"


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


def test_pro_api_key_default(monkeypatch):
    monkeypatch.delenv("BLOCKSCOUT_PRO_API_KEY", raising=False)
    cfg = ServerConfig(_env_file=None)
    assert cfg.pro_api_key == ""


def test_pro_api_key_env_override(monkeypatch):
    monkeypatch.setenv("BLOCKSCOUT_PRO_API_KEY", "proapi_test")
    cfg = ServerConfig(_env_file=None)
    assert cfg.pro_api_key == "proapi_test"


def test_pro_api_key_strips_surrounding_whitespace(monkeypatch):
    monkeypatch.setenv("BLOCKSCOUT_PRO_API_KEY", "  proapi_x \n")
    cfg = ServerConfig(_env_file=None)
    assert cfg.pro_api_key == "proapi_x"


def test_pro_api_key_whitespace_only_becomes_empty(monkeypatch):
    monkeypatch.setenv("BLOCKSCOUT_PRO_API_KEY", "   ")
    cfg = ServerConfig(_env_file=None)
    assert cfg.pro_api_key == ""


def test_pro_api_key_header_default(monkeypatch):
    monkeypatch.delenv("BLOCKSCOUT_PRO_API_KEY_HEADER", raising=False)
    cfg = ServerConfig(_env_file=None)
    assert cfg.pro_api_key_header == "Blockscout-MCP-Pro-Api-Key"


def test_pro_api_key_header_env_override(monkeypatch):
    monkeypatch.setenv("BLOCKSCOUT_PRO_API_KEY_HEADER", "X-Custom-Pro-Key")
    cfg = ServerConfig(_env_file=None)
    assert cfg.pro_api_key_header == "X-Custom-Pro-Key"


def test_pro_api_key_header_strips_surrounding_whitespace(monkeypatch):
    monkeypatch.setenv("BLOCKSCOUT_PRO_API_KEY_HEADER", "  Blockscout-MCP-Pro-Api-Key  ")
    cfg = ServerConfig(_env_file=None)
    assert cfg.pro_api_key_header == "Blockscout-MCP-Pro-Api-Key"


def test_pro_api_key_header_empty_string_preserved(monkeypatch):
    monkeypatch.setenv("BLOCKSCOUT_PRO_API_KEY_HEADER", "")
    cfg = ServerConfig(_env_file=None)
    assert cfg.pro_api_key_header == ""


def test_pro_api_low_credits_threshold_default(monkeypatch):
    monkeypatch.delenv("BLOCKSCOUT_PRO_API_LOW_CREDITS_THRESHOLD", raising=False)
    cfg = ServerConfig(_env_file=None)
    assert cfg.pro_api_low_credits_threshold == 5000


def test_pro_api_low_credits_threshold_env_override(monkeypatch):
    monkeypatch.setenv("BLOCKSCOUT_PRO_API_LOW_CREDITS_THRESHOLD", "1000")
    cfg = ServerConfig(_env_file=None)
    assert cfg.pro_api_low_credits_threshold == 1000


def test_pro_api_low_credits_threshold_zero_accepted(monkeypatch):
    monkeypatch.setenv("BLOCKSCOUT_PRO_API_LOW_CREDITS_THRESHOLD", "0")
    cfg = ServerConfig(_env_file=None)
    assert cfg.pro_api_low_credits_threshold == 0


def test_pro_api_low_credits_threshold_negative_rejected(monkeypatch):
    monkeypatch.setenv("BLOCKSCOUT_PRO_API_LOW_CREDITS_THRESHOLD", "-1")
    with pytest.raises(ValidationError):
        ServerConfig(_env_file=None)


def test_mixpanel_api_host_default(monkeypatch):
    monkeypatch.delenv("BLOCKSCOUT_MIXPANEL_API_HOST", raising=False)
    cfg = ServerConfig(_env_file=None)
    assert cfg.mixpanel_api_host == "api-eu.mixpanel.com"


def test_mixpanel_api_host_env_override(monkeypatch):
    monkeypatch.setenv("BLOCKSCOUT_MIXPANEL_API_HOST", "api.mixpanel.com")
    cfg = ServerConfig(_env_file=None)
    assert cfg.mixpanel_api_host == "api.mixpanel.com"


def test_mixpanel_api_host_empty_string_preserved(monkeypatch):
    monkeypatch.setenv("BLOCKSCOUT_MIXPANEL_API_HOST", "")
    cfg = ServerConfig(_env_file=None)
    assert cfg.mixpanel_api_host == ""
