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
    return json.dumps(
        [{"section_index": i, "queries": [f"q{i}"]} for i in range(section_count)]
    )


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


def _seo_json() -> str:
    return json.dumps({
        "title": "Test SEO Title for the Article",
        "description": "A test description that is long enough to pass validation for the SEO metadata.",
        "keywords": ["test", "seo", "ai"],
    })


def _discoverability_json() -> str:
    return json.dumps({
        "summary": "Test summary of the article content.",
        "key_claims": ["Key claim one [1]", "Key claim two [1]"],
    })


class TestContentPipelineWithSEO:
    async def test_full_graph_produces_seo_result(self) -> None:
        responses = [
            _outline_json(),         # outline
            _queries_json(2),        # queries for 2 sections
            "Draft section 0 [1].",  # draft section 0
            "Draft section 1 [1].",  # draft section 1
            "Redrafted section with more words about the topic [1].",  # validate re-draft
            _seo_json(),             # SEO metadata
            _discoverability_json(), # AI discoverability
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
        assert result.get("seo_result") is not None
        assert result["seo_result"].summary != ""

    async def test_seo_failure_sets_failed(self) -> None:
        responses = [
            _outline_json(),
            _queries_json(2),
            "Draft section 0 [1].",
            "Draft section 1 [1].",
            "Redrafted section with more words about the topic [1].",  # validate re-draft
            "bad seo json",
            "bad seo json",  # retry also fails
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
        assert result["status"] == "failed"


class TestContentPipelineWithDrafting:
    async def test_full_graph_with_retriever(self) -> None:
        responses = [
            _outline_json(),  # outline generation
            _queries_json(2),  # query generation for 2 sections
            "Draft section 0 text with [1] citation.",  # draft section 0
            "Draft section 1 text with [1] citation about more.",  # draft section 1
            "Redrafted section with more words about the topic [1].",  # validate re-draft
            _seo_json(),  # SEO metadata
            _discoverability_json(),  # AI discoverability
        ]
        llm = FakeListChatModel(responses=responses)
        retriever = _mock_retriever()
        graph = build_content_graph(llm, retriever=retriever)
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
        assert result["status"] == "draft_complete"
        assert len(result["section_drafts"]) == 2
        assert result["total_word_count"] > 0

    async def test_graph_without_retriever_stops_at_outline(self) -> None:
        llm = FakeListChatModel(responses=[_outline_json()])
        graph = build_content_graph(llm)  # no retriever
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
        assert result.get("section_drafts") is None

    async def test_query_generation_failure_sets_failed(self) -> None:
        responses = [_outline_json(), "bad json", "bad json"]
        llm = FakeListChatModel(responses=responses)
        retriever = _mock_retriever()
        graph = build_content_graph(llm, retriever=retriever)
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
