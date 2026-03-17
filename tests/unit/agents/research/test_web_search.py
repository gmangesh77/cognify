"""Tests for the WebSearchAgent callable class."""

import json
from unittest.mock import AsyncMock

from langchain_core.language_models.fake_chat_models import FakeListChatModel

from src.agents.research.web_search import WebSearchAgent
from src.models.research import FacetFindings, ResearchFacet, SourceDocument
from src.services.serpapi_client import SerpAPIClient, SerpAPIError, SerpAPIResult


def _make_facet(index: int = 0, queries: list[str] | None = None) -> ResearchFacet:
    return ResearchFacet(
        index=index,
        title="AI Security",
        description="Emerging AI security threats",
        search_queries=queries or ["AI security 2026"],
    )


def _make_results(
    num: int = 3, url_prefix: str = "https://a.com"
) -> list[SerpAPIResult]:
    return [
        SerpAPIResult(
            title=f"Result {i}",
            link=f"{url_prefix}/article-{i}",
            snippet=f"Snippet about topic for result {i}.",
            position=i + 1,
        )
        for i in range(num)
    ]


def _claims_json(claims: list[str] | None = None, summary: str = "Test summary") -> str:
    return json.dumps(
        {
            "claims": claims or ["Claim 1", "Claim 2", "Claim 3"],
            "summary": summary,
        }
    )


class TestWebSearchAgentHappyPath:
    async def test_returns_facet_findings(self) -> None:
        mock_client = AsyncMock(spec=SerpAPIClient)
        mock_client.search.return_value = _make_results(3)
        llm = FakeListChatModel(responses=[_claims_json()])

        agent = WebSearchAgent(mock_client, llm)
        result = await agent(_make_facet())

        assert isinstance(result, FacetFindings)
        assert result.facet_index == 0
        assert len(result.sources) == 3
        assert len(result.claims) == 3
        assert result.summary == "Test summary"

    async def test_sources_are_source_documents(self) -> None:
        mock_client = AsyncMock(spec=SerpAPIClient)
        mock_client.search.return_value = _make_results(2)
        llm = FakeListChatModel(responses=[_claims_json()])

        agent = WebSearchAgent(mock_client, llm)
        result = await agent(_make_facet())

        for src in result.sources:
            assert isinstance(src, SourceDocument)
            assert src.url.startswith("https://")
            assert src.snippet != ""
            assert src.retrieved_at is not None


class TestWebSearchAgentDeduplication:
    async def test_deduplicates_across_queries(self) -> None:
        """3 queries returning overlapping URLs -> deduplicated."""
        mock_client = AsyncMock(spec=SerpAPIClient)
        results_q1 = _make_results(2, "https://a.com")
        results_q2 = [
            SerpAPIResult(
                title="Dup",
                link="https://a.com/article-0",
                snippet="Dup snippet",
                position=1,
            ),
            SerpAPIResult(
                title="Unique",
                link="https://b.com/unique",
                snippet="Unique snippet",
                position=2,
            ),
        ]
        mock_client.search.side_effect = [results_q1, results_q2]
        llm = FakeListChatModel(responses=[_claims_json()])

        facet = _make_facet(queries=["q1", "q2"])
        agent = WebSearchAgent(mock_client, llm)
        result = await agent(facet)

        urls = [s.url for s in result.sources]
        assert len(urls) == len(set(urls))
        assert len(result.sources) == 3  # 2 from q1 + 1 unique from q2


