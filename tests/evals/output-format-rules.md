<output_format_rules>
When performing blockchain analysis using MCP tools, you MUST format your complete response as a structured JSON object that captures the entire analysis workflow, reasoning chain, and provides a parseable final answer.

## CRITICAL: Output Method

Your final JSON response MUST be output as plain text in your reply - simply write the JSON directly as your response.

**DO NOT:**

- Use `write_file` to create JSON files
- Use shell commands (`cat`, `echo`, heredocs) to output JSON
- Create any files containing the output

**DO:**
Just include the JSON object directly in your response text.

## Output Format

Your response must be a valid JSON object with the following structure:

```json
{
  "response": {
    "final": "Simple parseable answer OR null if is_error is true",
    "is_error": false,
    "error_type": null,
    "confidence": "high|medium|low", 
    "comments": "Detailed explanation supporting the final answer or error description"
  }
}
```

## Guidelines

### Final Response

- **final**: Provide the most concise, parseable answer possible, or `null` if `is_error` is `true`:
  - For yes/no questions: "yes" or "no"
  - For numerical answers: just the number (e.g., "42161" for chain ID)
  - For addresses: the full address without "0x" prefix explanation
  - For timestamps: "YYYY-MM-DDTHH-MM-SS" format (e.g., "2025-09-25T07-22-39")
  - For lists: JSON array format (e.g., ["item1", "item2"]) or count if asking for quantity
- **is_error**: Set to `true` when technical issues prevent completing the analysis
- **error_type**: If `is_error` is `true`, specify the error category:
  - "mcp_tool_failure": MCP tools consistently failed or returned errors
  - "web_search_failure": Web search operations failed
  - "network_connectivity": Unable to reach blockchain networks
  - "contract_not_found": Target contract/address doesn't exist
  - "insufficient_data": Found contracts but couldn't retrieve necessary data
  - "timeout": Analysis exceeded reasonable time limits
- **confidence**: Rate your confidence based on:
  - "high": Direct evidence from verified contracts/clear blockchain data
  - "medium": Inferred from partial evidence or requires assumptions  
  - "low": Limited evidence or significant uncertainty
  - Not applicable when `is_error` is `true`
- **comments**: Provide supporting details, caveats, context, or error descriptions

## Examples of Final Responses

### Boolean Questions

```json
"response": {
  "final": "yes",
  "is_error": false,
  "error_type": null,
  "confidence": "high", 
  "comments": "Contract contains addToBlockedList(), removeFromBlockedList(), isBlocked(), and destroyBlockedFunds() functions"
}
```

### Numerical Questions

```json
"response": {
  "final": "876428667483764",
  "is_error": false,
  "error_type": null,
  "confidence": "high",
  "comments": "Total supply returned directly from totalSupply() function call on verified contract"
}
```

### Address Questions

```json
"response": {
  "final": "0xFd086bC7CD5C481DCC9C85ebE478A1C0b69FCbb9",
  "is_error": false,
  "error_type": null,
  "confidence": "high",
  "comments": "Main USDT token contract on Arbitrum One, verified and widely recognized"
}
```

### Timestamp Questions

```json
"response": {
  "final": "2025-09-25T07-22-39",
  "is_error": false,
  "error_type": null,
  "confidence": "high",
  "comments": "Block timestamp for the requested block"
}
```

### List Questions

```json
"response": {
  "final": ["addToBlockedList", "removeFromBlockedList", "isBlocked", "destroyBlockedFunds"],
  "is_error": false,
  "error_type": null,
  "confidence": "high",
  "comments": "Four blacklisting-related functions found in the contract ABI"
}
```

### Error Responses

```json
"response": {
  "final": null,
  "is_error": true,
  "error_type": "mcp_tool_failure",
  "confidence": null,
  "comments": "Multiple MCP tools failed with 500 Internal Server Error. Unable to retrieve contract ABI or address information to determine blacklisting functionality."
}
```

```json
"response": {
  "final": null,
  "is_error": true,
  "error_type": "contract_not_found",
  "confidence": null,
  "comments": "No USDT token contract found on specified chain ID 999999. Chain may not exist or token may not be deployed there."
}
```

## Error Handling Guidelines

### When to Set is_error = true

- MCP tools consistently fail with errors (500, timeout, etc.)
- Web search operations repeatedly fail
- Cannot establish connection to blockchain networks

### When NOT to Set is_error = true

- Found a contract but it lacks the requested functionality (answer is legitimately "no")
- Successfully retrieved data that shows zero/empty results (answer might be "0" or "none")
- Analysis completed but with low confidence due to ambiguous results
- User query asks about something that doesn't exist by design (legitimate negative answer)

## Quality Checklist

Before outputting, verify:

- [ ] Final answer directly addresses the original question OR is_error is properly set
- [ ] If is_error is true: final is null, error_type is specified, comments explain the issue
- [ ] If is_error is false: confidence level matches the quality of evidence
- [ ] Comments provide sufficient context for the final answer or error
- [ ] JSON is valid and properly formatted
</output_format_rules>
