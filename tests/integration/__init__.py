# Integration tests for Blockscout MCP Server
#
# These tests make real network calls to live APIs and are slower than unit tests.
# Run with: pytest -m integration -v
#
# The directory structure mirrors MCP tool groupings. Each ``*_real.py`` module
# contains integration tests for a single tool so that coding agents can load
# focused contexts without unrelated scenarios.
