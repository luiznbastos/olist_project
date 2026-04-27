import asyncio

from fastmcp import Context
from tabulate import tabulate

from src.utils.duckdb_client import DuckDBClient
from src.utils.logger import get_logger

logger = get_logger(__name__)


def _format_results(results: list[dict], headers: list[str] | None = None) -> str:
    if not results:
        return "No results found."
    if headers is None:
        headers = list(results[0].keys())
    rows = [[r.get(h, "") for h in headers] for r in results]
    table = tabulate(rows, headers=headers, tablefmt="github")
    return f"Found {len(results)} rows:\n\n{table}"


def _get_db(ctx: Context) -> DuckDBClient:
    return ctx.lifespan_context["db"]


async def query_database(query: str, limit: int = 100, ctx: Context = None) -> str:
    """Execute a read-only SQL query against the Olist data lake (DuckDB over local Parquet).
    Results are returned as a formatted markdown table."""
    db = _get_db(ctx)

    clean = query.strip().rstrip(";")
    upper = clean.upper()

    starts_with_select = upper.startswith("SELECT") or upper.startswith("WITH")
    has_limit = "LIMIT" in upper.split(")")[-1]

    if starts_with_select and not has_limit:
        clean = f"{clean} LIMIT {int(limit)}"

    results = await asyncio.to_thread(db.query, clean)
    return _format_results(results)


async def list_tables(ctx: Context = None) -> str:
    """List all tables and views available in the data lake, classified by pipeline layer
    (Raw, Bronze, Silver, Gold)."""
    db = _get_db(ctx)

    sql = """
    SELECT table_name, table_type
    FROM information_schema.tables
    WHERE table_schema = 'main'
    ORDER BY table_name
    """
    results = await asyncio.to_thread(db.query, sql)

    if not results:
        return "No tables found. The data lake may be empty (run dbt to populate it)."

    for row in results:
        row["layer"] = db.table_layers.get(row["table_name"], "Other")

    return _format_results(results, headers=["table_name", "table_type", "layer"])


async def describe_table(table_name: str, ctx: Context = None) -> str:
    """Get schema information for a specific table: column names, data types, and nullability."""
    db = _get_db(ctx)

    columns_sql = f"""
    SELECT column_name, data_type, is_nullable, column_default
    FROM information_schema.columns
    WHERE table_name = '{table_name}' AND table_schema = 'main'
    ORDER BY ordinal_position
    """
    columns = await asyncio.to_thread(db.query, columns_sql)

    if not columns:
        return (
            f"No columns found for table '{table_name}'. "
            "The table may not exist or the dbt run that produces it has not completed yet."
        )

    return (
        f"Schema for table '{table_name}':\n\n"
        + _format_results(
            columns,
            headers=["column_name", "data_type", "is_nullable", "column_default"],
        )
    )


async def get_dataset_summary(ctx: Context = None) -> str:
    """Get row counts for all registered tables in the data lake."""
    db = _get_db(ctx)

    if not db.table_layers:
        return "No tables registered. Run dbt to populate the data lake."

    rows = []
    for table, layer in sorted(db.table_layers.items()):
        try:
            result = await asyncio.to_thread(db.query, f"SELECT COUNT(*) AS row_count FROM {table}")
            count = result[0]["row_count"] if result else 0
        except Exception as e:
            count = f"ERROR: {e}"
        rows.append({"table": table, "layer": layer, "row_count": count})

    return _format_results(rows, headers=["table", "layer", "row_count"])
