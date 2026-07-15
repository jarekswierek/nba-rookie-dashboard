"""Application configuration via pydantic-settings.

All settings are read from environment variables or a .env file. The application
will raise a ValidationError at startup if any required variable is missing —
fail-fast is intentional.
"""

import os
from functools import lru_cache
from typing import Literal

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration object.

    Validated at import time — missing required fields raise ValidationError
    immediately, before the first request is served.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ───────────────────────────────────────────────────
    app_env: Literal["development", "staging", "production"] = "development"
    app_debug: bool = False

    # ── PostgreSQL ────────────────────────────────────────────────────
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "nba_rookie_dashboard"
    postgres_user: str = "postgres"
    postgres_password: str = Field(..., min_length=1)

    # ── Redis ─────────────────────────────────────────────────────────
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0

    # ── Frontend ──────────────────────────────────────────────────────
    frontend_url: str = "http://localhost:8501"

    # ── Anthropic ─────────────────────────────────────────────────────
    anthropic_api_key: str = Field(..., min_length=1)

    # ── Computed DSNs ─────────────────────────────────────────────────
    @computed_field  # type: ignore[prop-decorator]
    @property
    def database_url(self) -> str:
        """Async-compatible PostgreSQL DSN (asyncpg driver)."""
        return (
            f"postgresql+asyncpg://{self.postgres_user}"
            f":{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}"
            f"/{self.postgres_db}"
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def database_url_sync(self) -> str:
        """PostgreSQL DSN for Alembic migrations (asyncpg driver)."""
        return (
            f"postgresql+asyncpg://{self.postgres_user}"
            f":{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}"
            f"/{self.postgres_db}"
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def redis_url(self) -> str:
        """Redis connection URL.

        REDIS_URL env var takes precedence over the individual host/port fields
        so that managed Redis providers can inject a single connection string.
        """
        if url := os.environ.get("REDIS_URL"):
            return url
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @property
    def is_production(self) -> bool:
        """True when running in production environment."""
        return self.app_env == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached Settings instance.

    Uses lru_cache so the .env file is read exactly once per process. In tests,
    call get_settings.cache_clear() to reset between cases.
    """
    return Settings()
