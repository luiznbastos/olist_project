# Olist Analytics Agent — Architecture & Analytics Engineering Guide

> Baseline document for understanding how the agent works, how to shape its behaviour,
> and how we plan to measure its quality.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [How It Works — Engineering Concepts](#2-how-it-works--engineering-concepts)
   - [The Data Foundation](#21-the-data-foundation-dbt-medallion-pipeline)
   - [The Semantic Layer](#22-the-semantic-layer-cube)
   - [The MCP Server](#23-the-mcp-server-connecting-language-to-data)
   - [The Agent and the Agentic Loop](#24-the-agent-and-the-agentic-loop)
3. [What You Can Influence — The Analytics Engineer's Levers](#3-what-you-can-influence--the-analytics-engineers-levers)
   - [Lever 1: Cube YAML — What Questions Can Be Answered](#31-lever-1-cube-yaml--what-questions-can-be-answered)
   - [Lever 2: Tool Docstrings — How the Agent Reads the Menu](#32-lever-2-tool-docstrings--how-the-agent-reads-the-menu)
   - [Lever 3: System Prompt — Rules of Engagement](#33-lever-3-system-prompt--rules-of-engagement)
   - [Tracing a Question End to End](#34-tracing-a-question-end-to-end)
4. [Benchmarking the Agent](#4-benchmarking-the-agent)
   - [Why Benchmarking Matters](#41-why-benchmarking-matters)
   - [Query Complexity Levels](#42-query-complexity-levels)
   - [Proposed Benchmark Queries](#43-proposed-benchmark-queries)
   - [What to Measure](#44-what-to-measure)

---

## 1. Project Overview

This project answers business questions about the [Olist Brazilian e-commerce dataset (2016–2018)](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) using natural language.

A user types a question like *"What were the top 10 product categories by revenue in 2017?"* into a chat interface and gets a structured, auditable answer — with every data access step visible.

The stack that makes this possible:

```
User → Streamlit UI → Agent API → MCP Server → Cube → dbt-built Parquet files
```

| Layer | Technology | Role |
|---|---|---|
| Data lake | dbt + DuckDB + Parquet | Builds raw → bronze → silver → gold tables |
| Semantic layer | Cube | Defines named metrics and dimensions |
| Tool server | FastMCP (Python) | Exposes the semantic layer as callable tools |
| Agent | FastAPI + Claude / OpenAI | Reasons over tools to answer questions |
| UI | Streamlit | Chat interface with tool-call inspector |

---

## 2. How It Works — Engineering Concepts

### 2.1 The Data Foundation: dbt Medallion Pipeline

Before any question can be answered, the raw Olist CSV data is transformed into a structured, analysis-ready format using **dbt** (data build tool). The transformation follows a medallion pattern with four layers:

| Layer | What it contains |
|---|---|
| **Raw** | Views over source Parquet — no transformation |
| **Bronze** | Cleaned and typed staging tables |
| **Silver** | Star-schema facts and dimensions — this is where Cube reads |
| **Gold** | Wide, denormalised analytics tables for ad-hoc use |

The silver layer is the critical one: it contains a `fact_orders` table joined to dimension tables (`dim_customers`, `dim_products`, `dim_sellers`, etc.). This star schema is what allows Cube to resolve joins automatically when the agent queries across entities.

> **Key idea:** dbt runs on the host machine and writes Parquet files to disk. All runtime services (Cube, MCP, Agent) mount those files read-only. Changing a dbt model means rebuilding the Parquet — it does not require touching any of the runtime services.

### 2.2 The Semantic Layer: Cube

**Cube** sits on top of the silver Parquet files and exposes a governed vocabulary of business metrics. Instead of raw tables and SQL columns, Cube speaks in **measures** and **dimensions** defined once in YAML.

A measure is a numeric aggregation with a business name:

```yaml
- name: total_revenue
  type: sum
  sql: price
  description: "Total revenue — sum of item prices (GMV)"
```

A dimension is an attribute you can group or filter by:

```yaml
- name: order_status
  sql: order_status
  type: string
  description: "delivered, shipped, processing, canceled, ..."
```

Cube also **resolves joins automatically**. If you ask for `orders.total_revenue` grouped by `products.product_category_name_english`, Cube knows the join path and handles it — you never write a `JOIN` clause.

> **Key idea:** Cube is the gatekeeper of "what can be measured." Anything not defined in a Cube YAML cannot be queried. This is a feature: it prevents the agent from making up SQL and producing wrong numbers.

### 2.3 The MCP Server: Connecting Language to Data

**MCP (Model Context Protocol)** is a standard that lets LLMs call external tools in a structured, safe way. Think of it as a well-defined API contract between an AI model and a data system.

The MCP server in this project (`olist_mcp`) exposes exactly **three tools**:

| Tool | What it does |
|---|---|
| `list_cubes` | Returns all available cubes with their measures and dimensions |
| `describe_cube` | Returns full details (field names, types, descriptions) for one cube |
| `query_metrics` | Executes a query against the Cube semantic layer |

These three tools are all the agent ever needs. It cannot write SQL, it cannot access raw tables, and it cannot query anything outside the Cube model. The tool interface is the boundary of the system.

> **Key idea:** MCP acts as a translation layer. The agent speaks "natural language → tool calls," the MCP server speaks "tool calls → Cube API calls," and Cube speaks "Cube API → SQL over Parquet." Each layer only knows its own interface.

### 2.4 The Agent and the Agentic Loop

An **agent** is an LLM that, instead of generating a single response, can decide to call tools, observe the results, and continue reasoning until it has enough information to answer.

This is fundamentally different from a plain chatbot. A chatbot generates an answer from its training knowledge. An agent *queries real data* and builds its answer from what it finds.

The reasoning pattern this agent follows is called **ReAct** (Reason + Act):

```
┌──────────────────────────────────────────────────────────┐
│                     AGENTIC LOOP                         │
│                                                          │
│  User question                                           │
│       │                                                  │
│       ▼                                                  │
│  [THINK]  What do I know? What do I need?                │
│       │                                                  │
│       ▼                                                  │
│  [ACT]    Call list_cubes → see what's available         │
│       │                                                  │
│       ▼                                                  │
│  [OBSERVE] Here are 6 cubes: orders, customers, ...      │
│       │                                                  │
│       ▼                                                  │
│  [THINK]  I need the "orders" cube. Let me inspect it.   │
│       │                                                  │
│       ▼                                                  │
│  [ACT]    Call describe_cube("orders")                   │
│       │                                                  │
│       ▼                                                  │
│  [OBSERVE] Measures: total_revenue, order_count, ...     │
│       │                                                  │
│       ▼                                                  │
│  [THINK]  I have the exact names. Now I can query.       │
│       │                                                  │
│       ▼                                                  │
│  [ACT]    Call query_metrics(measures=[...], ...)        │
│       │                                                  │
│       ▼                                                  │
│  [OBSERVE] Found 12 rows: ...                            │
│       │                                                  │
│       ▼                                                  │
│  [ANSWER]  Formulate and return the final response       │
└──────────────────────────────────────────────────────────┘
```

The agent always follows the same mandatory workflow: **discover → inspect → query**. This is enforced via the system prompt and means every answer is backed by confirmed field names, not guesses.

> **Key idea:** The agent does not have prior knowledge of the Olist schema. It learns the schema fresh at the start of each question by calling `list_cubes` and `describe_cube`. This makes it robust to schema changes — update the Cube YAML and the agent adapts automatically on the next query.

---

## 3. What You Can Influence — The Analytics Engineer's Levers

The quality of the agent's answers depends heavily on three things you control directly as an analytics engineer. None of them require changing application code.

### 3.1 Lever 1: Cube YAML — What Questions Can Be Answered

The Cube YAML files under `olist_cube/model/cubes/` define the **universe of answerable questions**. If a metric or dimension is not defined here, the agent cannot answer questions that require it.

**To add a new measure** (e.g., cancellation rate):

```yaml
# In olist_cube/model/cubes/fact_orders.yml
- name: cancellation_rate
  type: number
  sql: "COUNT(CASE WHEN order_status = 'canceled' THEN 1 END) * 1.0 / COUNT(*)"
  description: "Fraction of orders that were canceled (0.0 – 1.0)"
```

**To add a new dimension** (e.g., whether the delivery was late):

```yaml
- name: is_late_delivery
  sql: "CASE WHEN order_delivered_customer_date > order_estimated_delivery_date THEN 'late' ELSE 'on_time' END"
  type: string
  description: "Whether the order was delivered after the estimated date: late or on_time"
```

After editing a YAML, restart Cube and the agent:

```bash
docker compose restart cube olist_agent
```

The agent will discover the new field on its next `list_cubes` call — no code changes needed.

**What makes a good measure or dimension description?**

The description field is read directly by the LLM during `describe_cube`. A good description:
- States the **unit** (e.g., "in days", "in BRL")
- Lists **valid values** for categorical dimensions (e.g., `"delivered, shipped, canceled, ..."`)
- Clarifies **deduplication logic** for counts (e.g., "distinct orders, deduplicates multi-item orders")

Vague descriptions lead to wrong tool calls. Precise descriptions lead to correct ones.

### 3.2 Lever 2: Tool Docstrings — How the Agent Reads the Menu

The three MCP tools live in `olist_mcp/src/tools/cube.py`. Their **docstrings are part of what the agent reads** when it decides how to call them. Docstrings serve two functions:

1. **Signature documentation** — what arguments exist, what format they must follow
2. **Anti-pattern warnings** — explicit examples of what *not* to do

The `query_metrics` docstring is particularly important because the Cube filter format is non-obvious (no SQL operators, string-valued arrays, specific dict shape). Every anti-pattern listed in the docstring was added because the agent made that exact mistake at some point.

**Example: if the agent keeps using wrong filter operators**, add a clarifying example to the docstring:

```python
# Add to the "Examples (correct)" section of query_metrics docstring:
# 6) Orders placed in Q1 2018
query_metrics(
    measures=["orders.order_count"],
    time_dimension="orders.purchase_date",
    granularity="month",
    filters=[{
        "member": "orders.purchase_date",
        "operator": "inDateRange",
        "values": ["2018-01-01", "2018-03-31"],
    }],
)
```

After editing tool docstrings:

```bash
docker compose up -d --build olist_mcp olist_agent
```

### 3.3 Lever 3: System Prompt — Rules of Engagement

The system prompt in `olist_agent/src/services/agent_service.py` (and its Claude equivalent in `agent_service_claude.py`) defines **how the agent reasons**, not what data it can access. It sets:

- The mandatory three-step workflow (discover → inspect → query)
- Hard constraints (never invent field names, never use SQL operators, filter values must be strings)
- Scope limits (only answer Olist e-commerce questions)

The system prompt is the place to add **behavioral rules** that apply regardless of the specific question. For example:
- "Always round monetary values to 2 decimal places in your answer"
- "When a question is ambiguous between order count and revenue, ask for clarification"
- "If the result set has more than 20 rows, summarize the top 5 and note the total"

After editing the system prompt:

```bash
docker compose up -d --build olist_agent
```

### 3.4 Tracing a Question End to End

Here is what happens when a user asks: *"Which product categories had above-average revenue in São Paulo in 2017?"*

| Step | What happens | Where it happens |
|---|---|---|
| 1 | User types the question in the chat UI | Streamlit |
| 2 | UI sends `POST /ask {"query": "..."}` | Agent API |
| 3 | Agent receives the question and starts its loop | Agent (LLM) |
| 4 | Agent calls `list_cubes` to discover available cubes | MCP → Cube |
| 5 | Agent calls `describe_cube("orders")` and `describe_cube("products")` and `describe_cube("customers")` to confirm field names | MCP → Cube |
| 6 | Agent calls `query_metrics` with `total_revenue` grouped by `product_category_name_english`, filtered by `customers.customer_state = ["SP"]` and `purchase_date inDateRange ["2017-01-01", "2017-12-31"]` | MCP → Cube |
| 7 | Cube resolves the cross-cube join and returns rows | Cube → MCP |
| 8 | Agent receives the table and computes/describes the above-average categories | Agent (LLM) |
| 9 | Agent returns a formatted answer with sources | Agent API |
| 10 | UI renders the answer and an expandable tool-call inspector | Streamlit |

Steps 4–8 may repeat if the agent decides it needs more information. The agent can also correct itself — for example, if a field name it assumed turns out not to exist, it will fall back to `describe_cube` to confirm the real name.

---

## 4. Benchmarking the Agent

### 4.1 Why Benchmarking Matters

The agent's answer quality is a function of the LLM, the system prompt, the tool docstrings, and the Cube schema. When you change any of these, you need a way to know whether things got better or worse.

Without a benchmark, you can only test by asking questions ad hoc and judging by intuition. With a benchmark, you can:
- Compare two LLMs on the same question set (e.g., `gpt-4o-mini` vs. `claude-sonnet-4-6`)
- Measure the impact of a system prompt change
- Catch regressions when Cube schema changes break previously working queries
- Track quality over time as the project evolves

### 4.2 Query Complexity Levels

Questions can be classified into four levels based on how many cubes, filters, and reasoning steps they require:

| Level | Description | Typical tool calls |
|---|---|---|
| **L1 — Simple** | Single measure, no filter, no join | 1× list_cubes, 1× describe_cube, 1× query_metrics |
| **L2 — Filtered** | Single cube with one or more filters (date range, status, category) | 1× list_cubes, 1× describe_cube, 1× query_metrics |
| **L3 — Multi-cube** | Requires joining two or more cubes (e.g., orders + customers + products) | 1× list_cubes, 2–3× describe_cube, 1× query_metrics |
| **L4 — Reasoning** | Requires computing derived values, multi-step logic, or interpreting the result set (e.g., "above average", "growth rate", "rank") | 1× list_cubes, 2–3× describe_cube, 1–2× query_metrics + LLM post-processing |

### 4.3 Proposed Benchmark Queries

**L1 — Simple**

| # | Question | Expected measures | Expected dimensions |
|---|---|---|---|
| L1-01 | How many orders are in the dataset? | `orders.order_count` | — |
| L1-02 | What is the total GMV? | `orders.total_revenue` | — |
| L1-03 | What is the average delivery time in days? | `orders.avg_delivery_days` | — |
| L1-04 | How many unique customers are there? | `customers.customer_count` | — |
| L1-05 | How many products are listed in the catalog? | `products.product_count` | — |

**L2 — Filtered**

| # | Question | Key filters |
|---|---|---|
| L2-01 | How many orders were delivered in 2017? | `order_status = delivered`, `purchase_date inDateRange 2017` |
| L2-02 | What is the total revenue from credit card payments? | `primary_payment_type = credit_card` |
| L2-03 | What is the average order value for orders over R$200? | `avg_order_value > 200` |
| L2-04 | How many orders were placed in São Paulo state? | `customers.customer_state = SP` |
| L2-05 | Show monthly order count for 2018. | `purchase_date granularity=month, year=2018` |

**L3 — Multi-cube**

| # | Question | Cubes involved |
|---|---|---|
| L3-01 | What are the top 10 product categories by revenue? | orders + products |
| L3-02 | Which states have the highest number of distinct customers who placed at least one order? | orders + customers |
| L3-03 | What is the average revenue per seller, broken down by seller state? | orders + sellers |
| L3-04 | Show monthly revenue trend for 2017 by product category. | orders + products + time |
| L3-05 | How does average delivery time vary across customer states? | orders + customers |

**L4 — Reasoning**

| # | Question | Why it requires reasoning |
|---|---|---|
| L4-01 | Which product categories had above-average revenue in 2017? | Must compute the average and filter the result set |
| L4-02 | What is the year-over-year revenue growth between 2017 and 2018? | Must run two queries and compute the ratio |
| L4-03 | Which sellers are in the top 10% by revenue but have below-average delivery times? | Multi-query; requires percentile reasoning |
| L4-04 | What percentage of orders were delivered on time vs. late, by product category? | Requires the `is_late_delivery` derived dimension and ratio computation |
| L4-05 | Which month in 2017 had the biggest revenue spike, and what drove it? | Multi-query exploration; requires narrative synthesis |

### 4.4 What to Measure

For each benchmark query, the following signals should be captured:

**Correctness**

- Does the final answer contain the correct numbers? (validate against a known ground truth computed directly from the silver Parquet)
- Did the agent use the right measures and dimensions?
- Were the filters applied correctly?

**Efficiency**

- How many tool calls did the agent make? (lower is better for well-defined questions)
- Did the agent make any unnecessary `describe_cube` calls for cubes it did not end up using?
- Did the agent ever call `query_metrics` with an invalid field name and have to retry?

**Robustness**

- Did the agent handle questions outside the semantic layer gracefully (say "I cannot answer this" rather than hallucinate)?
- Did it correctly reject questions unrelated to Olist e-commerce?

**Model comparison**

Run the same benchmark set against each agent configuration and record:

| Metric | gpt-4o-mini | claude-sonnet-4-6 | claude-sonnet-4-6 + thinking |
|---|---|---|---|
| L1 accuracy | | | |
| L2 accuracy | | | |
| L3 accuracy | | | |
| L4 accuracy | | | |
| Avg tool calls per question | | | |
| Retry rate (bad field names) | | | |
| Avg latency (seconds) | | | |

The goal is not to find a single "winner" but to understand the quality-cost-latency tradeoffs across configurations, so we can recommend the right model for the right use case.
