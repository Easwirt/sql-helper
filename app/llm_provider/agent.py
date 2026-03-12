"""
Agent that connects the LLM to the database via MCP tool calls.
"""

import json
import logging
import os

from openai import AsyncOpenAI, APIError, RateLimitError

from app.config import load_project_env
from app.service.mcp_client import mcp_client
from app.service.sql_validator import (
    ALLOWED_TABLES,
    SqlValidationError,
    apply_authorization_scope,
    validate_sql,
)

load_project_env()

logger = logging.getLogger(__name__)

# Config
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
MAX_TOOL_ROUNDS = 10
EXPOSED_TOOLS = {"execute_sql", "explain_query"}

# Role-based access (maps role to allowed authorization_group values)
ROLE_AUTH_GROUPS = {
    "operations": [40],
    "finance": [60],
    "controller": [40, 60],
}

# OpenAI client (created once)
openai_client = AsyncOpenAI()

_SYSTEM_PROMPT_TEMPLATE = """\
You are a data quality analyst assistant. Your job is to help non-technical users \
explore and understand their data through natural language questions.

## Database Access
You may ONLY query these tables:
{allowed_tables}

{schema_section}

## Data Quality Focus
When users ask about their data, think in terms of these dimensions:

1. **Completeness**: NULL counts, empty fields, missing values
2. **Validity**: Unexpected values, values outside expected ranges
3. **Uniqueness**: Duplicate detection
4. **Distribution**: Min/max/avg, counts by category, histograms
5. **Outliers**: Values that deviate significantly from the norm
6. **Timeliness**: Date ranges, latest records, gaps in time series

## Few-Shot Examples

User: "Are there any data quality issues?"
→ Run multiple queries: count NULLs per column, check value distributions, look for outliers in numeric fields.

User: "How complete is the data?"
→ Query: SELECT column_name, COUNT(*) FILTER (WHERE column IS NULL) as nulls FROM table
→ Report: "X rows have empty clearing_date (Y%), Z rows missing exchange_rate..."

User: "Any outliers in transaction values?"
→ Query: Calculate mean and stddev, find values > 3 standard deviations from mean
→ Report: "Found N transactions with unusually high/low values: [list top examples]"

User: "Summarize the data"
→ Run: row count, date range, value distribution, top categories, NULL percentages
→ Report: structured summary with key stats

## Output Formatting
- Use clear headers and bullet points
- Include actual numbers (counts, percentages)
- For large result sets, show top 5-10 examples
- Round decimals to 2 places for readability
- Format currency values with commas

## Handling Ambiguous Queries
If the user's question is vague (e.g., "tell me about the data"):
1. Start with a general profile: row count, date range, key distributions
2. Highlight any obvious data quality issues
3. Suggest follow-up questions they might ask

If you're unsure what column they mean, check the schema and make a reasonable guess, \
or briefly clarify while still providing useful output.

## Important Rules
- Always query the database — never guess at data values
- Use LIMIT for exploratory queries to avoid huge outputs
- If a query returns too many rows, summarize or show a sample
- Never query tables outside the allowed list

{role_section}

## Conversation Rules
- Previous context is for reference only — do NOT re-answer old questions
- ONLY respond to the final user message
"""


def _build_system_prompt(role: str) -> str:
    schema = mcp_client.schema_context
    allowed_groups = ROLE_AUTH_GROUPS[role]

    allowed_tables = "\n".join(f"  - {t}" for t in sorted(ALLOWED_TABLES))
    schema_section = f"### Table Schema\n```\n{schema}\n```" if schema else ""
    role_section = (
        "## Access Control\n"
        f"- Role: {role}\n"
        f"- Allowed authorization_group values: {allowed_groups}\n"
        "- All queries are automatically scoped to these groups"
    )
    
    logger.info("SCHEMA IS" + schema_section)

    return _SYSTEM_PROMPT_TEMPLATE.format(
        allowed_tables=allowed_tables,
        schema_section=schema_section,
        role_section=role_section,
    )


def _truncate(text: str, max_chars: int = 12000) -> str:
    """Truncate large outputs to avoid token limits."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n\n[OUTPUT TRUNCATED - use LIMIT or filters for smaller results]"


def _add_context(messages: list, context_messages: list[dict] | None) -> None:
    """Add previous conversation context to messages."""
    if not context_messages:
        return
    
    lines = []
    for i, msg in enumerate(context_messages, 1):
        content = (msg.get("content") or "").strip()
        if content:
            lines.append(f"  [past-Q{i}]: {content}")
    
    if lines:
        messages.append({
            "role": "system",
            "content": "Previous questions (for context only, don't re-answer):\n" + "\n".join(lines)
        })


async def run_agent(
    user_message: str,
    role: str = "controller",
    context_messages: list[dict] | None = None,
) -> dict:
    """Run the agent loop. Returns dict with 'reply' and 'tool_calls'."""
    if role not in ROLE_AUTH_GROUPS:
        role = "controller"  # Default fallback
    
    # Get available tools from MCP
    tools = [t for t in mcp_client.openai_tools if t["function"]["name"] in EXPOSED_TOOLS]
    
    # Build messages
    messages = [{"role": "system", "content": _build_system_prompt(role)}]
    _add_context(messages, context_messages)
    messages.append({"role": "user", "content": user_message})
    
    tool_calls_log = []
    allowed_groups = ROLE_AUTH_GROUPS[role]
    
    # Agent loop
    for _ in range(MAX_TOOL_ROUNDS):
        try:
            response = await openai_client.chat.completions.create(
                model=MODEL,
                messages=messages,
                tools=tools or None,
            )
        except (RateLimitError, APIError) as e:
            return {"reply": f"API error: {e}", "tool_calls": tool_calls_log}
        
        choice = response.choices[0]
        
        # If no tool calls, we're done
        if choice.finish_reason != "tool_calls":
            return {"reply": choice.message.content or "", "tool_calls": tool_calls_log}
        
        messages.append(choice.message.model_dump(exclude_none=True))
        
        # Process each tool call
        for tc in choice.message.tool_calls:
            fn_name = tc.function.name
            fn_args = json.loads(tc.function.arguments)
            tool_calls_log.append({"tool": fn_name, "arguments": fn_args})
            logger.info("Tool call: %s(%s)", fn_name, fn_args)
            
            # Validate and scope SQL queries
            if fn_name in ("execute_sql", "explain_query") and "sql" in fn_args:
                try:
                    validate_sql(fn_args["sql"])
                    fn_args["sql"] = apply_authorization_scope(fn_args["sql"], allowed_groups)
                except SqlValidationError as e:
                    messages.append({"role": "tool", "tool_call_id": tc.id, "content": f"BLOCKED: {e}"})
                    continue
            
            # Call the tool
            try:
                result = await mcp_client.call_tool(fn_name, fn_args)
            except Exception as e:
                result = f"Error: {e}"
            
            # Truncate large results
            if fn_name in ("execute_sql", "explain_query"):
                result = _truncate(result)
            
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})
    
    # If we hit max rounds, ask for a summary
    try:
        messages.append({"role": "user", "content": "Please summarize what you found."})
        response = await openai_client.chat.completions.create(model=MODEL, messages=messages)
        return {"reply": response.choices[0].message.content or "", "tool_calls": tool_calls_log}
    except Exception:
        return {"reply": "Could not complete the request.", "tool_calls": tool_calls_log}
