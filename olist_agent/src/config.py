from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    openai_api_key: str
    openai_model: str = "gpt-4o-mini"
    mcp_server_url: str = "http://localhost:8000/mcp"

    host: str = "0.0.0.0"
    port: int = 8001
    log_level: str = "INFO"


settings = Settings()
