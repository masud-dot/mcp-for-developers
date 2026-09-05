"""Configuration loaded from the environment."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Every value the book's servers read at startup."""

    model_config = SettingsConfigDict(
        env_prefix="MCPDEV_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    log_level: str = "INFO"
    repo_api_base: str = "https://api.github.com"
    repo_token: str = ""
    repo_timeout_seconds: float = 10.0
    ci_db_path: str = "builds.db"
    handle_key: str = ""
    handle_ttl_seconds: int = 900
    request_state_key: str = ""
    environment: str = "development"
    allowed_hosts: list[str] = ["127.0.0.1:8000", "localhost:8000"]
    allowed_origins: list[str] = []
    readiness_probe_url: str = ""
    otlp_endpoint: str = ""
    auth_issuer: str = "https://auth.example.com"
    auth_audience: str = "https://mcp.example.com"
    auth_signing_key: str = ""
    auth_algorithm: str = "HS256"
    http_host: str = "127.0.0.1"
    http_port: int = 8000


settings = Settings()
