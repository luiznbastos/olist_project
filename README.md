# Olist Analytics

**Ask business questions in plain language. Get answers backed by a governed semantic layer over a dbt-built data lake.**

A self-contained analytics stack on the [Olist Brazilian e-commerce dataset](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce). Everything runs locally — no cloud warehouse, no orchestrator — so you can experiment with semantic-layer-driven analytics, agentic data assistants, and dbt medallion modelling end to end on your machine.

## What you get

- **A chat interface for your data** — Streamlit UI where a LangGraph agent answers business questions using a curated set of metrics and dimensions, with every tool call inspectable inline for full transparency.
- **A governed semantic layer** — Cube exposes named measures (revenue, order count, average delivery days, …) and dimensions (status, customer state, product category, …) over the silver-layer star schema. Joins, aggregations, and time grain handling are defined once in YAML and reused everywhere.
- **A medallion-style data lake** — dbt models materialise raw → bronze → silver → gold Parquet on local disk via the DuckDB adapter, mirroring real warehouse patterns without a warehouse.
- **An MCP server speaking the semantic layer** — three structured tools (`list_cubes`, `describe_cube`, `query_metrics`) any MCP-compatible client can call. The agent gets metric discovery and querying for free; you cannot write a free-form SQL query through this surface, only request known metrics — which is the whole point.

## Example questions

