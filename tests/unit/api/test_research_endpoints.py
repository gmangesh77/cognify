"""Tests for the research session API endpoints."""

from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI

from src.api.main import create_app
from src.config.settings import Settings
from src.models.research import TopicInput
from src.services.research import (
    InMemoryAgentStepRepository,
    InMemoryResearchSessionRepository,
    InMemoryTopicRepository,
    ResearchRepositories,
    ResearchService,
)
from tests.unit.api.conftest import make_auth_header


class FakeOrchestrator:
    async def run(self, session_id, topic):  # type: ignore[no-untyped-def]
        return {"status": "complete"}


@pytest.fixture
def test_topic_id() -> str:
    return str(uuid4())


@pytest.fixture
def research_app(auth_settings: Settings, test_topic_id: str) -> FastAPI:
    app = create_app(auth_settings)
    topic_repo = InMemoryTopicRepository()
    from uuid import UUID
    topic_repo.seed(TopicInput(
        id=UUID(test_topic_id),
        title="Test Topic",
        description="Desc",
        domain="tech",
    ))
    repos = ResearchRepositories(
        sessions=InMemoryResearchSessionRepository(),
        steps=InMemoryAgentStepRepository(),
        topics=topic_repo,
    )
    svc = ResearchService(repos, FakeOrchestrator())
    app.state.research_service = svc
    return app


@pytest.fixture
async def research_client(
    research_app: FastAPI,
) -> httpx.AsyncClient:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=research_app),
        base_url="http://test",
    ) as ac:
        yield ac  # type: ignore[misc]


class TestCreateSession:
    async def test_returns_201(
        self, research_client: httpx.AsyncClient, auth_settings: Settings, test_topic_id: str
    ) -> None:
        headers = make_auth_header("editor", auth_settings)
        resp = await research_client.post(
            "/api/v1/research/sessions",
            json={"topic_id": test_topic_id},
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "session_id" in data
        assert data["status"] == "planning"

    async def test_viewer_cannot_create(
        self, research_client: httpx.AsyncClient, auth_settings: Settings, test_topic_id: str
    ) -> None:
        headers = make_auth_header("viewer", auth_settings)
        resp = await research_client.post(
            "/api/v1/research/sessions",
            json={"topic_id": test_topic_id},
            headers=headers,
        )
        assert resp.status_code == 403

    async def test_invalid_topic_returns_404(
        self, research_client: httpx.AsyncClient, auth_settings: Settings
    ) -> None:
        headers = make_auth_header("editor", auth_settings)
        resp = await research_client.post(
            "/api/v1/research/sessions",
            json={"topic_id": str(uuid4())},
            headers=headers,
        )
        assert resp.status_code == 404


class TestGetSession:
    async def test_returns_session(
        self, research_client: httpx.AsyncClient, auth_settings: Settings, test_topic_id: str
    ) -> None:
        headers = make_auth_header("editor", auth_settings)
        create_resp = await research_client.post(
            "/api/v1/research/sessions",
            json={"topic_id": test_topic_id},
            headers=headers,
        )
        session_id = create_resp.json()["session_id"]
        resp = await research_client.get(
            f"/api/v1/research/sessions/{session_id}",
            headers=make_auth_header("viewer", auth_settings),
        )
        assert resp.status_code == 200
        assert resp.json()["session_id"] == session_id

    async def test_not_found(
        self, research_client: httpx.AsyncClient, auth_settings: Settings
    ) -> None:
        headers = make_auth_header("viewer", auth_settings)
        resp = await research_client.get(
            f"/api/v1/research/sessions/{uuid4()}",
            headers=headers,
        )
        assert resp.status_code == 404


class TestListSessions:
    async def test_returns_paginated_list(
        self, research_client: httpx.AsyncClient, auth_settings: Settings, test_topic_id: str
    ) -> None:
        headers = make_auth_header("editor", auth_settings)
        await research_client.post(
            "/api/v1/research/sessions",
            json={"topic_id": test_topic_id},
            headers=headers,
        )
        resp = await research_client.get(
            "/api/v1/research/sessions",
            headers=make_auth_header("viewer", auth_settings),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
