from src.tools.cube import describe_cube, list_cubes, query_metrics
from src.tools.database import (
    describe_table,
    get_dataset_summary,
    list_tables,
    query_database,
)


def register_tools(mcp):
    # DuckDB direct tools — raw SQL and schema exploration
    # mcp.tool(query_database)
    # mcp.tool(list_tables)
    # mcp.tool(describe_table)
    # mcp.tool(get_dataset_summary)
    # Cube semantic tools — named metrics with automatic join resolution
    mcp.tool(list_cubes)
    mcp.tool(describe_cube)
    mcp.tool(query_metrics)
