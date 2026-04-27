from fastmcp import FastMCP
from fastmcp.server.lifespan import lifespan

from src.config import settings
from src.tools import register_tools
from src.utils.cube_client import CubeClient
from src.utils.duckdb_client import DuckDBClient
from src.utils.logger import get_logger

logger = get_logger(__name__)


@lifespan
async def app_lifespan(server):
    logger.info("Starting MCP server, initializing database connections...")
    db_client = DuckDBClient(
        data_lake_path=settings.data_lake_path,
        layers=settings.duckdb_layers_list,
    )
    cube_client = CubeClient(
        base_url=settings.cube_api_url,
        api_secret=settings.cube_api_secret,
    )
    try:
        yield {"db": db_client, "cube": cube_client}
    finally:
        db_client.close()
        await cube_client.close()
        logger.info("Database connections closed.")


mcp = FastMCP(
    "olist-mcp-server",
    instructions=(
        "MCP server for querying Olist Brazilian e-commerce analytics data from the local data lake. "
        "Use the available tools to explore tables, run SQL queries, and inspect dataset statistics. "
        "Data is read-only and served via DuckDB over local Parquet files."
    ),
    lifespan=app_lifespan,
)

register_tools(mcp)

if __name__ == "__main__":
    mcp.run(transport="http", host=settings.mcp_host, port=settings.mcp_port)
