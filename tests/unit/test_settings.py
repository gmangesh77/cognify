import pytest

from src.config.settings import Settings


class TestSettings:
    def test_default_values(self) -> None:
        settings = Settings()
        assert settings.app_name == "Cognify"
        assert settings.app_version == "0.1.0"
        assert settings.debug is False
        assert settings.log_level == "INFO"
        assert settings.cors_allowed_origins == ["http://localhost:3000"]
        assert settings.rate_limit_default == "100/minute"
        assert settings.api_v1_prefix == "/api/v1"

    def test_env_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("COGNIFY_DEBUG", "true")
        monkeypatch.setenv("COGNIFY_LOG_LEVEL", "DEBUG")
        settings = Settings()
        assert settings.debug is True
        assert settings.log_level == "DEBUG"
