"""Tests for the TaskDispatcher protocol and AsyncIODispatcher."""

import asyncio
import time

import pytest

from src.models.research import FacetFindings, ResearchFacet, SourceDocument
from src.services.task_dispatch import AsyncIODispatcher


def _make_facet(index: int) -> ResearchFacet:
    return ResearchFacet(
        index=index,
        title=f"Facet {index}",
        description=f"Description {index}",
        search_queries=[f"query {index}"],
    )


class TestAsyncIODispatcher:
    async def test_dispatches_all_facets(self) -> None:
        async def agent(facet: ResearchFacet) -> FacetFindings:
            return FacetFindings(
                facet_index=facet.index,
                sources=[],
                claims=[],
                summary="done",
            )

        dispatcher = AsyncIODispatcher(timeout_seconds=10)
        facets = [_make_facet(i) for i in range(3)]
        results = await dispatcher.dispatch(facets, agent)
        assert len(results) == 3
        indices = {r.facet_index for r in results}
        assert indices == {0, 1, 2}

    async def test_runs_in_parallel(self) -> None:
        async def slow_agent(facet: ResearchFacet) -> FacetFindings:
            await asyncio.sleep(0.2)
            return FacetFindings(
                facet_index=facet.index,
                sources=[],
                claims=[],
                summary="done",
            )

        dispatcher = AsyncIODispatcher(timeout_seconds=10)
        facets = [_make_facet(i) for i in range(3)]
        start = time.monotonic()
        await dispatcher.dispatch(facets, slow_agent)
        elapsed = time.monotonic() - start
        # 3 tasks at 0.2s each; parallel should be ~0.2s, not ~0.6s
        assert elapsed < 0.5

    async def test_timeout_returns_empty_findings(self) -> None:
        async def hanging_agent(facet: ResearchFacet) -> FacetFindings:
            await asyncio.sleep(10)
            return FacetFindings(
                facet_index=facet.index,
                sources=[],
                claims=[],
                summary="done",
            )

        dispatcher = AsyncIODispatcher(timeout_seconds=0.3)
        facets = [_make_facet(0)]
        results = await dispatcher.dispatch(facets, hanging_agent)
        assert len(results) == 1
        assert results[0].sources == []
        assert results[0].summary == ""

    async def test_partial_failure(self) -> None:
        call_count = 0

        async def flaky_agent(facet: ResearchFacet) -> FacetFindings:
            nonlocal call_count
            call_count += 1
            if facet.index == 1:
                raise RuntimeError("Agent crashed")
            return FacetFindings(
                facet_index=facet.index,
                sources=[],
                claims=["claim"],
                summary="done",
            )

        dispatcher = AsyncIODispatcher(timeout_seconds=10)
        facets = [_make_facet(i) for i in range(3)]
        results = await dispatcher.dispatch(facets, flaky_agent)
        assert len(results) == 3
        # Failed facet gets empty findings
        failed = next(r for r in results if r.facet_index == 1)
        assert failed.sources == []
        assert failed.summary == ""
        # Successful facets are intact
        ok = [r for r in results if r.facet_index != 1]
        assert all(r.claims == ["claim"] for r in ok)
