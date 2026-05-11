import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI

from src.api.endpoints.ask import router as ask_router
from src.config import settings
from src.services.agent_service import AgentService
from src.services.agent_service_claude import ClaudeAgentService

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.agent_type == "claude":
        os.environ.setdefault("ANTHROPIC_API_KEY", settings.anthropic_api_key)
        app.state.agent_service = ClaudeAgentService(
            mcp_server_url=settings.mcp_server_url,
            model=settings.anthropic_model,
            enable_thinking=settings.enable_thinking,
            thinking_budget=settings.thinking_budget,
        )
        logger.info("Started ClaudeAgentService with model=%s", settings.anthropic_model)
    else:
        logger.info("Connecting to MCP server at %s", settings.mcp_server_url)
        mcp_client = MultiServerMCPClient(
            {"olist-mcp": {"url": settings.mcp_server_url, "transport": "streamable_http"}}
        )
        tools = await mcp_client.get_tools()
        logger.info("Loaded %d tools from olist-mcp", len(tools))
        llm = ChatOpenAI(model=settings.openai_model, api_key=settings.openai_api_key, temperature=0)
        app.state.agent_service = AgentService(llm, tools)
        logger.info("Started AgentService with model=%s", settings.openai_model)

    yield


app = FastAPI(title="olist-agent", lifespan=lifespan)
app.include_router(ask_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host=settings.host, port=settings.port, reload=False)
