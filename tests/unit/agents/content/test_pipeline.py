"""Tests for the content pipeline LangGraph graph."""

import json
from datetime import UTC, datetime
from uuid import uuid4

from langchain_core.language_models.fake_chat_models import FakeListChatModel

from src.agents.content.pipeline import build_content_graph
from src.models.research import (
    FacetFindings,
    ResearchFacet,
    ResearchPlan,
    SourceDocument,
    TopicInput,
)


def _make_topic() -> TopicInput:
    return TopicInput(id=uuid4(), title="Test", description="Desc", domain="tech")


def _make_plan() -> ResearchPlan:
    return ResearchPlan(
        facets=[
            ResearchFacet(
                index=0,
                title="F0",
                description="D0",
                search_queries=["q0"],
            )
        ],
        reasoning="Plan",
    )


def _make_findings() -> list[FacetFindings]:
    return [
        FacetFindings(
            facet_index=0,
            sources=[
                SourceDocument(
                    url="https://a.com",
                    title="A",
                    snippet="S",
                    retrieved_at=datetime.now(UTC),
                )
            ],
            claims=["Claim"],
            summary="Summary",
        )
    ]


def _outline_json() -> str:
    return json.dumps(
        {
            "title": "Test Article",
            "content_type": "article",
            "sections": [
                {
                    "index": 0,
                    "title": "Intro",
                    "description": "D",
                    "key_points": ["P"],
                    "target_word_count": 300,
                    "relevant_facets": [0],
                },
                {
                    "index": 1,
                    "title": "Conclusion",
                    "description": "D",
                    "key_points": ["P"],
                    "target_word_count": 200,
                    "relevant_facets": [0],
                },
            ],
            "total_target_words": 500,
            "reasoning": "Simple structure",
        }
    )


class TestContentPipeline:
    async def test_graph_generates_outline(self) -> None:
        llm = FakeListChatModel(responses=[_outline_json()])
        graph = build_content_graph(llm)
        result = await graph.ainvoke(
            {
                "topic": _make_topic(),
                "research_plan": _make_plan(),
                "findings": _make_findings(),
                "session_id": uuid4(),
                "outline": None,
                "status": "outline_generating",
                "error": None,
            }
        )
        assert result["status"] == "outline_complete"
        assert result["outline"] is not None
        assert len(result["outline"].sections) == 2

    async def test_graph_handles_failure(self) -> None:
        llm = FakeListChatModel(responses=["bad1", "bad2"])
        graph = build_content_graph(llm)
        result = await graph.ainvoke(
            {
                "topic": _make_topic(),
                "research_plan": _make_plan(),
                "findings": _make_findings(),
                "session_id": uuid4(),
                "outline": None,
                "status": "outline_generating",
                "error": None,
            }
        )
        assert result["status"] == "failed"
        assert result["error"] is not None
