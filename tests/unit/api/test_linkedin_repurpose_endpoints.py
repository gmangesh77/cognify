"""Contract tests for /articles/{id}/repurpose/linkedin[/publish] (AUTHOR-013)."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from src.api.errors import NotFoundError
from src.config.settings import Settings
from src.models.publishing import PublicationResult, PublicationStatus
from tests.unit.api.conftest import make_auth_header
from tests.unit.api.test_content_endpoints import _build_article

ARTICLE_ID = uuid4()

VALID_JSON = (
    '{"hook": "AI agents are eating the backlog.", '
    '"beats": ["First beat.", "Second beat.", "Third beat."], '
    '"cta": "Read the full article.", '
    '"hashtags": ["ai", "cloud", "devops"]}'
)


def _content_service(llm=None) -> MagicMock:
    svc = MagicMock()
    svc.deps.llm = llm
    svc.repos.drafts.find_by_article_id = AsyncMock(return_value=None)
    svc.get_article = AsyncMock(return_value=_build_article(ARTICLE_ID))
    return svc


def _publishing_service(platforms: dict | None = None) -> MagicMock:
    svc = MagicMock()
    svc._platforms = platforms if platforms is not None else {"linkedin_post": object()}
    svc.publish = AsyncMock(
        return_value=PublicationResult(
            article_id=ARTICLE_ID,
            platform="linkedin_post",
            status=PublicationStatus.SUCCESS,
            external_id="urn:li:share:1",
            external_url="https://linkedin.com/feed/update/1",
        )
    )
    return svc


@pytest.fixture
def app(auth_settings: Settings) -> FastAPI:
    from src.api.main import create_app

    application = create_app(auth_settings)
    application.state.content_service = _content_service(
        llm=FakeListChatModel(responses=[VALID_JSON])
    )
    application.state.publishing_service = _publishing_service()
    return application


@pytest.fixture
async def client(app: FastAPI) -> AsyncGenerator[httpx.AsyncClient, None]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _repurpose_url(article_id=ARTICLE_ID) -> str:
    return f"/api/v1/articles/{article_id}/repurpose/linkedin"


def _publish_url(article_id=ARTICLE_ID) -> str:
    return f"/api/v1/articles/{article_id}/repurpose/linkedin/publish"


class TestRepurposeEndpoint:
    async def test_returns_draft_shape(
        self, client: httpx.AsyncClient, auth_settings: Settings
    ) -> None:
        resp = await client.post(
            _repurpose_url(),
            json={},
            headers=make_auth_header("editor", auth_settings),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["article_id"] == str(ARTICLE_ID)
        assert body["hook"] == "AI agents are eating the backlog."
        assert body["beats"] == ["First beat.", "Second beat.", "Third beat."]
        assert body["cta"] == "Read the full article."
        assert body["hashtags"] == ["#ai", "#cloud", "#devops"]
        assert "text" in body
        assert "char_count" in body
        assert "slop_score" in body
        assert "slop_rating" in body
        assert "model" in body
        assert body["truncated"] is False

    async def test_503_when_llm_not_configured(
        self, app: FastAPI, client: httpx.AsyncClient, auth_settings: Settings
    ) -> None:
        app.state.content_service = _content_service(llm=None)
        resp = await client.post(
            _repurpose_url(),
            json={},
            headers=make_auth_header("editor", auth_settings),
        )
        assert resp.status_code == 503

    async def test_viewer_forbidden(
        self, client: httpx.AsyncClient, auth_settings: Settings
    ) -> None:
        resp = await client.post(
            _repurpose_url(),
            json={},
            headers=make_auth_header("viewer", auth_settings),
        )
        assert resp.status_code == 403

    async def test_404_unknown_article(
        self, app: FastAPI, client: httpx.AsyncClient, auth_settings: Settings
    ) -> None:
        llm = FakeListChatModel(responses=[VALID_JSON])
        content_service = _content_service(llm=llm)
        content_service.get_article = AsyncMock(
            side_effect=NotFoundError("Article not found")
        )
        app.state.content_service = content_service
        resp = await client.post(
            _repurpose_url(),
            json={},
            headers=make_auth_header("editor", auth_settings),
        )
        assert resp.status_code == 404

    async def test_rate_limited_after_ten_calls_per_minute(
        self, app: FastAPI, client: httpx.AsyncClient, auth_settings: Settings
    ) -> None:
        app.state.content_service = _content_service(
            llm=FakeListChatModel(responses=[VALID_JSON] * 15)
        )
        headers = make_auth_header("editor", auth_settings)
        statuses = []
        for _ in range(11):
            resp = await client.post(_repurpose_url(), json={}, headers=headers)
            statuses.append(resp.status_code)
        assert statuses[:10] == [200] * 10
        assert statuses[10] == 429

    async def test_instruction_passed_through(
        self, client: httpx.AsyncClient, auth_settings: Settings
    ) -> None:
        resp = await client.post(
            _repurpose_url(),
            json={"instruction": "make it punchier"},
            headers=make_auth_header("editor", auth_settings),
        )
        assert resp.status_code == 200


class TestPublishLinkedinPostEndpoint:
    async def test_publish_passes_content_override(
        self, app: FastAPI, client: httpx.AsyncClient, auth_settings: Settings
    ) -> None:
        resp = await client.post(
            _publish_url(),
            json={"text": "Editor-approved post text"},
            headers=make_auth_header("editor", auth_settings),
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["status"] == "success"
        publishing_service = app.state.publishing_service
        publishing_service.publish.assert_awaited_once_with(
            ARTICLE_ID, "linkedin_post", content_override="Editor-approved post text"
        )

    async def test_503_when_platform_unregistered(
        self, app: FastAPI, client: httpx.AsyncClient, auth_settings: Settings
    ) -> None:
        app.state.publishing_service = _publishing_service(platforms={})
        resp = await client.post(
            _publish_url(),
            json={"text": "Editor-approved post text"},
            headers=make_auth_header("editor", auth_settings),
        )
        assert resp.status_code == 503

    async def test_422_over_char_limit(
        self, client: httpx.AsyncClient, auth_settings: Settings
    ) -> None:
        resp = await client.post(
            _publish_url(),
            json={"text": "x" * 3001},
            headers=make_auth_header("editor", auth_settings),
        )
        assert resp.status_code == 422

    async def test_viewer_forbidden(
        self, client: httpx.AsyncClient, auth_settings: Settings
    ) -> None:
        resp = await client.post(
            _publish_url(),
            json={"text": "short post"},
            headers=make_auth_header("viewer", auth_settings),
        )
        assert resp.status_code == 403
