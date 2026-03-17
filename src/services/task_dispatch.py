"""Task dispatch protocol and implementations.

Provides a protocol for dispatching research facets to agent functions
in parallel. AsyncIODispatcher uses asyncio.gather; future CeleryDispatcher
will use Celery task queues (same protocol).
"""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Protocol

import structlog

from src.models.research import FacetFindings, ResearchFacet

logger = structlog.get_logger()

AgentFunction = Callable[[ResearchFacet], Awaitable[FacetFindings]]


class TaskDispatcher(Protocol):
    """Protocol for dispatching research facets to agent functions."""

    async def dispatch(
        self, facets: list[ResearchFacet], agent_fn: AgentFunction
    ) -> list[FacetFindings]: ...


class AsyncIODispatcher:
    """Dispatches facets in parallel using asyncio.gather."""

    def __init__(self, timeout_seconds: float = 300.0) -> None:
        self._timeout = timeout_seconds

    async def dispatch(
        self, facets: list[ResearchFacet], agent_fn: AgentFunction
    ) -> list[FacetFindings]:
        tasks = [self._run_one(facet, agent_fn) for facet in facets]
        return list(await asyncio.gather(*tasks))

    async def _run_one(
        self, facet: ResearchFacet, agent_fn: AgentFunction
    ) -> FacetFindings:
        try:
            return await asyncio.wait_for(agent_fn(facet), timeout=self._timeout)
        except (TimeoutError, Exception) as exc:
            logger.warning(
                "facet_dispatch_failed",
                facet_index=facet.index,
                error=str(exc),
            )
            return FacetFindings(
                facet_index=facet.index,
                sources=[],
                claims=[],
                summary="",
            )
