from importlib import reload


def test_mcp_allowed_hosts_default_empty(monkeypatch):
    monkeypatch.delenv("BLOCKSCOUT_MCP_ALLOWED_HOSTS", raising=False)
    from blockscout_mcp_server import config as cfg

    reload(cfg)
    assert cfg.config.mcp_allowed_hosts == ""
    reload(cfg)


def test_mcp_allowed_hosts_from_env(monkeypatch):
    monkeypatch.setenv("BLOCKSCOUT_MCP_ALLOWED_HOSTS", "host1,host2")
    from blockscout_mcp_server import config as cfg

    reload(cfg)
    assert cfg.config.mcp_allowed_hosts == "host1,host2"

    monkeypatch.delenv("BLOCKSCOUT_MCP_ALLOWED_HOSTS")
    reload(cfg)


def test_mcp_allowed_origins_default_empty(monkeypatch):
    monkeypatch.delenv("BLOCKSCOUT_MCP_ALLOWED_ORIGINS", raising=False)
    from blockscout_mcp_server import config as cfg

    reload(cfg)
    assert cfg.config.mcp_allowed_origins == ""
    reload(cfg)


def test_mcp_allowed_origins_from_env(monkeypatch):
    monkeypatch.setenv("BLOCKSCOUT_MCP_ALLOWED_ORIGINS", "https://example.ngrok-free.app")
    from blockscout_mcp_server import config as cfg

    reload(cfg)
    assert cfg.config.mcp_allowed_origins == "https://example.ngrok-free.app"

    monkeypatch.delenv("BLOCKSCOUT_MCP_ALLOWED_ORIGINS")
    reload(cfg)
