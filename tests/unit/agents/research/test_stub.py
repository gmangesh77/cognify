"""Tests for the stub research agent."""

from src.agents.research.stub import stub_research_agent
from src.models.research import FacetFindings, ResearchFacet


class TestStubResearchAgent:
    async def test_returns_findings_for_facet(self) -> None:
        facet = ResearchFacet(
            index=0,
            title="Security trends",
            description="Recent cybersecurity trends",
            search_queries=["cyber trends 2026"],
        )
        result = await stub_research_agent(facet)
        assert isinstance(result, FacetFindings)
        assert result.facet_index == 0
        assert len(result.sources) >= 1
        assert len(result.claims) >= 1
        assert result.summary != ""

    async def test_uses_facet_title_in_output(self) -> None:
        facet = ResearchFacet(
            index=2,
            title="AI regulation",
            description="Government AI policies",
            search_queries=["AI regulation 2026"],
        )
        result = await stub_research_agent(facet)
        assert "AI regulation" in result.summary
        assert result.facet_index == 2
