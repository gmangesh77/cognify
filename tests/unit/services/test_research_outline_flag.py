"""Tests for the require_outline_approval flag on ResearchService.start_session.

AUTHOR-002 — outline approval gate. This flag is opt-in (default False)
and threads from the API request / settings default through to the
persisted ResearchSession.
"""

from uuid import uuid4

from src.models.research import TopicInput
from src.models.session_params import SessionParams
from src.services.research import (
    InMemoryAgentStepRepository,
    InMemoryResearchSessionRepository,
    InMemoryTopicRepository,
    ResearchRepositories,
    ResearchService,
)


class FakeOrchestrator:
    async def run(self, session_id, topic):  # type: ignore[no-untyped-def]
        return {"status": "complete"}


def _make_repos(topic_id) -> ResearchRepositories:  # type: ignore[no-untyped-def]
    topics = InMemoryTopicRepository()
    topics.seed(
        TopicInput(id=topic_id, title="Test", description="Desc", domain="tech")
    )
    return ResearchRepositories(
        sessions=InMemoryResearchSessionRepository(),
        steps=InMemoryAgentStepRepository(),
        topics=topics,
    )


class TestRequireOutlineApprovalFlag:
    async def test_defaults_to_false(self) -> None:
        topic_id = uuid4()
        repos = _make_repos(topic_id)
        svc = ResearchService(repos, FakeOrchestrator())
        session = await svc.start_session(topic_id)
        assert session.require_outline_approval is False

    async def test_persists_true_flag(self) -> None:
        topic_id = uuid4()
        repos = _make_repos(topic_id)
        svc = ResearchService(repos, FakeOrchestrator())
        session = await svc.start_session(
            topic_id, SessionParams(require_outline_approval=True)
        )
        assert session.require_outline_approval is True
        stored = await repos.sessions.get(session.id)
        assert stored is not None
        assert stored.require_outline_approval is True
