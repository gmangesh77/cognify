import structlog

from src.utils.logging import setup_logging


class TestLogging:
    def test_setup_logging_production_mode(self) -> None:
        setup_logging(debug=False)
        config = structlog.get_config()
        processors = config["processors"]
        assert any("JSONRenderer" in type(p).__name__ for p in processors)

    def test_setup_logging_debug_mode(self) -> None:
        setup_logging(debug=True)
        config = structlog.get_config()
        processors = config["processors"]
        assert any("ConsoleRenderer" in type(p).__name__ for p in processors)


class TestSensitiveFieldFilter:
    def test_redacts_password_field(self) -> None:
        from src.utils.logging import _filter_sensitive

        event_dict = {"event": "test", "password": "secret123"}
        result = _filter_sensitive(None, "info", event_dict)
        assert result["password"] == "***REDACTED***"

    def test_redacts_api_key_field(self) -> None:
        from src.utils.logging import _filter_sensitive

        event_dict = {"event": "test", "api_key": "sk-abc123"}
        result = _filter_sensitive(None, "info", event_dict)
        assert result["api_key"] == "***REDACTED***"

    def test_redacts_token_field(self) -> None:
        from src.utils.logging import _filter_sensitive

        event_dict = {"event": "test", "token": "jwt-xyz"}
        result = _filter_sensitive(None, "info", event_dict)
        assert result["token"] == "***REDACTED***"

    def test_redacts_authorization_field(self) -> None:
        from src.utils.logging import _filter_sensitive

        event_dict = {"event": "test", "authorization": "Bearer xyz"}
        result = _filter_sensitive(None, "info", event_dict)
        assert result["authorization"] == "***REDACTED***"

    def test_redacts_secret_field(self) -> None:
        from src.utils.logging import _filter_sensitive

        event_dict = {"event": "test", "secret": "my-secret"}
        result = _filter_sensitive(None, "info", event_dict)
        assert result["secret"] == "***REDACTED***"

    def test_passes_non_sensitive_fields(self) -> None:
        from src.utils.logging import _filter_sensitive

        event_dict = {"event": "test", "user_id": "abc", "path": "/api"}
        result = _filter_sensitive(None, "info", event_dict)
        assert result["user_id"] == "abc"
        assert result["path"] == "/api"

    def test_handles_multiple_sensitive_fields(self) -> None:
        from src.utils.logging import _filter_sensitive

        event_dict = {"event": "test", "password": "x", "token": "y", "user": "z"}
        result = _filter_sensitive(None, "info", event_dict)
        assert result["password"] == "***REDACTED***"
        assert result["token"] == "***REDACTED***"
        assert result["user"] == "z"

    def test_sensitive_keys_constant_is_frozenset(self) -> None:
        from src.utils.logging import SENSITIVE_KEYS

        assert isinstance(SENSITIVE_KEYS, frozenset)
        assert "password" in SENSITIVE_KEYS
        assert "token" in SENSITIVE_KEYS
        assert "secret" in SENSITIVE_KEYS
        assert "api_key" in SENSITIVE_KEYS
        assert "authorization" in SENSITIVE_KEYS

    def test_filter_in_pipeline(self) -> None:
        """Verify filter is wired into the structlog pipeline."""
        from src.utils.logging import _filter_sensitive

        setup_logging(debug=False)
        config = structlog.get_config()
        assert _filter_sensitive in config["processors"]
