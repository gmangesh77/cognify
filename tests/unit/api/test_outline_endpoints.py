"""Tests for the outline review / approve / cancel API endpoints
(AUTHOR-002, Task 4)."""

import asyncio
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import FastAPI
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from src.api.main import create_app
from src.config.settings import Settings
from src.models.research import TopicInput
from src.services.content import (
    ContentRepositories,
    ContentService,
    InMemoryArticleDraftRepository,
    InMemoryArticleRepository,
)
from src.services.content.outline_gate import OutlineGateService
from src.services.content_repositories import ContentDeps
from src.services.research import (
    InMemoryAgentStepRepository,
    InMemoryResearchSessionRepository,
    InMemoryTopicRepository,
    ResearchRepositories,
    ResearchService,
)
from src.services.session_tasks import SessionTaskRegistry
from tests.unit.api.conftest import make_auth_header
from tests.unit.services.test_content_service import (
    _four_section_outline_json,
    _four_section_queries_json,
    _make_retriever_mock,
)
from tests.unit.services.test_outline_gate import _full_pipeline_responses


class FakeOrchestrator:
    async def run(self, session_id, topic):  # type: ignore[no-untyped-def]
        return {"status": "complete"}


def _outline_only_pair() -> list[str]:
    return [_four_section_outline_json(), _four_section_queries_json()]


def _full_flow_responses() -> list[str]:
    """create (outline-only) + regenerate (outline-only) + approve (resume)."""
    return _outline_only_pair() * 2 + _full_pipeline_responses()


def _no_gate_responses() -> list[str]:
    """A single, uninterrupted outline -> full-article graph run."""
    return [_four_section_outline_json()] + _full_pipeline_responses()


def _make_outline_app(
    auth_settings: Settings, topic_id: UUID, llm_responses: list[str]
) -> FastAPI:
    app = create_app(auth_settings)
    topic_repo = InMemoryTopicRepository()
    topic_repo.seed(
        TopicInput(id=topic_id, title="Test Topic", description="Desc", domain="tech")
    )
    session_repo = InMemoryResearchSessionRepository()
    repos = ResearchRepositories(
        sessions=session_repo,
        steps=InMemoryAgentStepRepository(),
        topics=topic_repo,
    )
    app.state.research_service = ResearchService(repos, FakeOrchestrator())

    llm = FakeListChatModel(responses=llm_responses)
    content_repos = ContentRepositories(
        drafts=InMemoryArticleDraftRepository(),
        research=session_repo,
        articles=InMemoryArticleRepository(),
    )
    # A step_repo is required for ContentService._graph_deps() to build a
    # real ContentGraphDeps — without one, `stop_after_outline` is silently
    # ignored and the full pipeline graph runs regardless (matches the PG
    # wiring in main.py; only the no-DB dev fallback omits it).
    content_svc = ContentService(
        content_repos,
        ContentDeps(llm=llm, retriever=_make_retriever_mock()),
        step_repo=InMemoryAgentStepRepository(),
    )
    app.state.content_service = content_svc
    app.state.outline_gate = OutlineGateService(content_svc)
    app.state.session_tasks = SessionTaskRegistry()
    return app


