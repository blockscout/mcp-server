from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class ServerConfig(BaseSettings):
    model_config = ConfigDict(env_prefix="BLOCKSCOUT_")  # e.g., BLOCKSCOUT_BS_URL

    bs_api_key: str = ""  # Default to empty, can be set via env
    bs_timeout: float = 120.0  # Default timeout in seconds

    bens_url: str = "https://bens.services.blockscout.com"  # Add this now for Phase 2
    bens_timeout: float = 30.0  # Default timeout for BENS requests

    chainscout_url: str = "https://chains.blockscout.com"  # Updated to https
    chainscout_timeout: float = 15.0  # Default timeout for Chainscout requests

    # Metadata service configuration
    metadata_url: str = "https://metadata.services.blockscout.com"
    metadata_timeout: float = 30.0

    chain_cache_ttl_seconds: int = 1800  # Default 30 minutes
    chains_list_ttl_seconds: int = 300  # Default 5 minutes
    progress_interval_seconds: float = 15.0  # Default interval for periodic progress updates

    nft_page_size: int = 10
    logs_page_size: int = 10
    advanced_filters_page_size: int = 10


config = ServerConfig()
