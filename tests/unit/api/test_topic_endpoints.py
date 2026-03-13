from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import httpx
import pytest
from fastapi import FastAPI

from src.api.main import create_app
from src.config.settings import Settings
from tests.unit.services.conftest import MockEmbeddingService

from .conftest import _PRIVATE_KEY, _PUBLIC_KEY, make_auth_header


def _topic_payload(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "title": "Test Topic",
        "source": "hackernews",
        "trend_score": 75.0,
        "discovered_at": datetime.now(UTC).isoformat(),
        "velocity": 5.0,
        "domain_keywords": ["cyber"],
    }
    base.update(overrides)
    return base


def _rank_request(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "topics": [_topic_payload()],
        "domain": "cybersecurity",
        "domain_keywords": ["cyber"],
        "top_n": 10,
    }
    base.update(overrides)
    return base


@pytest.fixture
def topic_settings() -> Settings:
    return Settings(
        jwt_private_key=_PRIVATE_KEY,
        jwt_public_key=_PUBLIC_KEY,
    )


@pytest.fixture
def topic_app(topic_settings: Settings) -> FastAPI:
    app = create_app(topic_settings)
    app.state.embedding_service = MockEmbeddingService()
    return app


@pytest.fixture
async def topic_client(
    topic_app: FastAPI,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=topic_app),
        base_url="http://test",
    ) as ac:
        yield ac


class TestTopicEndpointAuth:
    async def test_no_token_returns_401(
        self,
        topic_client: httpx.AsyncClient,
    ) -> None:
        resp = await topic_client.post(
            "/api/v1/topics/rank",
            json=_rank_request(),
        )
        assert resp.status_code == 401

    async def test_viewer_returns_403(
        self,
        topic_client: httpx.AsyncClient,
        topic_settings: Settings,
    ) -> None:
        resp = await topic_client.post(
            "/api/v1/topics/rank",
            json=_rank_request(),
            headers=make_auth_header("viewer", topic_settings),
        )
        assert resp.status_code == 403

    async def test_editor_allowed(
        self,
        topic_client: httpx.AsyncClient,
        topic_settings: Settings,
    ) -> None:
        resp = await topic_client.post(
            "/api/v1/topics/rank",
            json=_rank_request(),
            headers=make_auth_header("editor", topic_settings),
        )
        assert resp.status_code == 200

    async def test_admin_allowed(
        self,
        topic_client: httpx.AsyncClient,
        topic_settings: Settings,
    ) -> None:
        resp = await topic_client.post(
            "/api/v1/topics/rank",
            json=_rank_request(),
            headers=make_auth_header("admin", topic_settings),
        )
        assert resp.status_code == 200


class TestTopicEndpointValidation:
    async def test_empty_topics_returns_422(
        self,
        topic_client: httpx.AsyncClient,
        topic_settings: Settings,
    ) -> None:
        resp = await topic_client.post(
            "/api/v1/topics/rank",
            json=_rank_request(topics=[]),
            headers=make_auth_header("editor", topic_settings),
        )
        assert resp.status_code == 422


class TestTopicEndpointSuccess:
    async def test_response_shape(
        self,
        topic_client: httpx.AsyncClient,
        topic_settings: Settings,
    ) -> None:
        resp = await topic_client.post(
            "/api/v1/topics/rank",
            json=_rank_request(),
            headers=make_auth_header("editor", topic_settings),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "ranked_topics" in data
        assert "duplicates_removed" in data
        assert "total_input" in data
        assert data["total_input"] == 1

    async def test_empty_after_filter(
        self,
        topic_client: httpx.AsyncClient,
        topic_settings: Settings,
    ) -> None:
        resp = await topic_client.post(
            "/api/v1/topics/rank",
            json=_rank_request(
                topics=[
                    _topic_payload(
                        title="cooking recipe",
                        domain_keywords=["food"],
                    )
                ],
                domain_keywords=["cybersecurity"],
            ),
            headers=make_auth_header("editor", topic_settings),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_returned"] == 0


class TestTopicEndpoint503:
    async def test_embedding_failure_returns_503(
        self,
        topic_settings: Settings,
    ) -> None:
        app = create_app(topic_settings)
        if hasattr(app.state, "embedding_service"):
            del app.state.embedding_service
        app.state.settings = Settings(
            jwt_private_key=topic_settings.jwt_private_key,
            jwt_public_key=topic_settings.jwt_public_key,
            embedding_model="nonexistent-model-xyz",
        )
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.post(
                "/api/v1/topics/rank",
                json=_rank_request(
                    topics=[
                        _topic_payload(title="topic 1"),
                        _topic_payload(title="topic 2"),
                    ]
                ),
                headers=make_auth_header("editor", topic_settings),
            )
            assert resp.status_code == 503
            data = resp.json()
            assert data["error"]["code"] == "embedding_service_unavailable"
