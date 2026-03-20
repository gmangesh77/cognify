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


class TestManageCitationsInGraph:
    def test_graph_includes_manage_citations_node(self) -> None:
        llm = FakeListChatModel(responses=["test"])
        retriever = AsyncMock()
        graph = build_content_graph(llm, retriever)
        node_names = list(graph.get_graph().nodes.keys())
        assert "manage_citations" in node_names

    def test_validate_article_routes_to_manage_citations(self) -> None:
        llm = FakeListChatModel(responses=["test"])
        retriever = AsyncMock()
        graph = build_content_graph(llm, retriever)
        edges = graph.get_graph().edges
        validate_targets = [e.target for e in edges if e.source == "validate_article"]
        assert "manage_citations" in validate_targets


def _seo_json() -> str:
    return json.dumps(
        {
            "title": "Test SEO Title for the Article",
            "description": "A test description that is long enough to pass validation for the SEO metadata.",
            "keywords": ["test", "seo", "ai"],
        }
    )


def _discoverability_json() -> str:
    return json.dumps(
        {
            "summary": "Test summary of the article content.",
            "key_claims": ["Key claim one [1]", "Key claim two [1]"],
        }
    )


class TestContentPipelineWithSEO:
    async def test_full_graph_produces_seo_result(self) -> None:
        responses = [
            _outline_json(),  # outline
            _queries_json(2),  # queries for 2 sections
            "Draft section 0 [1].",  # draft section 0
            "Draft section 1 [1].",  # draft section 1
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
        # manage_citations node runs after validate and fails with <5 sources
        assert result["status"] == "failed"
        assert "Need 5 sources" in result["error"]

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


def _long_clean_draft(section_num: int) -> str:
    """Generate a clean ~800-word draft that scores above slop threshold."""
    sentences = [
        "Researchers found a significant increase in attacks [1].",
        "The team tested three configurations during the trial [1].",
        "Results showed a clear pattern across all test groups [1].",
        "Performance metrics improved by roughly twelve percent [1].",
        "Data collection took place over a period of six months [1].",
        "The control group exhibited no notable changes [1].",
        "Analysts confirmed findings through independent review [1].",
        "Each participant completed the survey in ten minutes [1].",
        "The framework reduced deployment times for scenarios [1].",
        "Testing protocols followed standard industry guidelines [1].",
    ]
    # Repeat and vary to reach ~800 words
    lines: list[str] = []
    for i in range(80):
        base = sentences[i % len(sentences)]
        lines.append(f"In phase {i + 1} of section {section_num}, {base.lower()}")
    return " ".join(lines)


class TestContentPipelineWithHumanize:
    async def test_humanize_node_in_full_graph(self) -> None:
        """Full pipeline includes humanize node and produces section_drafts."""
        responses = [
            _outline_json(),
            _queries_json(2),
            _long_clean_draft(0),
            _long_clean_draft(1),
            _seo_json(),
            _discoverability_json(),
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
        assert result.get("section_drafts") is not None
        assert len(result["section_drafts"]) == 2
