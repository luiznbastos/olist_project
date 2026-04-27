# Olist Analytics

A local analytics stack built on the [Olist Brazilian e-commerce dataset](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce). Mirrors the architecture of the WS Analytics pipeline but runs entirely on your machine — no AWS, no Redshift, no cloud required.

## Architecture

```
olist_dbt  ──►  olist_cube  ──►  olist_mcp  ──►  olist_agent  ──►  olist_streamlit
(transform)   (semantic layer)  (data access)   (ReAct agent)      (chat UI)
```


| Repo                                 | Purpose                                                                     | Port |
| ------------------------------------ | --------------------------------------------------------------------------- | ---- |
| [olist_dbt/](olist_dbt/)             | dbt + DuckDB transforms raw Parquet through bronze → silver → gold          | —    |
| [olist_cube/](olist_cube/)           | Cube semantic layer — metrics, dimensions, and pre-aggregations *(pending)* | —    |
| [olist_mcp/](olist_mcp/)             | FastMCP server exposing SQL tools over the local data lake                  | 8000 |
| [olist_agent/](olist_agent/)         | FastAPI + LangGraph ReAct agent wired to the MCP server                     | 8001 |
| [olist_streamlit/](olist_streamlit/) | Single-page chat UI that talks to the agent                                 | 8501 |


### Data flow

```
olist.zip
    │
    ▼  (init_data_lake.py)
data_lake/raw/*.parquet          ← 9 source tables as Parquet
    │
    ▼  (dbt run)
data_lake/bronze/*.parquet
data_lake/silver/*.parquet
data_lake/gold/*.parquet
    │
    ▼  (DuckDB views, registered at startup)
olist_mcp  :8000
    │
    ▼  (MCP tools: query_database, list_tables, describe_table, get_dataset_summary)
olist_agent  :8001  POST /ask
    │
    ▼  (HTTP)
olist_streamlit  :8501
```

## Dataset

The Olist dataset covers a Brazilian e-commerce marketplace from 2016 to 2018 and contains nine tables:


| Table                               | Description                                                |
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


## Prerequisites

- Python 3.11+
- An OpenAI API key (used by `olist_agent`)

## Quick start

### 1. Set your OpenAI key

```bash
export OPENAI_API_KEY=sk-...
```

Or open [setenv.sh](setenv.sh) and fill in the `OPENAI_API_KEY` line near the top.

### 2. One-time setup

Run from the `olist_project/` directory:

```bash
bash setenv.sh setup
```

This will:

1. Create a `.venv` in each repo and install its dependencies
2. Unzip `olist.zip` and convert the 9 CSVs to Parquet under `olist_dbt/data_lake/raw/`
3. Install dbt packages (`dbt deps`)

### 3. Build the dbt models

Once models are implemented, run:

```bash
bash setenv.sh dbt-run
```

To verify the dbt connection first:

```bash
bash setenv.sh dbt-debug
```

### 4. Start the servers

```bash
bash setenv.sh start
```

This starts all three servers in the background and prints their URLs:

```
MCP server : http://localhost:8000/mcp
Agent API  : http://localhost:8001/ask
Chat UI    : http://localhost:8501
```

Open `http://localhost:8501` in your browser to start chatting.

### 5. Stop the servers

```bash
bash setenv.sh stop
```

## Running servers individually

Each server can be started in the foreground for development:

```bash
bash setenv.sh mcp        # olist_mcp   — port 8000
bash setenv.sh agent      # olist_agent — port 8001
bash setenv.sh streamlit  # olist_streamlit — port 8501
```

## Configuration

All configuration lives in [setenv.sh](setenv.sh). The key variables:


| Variable               | Default                     | Description                                                                 |
| ---------------------- | --------------------------- | --------------------------------------------------------------------------- |
| `OPENAI_API_KEY`       | *(required)*                | API key for the LLM used by olist_agent                                     |
| `OLIST_DATA_LAKE_PATH` | `olist_dbt/data_lake`       | Absolute path to the data lake root                                         |
| `MCP_SERVER_URL`       | `http://localhost:8000/mcp` | URL the agent uses to reach the MCP server                                  |
| `AGENT_URL`            | `http://localhost:8001/ask` | URL Streamlit uses to reach the agent                                       |
| `DUCKDB_LAYERS`        | `Silver`                    | Comma-separated layers exposed by the MCP server (`Raw,Bronze,Silver,Gold`) |


Each repo also accepts a `.env` file. Copy [olist_agent/.env.example](olist_agent/.env.example) to `olist_agent/.env` to configure the agent independently of `setenv.sh`.

## Project structure

```
olist_project/
├── olist.zip                       # source dataset
├── setenv.sh                       # setup + server launcher
│
├── olist_dbt/                      # dbt project
│   ├── dbt_project.yml
│   ├── profiles.yml                # DuckDB adapter, external_root = data_lake/
│   ├── packages.yml                # dbt-utils
│   ├── macros/
│   │   └── external_location.sql  # routes external tables to data_lake/{layer}/
│   ├── models/
│   │   ├── raw/                    # views over data_lake/raw/*.parquet
│   │   ├── bronze_layer/           # external Parquet → data_lake/bronze/
│   │   ├── silver_layer/           # external Parquet → data_lake/silver/
│   │   └── gold_layer/             # external Parquet → data_lake/gold/
│   ├── scripts/
│   │   └── init_data_lake.py      # unzip + CSV → Parquet
│   └── data_lake/                  # created by init_data_lake.py + dbt run
│       ├── raw/
│       ├── bronze/
│       ├── silver/
│       └── gold/
│
├── olist_cube/                     # Cube semantic layer (pending)
│   └── README.md
│
├── olist_mcp/                      # FastMCP server
│   └── src/
│       ├── server.py
│       ├── config.py               # data_lake_path, duckdb_layers
│       ├── tools/database.py       # query_database, list_tables, describe_table, get_dataset_summary
│       └── utils/duckdb_client.py  # discovers + registers DuckDB views from local Parquet
│
├── olist_agent/                    # FastAPI + LangGraph agent
│   └── src/
│       ├── main.py                 # FastAPI app, connects to olist_mcp at startup
│       ├── config.py
│       ├── models.py               # QueryRequest / QueryResponse
│       ├── api/endpoints/ask.py    # POST /ask
│       └── services/agent_service.py  # ReAct agent + system prompt
│
└── olist_streamlit/                # Chat UI
    └── src/
        └── app.py                  # single-page Streamlit chat interface
```

## MCP tools

The MCP server exposes four tools to the agent:


| Tool                  | Description                                          |
| --------------------- | ---------------------------------------------------- |
| `list_tables`         | List all registered tables with their pipeline layer |
| `describe_table`      | Column names, types, and nullability for a table     |
| `query_database`      | Execute a read-only SQL query (auto-LIMIT applied)   |
| `get_dataset_summary` | Row counts for all registered tables                 |


By default only the Silver layer is exposed. To open all layers, set `DUCKDB_LAYERS=Raw,Bronze,Silver,Gold` before starting the MCP server.

## dbt medallion layers


| Layer  | Schema   | Location            | Purpose                                       |
| ------ | -------- | ------------------- | --------------------------------------------- |
| Raw    | `raw`    | `data_lake/raw/`    | Views over source Parquet — no transformation |
| Bronze | `bronze` | `data_lake/bronze/` | Cleaned and typed staging tables              |
| Silver | `silver` | `data_lake/silver/` | Star schema facts and dimensions              |
| Gold   | `gold`   | `data_lake/gold/`   | Wide, denormalised analytics tables           |


