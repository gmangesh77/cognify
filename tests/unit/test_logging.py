import structlog

from src.utils.logging import setup_logging


class TestLogging:
    def test_setup_logging_production_mode(self) -> None:
        setup_logging(debug=False)
        config = structlog.get_config()
        processors = config["processors"]
        assert any(
            "JSONRenderer" in type(p).__name__
            for p in processors
        )

    def test_setup_logging_debug_mode(self) -> None:
        setup_logging(debug=True)
        config = structlog.get_config()
        processors = config["processors"]
        assert any(
            "ConsoleRenderer" in type(p).__name__
            for p in processors
        )
