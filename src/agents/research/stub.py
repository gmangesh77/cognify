"""Stub research agent — placeholder for RESEARCH-002/003.

Returns realistic-shaped fake findings. Replace with real web search
(RESEARCH-002) and RAG pipeline (RESEARCH-003) agents.
"""

import asyncio
from datetime import UTC, datetime

from src.models.research import (
    FacetFindings,
    ResearchFacet,
    SourceDocument,
)


async def stub_research_agent(facet: ResearchFacet) -> FacetFindings:
    """Return fake findings shaped like real research output."""
    await asyncio.sleep(0.1)
    return FacetFindings(
        facet_index=facet.index,
        sources=[
            SourceDocument(
                url=f"https://example.com/source-{facet.index}-1",
                title=f"Source for {facet.title}",
                snippet=f"Relevant content about {facet.title}...",
                retrieved_at=datetime.now(UTC),
            ),
        ],
        claims=[f"Key finding about {facet.title}"],
        summary=f"Research summary for facet: {facet.title}",
    )
