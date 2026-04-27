# olist_cube

Semantic layer for the Olist analytics project, to be implemented with [Cube](https://cube.dev).

Cube will sit between the data lake (built by `olist_dbt`) and downstream consumers, providing:
- A unified semantic model (metrics, dimensions, joins) on top of the gold/silver Parquet tables
- A consistent query API (REST, GraphQL, SQL) so the agent and dashboards share the same business logic
- Caching and pre-aggregations to keep query latency low

> Implementation is pending.
