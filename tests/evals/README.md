# MCP Server Evaluation Tests

This directory contains initial version of the Blockscout MCP Server evaluation framework.

The idea is to re-use an existing AI agent to evaluate the MCP Server. Currently, we are using Gemini CLI.

The framework consists of two components:

1. The Blockscout MCP Server docker image.

    - Configured to run in the HTTP Streamable mode.

2. The sandbox image of the Gemini CLI agent.

    - Configured to pick up the config from the local `.gemini` directory.
    - The URL to the MCP Server is defined in the `mcpServers` section of the config.
    - The common instructions of the agent are defined in the `GEMINI.md` file.
    - It is expected that the Gemini CLI authorization defined in the `~/.gemini` directory.
    - The model could be specified in `.gemini/.env` file or in the command line when running the agent.

## Run the tests

1. If it is necessary, build the docker image of the Blockscout MCP Server in the project root directory. Otherwise, the latest image from the Blockscout registry will be used.

    ```bash
    docker rmi ghcr.io/blockscout/mcp-server:latest
    docker build -t ghcr.io/blockscout/mcp-server .
    ```

2. Move to the `tests/evals` directory and run a test.

    ```bash
    cd tests/evals
    docker compose run --rm -i evaluation gemini -y -p 'Which 10 most recent logs were emitted by 0xFe89cc7aBB2C4183683ab71653C4cdc9B02D44b7 before "Nov 08 2024 04:21:35 AM (-06:00 UTC)"? on Ethereum Mainnet'
    ```

   The MCP Server will be run automatically.
   An output of the test will be on the console.
   The evaluation docker container will be removed after the test is finished.

3. Stop the MCP Server.

    ```bash
    docker compose down
    ```
