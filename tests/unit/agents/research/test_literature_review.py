"""Tests for the LiteratureReviewAgent callable class."""

import json
from unittest.mock import AsyncMock

from langchain_core.language_models.fake_chat_models import FakeListChatModel

from src.agents.research.literature_review import LiteratureReviewAgent
from src.models.research import FacetFindings, ResearchFacet, SourceDocument
from src.services.semantic_scholar import (
    ScholarPaper,
    SemanticScholarClient,
    SemanticScholarError,
)


def _make_facet(index: int = 0, queries: list[str] | None = None) -> ResearchFacet:
    return ResearchFacet(
        index=index,
        title="Machine Learning Security",
        description="Recent advances in adversarial ML",
        search_queries=queries or ["adversarial ML 2026"],
        source_type="academic",
    )


def _make_papers(num: int = 3, id_prefix: str = "paper") -> list[ScholarPaper]:
    return [
        ScholarPaper(
            paper_id=f"{id_prefix}_{i}",
            title=f"Paper {i}: A Study on Topic",
            abstract=f"This paper examines topic for result {i}.",
            authors=[f"Author {i}", f"Coauthor {i}"],
            year=2025 - i,
            citation_count=10 * (i + 1),
            venue=f"Conference {i}",
            url=f"https://semanticscholar.org/paper/{id_prefix}_{i}",
            doi=f"10.1234/{id_prefix}_{i}",
        )
        for i in range(num)
    ]


def _claims_json(
    claims: list[str] | None = None,
    summary: str = "Academic summary",
) -> str:
    return json.dumps(
        {
            "claims": claims or ["Claim 1", "Claim 2", "Claim 3"],
            "summary": summary,
        }
    )


class TestLiteratureReviewAgentHappyPath:
    async def test_returns_facet_findings(self) -> None:
        mock_client = AsyncMock(spec=SemanticScholarClient)
        mock_client.search.return_value = _make_papers(3)
        llm = FakeListChatModel(responses=[_claims_json()])

        agent = LiteratureReviewAgent(mock_client, llm)
        result = await agent(_make_facet())

        assert isinstance(result, FacetFindings)
        assert result.facet_index == 0
        assert len(result.sources) == 3
        assert len(result.claims) == 3
        assert result.summary == "Academic summary"

    async def test_sources_are_source_documents(self) -> None:
        mock_client = AsyncMock(spec=SemanticScholarClient)
        mock_client.search.return_value = _make_papers(2)
        llm = FakeListChatModel(responses=[_claims_json()])

        agent = LiteratureReviewAgent(mock_client, llm)
        result = await agent(_make_facet())

        for src in result.sources:
            assert isinstance(src, SourceDocument)
            assert src.url.startswith("https://")
            assert src.snippet != ""
            assert src.retrieved_at is not None

    async def test_maps_year_to_published_at(self) -> None:
        """Paper year is mapped to datetime(year, 1, 1, UTC)."""
        mock_client = AsyncMock(spec=SemanticScholarClient)
        mock_client.search.return_value = _make_papers(1)
        llm = FakeListChatModel(responses=[_claims_json()])

        agent = LiteratureReviewAgent(mock_client, llm)
        result = await agent(_make_facet())

        assert len(result.sources) == 1
        src = result.sources[0]
        assert src.published_at is not None
        assert src.published_at.year == 2025
        assert src.published_at.month == 1
        assert src.published_at.day == 1

    async def test_maps_first_author(self) -> None:
        """First author from authors list is used as source author."""
        mock_client = AsyncMock(spec=SemanticScholarClient)
        mock_client.search.return_value = _make_papers(1)
        llm = FakeListChatModel(responses=[_claims_json()])

        agent = LiteratureReviewAgent(mock_client, llm)
        result = await agent(_make_facet())

        assert result.sources[0].author == "Author 0"

    async def test_no_year_gives_none_published_at(self) -> None:
        """Paper without year -> published_at is None."""
        mock_client = AsyncMock(spec=SemanticScholarClient)
        mock_client.search.return_value = [
            ScholarPaper(
                paper_id="no_year",
                title="No Year Paper",
                abstract="Abstract without year.",
                authors=["Author"],
                year=None,
                url="https://semanticscholar.org/paper/no_year",
            ),
        ]
        llm = FakeListChatModel(responses=[_claims_json()])

        agent = LiteratureReviewAgent(mock_client, llm)
        result = await agent(_make_facet())

        assert result.sources[0].published_at is None


