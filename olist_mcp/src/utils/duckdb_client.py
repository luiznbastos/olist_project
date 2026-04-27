"""
DuckDB-backed read-only client for the Olist MCP server.

Discovers available tables by globbing local Parquet files in data_lake/{layer}/
at init time and registers DuckDB views for each file found.

Local path layout produced by olist_dbt:
  Raw:    data_lake/raw/<table>.parquet
  Bronze: data_lake/bronze/<model>.parquet
  Silver: data_lake/silver/<model>.parquet
  Gold:   data_lake/gold/<model>.parquet
"""

import glob
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import duckdb

logger = logging.getLogger(__name__)

_LAYER_DIRS = {
    "Raw": "raw",
    "Bronze": "bronze",
    "Silver": "silver",
    "Gold": "gold",
}


class DuckDBClient:
    """
    Read-only DuckDB client that queries local Parquet files produced by olist_dbt.

    At init time, discovers all Parquet files in data_lake/ and registers DuckDB views.
    New dbt models are picked up on the next server restart.

    Exposes:
      - query(sql) -> List[Dict[str, Any]]
      - close()
      - table_layers: Dict[str, str]  — maps table name → layer label
    """

    def __init__(
        self,
        data_lake_path: str = "data_lake",
        layers: Optional[List[str]] = None,
    ):
        self.data_lake_path = Path(data_lake_path).resolve()
        self._layers: Set[str] = set(layers) if layers is not None else {"Silver"}
        self.table_layers: Dict[str, str] = {}
        self._con = duckdb.connect()
        self._discover_and_register_views()

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def _discover_and_register_views(self) -> None:
        logger.info(
            "Registering views for layers: %s from %s",
            sorted(self._layers),
            self.data_lake_path,
        )
        for label, subdir in _LAYER_DIRS.items():
            if label not in self._layers:
                continue
            layer_dir = self.data_lake_path / subdir
            pattern = str(layer_dir / "*.parquet")
            files = sorted(glob.glob(pattern))
            if not files:
                logger.info("No Parquet files found in %s — skipping %s layer", layer_dir, label)
                continue
            for path in files:
                table = Path(path).stem
                self._con.execute(
                    f"CREATE OR REPLACE VIEW {table} AS SELECT * FROM read_parquet('{path}')"
                )
                self.table_layers[table] = label
                logger.debug("Registered %s view %s → %s", label, table, path)

        logger.info(
            "Registered %d views: %s",
            len(self.table_layers),
            sorted(self.table_layers.keys()),
        )

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def query(self, sql_query: str) -> List[Dict[str, Any]]:
        """Execute a SQL query and return results as a list of dicts."""
        try:
            result = self._con.execute(sql_query)
            columns = [desc[0] for desc in result.description]
            return [dict(zip(columns, row)) for row in result.fetchall()]
        except Exception as e:
            if "No files found" in str(e) or "Cannot open file" in str(e):
                logger.info("No Parquet files found, returning empty result. Query: %r", sql_query)
                return []
            logger.error("Query failed: %s", e)
            raise

    def close(self) -> None:
        self._con.close()
        logger.info("DuckDB connection closed")
