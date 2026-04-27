#!/usr/bin/env bash
# setenv.sh — setup and run the Olist analytics stack
#
# Usage:
#   source setenv.sh          # export env vars into your current shell
#   bash setenv.sh setup      # one-time setup: install deps + init data lake + dbt deps
#   bash setenv.sh mcp        # start olist_mcp   (port 8000)
#   bash setenv.sh agent      # start olist_agent (port 8001)
#   bash setenv.sh streamlit  # start olist_streamlit (port 8501)
#   bash setenv.sh start      # start all three servers in background
#   bash setenv.sh stop       # kill all background servers started by this script

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OLIST_DBT_DIR="$SCRIPT_DIR/olist_dbt"
OLIST_MCP_DIR="$SCRIPT_DIR/olist_mcp"
OLIST_AGENT_DIR="$SCRIPT_DIR/olist_agent"
OLIST_STREAMLIT_DIR="$SCRIPT_DIR/olist_streamlit"

# ------------------------------------------------------------------
# Environment variables — edit these before running
# ------------------------------------------------------------------

export OLIST_DATA_LAKE_PATH="$SCRIPT_DIR/data_lake"  # absolute path fed to olist_mcp

export OPENAI_API_KEY="${OPENAI_API_KEY:-}"              # required by olist_agent; set in env or fill in here

# Optional overrides (defaults shown)
export MCP_SERVER_URL="http://localhost:8000/mcp"
export AGENT_URL="http://localhost:8001/ask"
export DUCKDB_LAYERS="Silver"                            # comma-separated; e.g. "Raw,Bronze,Silver,Gold"

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

_check_openai_key() {
  if [[ -z "${OPENAI_API_KEY:-}" ]]; then
    echo "ERROR: OPENAI_API_KEY is not set."
    echo "  Set it in your shell:  export OPENAI_API_KEY=sk-..."
    echo "  Or fill it in setenv.sh before running."
    exit 1
  fi
}

_venv() {
  # Print the expected venv Python path for a given repo directory.
  echo "$1/.venv/bin/python"
}

_pip() {
  "$1/.venv/bin/pip" install -q -r "$1/requirements.txt"
}

_create_venv() {
  local dir="$1"
  if [[ ! -d "$dir/.venv" ]]; then
    echo "  Creating venv in $dir/.venv ..."
    python3 -m venv "$dir/.venv"
  fi
}

# ------------------------------------------------------------------
# Setup (one-time)
# ------------------------------------------------------------------

setup() {
  echo "==> [1/4] Installing olist_dbt dependencies ..."
  _create_venv "$OLIST_DBT_DIR"
  _pip "$OLIST_DBT_DIR"

  echo "==> [2/4] Initialising data lake (unzip + CSV → Parquet) ..."
  (cd "$OLIST_DBT_DIR" && "$OLIST_DBT_DIR/.venv/bin/python" scripts/init_data_lake.py)

  echo "==> [3/4] Installing dbt packages ..."
  (cd "$OLIST_DBT_DIR" && "$OLIST_DBT_DIR/.venv/bin/dbt" deps --profiles-dir .)

  echo "==> [4/4] Installing olist_mcp, olist_agent, olist_streamlit dependencies ..."
  for repo in "$OLIST_MCP_DIR" "$OLIST_AGENT_DIR" "$OLIST_STREAMLIT_DIR"; do
    _create_venv "$repo"
    _pip "$repo"
  done

  echo ""
  echo "Setup complete."
  echo "Next: bash setenv.sh start"
}

# ------------------------------------------------------------------
# Individual server launchers
# ------------------------------------------------------------------

start_mcp() {
  echo "Starting olist_mcp on port 8000 ..."
  (
    cd "$OLIST_MCP_DIR"
    export OLIST_DATA_LAKE_PATH
    export DUCKDB_LAYERS
    "$OLIST_MCP_DIR/.venv/bin/python" -m src.server
  )
}

