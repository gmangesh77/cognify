# INFRA-008 — Embedding warm-up, live user re-check, shared toaster, component splits

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the four Phase-B platform items bundled as INFRA-008 (4 SP): the embedding model warms up in the background with graceful RAG degradation, deactivated users lose API access within 30 s without a restart, one `useToast` replaces three hand-rolled toasts, and no page/component file in `frontend/src` is over 200 lines (enforced by a test).

**Architecture:** Backend changes are additive and flag-free: `EmbeddingService` gains a daemon-thread warm-up and a `try_embed()` that returns `None` only *while* a warm-up is in flight (so the Celery worker, which never warms up, keeps today's synchronous load — no RAG regression); `MilvusRetriever` returns `[]` when cold; `/health` reports `embedding`. Auth adds `UserData.is_active`, a 30 s TTL `UserStatusCache` consulted by `get_current_user`, and an admin `PATCH /auth/users/{id}/active`. Frontend adds `ToastProvider`/`useToast` in `components/ui`, mounted in `app/providers.tsx`, and splits six oversized components into hook + presentational files with **zero behaviour change** (existing tests are the safety net; a new size-budget test keeps it that way).

**Tech Stack:** Python 3.12 / FastAPI / pydantic-settings / structlog / pytest; Next.js 15 / React 19 / Vitest + Testing Library.

**Spec:** `docs/superpowers/plans/2026-08-19-epic-11-supervised-authoring-plan.md` §5.9, §5.10, §9 Phase B (INFRA-008 row + acceptance criteria); `docs/architecture/COGNIFY_VS_IMPACTAI_REVIEW_2026-08.md` §6 #15/#16.

## Global Constraints

- All functions < 20 lines, files < 200 lines, max 3 params (CLAUDE.md). Existing backend files already over 200 lines that this ticket touches (`src/api/main.py` 688 l., `src/api/routers/health.py`) are **not** split here — backend splits are a recorded follow-up; the frontend budget is the acceptance criterion.
- TDD: failing test first. Backend: `uv run pytest tests/unit/ -q` with `COGNIFY_ANTHROPIC_API_KEY` blanked (memory: Milvus hang). Frontend: `cd frontend && npx vitest run`.
- Every new setting is `COGNIFY_*` in `src/config/settings.py`; nothing hardcoded.
- Feature behaviour defaults to current behaviour except the two things the ticket exists for: warm-up on API boot (`COGNIFY_EMBEDDING_WARMUP=true`) and the active-flag check (all seeded users are active, so nothing changes until an admin deactivates someone).
- No new colour/font tokens; the toast keeps the exact markup used today (`role="status"`, `fixed bottom-6 right-6 z-50 rounded-lg bg-neutral-900 px-4 py-3 text-sm text-white shadow-lg`).
- Named exports only; no default exports (pages excepted — Next.js requires them).
- One PR off `develop`, never stacked. No Azure Boards items exist for Epic 11 — no `AB#`.
- Conventional commits: `feat(embeddings): …`, `feat(auth): …`, `feat(frontend): …`, `refactor(frontend): …`, `test: …`, `docs: …`.

### Deviations from the program plan (decided 2026-08-28, record in PROGRESS.md)

1. **Role re-check is logged, not enforced.** §5.9 says "re-reads role/active". There is no user store beyond the in-memory dev seed and no endpoint that changes a role, so "DB role wins" has no real-world trigger — but it would silently break ~125 test usages that mint `sub="user-1"` tokens with arbitrary roles. `get_current_user` enforces `is_active` and logs `auth_role_drift` when the repo role differs from the token role. Enforce it when a real user table lands.
2. **Unknown user ⇒ token stays authoritative.** ~10 API test modules build `create_app(auth_settings)` (debug=False ⇒ empty seed) and mint `user-1` tokens. A user missing from the repo is *not* a 401; only `is_active=False` is. Deleting a user therefore takes effect at access-token expiry (24 h); deactivating takes effect within the TTL. The acceptance criterion ("deactivating a user blocks their next request within 30 s") is met.
3. **Scope of "split >200-line files":** frontend `src/app/**` and `src/components/**` non-test files (the Phase-B acceptance criterion). `hooks/use-settings.ts` (353), `hooks/session-events-reducer.ts` (220), `types/visuals.ts` (237), `lib/mock/topics.ts` (389) and the 29 backend files over 200 lines are out of scope — list them as follow-ups.

---

## File map

| Area | Create | Modify |
|---|---|---|
| Embedding warm-up | — | `src/services/embeddings.py`, `src/services/milvus_retriever.py`, `src/api/routers/health.py`, `src/api/main.py` (`_lifespan`), `src/config/settings.py`, tests: `tests/unit/services/test_embeddings.py`, `tests/unit/services/test_milvus_retriever.py`, `tests/unit/api/test_health.py`, `tests/unit/api/test_app.py` |
| Auth re-check | `src/api/auth/user_status.py`, `tests/unit/api/test_user_status.py`, `tests/unit/api/test_user_active_endpoint.py` | `src/api/auth/schemas.py`, `src/api/auth/repository.py`, `src/api/auth/service.py`, `src/api/dependencies.py`, `src/api/routers/auth.py`, `src/api/main.py` (`create_app`), `src/config/settings.py`, `tests/unit/api/test_auth.py` |
| Toaster | `frontend/src/components/ui/toaster.tsx`, `frontend/src/components/ui/toaster.test.tsx` | `frontend/src/app/providers.tsx`, `frontend/src/app/(dashboard)/articles/[id]/page.tsx`, `frontend/src/app/(dashboard)/settings/page.tsx`, `frontend/src/app/(dashboard)/topics/page.tsx`, `frontend/src/app/(dashboard)/topics/use-generate-actions.ts` (+ `.test.ts`), `frontend/src/hooks/use-article-actions.ts` |
| Splits | `frontend/src/file-size-budget.test.ts`, `frontend/src/hooks/use-visual-studio.ts`, `frontend/src/components/visuals/VisualStudioSections.tsx`, `frontend/src/components/visuals/SpecListSection.tsx`, `frontend/src/components/visuals/SpecCardMedia.tsx`, `frontend/src/components/visuals/SpecCardFooter.tsx`, `frontend/src/components/visuals/SavedAssetFacets.tsx`, `frontend/src/components/visuals/SavedAssetGrid.tsx`, `frontend/src/lib/visuals/savedAssetFormat.ts` (+ `.test.ts`), `frontend/src/components/visuals/ImageUploadTab.tsx`, `frontend/src/components/visuals/ImageFetchUrlTab.tsx`, `frontend/src/hooks/use-ai-rewrite.ts`, `frontend/src/lib/research/outline-edit.ts` (+ `.test.ts`) | `VisualStudio.tsx`, `SpecCard.tsx`, `SavedAssetGallery.tsx`, `ImageImportModal.tsx`, `AIRewritePopover.tsx`, `outline-review-step.tsx` |
| Docs | — | `project-management/PROGRESS.md`, `project-management/BACKLOG.md`, `CLAUDE.md` (Current Status), this plan's checkboxes |

---

### Task 1: `EmbeddingService` — background warm-up + `try_embed`

**Files:**
- Modify: `src/services/embeddings.py`
- Test: `tests/unit/services/test_embeddings.py`

**Interfaces:**
- Produces: `EmbeddingService.is_ready -> bool`, `EmbeddingService.is_warming -> bool`, `EmbeddingService.warm_up_in_background() -> threading.Thread | None`, `EmbeddingService.try_embed(texts: list[str]) -> list[list[float]] | None`. `embed()` and `cosine_similarity_matrix()` unchanged.
- Semantics: `try_embed` returns `None` **only** when a warm-up thread is alive and the model is not yet loaded; otherwise it behaves exactly like `embed()` (synchronous lazy load). `_load_model` is lock-guarded and a no-op when already loaded.

- [x] **Step 1: Write the failing tests** — append to `tests/unit/services/test_embeddings.py`:

```python
import threading
from unittest.mock import MagicMock

import numpy as np
import structlog.testing


def _service_with_fake_loader(
    gate: threading.Event | None = None,
) -> EmbeddingService:
    """EmbeddingService whose loader never touches sentence-transformers."""
    svc = EmbeddingService(model_name="fake-model")

    def fake_load() -> None:
        if gate is not None:
            gate.wait(timeout=5)
        model = MagicMock()
        model.encode.return_value = np.array([[0.1, 0.2]])
        svc._model = model

    svc._load_model = fake_load  # type: ignore[method-assign]
    return svc


class TestEmbeddingWarmUp:
    def test_not_ready_and_not_warming_at_init(self) -> None:
        svc = EmbeddingService(model_name="fake-model")
        assert svc.is_ready is False
        assert svc.is_warming is False

    def test_try_embed_returns_none_while_warming(self) -> None:
        gate = threading.Event()
        svc = _service_with_fake_loader(gate)
        thread = svc.warm_up_in_background()
        assert thread is not None
        assert svc.is_warming is True
        assert svc.try_embed(["x"]) is None
        gate.set()
        thread.join(timeout=5)
        assert svc.is_ready is True
        assert svc.is_warming is False
        assert svc.try_embed(["x"]) == [[0.1, 0.2]]

    def test_try_embed_loads_synchronously_when_no_warmup(self) -> None:
        # Worker path: nobody called warm_up_in_background → same as embed().
        svc = _service_with_fake_loader()
        assert svc.try_embed(["x"]) == [[0.1, 0.2]]
        assert svc.is_ready is True

    def test_warm_up_is_idempotent(self) -> None:
        gate = threading.Event()
        svc = _service_with_fake_loader(gate)
        first = svc.warm_up_in_background()
        second = svc.warm_up_in_background()
        assert first is second
        gate.set()
        assert first is not None
        first.join(timeout=5)
        assert svc.warm_up_in_background() is None

    def test_warm_up_failure_is_logged_not_raised(self) -> None:
        svc = EmbeddingService(model_name="fake-model")

        def boom() -> None:
            raise RuntimeError("no network")

        svc._load_model = boom  # type: ignore[method-assign]
        with structlog.testing.capture_logs() as logs:
            thread = svc.warm_up_in_background()
            assert thread is not None
            thread.join(timeout=5)
        assert any(log["event"] == "embedding_warmup_failed" for log in logs)
        assert svc.is_ready is False
        assert svc.is_warming is False

    def test_load_model_is_noop_when_already_loaded(self) -> None:
        svc = EmbeddingService(model_name="fake-model")
        sentinel = MagicMock()
        svc._model = sentinel
        svc._load_model()  # must not import sentence_transformers
        assert svc._model is sentinel
```

- [x] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/unit/services/test_embeddings.py -q`
Expected: 6 failures (`AttributeError: ... has no attribute 'is_ready'` etc.). The existing 4 tests still pass.

- [x] **Step 3: Implement** — replace `src/services/embeddings.py` with:

```python
import threading
import time
from typing import Any

import numpy as np
import structlog

logger = structlog.get_logger()


class EmbeddingService:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        self._model_name = model_name
        self._model: Any = None
        self._lock = threading.Lock()
        self._warmup_thread: threading.Thread | None = None

    @property
    def is_ready(self) -> bool:
        return self._model is not None

    @property
    def is_warming(self) -> bool:
        thread = self._warmup_thread
        return thread is not None and thread.is_alive()

    def _load_model(self) -> None:
        with self._lock:
            if self._model is not None:
                return
            from sentence_transformers import SentenceTransformer

            start = time.monotonic()
            self._model = SentenceTransformer(self._model_name)
            duration_ms = (time.monotonic() - start) * 1000
            logger.info(
                "embedding_model_loaded",
                model_name=self._model_name,
                load_duration_ms=round(duration_ms),
            )

    def _warm_up(self) -> None:
        try:
            self._load_model()
        except Exception as exc:  # noqa: BLE001 — warm-up must never take the app down
            logger.warning(
                "embedding_warmup_failed",
                model_name=self._model_name,
                error=str(exc),
            )

    def warm_up_in_background(self) -> threading.Thread | None:
        """INFRA-008: load the model on a daemon thread. Idempotent.

        Returns the running thread, or None when the model is already loaded.
        """
        if self.is_ready:
            return None
        if self.is_warming:
            return self._warmup_thread
        thread = threading.Thread(
            target=self._warm_up, name="embedding-warmup", daemon=True
        )
        self._warmup_thread = thread
        thread.start()
        logger.info("embedding_warmup_started", model_name=self._model_name)
        return thread

    def try_embed(self, texts: list[str]) -> list[list[float]] | None:
        """Embed, or return None while a background warm-up is still running.

        Without an in-flight warm-up this is exactly ``embed()`` (synchronous
        lazy load) so callers that never warm up — the Celery worker — keep
        today's behaviour.
        """
        if not self.is_ready and self.is_warming:
            return None
        return self.embed(texts)

    def embed(self, texts: list[str]) -> list[list[float]]:
        if self._model is None:
            self._load_model()
        embeddings = self._model.encode(texts, normalize_embeddings=True)
        return embeddings.tolist()  # type: ignore[no-any-return]

    def cosine_similarity_matrix(
        self,
        embeddings: list[list[float]],
    ) -> list[list[float]]:
        arr = np.array(embeddings)
        similarity = (arr @ arr.T).tolist()
        return similarity  # type: ignore[no-any-return]
```

- [x] **Step 4: Run to verify they pass**

Run: `uv run pytest tests/unit/services/test_embeddings.py -q`
Expected: 10 passed.

- [x] **Step 5: Commit**

```bash
git add src/services/embeddings.py tests/unit/services/test_embeddings.py
git commit -m "feat(embeddings): background warm-up + try_embed for graceful cold start (INFRA-008)"
```

---

### Task 2: Retriever degrades when cold; `/health` reports `embedding`; API boot warms up

**Files:**
- Modify: `src/services/milvus_retriever.py`, `src/api/routers/health.py`, `src/config/settings.py`, `src/api/main.py`
- Test: `tests/unit/services/test_milvus_retriever.py`, `tests/unit/api/test_health.py`, `tests/unit/api/test_app.py`

**Interfaces:**
- Consumes: `EmbeddingService.try_embed`, `is_ready`, `is_warming` (Task 1).
- Produces: `Settings.embedding_warmup: bool = True` (`COGNIFY_EMBEDDING_WARMUP`); `DependencyChecks.embedding: CheckStatus` (`ok` = loaded, `degraded` = warming, `unavailable` = no service / cold); `_lifespan` calls `warm_up_in_background()` on the shared `app.state.embedding_service` when the flag is on.

- [x] **Step 1: Failing tests**

(a) `tests/unit/services/test_milvus_retriever.py` — change every `mock_embedding.embed = MagicMock(...)` to `mock_embedding.try_embed = MagicMock(...)` and every `mock_embedding.embed.assert_called_once_with(...)` to `mock_embedding.try_embed.assert_called_once_with(...)`, then add:

```python
    async def test_retrieve_returns_empty_while_embedding_warming(self) -> None:
        mock_milvus = AsyncMock()
        mock_embedding = MagicMock()
        mock_embedding.try_embed = MagicMock(return_value=None)

        retriever = MilvusRetriever(mock_milvus, mock_embedding)
        results = await retriever.retrieve("query", "topic-1")

        assert results == []
        mock_milvus.search.assert_not_called()
```

(b) `tests/unit/api/test_health.py` — in `test_health_checks_all_unavailable` change `expected_keys` to `{"database", "redis", "milvus", "celery", "embedding"}`, then add a class (reuse the module's `health_client` fixture; find how it builds its app and set state on it — it exposes the `FastAPI` app via `health_client._transport.app` if no app fixture exists):

```python
class TestEmbeddingHealthCheck:
    """INFRA-008 — embedding check mirrors the warm-up state."""

    def _app(self, health_client: httpx.AsyncClient) -> FastAPI:
        transport = health_client._transport  # noqa: SLF001
        assert isinstance(transport, httpx.ASGITransport)
        return transport.app  # type: ignore[return-value]

    async def test_reports_ok_when_model_loaded(
        self, health_client: httpx.AsyncClient
    ) -> None:
        svc = MagicMock(is_ready=True, is_warming=False)
        self._app(health_client).state.embedding_service = svc
        response = await health_client.get("/api/v1/health")
        assert response.json()["checks"]["embedding"] == "ok"

    async def test_reports_degraded_while_warming(
        self, health_client: httpx.AsyncClient
    ) -> None:
        svc = MagicMock(is_ready=False, is_warming=True)
        self._app(health_client).state.embedding_service = svc
        response = await health_client.get("/api/v1/health")
        assert response.json()["checks"]["embedding"] == "degraded"

    async def test_reports_unavailable_when_cold(
        self, health_client: httpx.AsyncClient
    ) -> None:
        svc = MagicMock(is_ready=False, is_warming=False)
        self._app(health_client).state.embedding_service = svc
        response = await health_client.get("/api/v1/health")
        assert response.json()["checks"]["embedding"] == "unavailable"
```

Add `from unittest.mock import MagicMock` and `from fastapi import FastAPI` imports at the top of the test module if absent.

(c) `tests/unit/api/test_app.py` — add:

```python
class TestEmbeddingWarmupAtBoot:
    """INFRA-008 — lifespan kicks off the warm-up when the flag is on."""

    async def test_lifespan_warms_up_when_enabled(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src.api.main import _lifespan
        from src.services.embeddings import EmbeddingService

        calls: list[str] = []
        monkeypatch.setattr(
            EmbeddingService,
            "warm_up_in_background",
            lambda self: calls.append(self._model_name),
        )
        app = create_app(Settings(_env_file=None, embedding_warmup=True))  # type: ignore[call-arg]
        async with _lifespan(app):
            pass
        assert calls == [app.state.settings.embedding_model]

    async def test_lifespan_skips_warmup_when_disabled(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src.api.main import _lifespan
        from src.services.embeddings import EmbeddingService

        calls: list[str] = []
        monkeypatch.setattr(
            EmbeddingService,
            "warm_up_in_background",
            lambda self: calls.append(self._model_name),
        )
        app = create_app(Settings(_env_file=None, embedding_warmup=False))  # type: ignore[call-arg]
        async with _lifespan(app):
            pass
        assert calls == []
```

Add `import pytest` and `from src.config.settings import Settings` at the top of `test_app.py` if absent (it already imports `create_app` and `Settings`).

- [x] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/unit/services/test_milvus_retriever.py tests/unit/api/test_health.py tests/unit/api/test_app.py -q`
Expected: the retriever tests fail (`try_embed` never called / `embed` called), health `expected_keys` and the 3 embedding checks fail, both boot tests fail (`Settings` has no field `embedding_warmup`).

- [x] **Step 3: Implement**

`src/config/settings.py` — directly under `embedding_model`:

```python
    # INFRA-008: load the sentence-transformer on a background thread at API
    # boot; RAG retrieval is skipped (keyword/no-context drafting) while cold.
    embedding_warmup: bool = True
```

`src/services/milvus_retriever.py`:

```python
"""Milvus retrieval service.

Embeds a query via EmbeddingService, searches Milvus for top-k
similar chunks with topic_id filtering. Returns ranked ChunkResults.
"""

import structlog

from src.models.research import ChunkResult
from src.services.embeddings import EmbeddingService
from src.services.milvus_service import MilvusService

logger = structlog.get_logger()


class MilvusRetriever:
    """Retrieves relevant chunks from Milvus by semantic similarity."""

    def __init__(
        self, milvus_service: MilvusService, embedding_service: EmbeddingService
    ) -> None:
        self._milvus = milvus_service
        self._embeddings = embedding_service

    async def retrieve(
        self, query: str, topic_id: str, top_k: int = 5
    ) -> list[ChunkResult]:
        """Embed query and search Milvus with topic filtering.

        INFRA-008: while the embedding model is still warming up the
        retriever degrades to "no RAG context" instead of blocking the
        event loop on a synchronous model load.
        """
        vectors = self._embeddings.try_embed([query])
        if vectors is None:
            logger.info("retriever_skipped_embedding_cold", topic_id=topic_id)
            return []
        if not vectors:
            return []
        return await self._milvus.search(vectors[0], topic_id, top_k)
```

`src/api/routers/health.py` — add the field and check:

```python
class DependencyChecks(BaseModel):
    database: CheckStatus = "unavailable"
    redis: CheckStatus = "unavailable"
    milvus: CheckStatus = "unavailable"
    celery: CheckStatus = "unavailable"
    embedding: CheckStatus = "unavailable"
```

```python
def _check_embedding(request: Request) -> CheckStatus:
    """INFRA-008 — ok once loaded, degraded while the warm-up thread runs."""
    service = getattr(request.app.state, "embedding_service", None)
    if service is None:
        return "unavailable"
    if service.is_ready:
        return "ok"
    if service.is_warming:
        return "degraded"
    return "unavailable"
```

and in `_run_checks` add `embedding=_check_embedding(request),` to the `DependencyChecks(...)` constructor.

`src/api/main.py` — in `_lifespan`, right after `app.state.session_tasks = SessionTaskRegistry()`:

```python
    # INFRA-008 — warm the embedding model on a daemon thread so the first
    # dedup/RAG call never blocks the event loop on a model load (PR #72
    # baked the weights into the image; this removes the first-call stall).
    if settings.embedding_warmup:
        _get_or_create_embedding_service(app).warm_up_in_background()
```

- [x] **Step 4: Run to verify they pass**

Run: `uv run pytest tests/unit/services/test_milvus_retriever.py tests/unit/api/test_health.py tests/unit/api/test_app.py tests/unit/services/test_embeddings.py -q`
Expected: all pass.

- [x] **Step 5: Commit**

```bash
git add src/services/milvus_retriever.py src/api/routers/health.py src/config/settings.py src/api/main.py tests/unit/services/test_milvus_retriever.py tests/unit/api/test_health.py tests/unit/api/test_app.py
git commit -m "feat(rag): skip retrieval while embedding warms up; health embedding check; warm-up at boot (INFRA-008)"
```

---

### Task 3: `UserData.is_active` + `UserStatusCache` + re-check in `get_current_user`

**Files:**
- Create: `src/api/auth/user_status.py`, `tests/unit/api/test_user_status.py`
- Modify: `src/api/auth/schemas.py`, `src/api/auth/repository.py`, `src/api/auth/service.py`, `src/api/dependencies.py`, `src/api/main.py` (`create_app`), `src/config/settings.py`
- Test: `tests/unit/api/test_user_status.py`, `tests/unit/api/test_auth.py`

**Interfaces:**
- Produces: `UserData.is_active: bool = True`; `UserRepository.set_active(user_id: str, is_active: bool) -> UserData | None` (Protocol + in-memory impl); `UserStatusCache(ttl_seconds: float = 30.0, clock=time.monotonic)` with `lookup(user_id, repo) -> UserData | None` and `invalidate(user_id) -> None`; `Settings.auth_recheck_ttl_seconds: float = 30.0` (`COGNIFY_AUTH_RECHECK_TTL_SECONDS`); `app.state.user_status_cache`; `AuthenticationError(code="user_inactive")` from both `get_current_user` and `AuthService.refresh`.

- [x] **Step 1: Failing tests**

`tests/unit/api/test_user_status.py` (new):

```python
"""INFRA-008 — TTL cache in front of the user repository."""

from src.api.auth.repository import InMemoryUserRepository
from src.api.auth.schemas import UserData
from src.api.auth.user_status import UserStatusCache


def _user(user_id: str = "u1", *, is_active: bool = True) -> UserData:
    return UserData(
        id=user_id,
        email=f"{user_id}@example.com",
        password_hash="x",
        role="editor",
        is_active=is_active,
    )


class TestUserStatusCache:
    def test_lookup_reads_through_and_caches(self) -> None:
        repo = InMemoryUserRepository([_user()])
        now = [100.0]
        cache = UserStatusCache(ttl_seconds=30, clock=lambda: now[0])
        assert cache.lookup("u1", repo) is not None
        repo.set_active("u1", False)
        now[0] = 120.0  # still inside the TTL
        cached = cache.lookup("u1", repo)
        assert cached is not None and cached.is_active is True

    def test_lookup_refreshes_after_ttl(self) -> None:
        repo = InMemoryUserRepository([_user()])
        now = [100.0]
        cache = UserStatusCache(ttl_seconds=30, clock=lambda: now[0])
        cache.lookup("u1", repo)
        repo.set_active("u1", False)
        now[0] = 131.0
        refreshed = cache.lookup("u1", repo)
        assert refreshed is not None and refreshed.is_active is False

    def test_lookup_caches_misses(self) -> None:
        repo = InMemoryUserRepository([])
        cache = UserStatusCache(ttl_seconds=30, clock=lambda: 0.0)
        assert cache.lookup("ghost", repo) is None
        repo._users_by_id["ghost"] = _user("ghost")  # noqa: SLF001
        assert cache.lookup("ghost", repo) is None

    def test_invalidate_forces_reload(self) -> None:
        repo = InMemoryUserRepository([_user()])
        cache = UserStatusCache(ttl_seconds=30, clock=lambda: 0.0)
        cache.lookup("u1", repo)
        repo.set_active("u1", False)
        cache.invalidate("u1")
        reloaded = cache.lookup("u1", repo)
        assert reloaded is not None and reloaded.is_active is False


class TestInMemoryUserRepositorySetActive:
    def test_set_active_updates_both_indexes(self) -> None:
        repo = InMemoryUserRepository([_user()])
        updated = repo.set_active("u1", False)
        assert updated is not None and updated.is_active is False
        by_id = repo.get_by_id("u1")
        by_email = repo.get_by_email("u1@example.com")
        assert by_id is not None and by_id.is_active is False
        assert by_email is not None and by_email.is_active is False

    def test_set_active_unknown_returns_none(self) -> None:
        repo = InMemoryUserRepository([])
        assert repo.set_active("nope", False) is None
```

`tests/unit/api/test_auth_endpoints.py` — add (uses the module's existing `auth_app`, `auth_client`, `auth_settings` fixtures and `create_access_token` import; `fastapi` is already imported there):

```python
class TestUserStatusRecheck:
    """INFRA-008 — deactivated users are rejected within the cache TTL."""

    def _add_protected_route(self, auth_app: FastAPI) -> None:
        from src.api.dependencies import get_current_user

        @auth_app.get("/api/v1/protected-recheck")
        async def protected(
            current_user: object = fastapi.Depends(get_current_user),
        ) -> dict[str, str]:
            return {"user_id": current_user.sub}  # type: ignore[union-attr]

    async def test_inactive_user_gets_401_after_ttl(
        self,
        auth_app: FastAPI,
        auth_client: httpx.AsyncClient,
        auth_settings: Settings,
    ) -> None:
        self._add_protected_route(auth_app)
        now = [0.0]
        auth_app.state.user_status_cache.clock = lambda: now[0]
        headers = {
            "Authorization": f"Bearer {create_access_token('user-1', 'editor', auth_settings)}"
        }
        assert (await auth_client.get("/api/v1/protected-recheck", headers=headers)).status_code == 200
        auth_app.state.user_repo.set_active("user-1", False)
        # Inside the TTL the cached "active" answer still wins…
        now[0] = 10.0
        assert (await auth_client.get("/api/v1/protected-recheck", headers=headers)).status_code == 200
        # …and after it the deactivation bites.
        now[0] = 31.0
        response = await auth_client.get("/api/v1/protected-recheck", headers=headers)
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "user_inactive"

    async def test_unknown_user_token_is_still_accepted(
        self,
        auth_app: FastAPI,
        auth_client: httpx.AsyncClient,
        auth_settings: Settings,
    ) -> None:
        # Deviation #2: the seed repo is not authoritative for existence.
        self._add_protected_route(auth_app)
        headers = {
            "Authorization": f"Bearer {create_access_token('someone-else', 'viewer', auth_settings)}"
        }
        response = await auth_client.get("/api/v1/protected-recheck", headers=headers)
        assert response.status_code == 200
```

Check the exact error envelope shape used by the other 401 tests in that module (`response.json()["error"]["code"]` vs `response.json()["code"]`) and use the same one.

`tests/unit/api/test_auth.py` — inside the existing `TestAuthService` class (the one that builds `self.user_repo` around line 324) add:

```python
    def test_refresh_rejects_inactive_user(self) -> None:
        tokens = self.service.login("test@example.com", "password123")
        self.user_repo.set_active("user-1", False)
        with pytest.raises(AuthenticationError) as exc_info:
            self.service.refresh(tokens.refresh_token)
        assert exc_info.value.code == "user_inactive"
```

Adapt the login email/password and user id to whatever `test_user` that class seeds (read the fixture at the top of the class before writing the test).

- [x] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/unit/api/test_user_status.py tests/unit/api/test_auth_endpoints.py tests/unit/api/test_auth.py -q`
Expected: import error on `src.api.auth.user_status`; `UserData` rejects `is_active`; `set_active` missing.

- [x] **Step 3: Implement**

`src/api/auth/schemas.py` — extend `UserData`:

```python
class UserData(BaseModel):
    id: str
    email: str
    password_hash: str
    role: Role
    is_active: bool = True
```

`src/api/auth/repository.py` — extend the Protocol and the in-memory repo:

```python
class UserRepository(Protocol):
    def get_by_email(self, email: str) -> UserData | None: ...

    def get_by_id(self, user_id: str) -> UserData | None: ...

    def set_active(self, user_id: str, is_active: bool) -> UserData | None: ...
```

```python
    def set_active(self, user_id: str, is_active: bool) -> UserData | None:
        user = self._users_by_id.get(user_id)
        if user is None:
            return None
        updated = user.model_copy(update={"is_active": is_active})
        self._users_by_id[user_id] = updated
        self._users_by_email[updated.email] = updated
        return updated
```

`src/api/auth/user_status.py` (new):

```python
"""INFRA-008 — live user status re-check with a short TTL cache.

``get_current_user`` consults this on every request so a deactivated user
loses access within ``Settings.auth_recheck_ttl_seconds`` without a restart,
while the hot path stays a dict lookup rather than a repository hit.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass, field

from src.api.auth.repository import UserRepository
from src.api.auth.schemas import UserData


@dataclass
class _Entry:
    user: UserData | None
    expires_at: float


@dataclass
class UserStatusCache:
    ttl_seconds: float = 30.0
    clock: Callable[[], float] = time.monotonic
    _entries: dict[str, _Entry] = field(default_factory=dict, repr=False)

    def lookup(self, user_id: str, repo: UserRepository) -> UserData | None:
        """Return the repo's view of the user, cached for ``ttl_seconds``.

        Misses (``None``) are cached too so an unknown id cannot hammer the
        repository.
        """
        now = self.clock()
        entry = self._entries.get(user_id)
        if entry is not None and entry.expires_at > now:
            return entry.user
        user = repo.get_by_id(user_id)
        self._entries[user_id] = _Entry(user=user, expires_at=now + self.ttl_seconds)
        return user

    def invalidate(self, user_id: str) -> None:
        self._entries.pop(user_id, None)
```

`src/api/dependencies.py` — change the tail of `get_current_user` and add the helper:

```python
    settings = request.app.state.settings
    payload = decode_access_token(parts[1], settings)
    return _recheck_user_status(request, payload)


def _recheck_user_status(request: Request, payload: TokenPayload) -> TokenPayload:
    """INFRA-008: deactivated users lose access within the cache TTL.

    A user unknown to the repository keeps the token's claims (the in-memory
    seed is not authoritative for existence); a role mismatch is logged, not
    enforced — see plan deviation #1/#2.
    """
    repo = getattr(request.app.state, "user_repo", None)
    cache = getattr(request.app.state, "user_status_cache", None)
    if repo is None or cache is None:
        return payload
    user = cache.lookup(payload.sub, repo)
    if user is None:
        return payload
    if not user.is_active:
        logger.warning("auth_user_inactive", user_id=payload.sub)
        raise AuthenticationError(
            code="user_inactive", message="User account is deactivated"
        )
    if user.role != payload.role:
        logger.warning(
            "auth_role_drift",
            user_id=payload.sub,
            token_role=payload.role,
            repo_role=user.role,
        )
    return payload
```

`src/api/auth/service.py` — in `refresh`, right after the `if user is None:` block:

```python
        if not user.is_active:
            raise AuthenticationError(
                code="user_inactive",
                message="User account is deactivated",
            )
```

`src/config/settings.py` — next to the JWT settings:

```python
    # INFRA-008: how long get_current_user trusts a cached user-status
    # answer before re-reading role/is_active from the user repository.
    auth_recheck_ttl_seconds: float = 30.0
```

`src/api/main.py` — in `create_app`, right after `app.state.user_repo = ...`:

```python
    app.state.user_status_cache = UserStatusCache(
        ttl_seconds=settings.auth_recheck_ttl_seconds
    )
```

with `from src.api.auth.user_status import UserStatusCache` added to the imports.

- [x] **Step 4: Run the whole API suite to verify nothing regressed**

Run: `uv run pytest tests/unit/api/ -q`
Expected: all pass (every existing fixture seeds `user-1` active or leaves the repo empty — both are pass-through).

- [x] **Step 5: Commit**

```bash
git add src/api/auth/ src/api/dependencies.py src/api/main.py src/config/settings.py tests/unit/api/test_user_status.py tests/unit/api/test_auth_endpoints.py tests/unit/api/test_auth.py
git commit -m "feat(auth): is_active + 30s user-status re-check in get_current_user (INFRA-008)"
```

---

### Task 4: Admin endpoint `PATCH /auth/users/{user_id}/active`

**Files:**
- Create: `tests/unit/api/test_user_active_endpoint.py`
- Modify: `src/api/routers/auth.py`, `src/api/auth/schemas.py`

**Interfaces:**
- Consumes: `UserRepository.set_active`, `UserStatusCache.invalidate`, `RefreshTokenRepository.revoke_all_for_user`, `require_admin` (Task 3 / existing).
- Produces: `UserActiveRequest {is_active: bool}`, `UserActiveResponse {user_id: str, is_active: bool}`; 404 `NotFoundError` for unknown ids; deactivation invalidates the cache entry and revokes the user's refresh tokens; 10/min rate limit; route decorator outermost (slowapi lesson from AUTHOR-006).

- [x] **Step 1: Failing tests** — `tests/unit/api/test_user_active_endpoint.py`:

```python
"""INFRA-008 — admin toggles a user's active flag; access changes immediately."""

import fastapi
import httpx
from fastapi import FastAPI

from src.api.auth.repository import InMemoryUserRepository
from src.api.auth.schemas import UserData
from src.api.auth.tokens import create_access_token
from src.config.settings import Settings

from .conftest import TEST_USER, make_auth_header

OTHER = UserData(id="user-2", email="other@example.com", password_hash="x", role="viewer")


def _seed(auth_app: FastAPI) -> None:
    auth_app.state.user_repo = InMemoryUserRepository([TEST_USER, OTHER])

    from src.api.dependencies import get_current_user

    @auth_app.get("/api/v1/whoami")
    async def whoami(
        current_user: object = fastapi.Depends(get_current_user),
    ) -> dict[str, str]:
        return {"user_id": current_user.sub}  # type: ignore[union-attr]


def _bearer(user_id: str, role: str, settings: Settings) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id, role, settings)}"}


class TestSetUserActive:
    async def test_admin_deactivates_and_reactivates(
        self, auth_app: FastAPI, auth_client: httpx.AsyncClient, auth_settings: Settings
    ) -> None:
        _seed(auth_app)
        admin = make_auth_header("admin", auth_settings)
        other = _bearer("user-2", "viewer", auth_settings)
        assert (await auth_client.get("/api/v1/whoami", headers=other)).status_code == 200

        response = await auth_client.patch(
            "/api/v1/auth/users/user-2/active", json={"is_active": False}, headers=admin
        )
        assert response.status_code == 200
        assert response.json() == {"user_id": "user-2", "is_active": False}
        # Cache invalidated → the very next request is rejected.
        assert (await auth_client.get("/api/v1/whoami", headers=other)).status_code == 401

        response = await auth_client.patch(
            "/api/v1/auth/users/user-2/active", json={"is_active": True}, headers=admin
        )
        assert response.status_code == 200
        assert (await auth_client.get("/api/v1/whoami", headers=other)).status_code == 200

    async def test_deactivation_revokes_refresh_tokens(
        self, auth_app: FastAPI, auth_client: httpx.AsyncClient, auth_settings: Settings
    ) -> None:
        _seed(auth_app)
        from datetime import UTC, datetime, timedelta

        auth_app.state.refresh_repo.save(
            "user-2", "refresh-2", datetime.now(UTC) + timedelta(days=1)
        )
        admin = make_auth_header("admin", auth_settings)
        await auth_client.patch(
            "/api/v1/auth/users/user-2/active", json={"is_active": False}, headers=admin
        )
        assert auth_app.state.refresh_repo.get("refresh-2").revoked is True

    async def test_editor_is_forbidden(
        self, auth_app: FastAPI, auth_client: httpx.AsyncClient, auth_settings: Settings
    ) -> None:
        _seed(auth_app)
        response = await auth_client.patch(
            "/api/v1/auth/users/user-2/active",
            json={"is_active": False},
            headers=make_auth_header("editor", auth_settings),
        )
        assert response.status_code == 403

    async def test_unknown_user_is_404(
        self, auth_app: FastAPI, auth_client: httpx.AsyncClient, auth_settings: Settings
    ) -> None:
        _seed(auth_app)
        response = await auth_client.patch(
            "/api/v1/auth/users/ghost/active",
            json={"is_active": False},
            headers=make_auth_header("admin", auth_settings),
        )
        assert response.status_code == 404
```

- [x] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/unit/api/test_user_active_endpoint.py -q`
Expected: 4 failures with 404/405 from the missing route.

- [x] **Step 3: Implement**

`src/api/auth/schemas.py` — append:

```python
class UserActiveRequest(BaseModel):
    is_active: bool


class UserActiveResponse(BaseModel):
    user_id: str
    is_active: bool
```

`src/api/routers/auth.py` — add imports and the route:

```python
import structlog
from fastapi import APIRouter, Depends, Request
from starlette.responses import Response

from src.api.auth.schemas import (
    LoginRequest,
    RefreshRequest,
    TokenPayload,
    TokenResponse,
    UserActiveRequest,
    UserActiveResponse,
)
from src.api.auth.service import AuthService
from src.api.dependencies import require_admin
from src.api.errors import NotFoundError
from src.api.rate_limiter import limiter

logger = structlog.get_logger()
```

```python
@auth_router.patch(
    "/auth/users/{user_id}/active",
    response_model=UserActiveResponse,
    summary="Activate or deactivate a user (admin only)",
)
@limiter.limit("10/minute")
async def set_user_active(
    request: Request,
    user_id: str,
    body: UserActiveRequest,
    admin: TokenPayload = Depends(require_admin),
) -> UserActiveResponse:
    """INFRA-008 — takes effect on the user's next request (cache invalidated)."""
    user = request.app.state.user_repo.set_active(user_id, body.is_active)
    if user is None:
        raise NotFoundError(message=f"User '{user_id}' not found")
    request.app.state.user_status_cache.invalidate(user_id)
    if not body.is_active:
        request.app.state.refresh_repo.revoke_all_for_user(user_id)
    logger.info(
        "user_active_changed",
        user_id=user_id,
        is_active=body.is_active,
        changed_by=admin.sub,
    )
    return UserActiveResponse(user_id=user_id, is_active=user.is_active)
```

Check `NotFoundError.__init__` in `src/api/errors.py` for its keyword names before writing the raise (it may take `resource`/`resource_id` rather than `message`; use whatever it defines).

- [x] **Step 4: Run to verify they pass**

Run: `uv run pytest tests/unit/api/test_user_active_endpoint.py tests/unit/api/ -q`
Expected: all pass.

- [x] **Step 5: Commit**

```bash
git add src/api/routers/auth.py src/api/auth/schemas.py tests/unit/api/test_user_active_endpoint.py
git commit -m "feat(auth): admin PATCH /auth/users/{id}/active with cache invalidation (INFRA-008)"
```

---

### Task 5: Shared `ToastProvider` / `useToast`

**Files:**
- Create: `frontend/src/components/ui/toaster.tsx`, `frontend/src/components/ui/toaster.test.tsx`
- Modify: `frontend/src/app/providers.tsx`

**Interfaces:**
- Produces: `export type ShowToast = (message: string, ms?: number) => void`; `export const DEFAULT_TOAST_MS = 4000`; `export function ToastProvider({ children })`; `export function useToast(): { showToast: ShowToast }` (throws outside the provider so a missing mount fails loudly in tests).

- [x] **Step 1: Failing test** — `frontend/src/components/ui/toaster.test.tsx`:

```tsx
import { describe, it, expect, vi, afterEach } from "vitest";
import { act, render, renderHook, screen } from "@testing-library/react";
import { ToastProvider, useToast, DEFAULT_TOAST_MS } from "./toaster";

function Trigger({ message, ms }: { message: string; ms?: number }) {
  const { showToast } = useToast();
  return (
    <button type="button" onClick={() => showToast(message, ms)}>
      fire
    </button>
  );
}

describe("ToastProvider / useToast", () => {
  afterEach(() => vi.useRealTimers());

  it("shows the message and hides it after the default duration", () => {
    vi.useFakeTimers();
    render(
      <ToastProvider>
        <Trigger message="Saved" />
      </ToastProvider>,
    );
    act(() => screen.getByText("fire").click());
    expect(screen.getByRole("status")).toHaveTextContent("Saved");
    act(() => vi.advanceTimersByTime(DEFAULT_TOAST_MS - 1));
    expect(screen.getByRole("status")).toBeInTheDocument();
    act(() => vi.advanceTimersByTime(1));
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("a newer toast replaces the old one and restarts the timer", () => {
    vi.useFakeTimers();
    render(
      <ToastProvider>
        <Trigger message="First" ms={1000} />
        <Trigger message="Second" ms={1000} />
      </ToastProvider>,
    );
    const [first, second] = screen.getAllByText("fire");
    act(() => first.click());
    act(() => vi.advanceTimersByTime(900));
    act(() => second.click());
    expect(screen.getByRole("status")).toHaveTextContent("Second");
    act(() => vi.advanceTimersByTime(900));
    // The first toast's timer must not have cleared the second one.
    expect(screen.getByRole("status")).toHaveTextContent("Second");
    act(() => vi.advanceTimersByTime(100));
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("useToast throws outside a provider", () => {
    expect(() => renderHook(() => useToast())).toThrow(/ToastProvider/);
  });
});
```

- [x] **Step 2: Run to verify it fails**

Run: `cd frontend && npx vitest run src/components/ui/toaster.test.tsx`
Expected: FAIL — cannot resolve `./toaster`.

- [x] **Step 3: Implement** — `frontend/src/components/ui/toaster.tsx`:

```tsx
"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

/**
 * INFRA-008 — one toaster for the whole dashboard. Replaces the three
 * hand-rolled `useState<string | null>` + `setTimeout` copies that lived
 * in the articles, settings and topics pages. Markup is unchanged.
 */

export const DEFAULT_TOAST_MS = 4000;

export type ShowToast = (message: string, ms?: number) => void;

interface ToastContextValue {
  showToast: ShowToast;
}

const ToastContext = createContext<ToastContextValue | null>(null);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [message, setMessage] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const clearTimer = useCallback(() => {
    if (timer.current) {
      clearTimeout(timer.current);
      timer.current = null;
    }
  }, []);

  const showToast = useCallback<ShowToast>(
    (text, ms = DEFAULT_TOAST_MS) => {
      clearTimer();
      setMessage(text);
      timer.current = setTimeout(() => {
        setMessage(null);
        timer.current = null;
      }, ms);
    },
    [clearTimer],
  );

  useEffect(() => clearTimer, [clearTimer]);

  const value = useMemo(() => ({ showToast }), [showToast]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      {message && (
        <div
          role="status"
          className="fixed bottom-6 right-6 z-50 rounded-lg bg-neutral-900 px-4 py-3 text-sm text-white shadow-lg"
        >
          {message}
        </div>
      )}
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used inside <ToastProvider>");
  return ctx;
}
```

`frontend/src/app/providers.tsx` — wrap children:

```tsx
import { ToastProvider } from "@/components/ui/toaster";
…
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <ToastProvider>{children}</ToastProvider>
      </TooltipProvider>
    </QueryClientProvider>
```

- [x] **Step 4: Run to verify it passes**

Run: `cd frontend && npx vitest run src/components/ui/toaster.test.tsx`
Expected: 3 passed.

- [x] **Step 5: Commit**

```bash
git add frontend/src/components/ui/toaster.tsx frontend/src/components/ui/toaster.test.tsx frontend/src/app/providers.tsx
git commit -m "feat(frontend): shared ToastProvider + useToast (INFRA-008)"
```

---

### Task 6: Migrate the three pages and two hooks to `useToast`

**Files:**
- Modify: `frontend/src/app/(dashboard)/articles/[id]/page.tsx`, `frontend/src/app/(dashboard)/settings/page.tsx`, `frontend/src/app/(dashboard)/topics/page.tsx`, `frontend/src/app/(dashboard)/topics/use-generate-actions.ts`, `frontend/src/app/(dashboard)/topics/use-generate-actions.test.ts`, `frontend/src/hooks/use-article-actions.ts`

**Interfaces:**
- Consumes: `useToast`, `ShowToast` (Task 5).
- Produces: `useGenerateActions({ showToast }: { showToast: ShowToast })` (was `{ setToast }`); `ArticleActionsDeps.showToast: ShowToast`. No page renders its own `role="status"` element any more.

- [x] **Step 1: Failing test** — in `use-generate-actions.test.ts` rename every `setToast` to `showToast` (variable names, the object passed to `useGenerateActions`, and the assertions). All existing `toHaveBeenCalledWith(<message>)` / `not.toHaveBeenCalledWith(...)` assertions stay as they are (the hook calls `showToast(message)` with a single argument).

Run: `cd frontend && npx vitest run "src/app/(dashboard)/topics/use-generate-actions.test.ts"`
Expected: FAIL — the hook ignores `showToast` and calls the now-undefined `setToast`.

- [x] **Step 2: Implement**

`use-generate-actions.ts` — delete `TOAST_DURATION_MS` and the inner `showToast` function; change the args interface and every `setToast(...)` call:

```ts
import type { ShowToast } from "@/components/ui/toaster";

interface UseGenerateActionsArgs {
  showToast: ShowToast;
}

export function useGenerateActions({ showToast }: UseGenerateActionsArgs): UseGenerateActionsResult {
  const router = useRouter();

  async function handleConfirm(topic: RankedTopic, articleParams?: ArticleParams) {
    if (!topic.id) {
      showToast(`Cannot start research — topic has no ID. Try scanning again.`);
      return;
    }
    showToast(`Starting research for "${topic.title}"…`);
    …
```

(and the same one-line substitutions in `handleCreateAndGenerate`).

`topics/page.tsx` — remove `const [toast, setToast] = useState<string | null>(null);`, the `{toast && (…)}` block, and the trailing `setTimeout(() => setToast(null), 5000);` in `handleCreateOnly`; add `import { useToast } from "@/components/ui/toaster";`, `const { showToast } = useToast();`, `useGenerateActions({ showToast })`, and replace the three `setToast(...)` calls in `handleCreateOnly` with `showToast(...)`. Drop `useState` from the react import if it becomes unused.

`settings/page.tsx` — remove the `toast` state, the inner `showToast` function and the `{toast && (…)}` block; add `const { showToast } = useToast();` and change the OAuth effect to:

```tsx
  useEffect(() => {
    if (!oauthToast) return;
    showToast(oauthToast);
    router.replace("/settings", { scroll: false });
  }, [oauthToast, router, showToast]);
```

`articles/[id]/page.tsx` — remove the `toast` state, the `showToast` `useCallback`, and the `{toast && (…)}` block; add `import { useToast } from "@/components/ui/toaster";` and `const { showToast } = useToast();`. Drop `useCallback`/`useState` from the react import if unused (keep `useMemo`). `useArticleActions({ id, refetch, showToast })` and `onToast={showToast}` stay as they are.

`hooks/use-article-actions.ts` — replace the `showToast` field type with the shared one:

```ts
import type { ShowToast } from "@/components/ui/toaster";

export interface ArticleActionsDeps {
  id: string;
  refetch: () => Promise<unknown>;
  showToast: ShowToast;
}
```

- [x] **Step 3: Verify**

Run: `cd frontend && npx vitest run && npx tsc --noEmit -p tsconfig.json 2>&1 | grep -c "error TS"`
Expected: all Vitest suites pass; the `tsc` error count is unchanged from `develop` (13 pre-existing errors in untouched settings/test files — record the number you see before and after). Also: `grep -rn 'role="status"' frontend/src/app` must return nothing.

- [x] **Step 4: Commit**

```bash
git add "frontend/src/app/(dashboard)" frontend/src/hooks/use-article-actions.ts
git commit -m "refactor(frontend): pages use the shared useToast (INFRA-008)"
```

---

### Task 7: File-size budget test (RED) + split `VisualStudio.tsx` (523 → 3 files)

**Files:**
- Create: `frontend/src/file-size-budget.test.ts`, `frontend/src/hooks/use-visual-studio.ts`, `frontend/src/components/visuals/VisualStudioSections.tsx`, `frontend/src/components/visuals/SpecListSection.tsx`
- Modify: `frontend/src/components/visuals/VisualStudio.tsx`

**Interfaces:**
- Produces: `useVisualStudio({ article, audiencePersona, focusSectionIndex })` returning `{ styles, pageDirection, setPageDirection, defaultStyleKey, setDefaultStyleKey, quality, setQuality, specs, lifecycles, planning, planError, totalCost, breakdown, focusedSectionTitle, renderedCount, canInsert, handlePlanVisuals, handleRenderSpec, skipSpec, readyVisuals }`; `export interface SpecLifecycle` moves to the hook file; `VisualStudioSections.tsx` exports `PanelHeader`, `PageArtDirectionField`, `DefaultStyleSection`, `RenderQualitySection`; `SpecListSection.tsx` exports `SpecListSection`. `VisualStudio.tsx` keeps exporting `VisualStudio`, `VisualStudioArticleContext`, `InsertedVisual`, `VisualStudioProps` unchanged so `VisualStudio.test.tsx` and `page.tsx` need no edits.

- [x] **Step 1: Write the budget test** — `frontend/src/file-size-budget.test.ts`:

```ts
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * INFRA-008 / CLAUDE.md "files < 200 lines" — enforced for every page and
 * component source file. Hooks, types, lib and mocks are tracked separately.
 */
const ROOTS = ["src/app", "src/components"];
const MAX_LINES = 200;
const SOURCE = /\.(ts|tsx)$/;
const EXCLUDED = /\.(test|spec)\.tsx?$/;

function walk(dir: string, out: string[] = []): string[] {
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) walk(full, out);
    else if (SOURCE.test(entry) && !EXCLUDED.test(entry)) out.push(full);
  }
  return out;
}

function lineCount(file: string): number {
  const text = readFileSync(file, "utf8");
  return text.split("\n").length - (text.endsWith("\n") ? 1 : 0);
}

describe("file size budget", () => {
  it("keeps every page/component source file within 200 lines", () => {
    const offenders = ROOTS.flatMap((root) => walk(join(process.cwd(), root)))
      .map((file) => ({ file: relative(process.cwd(), file), lines: lineCount(file) }))
      .filter((f) => f.lines > MAX_LINES);
    expect(offenders).toEqual([]);
  });
});
```

Run: `cd frontend && npx vitest run src/file-size-budget.test.ts`
Expected: FAIL listing exactly the six files: `VisualStudio.tsx` 523, `SpecCard.tsx` 413, `SavedAssetGallery.tsx` 355, `ImageImportModal.tsx` 288, `AIRewritePopover.tsx` 219, `outline-review-step.tsx` 204. This test stays red until Task 10.

- [x] **Step 2: Extract the hook** — create `frontend/src/hooks/use-visual-studio.ts`. Move, verbatim, from `VisualStudio.tsx`: the `SpecLifecycle` interface (add `export`), every `useState`/`useEffect`/`useMemo` block and the `applyDefaultStyle`, `handlePlanVisuals`, `handleRenderSpec` functions from the component body (lines 93–232 on `develop`). Wrap them as:

```ts
"use client";

import { useEffect, useMemo, useState } from "react";
import { planVisuals, renderSpec } from "@/lib/api/visuals";
import { getVisualStylesCached } from "@/lib/visuals/visualStyles";
import type {
  ImageSpec,
  PlanRequest,
  PlanResponse,
  RenderQuality,
  RenderResponse,
  SpecCardState,
  VisualStylesResponse,
} from "@/types/visuals";
import { QUALITY_TO_PROVIDER } from "@/types/visuals";
import type { VisualStudioArticleContext, InsertedVisual } from "@/components/visuals/VisualStudio";

export interface SpecLifecycle {
  state: SpecCardState;
  render: RenderResponse | null;
  error?: string;
}

export interface UseVisualStudioArgs {
  article: VisualStudioArticleContext;
  audiencePersona?: string | null;
  focusSectionIndex?: number | null;
}

/** State + orchestration for the Visual Studio panel (INFRA-008 split). */
export function useVisualStudio({ article, audiencePersona, focusSectionIndex }: UseVisualStudioArgs) {
  // …moved state, effects, memos, applyDefaultStyle, handlePlanVisuals, handleRenderSpec…

  const renderedCount = Object.values(lifecycles).filter((lc) => lc.state === "done").length;
  const canInsert = specs.length > 0 && renderedCount > 0;

  function skipSpec(id: string) {
    setSpecs((prev) => prev.filter((s) => s.id !== id));
  }

  function readyVisuals(): InsertedVisual[] {
    const ready: InsertedVisual[] = [];
    for (const spec of specs) {
      const lc = lifecycles[spec.id];
      if (lc?.state === "done" && lc.render) ready.push({ spec, render: lc.render });
    }
    return ready;
  }

  return {
    styles, pageDirection, setPageDirection, defaultStyleKey, setDefaultStyleKey,
    quality, setQuality, specs, lifecycles, planning, planError, totalCost, breakdown,
    focusedSectionTitle, renderedCount, canInsert, handlePlanVisuals, handleRenderSpec,
    skipSpec, readyVisuals,
  };
}
```

The type-only circular import (`VisualStudio.tsx` ⇄ hook) is erased at compile time; if `eslint` flags `import/no-cycle`, move `VisualStudioArticleContext` and `InsertedVisual` into `frontend/src/types/visuals.ts` and re-export them from `VisualStudio.tsx` (`export type { VisualStudioArticleContext, InsertedVisual } from "@/types/visuals";`).

- [x] **Step 3: Extract the presentational sections** — create `VisualStudioSections.tsx` with `"use client";`, imports (`cn`, `QUALITY_LABELS`, `QUALITY_PRICE_USD`, `QUALITY_TO_PROVIDER`, `RenderQuality`, `VisualStylesResponse`, `StyleChipRail`, `UsageBadge`) and the four functions `PanelHeader`, `PageArtDirectionField`, `DefaultStyleSection`, `RenderQualitySection` moved verbatim (lines 321–463) with `export` added. Create `SpecListSection.tsx` with `"use client";`, imports (`cn`, `SpecCard`, `ImageSpec`, `SpecLifecycle` from the hook) and `SpecListSection` moved verbatim (lines 464–523) with `export`.

- [x] **Step 4: Rewrite `VisualStudio.tsx`** to the three exported types (unchanged) plus:

```tsx
"use client";

import { cn } from "@/lib/utils";
import type { ImageSpec, RenderResponse } from "@/types/visuals";
import { useVisualStudio } from "@/hooks/use-visual-studio";
import { SpecListSection } from "./SpecListSection";
import {
  DefaultStyleSection,
  PageArtDirectionField,
  PanelHeader,
  RenderQualitySection,
} from "./VisualStudioSections";

/* …existing doc comment + VisualStudioArticleContext / InsertedVisual / VisualStudioProps… */

export function VisualStudio({ article, audiencePersona, onInsertIntoArticle, onClose, focusSectionIndex, className }: VisualStudioProps) {
  const studio = useVisualStudio({ article, audiencePersona, focusSectionIndex });

  function handleInsert() {
    const ready = studio.readyVisuals();
    if (ready.length > 0) onInsertIntoArticle?.(ready);
  }

  return (
    <aside data-testid="visual-studio-panel" className={cn("flex h-full w-full max-w-[560px] flex-col gap-5 rounded-lg border border-neutral-200 bg-white p-6 shadow-sm", className)} aria-label="Visual Studio">
      <PanelHeader specCount={studio.specs.length} renderedCount={studio.renderedCount} totalCost={studio.totalCost} breakdown={studio.breakdown} onClose={onClose} />
      {/* focus banner, action buttons, fields, quality, planError, SpecListSection — JSX moved verbatim,
          with `planning`→`studio.planning`, `handlePlanVisuals`→`studio.handlePlanVisuals`,
          the Insert button's `disabled` → `!studio.canInsert`, `pageDirection`/`setPageDirection`,
          `styles?.styles ?? []`→`studio.styles?.styles ?? []`, `quality`/`setQuality`,
          `planError`→`studio.planError`, and SpecListSection props
          `specs={studio.specs} lifecycles={studio.lifecycles} onRender={studio.handleRenderSpec}
           onSkip={studio.skipSpec} focusSectionIndex={focusSectionIndex ?? null}` */}
    </aside>
  );
}
```

- [x] **Step 5: Verify behaviour is unchanged**

Run: `cd frontend && npx vitest run src/components/visuals && wc -l src/components/visuals/VisualStudio.tsx src/components/visuals/VisualStudioSections.tsx src/components/visuals/SpecListSection.tsx src/hooks/use-visual-studio.ts`
Expected: `VisualStudio.test.tsx` passes unmodified; every listed file ≤ 200 lines.

- [x] **Step 6: Commit**

```bash
git add frontend/src/file-size-budget.test.ts frontend/src/hooks/use-visual-studio.ts frontend/src/components/visuals/VisualStudio.tsx frontend/src/components/visuals/VisualStudioSections.tsx frontend/src/components/visuals/SpecListSection.tsx
git commit -m "refactor(frontend): split VisualStudio into hook + sections; add file-size budget test (INFRA-008)"
```

---

### Task 8: Split `SpecCard.tsx` (413 → 3 files)

**Files:**
- Create: `frontend/src/components/visuals/SpecCardMedia.tsx`, `frontend/src/components/visuals/SpecCardFooter.tsx`
- Modify: `frontend/src/components/visuals/SpecCard.tsx`

**Interfaces:**
- Produces: `SpecCardMedia.tsx` exports `SpecMedia` (props `{ spec, state, render, generationEta?, errorMessage? }` exactly as today) and keeps the private `Spinner` + `aspectToStyle`; `SpecCardFooter.tsx` exports `SpecFooter` (props unchanged: `spec, state, refineNote, onRefineNoteChange, onPlan?, onRegenerate?, onEdit?, onRetryCheaper?, onSkip?, onRefine?`). `SpecCard.tsx` keeps `SpecCard`, `SpecCardProps`, `SpecHeader`, `StatePill`, `humanizeStyleKey`.

- [x] **Step 1: Move** `SpecMedia` (lines 159–271), `Spinner` (387–395) and `aspectToStyle` (397–406) verbatim into `SpecCardMedia.tsx` with header:

```tsx
"use client";

import { pickGeneratedImageSrc } from "@/lib/visuals/imageSrc";
import type { ImageSpec, RenderResponse, SpecCardState } from "@/types/visuals";
```

(add `import { cn } from "@/lib/utils";` only if `SpecMedia` uses `cn` — check the moved body). Export `SpecMedia`.

Move `SpecFooter` (lines 272–385) verbatim into `SpecCardFooter.tsx` with header:

```tsx
"use client";

import type { ImageSpec, SpecCardState } from "@/types/visuals";
```

(again add `cn` only if used). Export `SpecFooter`. If `SpecFooter` references `Spinner`, export `Spinner` from `SpecCardMedia.tsx` and import it.

In `SpecCard.tsx` delete the moved code, drop now-unused imports (`pickGeneratedImageSrc`, `RenderResponse` if unused), and add `import { SpecMedia } from "./SpecCardMedia";` and `import { SpecFooter } from "./SpecCardFooter";`.

- [x] **Step 2: Verify**

Run: `cd frontend && npx vitest run src/components/visuals/SpecCard.test.tsx src/components/visuals/VisualStudio.test.tsx && wc -l src/components/visuals/SpecCard*.tsx`
Expected: tests pass unmodified; each file ≤ 200 lines.

- [x] **Step 3: Commit**

```bash
git add frontend/src/components/visuals/SpecCard.tsx frontend/src/components/visuals/SpecCardMedia.tsx frontend/src/components/visuals/SpecCardFooter.tsx
git commit -m "refactor(frontend): split SpecCard media/footer (INFRA-008)"
```

---

### Task 9: Split `SavedAssetGallery.tsx` (355) and `ImageImportModal.tsx` (288)

**Files:**
- Create: `frontend/src/lib/visuals/savedAssetFormat.ts`, `frontend/src/lib/visuals/savedAssetFormat.test.ts`, `frontend/src/components/visuals/SavedAssetFacets.tsx`, `frontend/src/components/visuals/SavedAssetGrid.tsx`, `frontend/src/components/visuals/ImageUploadTab.tsx`, `frontend/src/components/visuals/ImageFetchUrlTab.tsx`
- Modify: `frontend/src/components/visuals/SavedAssetGallery.tsx`, `frontend/src/components/visuals/ImageImportModal.tsx`

**Interfaces:**
- Produces: `savedAssetFormat.ts` exports `humanize(key: string): string` and `aspectStyle(aspect: string): string` (bodies moved verbatim from `SavedAssetGallery.tsx` lines 339–355); `SavedAssetFacets.tsx` exports `RoleFilterRail`, `FacetSidebar` (and keeps `FacetSection`, `ROLE_FILTERS` private); `SavedAssetGrid.tsx` exports `AssetGrid`, `EmptyState`; `ImageUploadTab.tsx` exports `UploadTab` and owns `ACCEPTED_MIME`; `ImageFetchUrlTab.tsx` exports `FetchFromUrlTab`. Props of every moved component are unchanged.

- [x] **Step 1: Failing test for the pure helpers** — `frontend/src/lib/visuals/savedAssetFormat.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { aspectStyle, humanize } from "./savedAssetFormat";

describe("savedAssetFormat", () => {
  it("humanizes snake_case keys", () => {
    expect(humanize("feature_card")).toBe("Feature Card");
    expect(humanize("hero")).toBe("Hero");
  });

  it("maps aspect strings to a CSS aspect-ratio value", () => {
    expect(aspectStyle("16:9")).toBe("16 / 9");
    expect(aspectStyle("1:1")).toBe("1 / 1");
  });
});
```

Before writing the expectations, read the current `humanize` / `aspectStyle` bodies (lines 339–355) and mirror their exact behaviour (e.g. if `aspectStyle` returns a Tailwind class instead of a CSS value, assert that). Run the test; expected: FAIL (module missing).

- [x] **Step 2: Move code**

`savedAssetFormat.ts`: the two helpers verbatim, exported. `SavedAssetFacets.tsx` (`"use client"`, imports `cn` + `humanize`): `ROLE_FILTERS`, `RoleFilterRail`, `FacetSidebar`, `FacetSection` (lines 160–272) verbatim; export the first two. `SavedAssetGrid.tsx` (`"use client"`, imports `cn`, `humanize`, `aspectStyle`, `SavedAssetItem`): `AssetGrid`, `EmptyState` (lines 273–338) verbatim, exported. `SavedAssetGallery.tsx`: delete moved code, import `RoleFilterRail`, `FacetSidebar` from `./SavedAssetFacets` and `AssetGrid`, `EmptyState` from `./SavedAssetGrid`; drop unused imports.

`ImageUploadTab.tsx` (`"use client"`, imports `useState`, `cn` if used, `uploadBrandAsset`, `UploadResponse`): `ACCEPTED_MIME` + `UploadTab` (lines 133–211) verbatim, `UploadTab` exported. `ImageFetchUrlTab.tsx` (`"use client"`, imports `useState`, `cn` if used, `fetchImageFromUrl`, `FetchUrlResponse`): `FetchFromUrlTab` (lines 212–288) verbatim, exported. `ImageImportModal.tsx` keeps the modal shell + `TabBar`, imports the two tabs, drops unused imports.

- [x] **Step 3: Verify**

Run: `cd frontend && npx vitest run src/components/visuals src/lib/visuals && wc -l src/components/visuals/SavedAsset*.tsx src/components/visuals/Image*.tsx`
Expected: `SavedAssetGallery.test.tsx` and `ImageImportModal.test.tsx` pass unmodified; helper test passes; each file ≤ 200 lines.

- [x] **Step 4: Commit**

```bash
git add frontend/src/lib/visuals/savedAssetFormat.ts frontend/src/lib/visuals/savedAssetFormat.test.ts frontend/src/components/visuals/SavedAssetGallery.tsx frontend/src/components/visuals/SavedAssetFacets.tsx frontend/src/components/visuals/SavedAssetGrid.tsx frontend/src/components/visuals/ImageImportModal.tsx frontend/src/components/visuals/ImageUploadTab.tsx frontend/src/components/visuals/ImageFetchUrlTab.tsx
git commit -m "refactor(frontend): split SavedAssetGallery and ImageImportModal (INFRA-008)"
```

---

### Task 10: Split `AIRewritePopover.tsx` (219) and `outline-review-step.tsx` (204) — budget test goes GREEN

**Files:**
- Create: `frontend/src/hooks/use-ai-rewrite.ts`, `frontend/src/lib/research/outline-edit.ts`, `frontend/src/lib/research/outline-edit.test.ts`
- Modify: `frontend/src/components/article/AIRewritePopover.tsx`, `frontend/src/components/research/outline-review-step.tsx`

**Interfaces:**
- Produces: `useAIRewrite({ sectionId, scope, paragraphIndex, currentMarkdown, audiencePersona })` returning `{ state, runRewrite(promptText: string): Promise<void>, runPreset(preset: TonePreset): Promise<void>, reset(): void }` with `state: { busy: boolean; error: string | null; result: SectionRewriteResponse | null }`; `outline-edit.ts` exports `averageBudget(sections)`, `newSection(index, sections)`, `reindex(sections)`, `swapSections(sections, index, direction: -1 | 1): OutlineSection[]` (returns the input unchanged when the target is out of range).

- [x] **Step 1: Failing test** — `frontend/src/lib/research/outline-edit.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { averageBudget, newSection, reindex, swapSections } from "./outline-edit";
import type { OutlineSection } from "@/types/research";

function section(index: number, words: number): OutlineSection {
  return { index, title: `S${index}`, description: "", key_points: [], target_word_count: words, relevant_facets: [] };
}

describe("outline-edit helpers", () => {
  it("averageBudget rounds to 50 and defaults to 300", () => {
    expect(averageBudget([])).toBe(300);
    expect(averageBudget([section(0, 420), section(1, 380)])).toBe(400);
    expect(averageBudget([section(0, 10)])).toBe(50);
  });

  it("newSection inherits the average budget", () => {
    const s = newSection(2, [section(0, 200), section(1, 400)]);
    expect(s).toMatchObject({ index: 2, title: "New section", target_word_count: 300 });
  });

  it("reindex renumbers sequentially", () => {
    expect(reindex([section(5, 1), section(9, 1)]).map((s) => s.index)).toEqual([0, 1]);
  });

  it("swapSections moves a section and reindexes; out-of-range is a no-op", () => {
    const input = [section(0, 1), section(1, 2), section(2, 3)];
    expect(swapSections(input, 0, 1).map((s) => s.target_word_count)).toEqual([2, 1, 3]);
    expect(swapSections(input, 0, 1).map((s) => s.index)).toEqual([0, 1, 2]);
    expect(swapSections(input, 0, -1)).toBe(input);
    expect(swapSections(input, 2, 1)).toBe(input);
  });
});
```

Run: `cd frontend && npx vitest run src/lib/research/outline-edit.test.ts` → FAIL (module missing).

- [x] **Step 2: Implement `outline-edit.ts`** — move `averageBudget`, `newSection`, `reindex` verbatim (with `export`), keep the AUTHOR-008 doc comment, and add:

```ts
/** Swap `index` with its neighbour in `direction`; returns the same array when out of range. */
export function swapSections(
  sections: OutlineSection[],
  index: number,
  direction: -1 | 1,
): OutlineSection[] {
  const target = index + direction;
  if (target < 0 || target >= sections.length) return sections;
  const next = [...sections];
  [next[index], next[target]] = [next[target], next[index]];
  return reindex(next);
}
```

In `outline-review-step.tsx` import the four helpers and simplify `moveSection`:

```ts
  function moveSection(index: number, direction: -1 | 1) {
    if (!local) return;
    const next = swapSections(local.sections, index, direction);
    if (next !== local.sections) update({ sections: next });
  }
```

- [x] **Step 3: Extract `useAIRewrite`** — `frontend/src/hooks/use-ai-rewrite.ts`:

```ts
"use client";

import { useState } from "react";
import { applyTonePreset, rewriteSectionProse } from "@/lib/api/content";
import type { SectionRewriteResponse, TonePreset } from "@/types/content";

export interface AIRewriteState {
  busy: boolean;
  error: string | null;
  result: SectionRewriteResponse | null;
}

export interface UseAIRewriteArgs {
  sectionId: string;
  scope: "section" | "paragraph";
  paragraphIndex?: number;
  currentMarkdown: string;
  audiencePersona?: string | null;
}

const INITIAL_STATE: AIRewriteState = { busy: false, error: null, result: null };

/** Rewrite / tone-preset calls for the AI rewrite popover (INFRA-008 split). */
export function useAIRewrite({ sectionId, scope, paragraphIndex, currentMarkdown, audiencePersona }: UseAIRewriteArgs) {
  const [state, setState] = useState<AIRewriteState>(INITIAL_STATE);

  async function runRewrite(promptText: string) {
    /* body moved verbatim from AIRewritePopover.runRewrite */
  }

  async function runPreset(preset: TonePreset) {
    /* body moved verbatim from AIRewritePopover.runPreset */
  }

  function reset() {
    setState(INITIAL_STATE);
  }

  return { state, runRewrite, runPreset, reset };
}
```

`AIRewritePopover.tsx`: delete `PopoverState`, `INITIAL_STATE`, `runRewrite`, `runPreset` and the `state` `useState`; keep `instruction` state; `const { state, runRewrite, runPreset, reset } = useAIRewrite({ sectionId, scope, paragraphIndex, currentMarkdown, audiencePersona });`; `handleReject` becomes `reset(); setInstruction("");`. Drop the now-unused `applyTonePreset` / `rewriteSectionProse` / `SectionRewriteResponse` imports. **`AIRewritePopover.test.tsx` mocks `@/lib/api/content`** — the hook imports from the same module path, so the mocks keep working; run it to confirm.

- [x] **Step 4: Verify — the budget test must now pass**

Run: `cd frontend && npx vitest run`
Expected: every suite green, including `src/file-size-budget.test.ts` with `offenders = []`.

- [x] **Step 5: Commit**

```bash
git add frontend/src/hooks/use-ai-rewrite.ts frontend/src/lib/research/outline-edit.ts frontend/src/lib/research/outline-edit.test.ts frontend/src/components/article/AIRewritePopover.tsx frontend/src/components/research/outline-review-step.tsx
git commit -m "refactor(frontend): extract useAIRewrite + outline-edit helpers; all components ≤200 lines (INFRA-008)"
```

---

### Task 11: Full verification, docs, PR

**Files:**
- Modify: `project-management/PROGRESS.md`, `project-management/BACKLOG.md`, `CLAUDE.md`, this plan (tick boxes)

- [x] **Step 1: Backend gates**

```bash
COGNIFY_ANTHROPIC_API_KEY= uv run pytest tests/unit/ -q
uv run ruff check src/ tests/ && uv run ruff format --check src/ tests/ && uv run mypy src/ --ignore-missing-imports
```

Expected: 0 failures (count ≥ 1701 + ~20 new); ruff/mypy clean. Fix with `uv run ruff format src/ tests/` if the format check fails.

- [x] **Step 2: Frontend gates**

```bash
cd frontend && npx vitest run && npm run lint && npx tsc --noEmit 2>&1 | grep -c "error TS"
```

Expected: all suites pass (≥ 557 + new); eslint clean for touched files; `tsc` error count equal to the `develop` baseline recorded in Task 6.

- [x] **Step 3: Live smoke (Docker, optional but recommended)** — `docker compose up --build -d api` from the main checkout on this branch, then: `curl -s localhost:8000/api/v1/health | jq .checks.embedding` shows `degraded` within the first seconds after boot and `ok` shortly after (with the baked HF cache this is < 1 s — check the api log for `embedding_warmup_started` → `embedding_model_loaded`); login as admin, `PATCH /api/v1/auth/users/user-3/active {"is_active": false}` → a viewer token for `user-3` gets 401 `user_inactive` on `/api/v1/articles`; reactivate → 200. In the dashboard: Settings → change a domain → toast appears bottom-right and disappears after 4 s; article page → Insert visuals toast still shows.

- [x] **Step 4: Docs**

- `PROGRESS.md`: Epic 11 table row INFRA-008 → `Done (2026-08-28, PR pending; …)` with the three deviations above; add a numbered entry to the RESUME block (what shipped, the deviations, the follow-ups: backend >200-line files, hooks/types over 200 lines, lifespan↔bootstrap convergence, dead `@limiter.limit` order sweep, real user table + enforced role re-check).
- `BACKLOG.md`: INFRA-008 row `— **DONE** (2026-08-28)`; Epic 11 summary counts (Done 10 / Remaining 7 / ~33 SP); velocity `393 SP`.
- `CLAUDE.md` Current Status: one sentence for INFRA-008 (warm-up + `/health.embedding`, `is_active` re-check + `PATCH /auth/users/{id}/active`, `useToast`, file-size budget test) and update **Next action** to AUTHOR-009/010 or PUBLISH-002.
- Tick every checkbox in this plan.

- [x] **Step 5: Commit + PR**

```bash
git add project-management/ CLAUDE.md docs/superpowers/plans/2026-08-28-infra-008-warmup-recheck-toaster-splits.md
git commit -m "docs: INFRA-008 done — progress/backlog/CLAUDE status"
git push -u origin feature/INFRA-008-warmup-recheck-splits
gh pr create --base develop --title "INFRA-008: embedding warm-up, live user re-check, shared toaster, component splits" --body-file <(cat <<'EOF'
## Summary
- `EmbeddingService.warm_up_in_background()` at API boot (`COGNIFY_EMBEDDING_WARMUP`, default on); `try_embed()` returns `None` only while a warm-up is in flight → `MilvusRetriever` degrades to no-RAG instead of blocking the event loop; `/health` reports `embedding: ok|degraded|unavailable`. Worker path unchanged.
- `UserData.is_active` + `UserStatusCache` (`COGNIFY_AUTH_RECHECK_TTL_SECONDS`, 30 s) consulted by `get_current_user`; `AuthService.refresh` rejects inactive users; admin `PATCH /auth/users/{id}/active` invalidates the cache and revokes refresh tokens.
- Frontend `ToastProvider`/`useToast` replaces three hand-rolled toasts.
- `VisualStudio`, `SpecCard`, `SavedAssetGallery`, `ImageImportModal`, `AIRewritePopover`, `outline-review-step` split under 200 lines; `src/file-size-budget.test.ts` enforces it.

## Deviations from program plan §5.9 (documented in PROGRESS.md)
- Role drift is logged (`auth_role_drift`), not enforced; unknown-to-repo users keep their token claims. Rationale: no user table / role management exists yet; enforcing would break ~125 fixture usages for no live benefit.

## Test plan
- [ ] backend unit suite green, ruff/mypy clean
- [ ] frontend vitest green incl. budget test, eslint clean, tsc baseline unchanged
- [ ] live smoke: health `embedding` transitions; deactivate → 401 → reactivate → 200; toasts on settings/articles pages

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)
```

(If `--body-file <(…)` is unavailable in the shell, write the body to the scratchpad and pass the path.)

---

## Self-review

- **Spec coverage**: §5.10 warm-up + `try_embed` + retriever skip → Tasks 1–2. §5.9 role/active re-check with 30 s cache → Tasks 3–4 (role: logged only — deviation #1). Phase B row "shared `useToast` replacing hand-rolled toasts" → Tasks 5–6. "split `articles/[id]/page.tsx` & `VisualStudio.tsx` under 200 l." → `page.tsx` already 195 l. since AUTHOR-006; `VisualStudio.tsx` Task 7; the acceptance criterion "no page/component file over 200 lines" → Tasks 7–10 + the budget test. Acceptance "deactivating a user blocks their next request within 30 s without restart" → Task 3 TTL test + Task 4 immediate invalidation.
- **Placeholders**: the "moved verbatim" steps name the exact function and line range on `develop` and give the new file headers; Task 7's JSX comment lists every identifier substitution. No TBDs.
- **Type consistency**: `ShowToast` (Task 5) is the type used by `useGenerateActions` and `ArticleActionsDeps` (Task 6); `SpecLifecycle` is exported from the hook (Task 7) and imported by `SpecListSection`; `UserStatusCache.lookup(user_id, repo)` signature is the same in Task 3 tests, `dependencies.py`, and Task 4's `invalidate` use; `set_active` returns `UserData | None` everywhere.
