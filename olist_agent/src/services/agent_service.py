import logging
from typing import Any, Dict, List

from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain_core.tools import BaseTool

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


class AgentService:
    def __init__(self, llm: ChatOpenAI, tools: List[BaseTool]):
        self.agent = create_react_agent(llm, tools, prompt=SYSTEM_PROMPT)
        logger.info("AgentService initialized with %d tools", len(tools))

    def _extract_response(self, final_state: dict) -> str:
        ai_messages = [
            msg for msg in final_state.get("messages", [])
            if isinstance(msg, AIMessage)
        ]
        if not ai_messages:
            return "No response generated."
        content = ai_messages[-1].content
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            text_parts = [item for item in content if isinstance(item, str)]
            return "\n".join(text_parts) if text_parts else str(content)
        return str(content)

    def _extract_sources(self, final_state: dict) -> List[Dict[str, Any]]:
        tool_call_inputs: Dict[str, Any] = {}
        for msg in final_state.get("messages", []):
            if isinstance(msg, AIMessage) and msg.tool_calls:
                for tc in msg.tool_calls:
                    tool_call_inputs[tc["id"]] = tc["args"]

        sources = []
        for msg in final_state.get("messages", []):
            if isinstance(msg, ToolMessage):
                sources.append({
                    "tool": msg.name,
                    "input": tool_call_inputs.get(msg.tool_call_id, {}),
                    "content": msg.content,
                })
        return sources

    async def process_query(self, request: QueryRequest) -> QueryResponse:
        messages = [HumanMessage(content=request.query)]
        response_text = "No response generated."
        sources: List[Dict[str, Any]] = []
        try:
            final_state = await self.agent.ainvoke({"messages": messages})
            response_text = self._extract_response(final_state)
            sources = self._extract_sources(final_state)
        except Exception as e:
            logger.error("Error running agent: %s", e, exc_info=True)
            response_text = f"Error processing query: {e}"

        return QueryResponse(
            query=request.query,
            response=response_text,
            sources=sources,
        )