async def _create_session(
    client: httpx.AsyncClient, headers: dict[str, str], topic_id: UUID, *, gate: bool
) -> str:
    resp = await client.post(
        "/api/v1/research/sessions",
        json={"topic_id": str(topic_id), "require_outline_approval": gate},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return str(resp.json()["session_id"])


async def _wait_for_status(
    session_repo: InMemoryResearchSessionRepository,
    session_id: str,
    target: str,
    *,
    attempts: int = 400,
) -> str:
    """Poll the in-memory repo directly (no HTTP, no rate limit).

    Drafting can involve a real (short-timeout) citation-URL reachability
    check against unreachable fake test domains, adding a few real
    seconds of wall-clock time — so this budget is generous (~8s).
    """
    sid = UUID(session_id)
    status = ""
    for _ in range(attempts):
        session = await session_repo.get(sid)
        if session is not None:
            status = session.status
            if status == target:
                return status
        await asyncio.sleep(0.02)
    return status


@pytest.fixture
def test_topic_id() -> UUID:
    return uuid4()


class TestFullOutlineReviewFlow:
    async def test_review_edit_regenerate_approve(
        self, auth_settings: Settings, test_topic_id: UUID
    ) -> None:
        app = _make_outline_app(auth_settings, test_topic_id, _full_flow_responses())
        session_repo = app.state.research_service._repos.sessions
        editor_headers = make_auth_header("editor", auth_settings)
        viewer_headers = make_auth_header("viewer", auth_settings)

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            session_id = await _create_session(
                client, editor_headers, test_topic_id, gate=True
            )

            status = await _wait_for_status(
                session_repo, session_id, "awaiting_outline_review"
            )
            assert status == "awaiting_outline_review"

            # GET outline
            resp = await client.get(
                f"/api/v1/research/sessions/{session_id}/outline",
                headers=viewer_headers,
            )
            assert resp.status_code == 200, resp.text
            outline = resp.json()["outline"]
            assert len(outline["sections"]) == 4

            # PUT with invalid outline (no sections) -> 422
            invalid = {**outline, "sections": []}
            resp = await client.put(
                f"/api/v1/research/sessions/{session_id}/outline",
                json=invalid,
                headers=editor_headers,
            )
            assert resp.status_code == 422, resp.text
            assert isinstance(resp.json()["detail"], list)

            # PUT valid outline (rename section 0) -> 200
            renamed = {
                **outline,
                "sections": [
                    {**outline["sections"][0], "title": "Renamed Intro"},
                    *outline["sections"][1:],
                ],
            }
            resp = await client.put(
                f"/api/v1/research/sessions/{session_id}/outline",
                json=renamed,
                headers=editor_headers,
            )
            assert resp.status_code == 200, resp.text
            assert resp.json()["outline"]["sections"][0]["title"] == "Renamed Intro"

            # GET reflects the rename
            resp = await client.get(
                f"/api/v1/research/sessions/{session_id}/outline",
                headers=viewer_headers,
            )
            assert resp.json()["outline"]["sections"][0]["title"] == "Renamed Intro"

            # Regenerate -> 200 with a fresh outline
            resp = await client.post(
                f"/api/v1/research/sessions/{session_id}/outline/regenerate",
                json={"instruction": "make it punchier"},
                headers=editor_headers,
            )
            assert resp.status_code == 200, resp.text
            assert len(resp.json()["outline"]["sections"]) == 4

            # Approve -> 202, generating_article
            resp = await client.post(
                f"/api/v1/research/sessions/{session_id}/outline/approve",
                headers=editor_headers,
            )
            assert resp.status_code == 202, resp.text
            assert resp.json()["status"] == "generating_article"

            final_status = await _wait_for_status(
                session_repo, session_id, "article_complete"
            )
            assert final_status == "article_complete"

            # Approve again -> 409 (no longer awaiting review)
            resp = await client.post(
                f"/api/v1/research/sessions/{session_id}/outline/approve",
                headers=editor_headers,
            )
            assert resp.status_code == 409

            # Cancel a terminal session -> 409
            resp = await client.post(
                f"/api/v1/research/sessions/{session_id}/cancel",
                headers=editor_headers,
            )
            assert resp.status_code == 409


class TestCancel:
    async def test_cancel_active_session_returns_200(
        self, auth_settings: Settings, test_topic_id: UUID
    ) -> None:
        app = _make_outline_app(auth_settings, test_topic_id, _outline_only_pair() * 3)
        session_repo = app.state.research_service._repos.sessions
        editor_headers = make_auth_header("editor", auth_settings)

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            session_id = await _create_session(
                client, editor_headers, test_topic_id, gate=True
            )
            await _wait_for_status(session_repo, session_id, "awaiting_outline_review")

            resp = await client.post(
                f"/api/v1/research/sessions/{session_id}/cancel",
                headers=editor_headers,
            )
            assert resp.status_code == 200, resp.text
            assert resp.json()["status"] == "cancelled"


class TestApproveNotAwaiting:
    async def test_approve_before_awaiting_review_returns_409(
        self, auth_settings: Settings, test_topic_id: UUID
    ) -> None:
        app = _make_outline_app(auth_settings, test_topic_id, _outline_only_pair() * 3)
        editor_headers = make_auth_header("editor", auth_settings)

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            # gate=False -> session never reaches awaiting_outline_review
            session_id = await _create_session(
                client, editor_headers, test_topic_id, gate=False
            )
            resp = await client.post(
                f"/api/v1/research/sessions/{session_id}/outline/approve",
                headers=editor_headers,
            )
            assert resp.status_code == 409


class TestNoGateRegression:
    async def test_flag_off_reaches_article_complete_without_review_stop(
        self, auth_settings: Settings, test_topic_id: UUID
    ) -> None:
        app = _make_outline_app(auth_settings, test_topic_id, _no_gate_responses())
        session_repo = app.state.research_service._repos.sessions
        editor_headers = make_auth_header("editor", auth_settings)

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            session_id = await _create_session(
                client, editor_headers, test_topic_id, gate=False
            )
            final_status = await _wait_for_status(
                session_repo, session_id, "article_complete"
            )
            assert final_status == "article_complete"
