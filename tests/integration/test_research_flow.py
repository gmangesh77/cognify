"""Integration test: full research flow through API → service → orchestrator."""

import json
from collections.abc import AsyncGenerator
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from src.agents.research.orchestrator import build_graph
from src.agents.research.runner import LangGraphResearchOrchestrator
from src.agents.research.stub import stub_research_agent
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
from src.services.task_dispatch import AsyncIODispatcher
from tests.unit.api.conftest import make_auth_header


def _generate_test_keys() -> tuple[str, str]:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    return private_pem, public_pem


_PRIVATE_KEY, _PUBLIC_KEY = _generate_test_keys()


def _plan_json() -> str:
    facets = [
        {
            "index": i,
            "title": f"F{i}",
            "description": f"D{i}",
            "search_queries": [f"q{i}"],
        }
        for i in range(3)
    ]
    return json.dumps({"facets": facets, "reasoning": "Plan"})


def _eval_json() -> str:
    return json.dumps({"is_complete": True, "weak_facets": [], "reasoning": "Good"})


@pytest.fixture
def integration_settings() -> Settings:
    return Settings(
        jwt_private_key=_PRIVATE_KEY,
        jwt_public_key=_PUBLIC_KEY,
    )


@pytest.fixture
def integration_app(integration_settings: Settings) -> FastAPI:
    app = create_app(integration_settings)

    llm = FakeListChatModel(responses=[_plan_json(), _eval_json()])
    dispatcher = AsyncIODispatcher(timeout_seconds=10)
    graph = build_graph(llm, dispatcher, stub_research_agent)
    orchestrator = LangGraphResearchOrchestrator(graph)

    topic_id = uuid4()
    topic_repo = InMemoryTopicRepository()
    topic_repo.seed(
        TopicInput(id=topic_id, title="Test", description="D", domain="tech")
    )

    repos = ResearchRepositories(
        sessions=InMemoryResearchSessionRepository(),
        steps=InMemoryAgentStepRepository(),
        topics=topic_repo,
    )
    svc = ResearchService(repos, orchestrator)
    app.state.research_service = svc
    app.state._test_topic_id = str(topic_id)
    return app


@pytest.fixture
async def integration_client(
    integration_app: FastAPI,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=integration_app),
        base_url="http://test",
    ) as ac:
        yield ac


class TestResearchFlow:
    async def test_create_and_get_session(
        self,
        integration_client: httpx.AsyncClient,
        integration_settings: Settings,
        integration_app: FastAPI,
    ) -> None:
        topic_id = integration_app.state._test_topic_id
        headers = make_auth_header("editor", integration_settings)

        # Create session
        resp = await integration_client.post(
            "/api/v1/research/sessions",
            json={"topic_id": topic_id},
            headers=headers,
        )
        assert resp.status_code == 201
        session_id = resp.json()["session_id"]

        # Get session
        resp = await integration_client.get(
            f"/api/v1/research/sessions/{session_id}",
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["session_id"] == session_id
