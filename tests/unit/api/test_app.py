from fastapi import FastAPI

from src.api.main import create_app
from src.config.settings import Settings


class TestCreateApp:
    def test_returns_fastapi_instance(self) -> None:
        app = create_app()
        assert isinstance(app, FastAPI)

    def test_accepts_custom_settings(self) -> None:
        settings = Settings(app_version="9.9.9")
        app = create_app(settings)
        assert app.state.settings.app_version == "9.9.9"

    def test_health_endpoint_accessible(self) -> None:
        app = create_app()
        routes = [r.path for r in app.routes]
        assert "/api/v1/health" in routes

    def test_readiness_endpoint_accessible(self) -> None:
        app = create_app()
        routes = [r.path for r in app.routes]
        assert "/api/v1/health/ready" in routes

    def test_openapi_title(self) -> None:
        app = create_app()
        assert app.title == "Cognify API"

    def test_debug_never_enabled_on_fastapi(self) -> None:
        settings = Settings(debug=True)
        app = create_app(settings)
        assert app.debug is False
