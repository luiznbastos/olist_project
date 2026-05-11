import logging
from typing import Any, Dict, List

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    HookMatcher,
    ResultMessage,
    TextBlock,
    ThinkingBlock,
    ToolUseBlock,
    query,
)

from src.models import QueryRequest, QueryResponse

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
You are a data analyst assistant for the Olist Brazilian e-commerce dataset (2016–2018):
orders, customers, sellers, products, payments, reviews, and geolocation.

You DO NOT write SQL. You query a Cube semantic layer through three tools:

  1. list_cubes        — discover available cubes with their measures and dimensions
  2. describe_cube     — inspect exact field names, types, and descriptions of one cube
  3. query_metrics     — execute the actual query

Mandatory workflow for every business question:

  Step 1. Call list_cubes to see what is available.
  Step 2. Call describe_cube on each cube you plan to use to confirm the EXACT field names.
  Step 3. Call query_metrics with the validated names.

Hard rules — violating these will fail validation or cause a 400 from Cube:

  - NEVER invent measure or dimension names. Always confirm them via describe_cube first.
  - NEVER reference tables like `order_items`, `order_payments`, `order_reviews` — those are
    raw tables and are NOT exposed. Only the cubes returned by list_cubes are queryable.
  - NEVER use SQL operators like `greater_than`, `>`, `LIKE`. Cube uses: equals, notEquals,
    contains, notContains, gt, gte, lt, lte, set, notSet, inDateRange, beforeDate, afterDate.
  - Filter `values` MUST be a list of strings, even for numbers: ["100"], not [100].
  - The `filters` argument is ALWAYS a list of dicts — never a bare dict, never Mongo-style
    syntax like {"field": {"gt": [...]}}. Each list element has the shape
    {"member": "...", "operator": "...", "values": [...]}, or a boolean grouping
    {"or": [...]} / {"and": [...]} that wraps nested filter dicts.
  - Joins between cubes are automatic — just reference fields from multiple cubes in the same
    query (e.g. measures from `orders`, dimensions from `customers`).

If a question cannot be answered with the available measures and dimensions (for example,
because a needed field is not exposed as a dimension), say so explicitly instead of guessing.

If the question is unrelated to Olist e-commerce, say you are not able to answer it.
"""


def _extract_tool_response(tool_response: Any) -> str:
    """Normalize the tool_response field from PostToolUseHookInput into a plain string."""
    if tool_response is None:
        return ""
    if isinstance(tool_response, str):
        return tool_response
    if isinstance(tool_response, list):
        parts = []
        for item in tool_response:
            if isinstance(item, dict):
                parts.append(item.get("text") or item.get("content") or str(item))
            else:
                parts.append(str(item))
        return "\n".join(parts)
    if isinstance(tool_response, dict):
        content = tool_response.get("content") or tool_response.get("text") or tool_response.get("output")
        if isinstance(content, list):
            return "\n".join(
                item.get("text", "") if isinstance(item, dict) else str(item)
                for item in content
            )
        return str(content) if content is not None else str(tool_response)
    return str(tool_response)


class ClaudeAgentService:
    def __init__(
        self,
        mcp_server_url: str,
        model: str = "claude-sonnet-4-6",
        enable_thinking: bool = False,
        thinking_budget: int = 5000,
    ):
        self.mcp_server_url = mcp_server_url
        self.model = model
        self.enable_thinking = enable_thinking
        self.thinking_budget = thinking_budget
        logger.info("ClaudeAgentService initialized with model=%s", model)

    async def process_query(self, request: QueryRequest) -> QueryResponse:
        sources: List[Dict[str, Any]] = []
        response_text = "No response generated."

        # Capture MCP tool calls and their outputs via PostToolUse hook.
        # The hook runs inside the query() generator before the next message is yielded,
        # so appending here keeps sources in the correct chronological order.
        async def capture_tool_result(input_data, tool_use_id, context):
            logger.debug("PostToolUse: tool=%s keys=%s", input_data.get("tool_name"), list(input_data.keys()))
            sources.append({
                "tool": input_data.get("tool_name", "unknown"),
                "input": input_data.get("tool_input", {}),
                "content": _extract_tool_response(input_data.get("tool_response")),
            })
            return {}

        options_kwargs: Dict[str, Any] = {
            "model": self.model,
            "system_prompt": SYSTEM_PROMPT,
            "mcp_servers": {
                "olist-mcp": {
                    "type": "http",
                    "url": self.mcp_server_url,
                }
            },
            
            "allowed_tools": ["mcp__olist-mcp__*"], # Only allow the three semantic-layer MCP tools; nothing else.
            "permission_mode": "bypassPermissions", # bypassPermissions prevents the agent from stalling on approval prompts in a headless server context.
            "setting_sources": [], # Do not inherit any project-level Claude Code settings from disk.
            "hooks": {
                "PostToolUse": [
                    HookMatcher(matcher="^mcp__olist-mcp__", hooks=[capture_tool_result])
                ]
            },
        }

        if self.enable_thinking:
            options_kwargs["thinking"] = {
                "type": "enabled",
                "budget_tokens": self.thinking_budget,
            }

        options = ClaudeAgentOptions(**options_kwargs)

        try:
            async for message in query(prompt=request.query, options=options):
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, ThinkingBlock):
                            # Thinking blocks appear before the tool call in the same turn,
                            # so inserting here keeps the chronological order intact.
                            sources.append({
                                "type": "thinking",
                                "tool": "__thinking__",
                                "input": {},
                                "content": block.thinking,
                            })

                elif isinstance(message, ResultMessage) and message.subtype == "success":
                    if message.result:
                        response_text = message.result

        except Exception as e:
            logger.error("Error running Claude agent: %s", e, exc_info=True)
            response_text = f"Error processing query: {e}"

        return QueryResponse(
            query=request.query,
            response=response_text,
            sources=sources,
        )
