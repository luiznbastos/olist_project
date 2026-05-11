from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Select which agent implementation to use: "openai" or "claude"
    agent_type: str = "openai"

    # OpenAI settings (used when agent_type="openai")
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # Anthropic settings (used when agent_type="claude")
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"
    enable_thinking: bool = False
    thinking_budget: int = 5000

    mcp_server_url: str = "http://localhost:8000/mcp"

    host: str = "0.0.0.0"
    port: int = 8001
    log_level: str = "INFO"


settings = Settings()