class TestLiteratureReviewAgentURLFallback:
    async def test_doi_url_fallback(self) -> None:
        """When paper.url is empty, falls back to DOI URL."""
        mock_client = AsyncMock(spec=SemanticScholarClient)
        mock_client.search.return_value = [
            ScholarPaper(
                paper_id="doi_only",
                title="DOI Paper",
                abstract="Abstract with DOI only.",
                authors=["Author"],
                year=2025,
                url="",
                doi="10.1234/doi_only",
            ),
        ]
        llm = FakeListChatModel(responses=[_claims_json()])

        agent = LiteratureReviewAgent(mock_client, llm)
        result = await agent(_make_facet())

        assert result.sources[0].url == "https://doi.org/10.1234/doi_only"

    async def test_semanticscholar_url_fallback(self) -> None:
        """When url and doi both empty, falls back to semanticscholar URL."""
        mock_client = AsyncMock(spec=SemanticScholarClient)
        mock_client.search.return_value = [
            ScholarPaper(
                paper_id="fallback_id",
                title="Fallback Paper",
                abstract="Abstract with no URL or DOI.",
                authors=["Author"],
                year=2025,
                url="",
                doi=None,
            ),
        ]
        llm = FakeListChatModel(responses=[_claims_json()])

        agent = LiteratureReviewAgent(mock_client, llm)
        result = await agent(_make_facet())

        assert result.sources[0].url == (
            "https://semanticscholar.org/paper/fallback_id"
        )


class TestLiteratureReviewAgentDeduplication:
    async def test_deduplicates_by_paper_id(self) -> None:
        """Papers with same paper_id across queries are deduplicated."""
        mock_client = AsyncMock(spec=SemanticScholarClient)
        papers_q1 = _make_papers(2, "shared")
        papers_q2 = [
            ScholarPaper(
                paper_id="shared_0",
                title="Duplicate paper",
                abstract="Same paper returned by second query.",
                authors=["Author Dup"],
                year=2024,
                url="https://semanticscholar.org/paper/shared_0",
            ),
            ScholarPaper(
                paper_id="unique_1",
                title="Unique paper",
                abstract="Only from second query.",
                authors=["Author Unique"],
                year=2024,
                url="https://semanticscholar.org/paper/unique_1",
            ),
        ]
        mock_client.search.side_effect = [papers_q1, papers_q2]
        llm = FakeListChatModel(responses=[_claims_json()])

        facet = _make_facet(queries=["q1", "q2"])
        agent = LiteratureReviewAgent(mock_client, llm)
        result = await agent(facet)

        ids = [s.url for s in result.sources]
        assert len(result.sources) == 3  # 2 from q1 + 1 unique from q2
        assert len(ids) == len(set(ids))


