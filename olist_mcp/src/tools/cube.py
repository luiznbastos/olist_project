import json
from typing import Optional

from fastmcp import Context
from tabulate import tabulate

from src.utils.cube_client import CubeClient
from src.utils.logger import get_logger

logger = get_logger(__name__)


def _get_cube(ctx: Context) -> CubeClient:
    return ctx.lifespan_context["cube"]


async def list_cubes(ctx: Context = None) -> str:
    """List all Cube semantic models with their available measures and dimensions.
    Call this first to discover what business metrics and attributes can be queried
    before using query_metrics."""
    cube = _get_cube(ctx)
    meta = await cube.meta()

    rows = []
    for c in meta.get("cubes", []):
        measures = [m["name"] for m in c.get("measures", [])]
        dimensions = [d["name"] for d in c.get("dimensions", [])]
        rows.append({
            "cube": c["name"],
            "measures": ", ".join(measures),
            "dimensions": ", ".join(dimensions),
        })

    if not rows:
        return "No cubes found. Check Cube configuration."

    headers = ["cube", "measures", "dimensions"]
    table = tabulate(
        [[r[h] for h in headers] for r in rows],
        headers=headers,
        tablefmt="github",
    )
    return f"Available cubes ({len(rows)}):\n\n{table}"


async def describe_cube(cube_name: str, ctx: Context = None) -> str:
    """Get full measure and dimension details for a specific Cube model,
    including types and descriptions. Use before query_metrics to confirm exact field names."""
    cube = _get_cube(ctx)
    meta = await cube.meta()

    target = next((c for c in meta.get("cubes", []) if c["name"] == cube_name), None)
    if not target:
        available = [c["name"] for c in meta.get("cubes", [])]
        return f"Cube '{cube_name}' not found. Available: {available}"

    out = [f"# {cube_name}\n"]

    measures = target.get("measures", [])
    if measures:
        out.append("## Measures")
        rows = [[m["name"], m.get("type", ""), m.get("description", "")] for m in measures]
        out.append(tabulate(rows, headers=["name", "type", "description"], tablefmt="github"))

    dimensions = target.get("dimensions", [])
    if dimensions:
        out.append("\n## Dimensions")
        rows = [[d["name"], d.get("type", ""), d.get("description", "")] for d in dimensions]
        out.append(tabulate(rows, headers=["name", "type", "description"], tablefmt="github"))

    return "\n".join(out)


async def query_metrics(
    measures: list[str],
    dimensions: Optional[list[str]] = None,
    filters: Optional[list[dict]] = None,
    time_dimension: Optional[str] = None,
    granularity: Optional[str] = None,
    limit: int = 1000,
    ctx: Context = None,
) -> str:
    """Query Cube semantic metrics by name. Cube resolves joins automatically.

    ALWAYS call `list_cubes` and `describe_cube` first to confirm exact field names
    before invoking this tool. Inventing names causes a 400 error.

    Args:
        measures: Fully-qualified measure names, e.g. ['orders.total_revenue', 'orders.order_count'].
        dimensions: Fully-qualified dimensions to group by, e.g. ['orders.order_status'].
        filters: List of filter objects. See REQUIRED FORMAT below.
        time_dimension: Time dimension to filter/group on, e.g. 'orders.purchase_date'.
        granularity: One of 'day', 'week', 'month', 'quarter', 'year'.
        limit: Maximum rows returned (default 1000).

    Filter format (STRICT — anything else is rejected):

        `filters` is ALWAYS a Python list, even for a single filter.
        Each list element is a dict with this exact shape:
            {"member": "<cube>.<field>", "operator": "<op>", "values": ["<str>", ...]}

        - `member` must be `cube_name.field_name` (e.g. 'orders.order_status'),
          NOT a raw table or SQL column name.
        - `operator` must be one of:
            equals, notEquals, contains, notContains, startsWith, endsWith,
            gt, gte, lt, lte, set, notSet,
            inDateRange, notInDateRange, beforeDate, afterDate.
          DO NOT use SQL syntax like '>', '=', 'LIKE', 'greater_than'.
        - `values` MUST be a list of strings, even for numbers and booleans.
          Use ["100"], NOT [100]. Use ["true"], NOT [true].
        - `set` and `notSet` take an empty `values` list: [].

        Boolean grouping with `or` / `and`:
            Each grouping is itself a list element with exactly one key (`or` or `and`)
            whose value is a list of nested filter dicts. NEVER put `or`/`and` at the
            top level of `filters`; the top level is always a list.

    Anti-patterns (these WILL fail validation — do NOT do this):

        # WRONG — top-level dict instead of a list
        filters = {"or": [...]}

        # WRONG — Mongo / SQLAlchemy style; Cube does not understand this
        filters = [{"orders.avg_order_value": {"gt": ["100"]}}]

        # WRONG — SQL-style operator name and numeric value
        filters = [{"member": "orders.avg_order_value",
                    "operator": "greater_than", "values": [100]}]

        # WRONG — single filter passed as a dict instead of a one-item list
        filters = {"member": "orders.order_status",
                   "operator": "equals", "values": ["delivered"]}

    Examples (correct):

        # 1) Total revenue and order count for delivered orders only
        query_metrics(
            measures=["orders.total_revenue", "orders.order_count"],
            filters=[{
                "member": "orders.order_status",
                "operator": "equals",
                "values": ["delivered"],
            }],
        )

        # 2) Monthly revenue trend for 2017 (time dimension + granularity)
        query_metrics(
            measures=["orders.total_revenue"],
            time_dimension="orders.purchase_date",
            granularity="month",
            filters=[{
                "member": "orders.purchase_date",
                "operator": "inDateRange",
                "values": ["2017-01-01", "2017-12-31"],
            }],
        )

        # 3) Top 10 product categories by revenue (cross-cube join is automatic)
        query_metrics(
            measures=["orders.total_revenue"],
            dimensions=["products.product_category_name_english"],
            limit=10,
        )

        # 4) Average order value above a numeric threshold
        #    (note values=["50"] as STRING, and operator="gt")
        query_metrics(
            measures=["orders.order_count"],
            filters=[{
                "member": "orders.avg_order_value",
                "operator": "gt",
                "values": ["50"],
            }],
        )

        # 5) Boolean OR — orders that are either delivered OR shipped
        #    (note `or` is one ELEMENT of the outer list)
        query_metrics(
            measures=["orders.order_count"],
            filters=[{
                "or": [
                    {"member": "orders.order_status",
                     "operator": "equals", "values": ["delivered"]},
                    {"member": "orders.order_status",
                     "operator": "equals", "values": ["shipped"]},
                ],
            }],
        )
    """
    cube = _get_cube(ctx)

    query: dict = {"measures": measures, "limit": limit}
    if dimensions:
        query["dimensions"] = dimensions
    if filters:
        query["filters"] = filters
    if time_dimension:
        td: dict = {"dimension": time_dimension}
        if granularity:
            td["granularity"] = granularity
        query["timeDimensions"] = [td]

    result = await cube.load(query)
    data = result.get("data", [])

    if not data:
        return f"No data returned for query:\n```json\n{json.dumps(query, indent=2)}\n```"

    headers = list(data[0].keys())
    rows = [[r.get(h, "") for h in headers] for r in data]
    table = tabulate(rows, headers=headers, tablefmt="github")
    return f"Found {len(data)} rows:\n\n{table}"
