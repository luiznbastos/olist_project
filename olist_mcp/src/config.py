from pathlib import Path
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

env_file_path = Path(__file__).parent.parent / ".env"
if not env_file_path.exists():
    env_file_path = Path(".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(env_file_path),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # General
    log_level: str = Field(default="INFO")                      # LOG_LEVEL

    # DuckDB / data lake
    data_lake_path: str = Field(default="data_lake")            # DATA_LAKE_PATH
    duckdb_layers: str = Field(default="Silver")                # DUCKDB_LAYERS — comma-sep: "Silver,Bronze"

    # MCP server
    mcp_host: str = Field(default="0.0.0.0")                   # MCP_HOST
    mcp_port: int = Field(default=8000)                         # MCP_PORT

    # Cube semantic layer
    cube_api_url: str = Field(default="http://cube:4000")       # CUBE_API_URL
    cube_api_secret: str = Field(default="")                    # CUBE_API_SECRET

    @property
    def duckdb_layers_list(self) -> List[str]:
        return [s.strip() for s in self.duckdb_layers.split(",") if s.strip()]


settings = Settings()
