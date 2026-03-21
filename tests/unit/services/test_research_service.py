"""Tests for the ResearchService."""

from uuid import uuid4

import pytest

from src.api.errors import NotFoundError
from src.models.research import TopicInput
from src.services.research import (
    InMemoryAgentStepRepository,
    InMemoryResearchSessionRepository,
    InMemoryTopicRepository,
    ResearchRepositories,
    ResearchService,
)


class FakeOrchestrator:
    """Test double for ResearchOrchestrator."""

    def __init__(self, should_fail: bool = False) -> None:
        self.calls: list[tuple] = []
        self._should_fail = should_fail

    async def run(self, session_id, topic):  # type: ignore[no-untyped-def]
        self.calls.append((session_id, topic))
        if self._should_fail:
            raise RuntimeError("Orchestrator failed")
        return {"status": "complete"}


def _make_repos(
    topic_ids: list | None = None,
) -> ResearchRepositories:
    topics = InMemoryTopicRepository()
    for tid in topic_ids or []:
        topics.seed(
            TopicInput(
                id=tid,
                title="Test",
                description="Desc",
                domain="tech",
            )
        )
    return ResearchRepositories(
        sessions=InMemoryResearchSessionRepository(),
        steps=InMemoryAgentStepRepository(),
        topics=topics,
    )


class TestStartSession:
    async def test_creates_session(self) -> None:
        topic_id = uuid4()
        repos = _make_repos([topic_id])
        svc = ResearchService(repos, FakeOrchestrator())
        session = await svc.start_session(topic_id)
        assert session.topic_id == topic_id
        assert session.status == "planning"

    async def test_rejects_invalid_topic(self) -> None:
        repos = _make_repos([])
        svc = ResearchService(repos, FakeOrchestrator())
        with pytest.raises(NotFoundError):
            await svc.start_session(uuid4())


class TestGetSession:
    async def test_returns_session_with_steps(self) -> None:
        topic_id = uuid4()
        repos = _make_repos([topic_id])
        svc = ResearchService(repos, FakeOrchestrator())
        session = await svc.start_session(topic_id)
        detail = await svc.get_session(session.id)
        assert detail.session.id == session.id

    async def test_not_found(self) -> None:
        repos = _make_repos([])
        svc = ResearchService(repos, FakeOrchestrator())
        with pytest.raises(NotFoundError):
            await svc.get_session(uuid4())


class TestGetTopic:
    async def test_returns_topic(self) -> None:
        topic_id = uuid4()
        repos = _make_repos([topic_id])
        svc = ResearchService(repos, FakeOrchestrator())
        topic = await svc.get_topic(topic_id)
        assert topic.id == topic_id

    async def test_not_found(self) -> None:
        repos = _make_repos([])
        svc = ResearchService(repos, FakeOrchestrator())
        with pytest.raises(NotFoundError):
            await svc.get_topic(uuid4())


class TestAgentStepRepository:
    async def test_update_step(self) -> None:
        from datetime import UTC, datetime
        from src.models.research_db import AgentStep
        repo = InMemoryAgentStepRepository()
        session_id = uuid4()
        step = AgentStep(
            session_id=session_id,
            step_name="plan_research",
            status="running",
            started_at=datetime.now(UTC),
        )
        created = await repo.create(step)
        updated = created.model_copy(update={"status": "complete", "duration_ms": 1200})
        result = await repo.update(updated)
        assert result.status == "complete"
        assert result.duration_ms == 1200
        steps = await repo.list_by_session(session_id)
        assert len(steps) == 1
        assert steps[0].status == "complete"


class TestListSessions:
    async def test_returns_paginated(self) -> None:
        topic_id = uuid4()
        repos = _make_repos([topic_id])
        svc = ResearchService(repos, FakeOrchestrator())
        await svc.start_session(topic_id)
        await svc.start_session(topic_id)
        result = await svc.list_sessions(None, page=1, size=10)
        assert result.total == 2
        assert len(result.items) == 2

    async def test_filters_by_status(self) -> None:
        topic_id = uuid4()
        repos = _make_repos([topic_id])
        svc = ResearchService(repos, FakeOrchestrator())
        await svc.start_session(topic_id)
        result = await svc.list_sessions("complete", page=1, size=10)
        assert result.total == 0
