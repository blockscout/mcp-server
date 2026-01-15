# MCP Server Evaluation Tests

This directory contains initial version of the Blockscout MCP Server evaluation framework.

The idea is to re-use an existing AI agent to evaluate the MCP Server. Currently, we are using Gemini CLI.

The framework consists of two components:

1. The Blockscout MCP Server docker image.

    - Configured to run in the HTTP Streamable mode.

2. The sandbox image of the Gemini CLI agent.

    - Configured to pick up the config from the local `.gemini` directory.
    - The URL to the MCP Server is defined in the `mcpServers` section of the config.
    - The common instructions of the agent are defined in the [`GEMINI-evals.md`](GEMINI-evals.md) file.
    - Gemini CLI authorization is expected to be present in the `~/.gemini` directory.
    - The model could be specified in `.gemini/.env` file or in the command line when running the agent.

## Evaluation Set Format

The [`eval-set.json`](eval-set.json) file contains a standardized set of evaluation tasks in JSON format. Each evaluation item has the following structure:

```json
{
  "id": "eval-000",
  "model": "gemini-2.5-pro",
  "question": "What is the block number of the Ethereum Mainnet that corresponds to midnight (or any closer moment) of the 1st of July.",
  "expected_result_format": "Final answer is a block number.",
  "ground_truth": {}
}
```

### Field Descriptions

- **`id`** (string): Unique identifier for the evaluation task (e.g., `"eval-000"`, `"eval-001"`). The numeric suffix matches the 0-indexed position in the array.
- **`model`** (string): The Gemini model to use for this evaluation (e.g., `"gemini-2.5-pro"`, `"gemini-2.5-flash"`).
- **`question`** (string): The actual question or task for the AI agent to solve. This should contain only the query itself, without format instructions.
- **`expected_result_format`** (string): Description of how the final answer should be formatted. This helps both the AI agent structure its response and evaluators verify correctness.
- **`ground_truth`** (object): Container for the verified correct answer. Initially empty (`{}`), this should be populated with the verified correct result after running the evaluation.

## Run the tests

### Using `run.sh` (recommended)

The `run.sh` script provides a convenient way to run evaluations with proper validation and output management.

```bash
cd tests/evals

# Run a specific test by index (0-indexed)
./run.sh 4            # Runs eval-004

# Run a specific test by ID
./run.sh eval-004

# Run interactive Gemini session
./run.sh

# Stop and clean up containers
./run.sh clean
```

**Prerequisites:**

- Configure `GEMINI_CLI_DOCKER_IMAGE_VERSION` in `.env` file
- Either build/pull the MCP server image (`docker pull ghcr.io/blockscout/mcp-server:latest`) or set `MCP_SERVER_URL` to an external server. To build the image, run `docker build -t ghcr.io/blockscout/mcp-server .` in the project root directory.

**Output files** are saved to the `results/` directory with timestamps.

## Gemini CLI instructions

[`GEMINI-evals.md`](GEMINI-evals.md) contains comprehensive instructions for the Gemini CLI agent to be able analyze blockchain activities.

The instructions are almost the same as used for Blockscout X-Ray GPT. See [`gpt/instructions.md`](../../gpt/instructions.md) and [`gpt/README.md`](../../gpt/README.md) for more details how the GPT instructions are composed.

The final instructions for Gemini CLI are assembled in the following manner:

```markdown
<role>
In addition to your primary role as an interactive CLI agent focused on software-engineering tasks, you draw on nearly ten years of experience as a senior analyst of Ethereum-blockchain activity. Your deep knowledge of Web3 applications and protocols enriches the guidance you offer when users need blockchain-related engineering help.
</role>

[everything from `gpt/instructions.md` except the sections `<role>` and `<prerequisites>`]

<direct_call_endpoint_list>
[everything from `gpt/direct_call_endpoint_list.md`]
</direct_call_endpoint_list>

<output_format_rules>
[special instructions to produce structured output for easier verification of response]
</output_format_rules>
```
