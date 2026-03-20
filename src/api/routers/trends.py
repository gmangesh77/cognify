import asyncio
import time

import structlog
from fastapi import APIRouter, Depends, Request

from src.api.auth.schemas import TokenPayload
from src.api.dependencies import require_role
from src.api.errors import CognifyValidationError, ServiceUnavailableError
from src.api.rate_limiter import limiter
from src.api.schemas.trends import (
    SourceResult,
    TrendFetchRequest,
    TrendFetchResponse,
)
from src.services.trends.protocol import TrendFetchConfig, TrendSourceError
from src.services.trends.registry import TrendSourceRegistry

logger = structlog.get_logger()

trends_router = APIRouter()


def _resolve_sources(
    registry: TrendSourceRegistry, requested: list[str] | None,
) -> list[str]:
    """Resolve and validate requested source names."""
    sources = requested or registry.available_sources()
    unknown = set(sources) - set(registry.available_sources())
    if unknown:
        raise CognifyValidationError(
            message=f"Unknown sources: {sorted(unknown)}",
        )
    return sources


async def _run_source(
    source_name: str, registry: TrendSourceRegistry, config: TrendFetchConfig,
) -> SourceResult:
    """Run a single source, capturing timing and errors."""
    source = registry.get(source_name)
    start = time.monotonic()
    try:
        topics = await source.fetch_and_normalize(config)
        elapsed = int((time.monotonic() - start) * 1000)
        return SourceResult(
            source_name=source_name,
            topics=topics,
            topic_count=len(topics),
            duration_ms=elapsed,
        )
    except TrendSourceError as exc:
        elapsed = int((time.monotonic() - start) * 1000)
        logger.error("trend_source_error", source=source_name, error=str(exc))
        return SourceResult(
            source_name=source_name,
            topics=[],
            topic_count=0,
            duration_ms=elapsed,
            error=str(exc),
        )


@limiter.limit("5/minute")
@trends_router.post(
    "/trends/fetch",
    response_model=TrendFetchResponse,
    summary="Fetch trending topics from one or more sources",
)
async def fetch_trends(
    request: Request,
    body: TrendFetchRequest,
    user: TokenPayload = Depends(require_role("admin", "editor")),
) -> TrendFetchResponse:
    registry = request.app.state.trend_registry
    source_names = _resolve_sources(registry, body.sources)
    config = TrendFetchConfig(
        domain_keywords=body.domain_keywords,
        max_results=body.max_results,
    )

    results = await asyncio.gather(
        *[_run_source(n, registry, config) for n in source_names],
    )
    source_results = {r.source_name: r for r in results}
    all_topics = [t for r in results for t in r.topics]

    if all(r.error is not None for r in results):
        raise ServiceUnavailableError(
            code="all_sources_unavailable",
            message="All trend sources are unavailable",
        )

    return TrendFetchResponse(
        topics=all_topics,
        sources_queried=list(source_names),
        source_results=source_results,
    )
