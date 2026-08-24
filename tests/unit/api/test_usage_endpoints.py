"""Contract tests for the AUTHOR-005 usage endpoints.

GET /api/v1/research/sessions/{id}/usage and GET /api/v1/articles/{id}/usage.
The article route must resolve the session via the draft's real session_id
(L-013): the draft's session_id here is deliberately different from the
article/topic id used as `topic_id`.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from src.api.errors import CognifyError, build_error_response
from src.api.rate_limiter import limiter
from src.api.routers.usage import usage_router
from src.config.settings import Settings
from src.models.content import ImageAsset
from src.models.content_pipeline import ArticleDraft
from src.models.llm_call import LlmCall
from src.models.research_db import ResearchSession
from src.services.content_repositories import (
    ContentRepositories,
    InMemoryArticleDraftRepository,
    InMemoryArticleRepository,
)
from src.utils.llm_call_repo import InMemoryLlmCallRepository
from tests.unit.api.conftest import make_auth_header
from tests.unit.api.test_content_endpoints import _PRIV, _PUB

SESSION_ID = uuid4()
ARTICLE_ID = uuid4()
TOPIC_ID = uuid4()

SESSION_URL = f"/api/v1/research/sessions/{SESSION_ID}/usage"
ARTICLE_URL = f"/api/v1/articles/{ARTICLE_ID}/usage"


class _NoResearch:
    async def get(self, session_id: UUID) -> ResearchSession | None:
        return None


@pytest.fixture
def settings() -> Settings:
    return Settings(
        jwt_private_key=_PRIV,
        jwt_public_key=_PUB,
        jwt_access_token_expire_minutes=15,
        llm_pricing_json={
            "claude-sonnet": {"input_per_mtok": 3.0, "output_per_mtok": 15.0}
        },
    )


def _install_handlers(app: FastAPI) -> None:
    @app.exception_handler(CognifyError)
    async def _err_handler(_: object, exc: CognifyError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=build_error_response(code=exc.code, message=exc.message),
        )


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    app = FastAPI()
    _install_handlers(app)
    app.state.settings = settings
    app.state.limiter = limiter
    app.state.llm_call_repo = InMemoryLlmCallRepository()
    app.state.content_repos = ContentRepositories(
        drafts=InMemoryArticleDraftRepository(),
        research=_NoResearch(),
        articles=InMemoryArticleRepository(),
    )
    app.include_router(usage_router, prefix="/api/v1")
    return app


@pytest.fixture
async def client(app: FastAPI) -> AsyncGenerator[httpx.AsyncClient, None]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _seed(app: FastAPI, *, with_draft: bool = True) -> None:
    await app.state.llm_call_repo.create(
        LlmCall(
            session_id=SESSION_ID,
            call_name="content_draft",
            model_name="claude-sonnet-4-6",
            input_tokens=1000,
            output_tokens=500,
            started_at=datetime.now(UTC),
        )
    )
    if with_draft:
        await app.state.content_repos.drafts.create(
            ArticleDraft(
                session_id=SESSION_ID,
                topic_id=TOPIC_ID,
                article_id=ARTICLE_ID,
                created_at=datetime.now(UTC),
                visuals=[
                    ImageAsset(
                        url="http://x/i.png",
                        metadata={"provider": "openai", "cost_usd": 0.04},
                    )
                ],
            )
        )


class TestSessionUsage:
    async def test_no_auth_header_returns_401(self, client: httpx.AsyncClient) -> None:
        resp = await client.get(SESSION_URL)
        assert resp.status_code == 401

    async def test_viewer_reads_hand_computed_usage(
        self, app: FastAPI, client: httpx.AsyncClient, settings: Settings
    ) -> None:
        await _seed(app)
        resp = await client.get(
            SESSION_URL, headers=make_auth_header("viewer", settings)
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["session_id"] == str(SESSION_ID)
        assert body["llm_calls"] == 1
        assert body["input_tokens"] == 1000
        assert body["output_tokens"] == 500
        assert body["images"] == 1
        # 1000*3/1e6 + 500*15/1e6 = 0.0105 tokens + 0.04 image
        assert body["cost_usd"] == 0.0505
        ops = {o["op"]: o for o in body["by_operation"]}
        assert ops["content_draft"]["llm_calls"] == 1
        assert ops["content_draft"]["cost_usd"] == 0.0105
        assert ops["images"]["cost_usd"] == 0.04

    async def test_unknown_session_returns_zero_usage(
        self, client: httpx.AsyncClient, settings: Settings
    ) -> None:
        resp = await client.get(
            f"/api/v1/research/sessions/{uuid4()}/usage",
            headers=make_auth_header("viewer", settings),
        )
        assert resp.status_code == 200
        assert resp.json()["llm_calls"] == 0
        assert resp.json()["cost_usd"] == 0.0

    async def test_invalid_uuid_returns_422(
        self, client: httpx.AsyncClient, settings: Settings
    ) -> None:
        resp = await client.get(
            "/api/v1/research/sessions/not-a-uuid/usage",
            headers=make_auth_header("viewer", settings),
        )
        assert resp.status_code == 422


class TestArticleUsage:
    async def test_resolves_session_via_draft_not_provenance(
        self, app: FastAPI, client: httpx.AsyncClient, settings: Settings
    ) -> None:
        await _seed(app)
        resp = await client.get(
            ARTICLE_URL, headers=make_auth_header("viewer", settings)
        )
        assert resp.status_code == 200
        assert resp.json()["session_id"] == str(SESSION_ID)
        assert resp.json()["llm_calls"] == 1

    async def test_unknown_article_returns_404(
        self, client: httpx.AsyncClient, settings: Settings
    ) -> None:
        resp = await client.get(
            f"/api/v1/articles/{uuid4()}/usage",
            headers=make_auth_header("viewer", settings),
        )
        assert resp.status_code == 404


class TestUnconfigured:
    async def test_missing_llm_repo_returns_503(
        self, app: FastAPI, client: httpx.AsyncClient, settings: Settings
    ) -> None:
        del app.state.llm_call_repo
        resp = await client.get(
            SESSION_URL, headers=make_auth_header("viewer", settings)
        )
        assert resp.status_code == 503
