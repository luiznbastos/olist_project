import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI

from src.api.endpoints.ask import router as ask_router
from src.config import settings
from src.services.agent_service import AgentService

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Connecting to MCP server at %s", settings.mcp_server_url)
    client = MultiServerMCPClient(
        {"olist-mcp": {"url": settings.mcp_server_url, "transport": "streamable_http"}}
    )
    tools = await client.get_tools()
    logger.info("Loaded %d tools from olist-mcp", len(tools))
    llm = ChatOpenAI(model=settings.openai_model, api_key=settings.openai_api_key, temperature=0)
    app.state.agent_service = AgentService(llm, tools)
    yield


app = FastAPI(title="olist-agent", lifespan=lifespan)
app.include_router(ask_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host=settings.host, port=settings.port, reload=False)
