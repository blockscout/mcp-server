# System Prompt Customization

This document describes a process to customize the Gemini CLI system prompt for the Blockscout MCP Server project.

## Resources

- [System Prompt Customization Changelog for Blockscout MCP Server](./sp-customization-changelog.md)
- [Instructions for Generating the System Prompt Customization Changelog](./changelog-generation-instructions.md)

## Prompt Customization Process

1. Check with every new version of the Gemini CLI if the main part of the system prompt was changed: <https://github.com/google-gemini/gemini-cli/blob/main/packages/core/src/core/prompts.ts>

2. If the fact of the change is confirmed, run the new version of the Gemini CLI to compile the system prompt and store it in a file:

    - Add the environment variable `GEMINI_WRITE_SYSTEM_MD=.gemini/system-prompt-original.md` to `.env` file.
    - Run the Gemini CLI by `.gemini/gemini.sh` script and quit from it.
    - Remove the environment variable `GEMINI_WRITE_SYSTEM_MD` from `.env` file.
    - The system prompt will be stored in the file `.gemini/system-prompt-original.md`

3. Improve the original system prompt by explicitly separating the sections with HTML comments like:

    ```html
    <!-- start:section-name -->
    <!-- end:section-name -->
    ```

    The nested sections should be named like:

    ```html
    <!-- start:section-name:nested-section-name -->
    <!-- end:section-name:nested-section-name -->
    ```

    This provides a way to easily navigate through the sections in the system prompt and to adjust them for the Blockscout MCP Server project specifics.

4. Use any AI agent to generate the new system prompt for the Blockscout MCP Server project from the original system prompt and the changelog. The prompt for the agent could be like this:

    ```plaintext
    Apply the instructions from `sp-customization-changelog.md` to `system-prompt-original.md`.

    Your sole and exclusive output must be a single, well-structured Markdown document with the new system prompt.
    ```

5. Review the new system prompt to make sure that the changes were applied correctly.

6. [**IMPORTANT**] Since the original system prompt could contain some sections that were not presented in the previous version of the Gemini CLI, these sections must be adjusted manually to reflect Blockscout MCP Server project specifics.

7. If adjustments on the step 5 are needed use the AI agent to prepare the new changelog. The Instructions for Generating the System Prompt Customization Changelog must be used as a prompt for the agent.

8. The new system prompt must be stored in the file `.gemini/system-prompt.md`.
