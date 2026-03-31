"""Unit tests for per-article params in research session creation."""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.models.research import TopicInput
from src.services.research import (
    InMemoryAgentStepRepository,
    InMemoryResearchSessionRepository,
    InMemoryTopicRepository,
    ResearchRepositories,
    ResearchService,
)


@pytest.fixture
def topic() -> TopicInput:
    return TopicInput(
        id=uuid4(),
        title="AI Security Trends",
        description="Emerging threats in AI security",
        domain="cybersecurity",
    )


@pytest.fixture
def repos() -> ResearchRepositories:
    return ResearchRepositories(
        sessions=InMemoryResearchSessionRepository(),
        steps=InMemoryAgentStepRepository(),
        topics=InMemoryTopicRepository(),
    )


@pytest.fixture
def mock_orchestrator() -> AsyncMock:
    return AsyncMock()


@pytest.mark.asyncio
async def test_start_session_with_article_params(
    topic: TopicInput,
    repos: ResearchRepositories,
    mock_orchestrator: AsyncMock,
) -> None:
    """Session stores target_audience, content_tone, preferred_angle when provided."""
    repos.topics.seed(topic)  # type: ignore[attr-defined]
    svc = ResearchService(repos=repos, orchestrator=mock_orchestrator)

    session = await svc.start_session(
        topic.id,
        target_audience="senior engineers",
        content_tone="technical",
        preferred_angle="practical applications",
    )

    assert session.target_audience == "senior engineers"
    assert session.content_tone == "technical"
    assert session.preferred_angle == "practical applications"
    assert session.topic_id == topic.id
    assert session.status == "planning"


@pytest.mark.asyncio
async def test_start_session_without_article_params(
    topic: TopicInput,
    repos: ResearchRepositories,
    mock_orchestrator: AsyncMock,
) -> None:
    """Backward compatibility: all per-article params default to None."""
    repos.topics.seed(topic)  # type: ignore[attr-defined]
    svc = ResearchService(repos=repos, orchestrator=mock_orchestrator)

    session = await svc.start_session(topic.id)

    assert session.target_audience is None
    assert session.content_tone is None
    assert session.preferred_angle is None
    assert session.topic_id == topic.id
    assert session.status == "planning"
