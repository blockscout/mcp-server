# Generated by https://smithery.ai. See: https://smithery.ai/docs/build/project-config
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml pyproject.toml
# Install uv for dependency management
RUN pip install uv
RUN uv pip install --system . # Install dependencies from pyproject.toml

COPY blockscout_mcp_server /app/blockscout_mcp_server

ENV PYTHONUNBUFFERED=1

# Expose environment variables that can be set at runtime
# Set defaults here to document expected environment variables
# ENV BLOCKSCOUT_BS_API_KEY="" # It is commented out because docker build warns about sensitive data in ENV instructions
ENV BLOCKSCOUT_BS_TIMEOUT="120.0"
ENV BLOCKSCOUT_BENS_URL="https://bens.services.blockscout.com"
ENV BLOCKSCOUT_BENS_TIMEOUT="30.0"
ENV BLOCKSCOUT_METADATA_URL="https://metadata.services.blockscout.com"
ENV BLOCKSCOUT_METADATA_TIMEOUT="30.0"
ENV BLOCKSCOUT_CHAINSCOUT_URL="https://chains.blockscout.com"
ENV BLOCKSCOUT_CHAINSCOUT_TIMEOUT="15.0"
ENV BLOCKSCOUT_CHAIN_CACHE_TTL_SECONDS="1800"
ENV BLOCKSCOUT_PROGRESS_INTERVAL_SECONDS="15.0"
ENV BLOCKSCOUT_NFT_PAGE_SIZE="10"
ENV BLOCKSCOUT_LOGS_PAGE_SIZE="10"
ENV BLOCKSCOUT_ADVANCED_FILTERS_PAGE_SIZE="10"

CMD ["python", "-m", "blockscout_mcp_server"]