Try these in the chat UI (or via `curl` — see [Quick start](#quick-start)):

- *"What were our top 10 product categories by revenue in 2017?"*
- *"How many distinct customers placed an order in São Paulo state last year?"*
- *"What is our average delivery time, broken down by month?"*
- *"Which sellers have the highest average review rating, and how much did they bill?"*
- *"Show me monthly GMV split by payment method."*

Each answer is followed by a **🔧 Tool calls** expander showing exactly which measures and dimensions the agent picked, the filters it applied, and the rows Cube returned — auditable analytics by construction.

## Architecture

```
                              host                                         containers
┌──────────────────────────────────────────────────┐   ┌────────────────────────────────────────────┐
│  data_lake/olist.zip                             │   │                                            │
│           │                                      │   │   cube ──► olist_mcp ──► olist_agent ──► olist_streamlit
│           ▼  init_data_lake.py                   │   │  (4000)     (8000)        (8001)         (8501)
│   data_lake/raw/*.parquet                        │   │  semantic   tool calls    ReAct          chat UI
│           │                                      │   │  layer      over Cube     agent          + tool-call
│           ▼  dbt run                             │   │                                          inspector
│   data_lake/{bronze,silver,gold}/*.parquet ──────┼──►│  (mounted read-only at /data_lake)         │
└──────────────────────────────────────────────────┘   └────────────────────────────────────────────┘
```

| Component                            | Role                                                                                     | Port  |
| ------------------------------------ | ---------------------------------------------------------------------------------------- | ----- |
| [olist_dbt/](olist_dbt/)             | dbt + DuckDB pipeline that materialises raw → bronze → silver → gold Parquet            | —     |
| [olist_cube/](olist_cube/)           | Cube semantic layer — measures, dimensions, joins, pre-aggregations over the silver star schema | 4000  |
| [olist_mcp/](olist_mcp/)             | FastMCP server exposing semantic-layer tools (`list_cubes`, `describe_cube`, `query_metrics`)   | 8000  |
| [olist_agent/](olist_agent/)         | FastAPI + LangGraph ReAct agent that answers questions through MCP                                | 8001  |
| [olist_streamlit/](olist_streamlit/) | Chat UI with per-message tool-call inspector                                                      | 8501  |

The pipeline is split deliberately: **dbt runs on the host** (it owns the data lake), and **the four runtime services run in containers** (they read the data lake as a read-only volume). This keeps the dbt iteration loop fast (no rebuild needed) while service deployment stays reproducible.

## Quick start

### Prerequisites

- Docker Desktop (or any Docker Engine + Compose v2)
- Python 3.11+ (for dbt on the host)
- An OpenAI API key
- The Olist dataset zip at `data_lake/olist.zip` — download from [Kaggle](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce)

### 1. Configure environment

```bash
cp .env.example .env
# edit .env and set OPENAI_API_KEY=sk-...
```

`docker compose` reads `.env` automatically.

### 2. Build the data lake (one-off, host-side)

```bash
bash setenv.sh setup
```

This unzips the source data, sets up dbt, and runs the medallion pipeline. You only re-run it when the source data or dbt models change.

### 3. Start the stack

```bash
docker compose up -d --build
```

Wait ~30 seconds for Cube's healthcheck, then open:

| URL                                  | What you'll find                                |
| ------------------------------------ | ----------------------------------------------- |
| <http://localhost:8501>              | Chat UI (start here)                            |
| <http://localhost:4000>              | Cube Playground — explore measures & dimensions |
| <http://localhost:8001/docs>         | Agent OpenAPI docs                              |
| <http://localhost:8000/mcp>          | MCP server endpoint                             |

### 4. Ask a question

Through the UI, or directly:

```bash
curl -sS -X POST http://localhost:8001/ask \
  -H 'Content-Type: application/json' \
  -d '{"query": "what are the top 5 product categories by revenue?"}' \
  | jq
```

The response includes a `sources` array with every MCP tool call the agent made, in order.

### 5. Stop the stack

```bash
docker compose down
```

Add `-v` to also drop Cube's persistent pre-aggregation store. The host data lake is untouched.

## The data model

### Source dataset

Olist is a Brazilian e-commerce marketplace; the dataset spans 2016–2018:

| Source table                        | Description                                                |
| ----------------------------------- | ---------------------------------------------------------- |
| `orders`                            | Order lifecycle — status, purchase and delivery timestamps |
| `customers`                         | Customer geographic identifiers                            |
| `order_items`                       | Products purchased per order with price and freight        |
| `order_payments`                    | Payment methods and installment counts                     |
| `order_reviews`                     | Customer satisfaction scores and free-text comments        |
| `products`                          | Product catalog with dimensions and category               |
| `sellers`                           | Seller geographic data                                     |
| `geolocation`                       | Zip code → latitude/longitude lookup                       |
| `product_category_name_translation` | Portuguese → English category names                        |

### dbt medallion layers

| Layer  | Location            | Role                                          |
| ------ | ------------------- | --------------------------------------------- |
| Raw    | `data_lake/raw/`    | Views over source Parquet — no transformation |
| Bronze | `data_lake/bronze/` | Cleaned and typed staging tables              |
| Silver | `data_lake/silver/` | Star-schema facts and dimensions — **Cube reads here** |
| Gold   | `data_lake/gold/`   | Wide, denormalised analytics tables           |

### Cubes (the analyst-facing surface)

Defined in [`olist_cube/model/cubes/`](olist_cube/model/cubes/):

| Cube          | Source                              | What's exposed                                                       |
| ------------- | ----------------------------------- | -------------------------------------------------------------------- |
| `orders`      | `silver/fact_orders.parquet`        | Revenue, freight, AOV, order count, delivery days, payment type, status |
| `customers`   | `silver/dim_customers.parquet`      | Customer count, average lifetime spend, city/state                   |
| `products`    | `silver/dim_products.parquet`       | Product count, average price, average rating, category               |
| `sellers`     | `silver/dim_sellers.parquet`        | Seller count, average revenue, average rating, city/state            |
| `geolocation` | `silver/dim_geolocation.parquet`    | Zip-code centroids                                                   |
| `dates`       | `silver/dim_date.parquet`           | Calendar — year, quarter, month, week, day name, weekend flag        |

Joins between cubes (e.g. `orders` ↔ `customers`) are declared once in YAML; users never write them.

## Extending the model (for analytics engineers)

### Add a new measure or dimension

1. Edit the relevant YAML under [`olist_cube/model/cubes/`](olist_cube/model/cubes/), e.g. add a measure to `fact_orders.yml`.
2. Reload Cube:

   ```bash
   docker compose restart cube
   ```

3. The new field is immediately discoverable through `list_cubes` / `describe_cube`. Restart the agent so it picks up the refreshed schema description on its next conversation:

   ```bash
   docker compose restart olist_agent
   ```

### Add a new dbt model

1. Add a SQL file under `olist_dbt/models/{bronze_layer,silver_layer,gold_layer}/`.
2. Rebuild the Parquet:

   ```bash
   bash setenv.sh dbt-run
   ```

3. If you exposed it through Cube too, add a YAML cube and restart Cube as above.

### Iterate on agent behaviour

The agent's system prompt lives in [`olist_agent/src/services/agent_service.py`](olist_agent/src/services/agent_service.py); MCP tool docstrings live in [`olist_mcp/src/tools/cube.py`](olist_mcp/src/tools/cube.py). Both feed into how the LLM frames queries — adjust them when you want to tighten or relax behaviour. After editing either:

```bash
docker compose up -d --build olist_mcp olist_agent
```

## Configuration

All variables flow through [docker-compose.yml](docker-compose.yml). The user-facing knobs:

| Variable             | Default                  | Used by                                                          |
| -------------------- | ------------------------ | ---------------------------------------------------------------- |
| `OPENAI_API_KEY`     | *(required)*             | `olist_agent` — LLM provider                                     |
| `OPENAI_MODEL`       | `gpt-4o-mini`            | `olist_agent` — LangChain `ChatOpenAI` model                     |
| `CUBEJS_API_SECRET`  | `dev-secret`             | `cube`, `olist_mcp` — JWT secret (auth disabled in dev mode)     |
| `DUCKDB_LAYERS`      | `Silver`                 | `olist_mcp` — which `data_lake/` layers to register as DuckDB views |

Service-internal URLs (`MCP_SERVER_URL`, `CUBE_API_URL`, `AGENT_URL`) resolve over the `olist_net` Docker network and don't need to be set by hand.

For local development outside Docker, each service supports a per-folder `.env` via `pydantic-settings`.

## Project structure

```
olist_project/
├── docker-compose.yml             # all four runtime services
├── setenv.sh                      # host-side: data lake + dbt helpers
├── .env.example                   # OPENAI_API_KEY, CUBEJS_API_SECRET, …
│
├── data_lake/                     # NOT versioned — produced by setenv.sh
│   ├── olist.zip                  # source dataset (download from Kaggle)
│   └── {raw,bronze,silver,gold}/  # Parquet outputs of the medallion pipeline
│
├── olist_dbt/                     # dbt project (host-only)
│   ├── dbt_project.yml
│   ├── profiles.yml               # DuckDB adapter, external_root → ../data_lake
│   ├── packages.yml               # dbt-utils
│   ├── macros/external_location.sql
│   ├── models/{raw,bronze_layer,silver_layer,gold_layer}/
│   └── scripts/init_data_lake.py
│
├── olist_cube/                    # Cube semantic layer
│   ├── cube.yml
│   └── model/cubes/               # one YAML per cube
│
├── olist_mcp/                     # FastMCP server
│   └── src/
│       ├── server.py
│       ├── tools/cube.py          # list_cubes / describe_cube / query_metrics
│       └── utils/{cube_client.py, duckdb_client.py, logger.py}
│
├── olist_agent/                   # FastAPI + LangGraph
│   └── src/
│       ├── main.py                # connects to MCP, builds ReAct agent
│       ├── api/endpoints/ask.py   # POST /ask
│       └── services/agent_service.py
│
└── olist_streamlit/               # Chat UI
    └── src/app.py
```

## Development workflow

| You changed…                       | What to run                                                              |
| ---------------------------------- | ------------------------------------------------------------------------ |
| A dbt model                        | `bash setenv.sh dbt-run` then `docker compose restart cube`              |
| A Cube YAML                        | `docker compose restart cube olist_agent`                                |
| MCP tool code or system prompt     | `docker compose up -d --build olist_mcp olist_agent`                     |
| Streamlit UI                       | `docker compose up -d --build olist_streamlit`                           |

Tail logs of any single service:

```bash
docker compose logs -f olist_mcp
```

### `setenv.sh` reference

`setenv.sh` is intentionally minimal — service lifecycle belongs to Docker Compose. It only handles host-side tasks that write to `data_lake/`:

| Command                    | What it does                                              |
| -------------------------- | --------------------------------------------------------- |
| `bash setenv.sh setup`     | One-shot: venv + init data lake + `dbt deps` + `dbt run`  |
| `bash setenv.sh init`      | Unzip `olist.zip` into `data_lake/raw/*.parquet`          |
| `bash setenv.sh dbt-deps`  | Install dbt packages                                      |
| `bash setenv.sh dbt-debug` | Verify dbt's DuckDB connection                            |
| `bash setenv.sh dbt-run`   | Build bronze/silver/gold from raw                         |
