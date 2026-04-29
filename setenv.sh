#!/usr/bin/env bash
# setenv.sh — host-side data preparation for the Olist analytics stack.
#
# The runtime services (cube, olist_mcp, olist_agent, olist_streamlit) are
# managed by Docker Compose. This script only covers tasks that must run on
# the host because they write to data_lake/ (the containers mount it read-only):
#
#   - unzipping olist.zip into data_lake/raw/*.parquet
#   - running dbt to build data_lake/{bronze,silver,gold}/*.parquet
#
# Usage:
#   bash setenv.sh setup       One-shot: venv + init data lake + dbt deps + dbt run
#   bash setenv.sh init        Unzip data_lake/olist.zip → data_lake/raw/*.parquet
#   bash setenv.sh dbt-deps    Install dbt packages
#   bash setenv.sh dbt-debug   Verify dbt's DuckDB connection
#   bash setenv.sh dbt-run     Build bronze/silver/gold Parquet from raw
#
# Service lifecycle is managed by Docker Compose:
#   docker compose up -d --build      # start the stack
#   docker compose down               # stop and remove containers
#   docker compose logs -f olist_mcp  # tail logs of one service

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DBT_DIR="$SCRIPT_DIR/olist_dbt"
DBT_VENV="$DBT_DIR/.venv"
DBT_BIN="$DBT_VENV/bin"

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

_ensure_dbt_venv() {
  if [[ ! -d "$DBT_VENV" ]]; then
    echo "Creating dbt venv at $DBT_VENV ..."
    python3 -m venv "$DBT_VENV"
    "$DBT_BIN/pip" install -q -r "$DBT_DIR/requirements.txt"
  fi
}

_dbt() {
  (cd "$DBT_DIR" && "$DBT_BIN/dbt" "$@" --profiles-dir .)
}

# ------------------------------------------------------------------
# Commands
# ------------------------------------------------------------------

init_data_lake() {
  _ensure_dbt_venv
  echo "==> Initialising data lake (unzip olist.zip → data_lake/raw) ..."
  (cd "$DBT_DIR" && "$DBT_BIN/python" scripts/init_data_lake.py)
}

dbt_deps() {
  _ensure_dbt_venv
  _dbt deps
}

dbt_debug() {
  _ensure_dbt_venv
  _dbt debug
}

dbt_run() {
  _ensure_dbt_venv
  _dbt run
}

setup() {
  init_data_lake
  dbt_deps
  dbt_run
  echo ""
  echo "Data lake ready. Start the stack with:"
  echo "  docker compose up -d --build"
}

usage() {
  cat <<'EOF'
Usage: bash setenv.sh <command>

Host-side commands (write to data_lake/):
  setup       One-shot: venv + init data lake + dbt deps + dbt run
  init        Unzip olist.zip into data_lake/raw/*.parquet
  dbt-deps    Install dbt packages
  dbt-debug   Verify dbt's DuckDB connection
  dbt-run     Build bronze/silver/gold Parquet from raw

Runtime services are managed by Docker Compose:
  docker compose up -d --build
  docker compose down
  docker compose logs -f <service>
EOF
}

# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------

CMD="${1:-help}"

case "$CMD" in
  setup)      setup ;;
  init)       init_data_lake ;;
  dbt-deps)   dbt_deps ;;
  dbt-debug)  dbt_debug ;;
  dbt-run)    dbt_run ;;
  help|-h|--help|*) usage ;;
esac
