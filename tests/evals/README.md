# MCP Server Evaluation Tests

This directory contains the Blockscout MCP Server evaluation framework using Gemini CLI as the evaluation agent.

## Framework Overview

The framework consists of two Docker services orchestrated by `docker-compose.yml`:

1. **MCP Server** (optional)
   - Only runs when `MCP_SERVER_URL` is not configured or points to the internal server (`http://mcp-server:8080`)
   - Runs in HTTP Streamable mode on port 8080
   - Can be replaced by pointing to an external server (staging or production)

2. **Gemini CLI Agent** (evaluation runner)
   - Uses the sandbox image from Google's Gemini CLI
   - Connects to MCP server via URL specified in configuration chain (`.env` → `docker-compose.yml` → `.gemini/settings.json`)
   - Instructions are defined in [`GEMINI-evals.md`](GEMINI-evals.md) with additional output formatting rules from [`output-format-rules.md`](output-format-rules.md)
   - Authentication via Gemini API key (optional) or Login with Google (profile stored in `GEMINI_USER_PROFILE` directory, defaults to `~/.gemini`)
   - Models are specified per-test in [`eval-set.json`](eval-set.json), not via environment variables or command line

## Configuration

### Environment Variables

Create a `.env` file based on `.env.example` with the following variables:

- **`MCP_SERVER_URL`**: URL of the MCP server to test (default: `http://mcp-server:8080` for internal Docker server)
  - Set to external URL (e.g., `https://mcp.blockscout.com`) to skip running the internal MCP server container
  - When set to external URL, docker-compose will only run the evaluation container
- **`GEMINI_CLI_DOCKER_IMAGE_VERSION`**: Version of Gemini CLI sandbox image (e.g., `0.24.0`)
- **`GEMINI_USER_PROFILE`**: Path to Gemini profile directory (default: `${HOME}/.gemini`)
  - Contains authentication data when using "Login with Google"
  - Can be customized to separate testing and coding environments (e.g., use `~/.gemini` for coding, `~/.gemini-eval` for testing)
- **`GEMINI_API_KEY`**: Gemini API key for authentication (optional)
  - Alternative to "Login with Google" method
  - If not set, authentication profile must exist in `GEMINI_USER_PROFILE` directory

### Configuration Chain

The MCP server URL flows through the configuration chain:

```plaintext
.env → docker-compose.yml → .gemini/settings.json
```

The `.gemini/settings.json` file is kept intentionally minimal, as the main Gemini configuration is expected to be in `${GEMINI_USER_PROFILE}/settings.json`. It intentionally includes one `headers` override (`Blockscout-MCP-Intermediary: EvaluationSuite`) so eval traffic is identified distinctly from regular users in MCP server logs and analytics.

### Instructions and Output Format

- **Instructions**: [`GEMINI-evals.md`](GEMINI-evals.md) contains comprehensive blockchain analysis instructions
- **Output Format**: [`output-format-rules.md`](output-format-rules.md) defines the required JSON response structure
  - Only contains final result section (no reasoning steps or MCP tool call traces)
  - Reasoning and tool traces are captured separately in the debug file

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
- **`model`** (string): The Gemini model to use for this evaluation (e.g., `"gemini-2.5-pro"`, `"gemini-2.5-flash"`). This is the **only** way to specify the model - environment variables and command line flags are not used.
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

# List all available tests
./run.sh list

# Print details of a specific test
./run.sh print 4
./run.sh print eval-004

# Dry run (show command without executing)
./run.sh --dry 4

# Stop and clean up containers
./run.sh clean
```

**Prerequisites:**

- Create `.env` file with required configuration (see Configuration section above)
- Pull Gemini CLI image: `docker pull us-docker.pkg.dev/gemini-code-dev/gemini-cli/sandbox:${GEMINI_CLI_DOCKER_IMAGE_VERSION}`
- **For internal MCP server**: Either pull the image (`docker pull ghcr.io/blockscout/mcp-server:latest`) or build locally (`docker build -t ghcr.io/blockscout/mcp-server:latest .` from project root)
- **For external MCP server**: Set `MCP_SERVER_URL` to the external server URL in `.env` file (no MCP server image needed)

### Output Files

Each test run produces two files in the `results/` directory with timestamps:

1. **`{id}-{timestamp}.json`**: Debug file containing raw API interaction trace
   - Complete sequence of Gemini API method calls and responses
   - Model's reasoning thoughts
   - MCP tool function calls with full request/response data
   - Token usage metadata for each API round trip
   - Raw, unprocessed data useful for debugging and detailed analysis

2. **`{id}-output-{timestamp}.json`**: Output file with final result and statistics
   - Session ID for tracking
   - Final response following `output-format-rules.md` format
   - Comprehensive statistics including:
     - Model usage stats (API requests, latency, token counts including cached tokens and thoughts)
     - Tool usage stats (total calls, success/failure counts, duration, per-tool breakdown)
     - File operation stats (lines added/removed)
   - Ready for automated evaluation and performance analysis

Example:

```plaintext
results/eval-004-2026-01-20-17-50-59.json         # Debug file with raw API trace
results/eval-004-output-2026-01-20-17-50-59.json  # Output file with final result and stats
```

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

Follow instructions in @output-format-rules.md when outputting your response.
```

## Troubleshooting

### Authentication Issues

If you encounter authentication errors:

1. **Using Gemini API Key**: Ensure `GEMINI_API_KEY` is set in your `.env` file
2. **Using Login with Google**:
   - Run `./run.sh` to start an interactive session
   - Follow the prompts to authenticate via Google
   - Authentication data will be saved in `GEMINI_USER_PROFILE` directory (default: `~/.gemini`)
   - Subsequent runs will use the saved authentication

### MCP Server Connection Issues

If evaluations can't connect to the MCP server:

1. **Internal server**: Verify the Docker image exists: `docker images | grep mcp-server`
2. **External server**: Test connectivity: `curl -I ${MCP_SERVER_URL}`
3. **Check configuration chain**: Verify `MCP_SERVER_URL` is properly propagated through `.env` → `docker-compose.yml` → `.gemini/settings.json`

### Profile Isolation

To maintain separate environments for coding and testing:

```bash
# In .env file for testing
GEMINI_USER_PROFILE=/home/user/.gemini-eval

# Your regular coding environment will use the default ~/.gemini
```

This allows you to:

- Use different authentication credentials
- Maintain separate MCP server configurations
- Avoid conflicts between testing and development sessions
