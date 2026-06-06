# SPDX-License-Identifier: LicenseRef-Blockscout
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ServerConfig(BaseSettings):
    # Load environment variables from a local .env file (current working directory)
    # and require the BLOCKSCOUT_ prefix for all settings
    model_config = SettingsConfigDict(env_prefix="BLOCKSCOUT_", env_file=".env", env_file_encoding="utf-8")

    bs_timeout: float = 120.0  # Default timeout in seconds
    bs_light_timeout: float = 20.0  # Default timeout for simple point-lookup requests
    bs_request_max_retries: int = 3  # Conservative retries for transient transport errors

    bens_url: str = "https://bens.services.blockscout.com"  # Add this now for Phase 2
    bens_timeout: float = 30.0  # Default timeout for BENS requests

    chainscout_url: str = "https://chains.blockscout.com"  # Updated to https
    chainscout_timeout: float = 15.0  # Default timeout for Chainscout requests
    pro_api_base_url: str = "https://api.blockscout.com"
    pro_api_config_timeout: float = 15.0
    pro_api_config_ttl_seconds: int = 300
    pro_api_config_refresh_retry_seconds: int = 30
    pro_api_key: str = ""
    pro_api_key_header: str = "Blockscout-MCP-Pro-Api-Key"
    # Advisory low-credits threshold expressed in PRO API credits (same unit as
    # `endpoint_pricing` in /api/json/config).  A value of 0 disables the note
    # entirely (Phase 4 gates on threshold > 0).  The default of 5000 provides
    # comfortable runway: per-call costs observed live range 20–120 credits, so
    # 5000 ≈ 250 cheapest (20-credit) calls or ~41 most expensive (120-credit)
    # calls — enough time for an operator to react before exhaustion.  The ge=0
    # bound is intentional: a negative value would silently disable the warning
    # (the opposite of operator intent), so Pydantic rejects it loudly instead.
    pro_api_low_credits_threshold: int = Field(5000, ge=0)

    @field_validator("pro_api_base_url")
    @classmethod
    def normalize_pro_api_base_url(cls, value: str) -> str:
        return str(value).rstrip("/")

    @field_validator("pro_api_key")
    @classmethod
    def normalize_pro_api_key(cls, value: str) -> str:
        return value.strip()

    @field_validator("pro_api_key_header")
    @classmethod
    def normalize_pro_api_key_header(cls, value: str) -> str:
        return value.strip()

    # Metadata configuration (PRO API metadata endpoint)
    metadata_timeout: float = 30.0

    chains_list_ttl_seconds: int = 300  # Default 5 minutes
    progress_interval_seconds: float = 15.0  # Default interval for periodic progress updates

    contracts_cache_max_number: int = 10  # Default 10 contracts
    contracts_cache_ttl_seconds: int = 3600  # Default 1 hour

    nft_page_size: int = 10
    logs_page_size: int = 10
    advanced_filters_page_size: int = 10
    direct_api_response_size_limit: int = Field(
        100000,
        description="Maximum allowed characters for direct_api_call raw responses.",
    )

    # RPC connection pool configuration
    rpc_request_timeout: float = 60.0
    rpc_pool_per_host: int = 50

    # Base name used in the User-Agent header sent to Blockscout RPC
    mcp_user_agent: str = "Blockscout MCP"
    mcp_allowed_hosts: str = ""
    mcp_allowed_origins: str = ""

    # Analytics configuration
    mixpanel_token: str = ""
    mixpanel_api_host: str = ""  # Optional custom API host (e.g., EU region)
    disable_community_telemetry: bool = False

    # Transport mode for the server ("stdio" or "http").
    # Controls the server's operational mode, can be overridden by CLI flags.
    mcp_transport: str = "stdio"
    dev_json_response: bool = False

    # Optional port for the HTTP server, read from the PORT environment variable.
    port: int | None = Field(None, alias="PORT")

    # Composite client name configuration
    intermediary_header: str = "Blockscout-MCP-Intermediary"
    intermediary_allowlist: str = "ClaudeDesktop,HigressPlugin,EvaluationSuite"

    @property
    def pro_api_config_url(self) -> str:
        """URL for the PRO API chain config endpoint, derived from the PRO API base URL."""
        return f"{self.pro_api_base_url}/api/json/config"


config = ServerConfig()
