"""Unit tests for application configuration.

These tests verify that Settings validates fields correctly without
touching any external service or real .env file.
"""

import pytest
from pydantic import ValidationError

from backend.core.config import Settings, get_settings

# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_settings(**overrides: str) -> Settings:
    """Build Settings from explicit kwargs only — no .env file, no os.environ."""
    base: dict[str, str] = {
        "postgres_password": "secret",
        "anthropic_api_key": "sk-ant-test",
        "langchain_api_key": "ls__test",
    }
    base.update(overrides)
    return Settings(_env_file=None, **base)  # type: ignore[call-arg]


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestSettingsValidation:
    def test_valid_settings_loads(self) -> None:
        s = _make_settings()
        assert s.app_env == "development"
        assert s.postgres_port == 5432

    def test_missing_postgres_password_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)
        with pytest.raises(ValidationError):
            Settings(_env_file=None, anthropic_api_key="sk-ant-test", langchain_api_key="ls__test")  # type: ignore[call-arg]

    def test_missing_anthropic_key_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        with pytest.raises(ValidationError):
            Settings(_env_file=None, postgres_password="secret", langchain_api_key="ls__test")  # type: ignore[call-arg]

    def test_missing_langchain_key_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("LANGCHAIN_API_KEY", raising=False)
        with pytest.raises(ValidationError):
            Settings(_env_file=None, postgres_password="secret", anthropic_api_key="sk-ant-test")  # type: ignore[call-arg]

    def test_invalid_app_env_raises(self) -> None:
        with pytest.raises(ValidationError):
            _make_settings(app_env="local")

    def test_database_url_contains_asyncpg(self) -> None:
        assert "asyncpg" in _make_settings().database_url

    def test_database_url_sync_contains_asyncpg(self) -> None:
        assert "asyncpg" in _make_settings().database_url_sync

    def test_redis_url_scheme(self) -> None:
        assert _make_settings().redis_url.startswith("redis://")

    def test_is_production_false_by_default(self) -> None:
        assert _make_settings().is_production is False

    def test_is_production_true_when_set(self) -> None:
        assert _make_settings(app_env="production").is_production is True


class TestGetSettings:
    def test_get_settings_returns_singleton(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        get_settings.cache_clear()
        monkeypatch.setenv("POSTGRES_PASSWORD", "pw")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        monkeypatch.setenv("LANGCHAIN_API_KEY", "ls__test")
        monkeypatch.delenv("LANGCHAIN_TRACING_V2", raising=False)

        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2
        get_settings.cache_clear()
