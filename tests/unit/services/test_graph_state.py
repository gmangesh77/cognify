"""Tests for content-pipeline initial graph state construction."""

from datetime import UTC, datetime
from uuid import uuid4

from src.models.research import TopicInput
from src.models.research_db import ResearchSession
from src.services.content.graph_state import build_initial_state


def test_build_initial_state_seeds_audience_persona_and_brief_id() -> None:
    brief_id = uuid4()
    topic_id = uuid4()
    session = ResearchSession(
        topic_id=topic_id,
        started_at=datetime.now(UTC),
        audience_persona="general_business",
        brief_id=brief_id,
    )
    topic = TopicInput(id=topic_id, title="t", description="d", domain="tech")

    state = build_initial_state(session, topic, [])

    assert state["audience_persona"] == "general_business"
    assert state["brief_id"] == brief_id


def test_build_initial_state_seeds_content_type_and_length_target() -> None:
    topic_id = uuid4()
    session = ResearchSession(
        topic_id=topic_id,
        started_at=datetime.now(UTC),
        content_type="how-to",
        length_target="pillar",
    )
    topic = TopicInput(id=topic_id, title="t", description="d", domain="tech")

    state = build_initial_state(session, topic, [])

    assert state["content_type"] == "how-to"
    assert state["length_target"] == "pillar"
