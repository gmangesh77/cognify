"""Tests for per-article params in content pipeline."""

from unittest.mock import MagicMock

from src.agents.content.pipeline import ContentState


def test_content_state_accepts_article_params():
    """ContentState TypedDict accepts per-article params."""
    state: ContentState = {
        "topic": MagicMock(),
        "research_plan": None,
        "findings": [],
        "session_id": MagicMock(),
        "outline": None,
        "status": "outline_generating",
        "error": None,
        "target_audience": "Security engineers",
        "content_tone": "technical-authoritative",
        "preferred_angle": "Implementation guide",
    }
    assert state["target_audience"] == "Security engineers"
    assert state["content_tone"] == "technical-authoritative"
    assert state["preferred_angle"] == "Implementation guide"


def test_content_state_works_without_article_params():
    """ContentState works without per-article params (backward compat)."""
    state: ContentState = {
        "topic": MagicMock(),
        "research_plan": None,
        "findings": [],
        "session_id": MagicMock(),
        "outline": None,
        "status": "outline_generating",
        "error": None,
    }
    assert state.get("target_audience") is None