class TestLiteratureReviewAgentSanitization:
    async def test_truncates_long_abstracts(self) -> None:
        """Abstracts longer than 500 chars are truncated."""
        long_abstract = "A" * 1000
        mock_client = AsyncMock(spec=SemanticScholarClient)
        mock_client.search.return_value = [
            ScholarPaper(
                paper_id="long_abs",
                title="Long Abstract Paper",
                abstract=long_abstract,
                authors=["Author"],
                year=2025,
                url="https://semanticscholar.org/paper/long_abs",
            ),
        ]
        llm = FakeListChatModel(responses=[_claims_json()])

        agent = LiteratureReviewAgent(mock_client, llm)
        result = await agent(_make_facet())

        assert len(result.sources[0].snippet) <= 500

    async def test_strips_control_characters(self) -> None:
        """Control characters in abstracts and titles are removed."""
        mock_client = AsyncMock(spec=SemanticScholarClient)
        mock_client.search.return_value = [
            ScholarPaper(
                paper_id="dirty_paper",
                title="Clean\x00title\x0bhere",
                abstract="Clean\x00abstract\x0bhere\x1fend",
                authors=["Author"],
                year=2025,
                url="https://semanticscholar.org/paper/dirty_paper",
            ),
        ]
        llm = FakeListChatModel(responses=[_claims_json()])

        agent = LiteratureReviewAgent(mock_client, llm)
        result = await agent(_make_facet())

        snippet = result.sources[0].snippet
        title = result.sources[0].title
        assert "\x00" not in snippet
        assert "\x0b" not in snippet
        assert "\x00" not in title
        assert "Clean" in snippet
        assert "abstract" in snippet


class TestLiteratureReviewAgentErrors:
    async def test_partial_query_failure(self) -> None:
        """One query fails, others succeed -> partial results."""
        mock_client = AsyncMock(spec=SemanticScholarClient)
        mock_client.search.side_effect = [
            _make_papers(2),
            SemanticScholarError("API error"),
        ]
        llm = FakeListChatModel(responses=[_claims_json()])

        facet = _make_facet(queries=["q1", "q2"])
        agent = LiteratureReviewAgent(mock_client, llm)
        result = await agent(facet)

        assert len(result.sources) == 2
        assert result.claims != []

    async def test_all_queries_fail(self) -> None:
        """All queries fail -> empty FacetFindings."""
        mock_client = AsyncMock(spec=SemanticScholarClient)
        mock_client.search.side_effect = SemanticScholarError("API error")
        llm = FakeListChatModel(responses=[_claims_json()])

        facet = _make_facet(queries=["q1", "q2"])
        agent = LiteratureReviewAgent(mock_client, llm)
        result = await agent(facet)

        assert result.sources == []
        assert result.claims == []
        assert result.summary == ""

    async def test_llm_fallback_on_malformed_json(self) -> None:
        """LLM returns bad JSON -> falls back to abstract-based claims."""
        mock_client = AsyncMock(spec=SemanticScholarClient)
        mock_client.search.return_value = _make_papers(3)
        llm = FakeListChatModel(responses=["not valid json"])

        agent = LiteratureReviewAgent(mock_client, llm)
        result = await agent(_make_facet())

        assert len(result.sources) == 3
        assert len(result.claims) >= 1
        assert result.summary != ""


class TestLiteratureReviewAgentConfigurable:
    async def test_max_results_per_query_passed_to_client(self) -> None:
        """max_results_per_query is forwarded to client.search()."""
        mock_client = AsyncMock(spec=SemanticScholarClient)
        mock_client.search.return_value = _make_papers(1)
        llm = FakeListChatModel(responses=[_claims_json()])

        agent = LiteratureReviewAgent(mock_client, llm, max_results_per_query=10)
        await agent(_make_facet())

        mock_client.search.assert_called_once_with(
            "adversarial ML 2026", max_results=10
        )


class TestLiteratureReviewAgentCallable:
    async def test_works_with_dispatcher(self) -> None:
        """Verify __call__ satisfies AgentFunction for the dispatcher."""
        from src.services.task_dispatch import AsyncIODispatcher

        mock_client = AsyncMock(spec=SemanticScholarClient)
        mock_client.search.return_value = _make_papers(2)
        llm = FakeListChatModel(responses=[_claims_json(), _claims_json()])
        agent = LiteratureReviewAgent(mock_client, llm)

        dispatcher = AsyncIODispatcher(timeout_seconds=10)
        facets = [_make_facet(0), _make_facet(1)]

        results = await dispatcher.dispatch(facets, agent)
        assert len(results) == 2
        assert results[0].facet_index == 0
        assert results[1].facet_index == 1
