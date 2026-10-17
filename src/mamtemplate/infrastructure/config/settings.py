"""Externalized application settings via environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """Application settings loaded from environment variables or .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "MAMTemplate API"
    environment: str = "development"
    database_url: str = "sqlite+aiosqlite:///./mamtemplate.db"
    presentation_metrics_url: str = (
        "http://mamtemplate-presentation:80/internal/presentation-metrics.json"
    )
    business_service_host: str = "mamtemplate-business"
    business_service_port: int = 8000

    # Cloud-Native SQLAlchemy Connection Pool Sizing (per Business replica)
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_timeout: float = 30.0
    db_pool_recycle: int = 1800


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    """Return cached application settings instance.

    Returns:
        The singleton AppSettings instance.
    """
    return AppSettings()
