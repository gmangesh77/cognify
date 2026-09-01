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


class TestPersonaRepoWiring:
    """AUTHOR-011 review round 1 — `ContentService` must be built from a
    `content_deps` that already carries the (eventual) `app.state.persona_repo`.

    The DB branch used to build `ContentService` first and only reassign
    `app.state.persona_repo` to `PgPersonaRepository` afterward; because
    `ContentDeps` is frozen, the pipeline kept reading the in-memory seed
    repo from `create_app()` forever unless the anthropic key happened to
    be *resolved from the DB* (the only rebuild path). A full DB-branch
    lifespan run needs a real Postgres (`ApiKeyResolver.resolve_all()`
    issues real queries), so this covers the fix two ways instead: the
    no-DB branch (still correct, regression-proofed) and a direct unit
    test on `_wire_persona_repo`, the helper the DB branch now calls
    before constructing `ContentService`.
    """

    async def test_in_memory_branch_content_service_uses_app_state_persona_repo(
        self,
    ) -> None:
        from src.api.main import _lifespan

        settings = Settings(  # type: ignore[call-arg]
            _env_file=None,
            embedding_warmup=False,
            database_url="",
            anthropic_api_key="",
        )
        app = create_app(settings)
        async with _lifespan(app):
            pass
        assert app.state.content_service.deps.persona_repo is app.state.persona_repo

    def test_wire_persona_repo_replaces_persona_repo_before_content_service(
        self,
    ) -> None:
        from src.api.main import _wire_persona_repo
        from src.db.persona_repository import PgPersonaRepository
        from src.services.content_repositories import ContentDeps

        app = create_app(Settings(_env_file=None))  # type: ignore[call-arg]
        # `PgPersonaRepository` only stores `sf` — it never queries at
        # construction time, so a plain sentinel is safe here.
        sf = object()
        original_deps = ContentDeps(settings=app.state.settings)

        updated = _wire_persona_repo(app, sf, original_deps)  # type: ignore[arg-type]

        assert isinstance(app.state.persona_repo, PgPersonaRepository)
        assert updated.persona_repo is app.state.persona_repo
        assert updated is not original_deps
        # ContentDeps is frozen — the original snapshot must be untouched.
        assert original_deps.persona_repo is not app.state.persona_repo
