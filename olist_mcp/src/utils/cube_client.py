"""
Cube REST API client for olist_mcp semantic tools.

Cube runs in CUBEJS_DEV_MODE=true so auth is disabled.
All requests are unauthenticated; no JWT generation needed.
"""
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class CubeClient:
    def __init__(self, base_url: str, api_secret: str = ""):
        self._base = base_url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=30.0)

    async def meta(self) -> dict[str, Any]:
        """Fetch full schema metadata — all cubes with measures and dimensions."""
        r = await self._client.get(f"{self._base}/cubejs-api/v1/meta")
        r.raise_for_status()
        return r.json()

    async def load(self, query: dict[str, Any]) -> dict[str, Any]:
        """Execute a Cube query and return the result set."""
        r = await self._client.post(
            f"{self._base}/cubejs-api/v1/load",
            json={"query": query},
        )
        r.raise_for_status()
        return r.json()

    async def close(self) -> None:
        await self._client.aclose()