class TestWebSearchAgentSanitization:
    async def test_truncates_long_snippets(self) -> None:
        """Snippets longer than 500 chars are truncated."""
        long_snippet = "A" * 1000
        mock_client = AsyncMock(spec=SerpAPIClient)
        mock_client.search.return_value = [
            SerpAPIResult(
                title="Long",
                link="https://a.com/long",
                snippet=long_snippet,
                position=1,
            ),
        ]
        llm = FakeListChatModel(responses=[_claims_json()])

        agent = WebSearchAgent(mock_client, llm)
        result = await agent(_make_facet())

        assert len(result.sources[0].snippet) <= 500

    async def test_strips_control_characters(self) -> None:
        """Control characters in snippets are removed."""
        dirty_snippet = "Clean\x00text\x0bhere\x1fend"
        mock_client = AsyncMock(spec=SerpAPIClient)
        mock_client.search.return_value = [
            SerpAPIResult(
                title="Dirty",
                link="https://a.com/dirty",
                snippet=dirty_snippet,
                position=1,
            ),
        ]
        llm = FakeListChatModel(responses=[_claims_json()])

        agent = WebSearchAgent(mock_client, llm)
        result = await agent(_make_facet())

        snippet = result.sources[0].snippet
        assert "\x00" not in snippet
        assert "\x0b" not in snippet
        assert "Clean" in snippet
        assert "text" in snippet


class TestWebSearchAgentDeduplicationNormalization:
    async def test_normalizes_trailing_slash(self) -> None:
        """URLs with/without trailing slash are treated as same."""
        mock_client = AsyncMock(spec=SerpAPIClient)
        mock_client.search.side_effect = [
            [
                SerpAPIResult(
                    title="A",
                    link="https://a.com/page/",
                    snippet="S1",
                    position=1,
                ),
            ],
            [
                SerpAPIResult(
                    title="B",
                    link="https://a.com/page",
                    snippet="S2",
                    position=1,
                ),
            ],
        ]
        llm = FakeListChatModel(responses=[_claims_json()])

        facet = _make_facet(queries=["q1", "q2"])
        agent = WebSearchAgent(mock_client, llm)
        result = await agent(facet)

        assert len(result.sources) == 1


class TestWebSearchAgentErrors:
    async def test_partial_query_failure(self) -> None:
        """One query fails, others succeed -> partial results."""
        mock_client = AsyncMock(spec=SerpAPIClient)
        mock_client.search.side_effect = [
            _make_results(2),
            SerpAPIError("API error"),
        ]
        llm = FakeListChatModel(responses=[_claims_json()])

        facet = _make_facet(queries=["q1", "q2"])
        agent = WebSearchAgent(mock_client, llm)
        result = await agent(facet)

        assert len(result.sources) == 2
        assert result.claims != []

    async def test_all_queries_fail(self) -> None:
        """All queries fail -> empty FacetFindings."""
        mock_client = AsyncMock(spec=SerpAPIClient)
        mock_client.search.side_effect = SerpAPIError("API error")
        llm = FakeListChatModel(responses=[_claims_json()])

        facet = _make_facet(queries=["q1", "q2"])
        agent = WebSearchAgent(mock_client, llm)
        result = await agent(facet)

        assert result.sources == []
        assert result.claims == []
        assert result.summary == ""

    async def test_llm_fallback_on_malformed_json(self) -> None:
        """LLM returns bad JSON -> falls back to snippet-based claims."""
        mock_client = AsyncMock(spec=SerpAPIClient)
        mock_client.search.return_value = _make_results(3)
        llm = FakeListChatModel(responses=["not valid json"])

        agent = WebSearchAgent(mock_client, llm)
        result = await agent(_make_facet())

        assert len(result.sources) == 3
        assert len(result.claims) >= 1
        assert result.summary != ""


class TestWebSearchAgentCallable:
    async def test_works_with_dispatcher(self) -> None:
        """Verify __call__ satisfies AgentFunction for the dispatcher."""
        from src.services.task_dispatch import AsyncIODispatcher

        mock_client = AsyncMock(spec=SerpAPIClient)
        mock_client.search.return_value = _make_results(2)
        llm = FakeListChatModel(responses=[_claims_json(), _claims_json()])
        agent = WebSearchAgent(mock_client, llm)

        dispatcher = AsyncIODispatcher(timeout_seconds=10)
        facets = [_make_facet(0), _make_facet(1)]

        results = await dispatcher.dispatch(facets, agent)
        assert len(results) == 2
        assert results[0].facet_index == 0
        assert results[1].facet_index == 1