start_agent() {
  _check_openai_key
  echo "Starting olist_agent on port 8001 ..."
  (
    cd "$OLIST_AGENT_DIR"
    export OPENAI_API_KEY
    export MCP_SERVER_URL
    "$OLIST_AGENT_DIR/.venv/bin/python" -m src.main
  )
}

start_streamlit() {
  echo "Starting olist_streamlit on port 8501 ..."
  (
    cd "$OLIST_STREAMLIT_DIR"
    export AGENT_URL
    "$OLIST_STREAMLIT_DIR/.venv/bin/streamlit" run src/app.py --server.port 8501
  )
}

# ------------------------------------------------------------------
# Start / stop all servers
# ------------------------------------------------------------------

PIDFILE="$SCRIPT_DIR/.olist_pids"

start_all() {
  _check_openai_key
  echo "Starting all servers in background ..."
  rm -f "$PIDFILE"

  start_mcp &
  echo "$!" >> "$PIDFILE"
  echo "  olist_mcp   started (pid $!)"

  # Give the MCP server a moment before the agent tries to connect.
  sleep 2

  start_agent &
  echo "$!" >> "$PIDFILE"
  echo "  olist_agent started (pid $!)"

  sleep 1

  start_streamlit &
  echo "$!" >> "$PIDFILE"
  echo "  olist_streamlit started (pid $!)"

  echo ""
  echo "All servers running. PIDs saved to $PIDFILE"
  echo "  MCP server : http://localhost:8000/mcp"
  echo "  Agent API  : http://localhost:8001/ask"
  echo "  Chat UI    : http://localhost:8501"
  echo ""
  echo "Stop with:  bash setenv.sh stop"
}

stop_all() {
  if [[ ! -f "$PIDFILE" ]]; then
    echo "No PID file found at $PIDFILE — nothing to stop."
    return
  fi
  echo "Stopping servers ..."
  while read -r pid; do
    if kill "$pid" 2>/dev/null; then
      echo "  Killed pid $pid"
    fi
  done < "$PIDFILE"
  rm -f "$PIDFILE"
}

# ------------------------------------------------------------------
# dbt helpers
# ------------------------------------------------------------------

dbt_debug() {
  (cd "$OLIST_DBT_DIR" && "$OLIST_DBT_DIR/.venv/bin/dbt" debug --profiles-dir .)
}

dbt_run() {
  (cd "$OLIST_DBT_DIR" && "$OLIST_DBT_DIR/.venv/bin/dbt" run --profiles-dir .)
}

# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------

# When sourced (not executed), just export the env vars and return.
if [[ "${BASH_SOURCE[0]}" != "${0}" ]]; then
  echo "Env vars exported: OLIST_DATA_LAKE_PATH, MCP_SERVER_URL, AGENT_URL, DUCKDB_LAYERS"
  return 0
fi

CMD="${1:-help}"

case "$CMD" in
  setup)      setup ;;
  mcp)        start_mcp ;;
  agent)      start_agent ;;
  streamlit)  start_streamlit ;;
  start)      start_all ;;
  stop)       stop_all ;;
  dbt-debug)  dbt_debug ;;
  dbt-run)    dbt_run ;;
  help|*)
    echo "Usage: bash setenv.sh <command>"
    echo ""
    echo "Commands:"
    echo "  setup       One-time: install deps, init data lake, dbt deps"
    echo "  mcp         Start olist_mcp server (port 8000)"
    echo "  agent       Start olist_agent server (port 8001)"
    echo "  streamlit   Start olist_streamlit app (port 8501)"
    echo "  start       Start all three servers in background"
    echo "  stop        Kill all background servers"
    echo "  dbt-debug   Run dbt debug to verify connection"
    echo "  dbt-run     Run dbt models"
    echo ""
    echo "Or source it to export env vars:"
    echo "  source setenv.sh"
    ;;
esac
