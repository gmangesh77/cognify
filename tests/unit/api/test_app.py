import pytest
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


class TestEmbeddingWarmupAtBoot:
    """INFRA-008 — lifespan kicks off the warm-up when the flag is on."""

    async def _run_lifespan(
        self, monkeypatch: pytest.MonkeyPatch, *, warmup: bool
    ) -> tuple[FastAPI, list[str]]:
        from src.api.main import _lifespan
        from src.services.embeddings import EmbeddingService

        calls: list[str] = []
        monkeypatch.setattr(
            EmbeddingService,
            "warm_up_in_background",
            lambda self: calls.append(self._model_name),
        )
        settings = Settings(  # type: ignore[call-arg]
            _env_file=None,
            embedding_warmup=warmup,
            database_url="",
            anthropic_api_key="",
        )
        app = create_app(settings)
        async with _lifespan(app):
            pass
        return app, calls

    async def test_lifespan_warms_up_when_enabled(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        app, calls = await self._run_lifespan(monkeypatch, warmup=True)
        assert calls == [app.state.settings.embedding_model]

    async def test_lifespan_skips_warmup_when_disabled(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _, calls = await self._run_lifespan(monkeypatch, warmup=False)
        assert calls == []
