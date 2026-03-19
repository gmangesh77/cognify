"""Tests for the content pipeline LangGraph graph."""

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

from langchain_core.language_models.fake_chat_models import FakeListChatModel

from src.agents.content.pipeline import build_content_graph
from src.models.research import (
    ChunkResult,
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


def _queries_json(section_count: int = 2) -> str:
    return json.dumps([
        {"section_index": i, "queries": [f"q{i}"]}
        for i in range(section_count)
    ])


def _mock_retriever() -> AsyncMock:
    chunk = ChunkResult(
        text="Research finding about the topic.",
        source_url="https://src.com",
        source_title="Source",
        score=0.9,
        chunk_index=0,
    )
    retriever = AsyncMock()
    retriever.retrieve = AsyncMock(return_value=[chunk])
    return retriever


class TestContentPipelineWithDrafting:
    async def test_full_graph_with_retriever(self) -> None:
        responses = [
            _outline_json(),  # outline generation
            _queries_json(2),  # query generation for 2 sections
            "Draft section 0 text with [1] citation.",  # draft section 0
            "Draft section 1 text with [1] citation about more.",  # draft section 1
        ]
        llm = FakeListChatModel(responses=responses)
        retriever = _mock_retriever()
        graph = build_content_graph(llm, retriever=retriever)
        result = await graph.ainvoke({
            "topic": _make_topic(),
            "research_plan": _make_plan(),
            "findings": _make_findings(),
            "session_id": uuid4(),
            "outline": None,
            "status": "outline_generating",
            "error": None,
        })
        assert result["status"] == "draft_complete"
        assert len(result["section_drafts"]) == 2
        assert result["total_word_count"] > 0

    async def test_graph_without_retriever_stops_at_outline(self) -> None:
        llm = FakeListChatModel(responses=[_outline_json()])
        graph = build_content_graph(llm)  # no retriever
        result = await graph.ainvoke({
            "topic": _make_topic(),
            "research_plan": _make_plan(),
            "findings": _make_findings(),
            "session_id": uuid4(),
            "outline": None,
            "status": "outline_generating",
            "error": None,
        })
        assert result["status"] == "outline_complete"
        assert result.get("section_drafts") is None

    async def test_query_generation_failure_sets_failed(self) -> None:
        responses = [_outline_json(), "bad json", "bad json"]
        llm = FakeListChatModel(responses=responses)
        retriever = _mock_retriever()
        graph = build_content_graph(llm, retriever=retriever)
        result = await graph.ainvoke({
            "topic": _make_topic(),
            "research_plan": _make_plan(),
            "findings": _make_findings(),
            "session_id": uuid4(),
            "outline": None,
            "status": "outline_generating",
            "error": None,
        })
        assert result["status"] == "failed"
