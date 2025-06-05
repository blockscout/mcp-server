from pydantic_settings import BaseSettings

class ServerConfig(BaseSettings):
    bs_api_key: str = ""  # Default to empty, can be set via env
    bs_timeout: float = 120.0  # Default timeout in seconds

    bens_url: str = "https://bens.services.blockscout.com"  # Add this now for Phase 2
    bens_timeout: float = 30.0  # Default timeout for BENS requests

    chainscout_url: str = "https://chains.blockscout.com"  # Updated to https
    chainscout_timeout: float = 15.0  # Default timeout for Chainscout requests
    
    chain_cache_ttl_seconds: int = 1800  # Default 30 minutes
    progress_interval_seconds: float = 15.0  # Default interval for periodic progress updates

    class Config:
        env_prefix = "BLOCKSCOUT_"  # e.g., BLOCKSCOUT_BS_URL

config = ServerConfig() 