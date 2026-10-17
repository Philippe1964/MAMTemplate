"""Unit tests for externalized application settings."""

from mamtemplate.infrastructure.config.settings import AppSettings, get_settings


def test_app_settings_defaults() -> None:
    """Verify default values of AppSettings."""
    settings = AppSettings()
    assert settings.app_name == "MAMTemplate API"
    assert settings.environment == "development"
    assert "sqlite+aiosqlite" in settings.database_url


def test_get_settings_cached() -> None:
    """Verify get_settings returns a cached AppSettings instance."""
    first = get_settings()
    second = get_settings()
    assert first is second
