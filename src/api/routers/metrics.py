"""Dashboard metrics endpoint."""

import structlog
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import func, select

from src.api.auth.schemas import TokenPayload
from src.api.dependencies import require_viewer_or_above
from src.api.rate_limiter import limiter

logger = structlog.get_logger()

metrics_router = APIRouter()


class MetricValue(BaseModel):
    value: int | str
    trend: int = 0
    direction: str = "up"


class DashboardMetricsResponse(BaseModel):
    topics_discovered: MetricValue
    articles_generated: MetricValue
    avg_research_time: MetricValue
    published: MetricValue


class KnowledgeBaseStatsResponse(BaseModel):
    """Aggregated knowledge base stats from all research sessions."""

    total_sessions: int
    total_sources: int
    total_embeddings: int


@limiter.limit("30/minute")
@metrics_router.get(
    "/metrics",
    response_model=DashboardMetricsResponse,
    summary="Dashboard overview metrics",
)
async def get_metrics(
    request: Request,
    user: TokenPayload = Depends(require_viewer_or_above),
) -> DashboardMetricsResponse:
    """Return aggregated counts for the dashboard overview."""
    state = request.app.state
    topic_count = 0
    article_count = 0
    published_count = 0
    avg_time = "0m"

    if hasattr(state, "topic_repo"):
        _, topic_count = await state.topic_repo.list_by_domain("", 1, 0)
    if hasattr(state, "article_repo"):
        _, article_count = await state.article_repo.list(1, 0)
    if hasattr(state, "pub_repo"):
        _, published_count = await state.pub_repo.list(
            status="published",
        )
    avg_time = await _avg_research_time(state)

    return DashboardMetricsResponse(
        topics_discovered=MetricValue(value=topic_count),
        articles_generated=MetricValue(value=article_count),
        avg_research_time=MetricValue(value=avg_time),
        published=MetricValue(value=published_count),
    )


@limiter.limit("30/minute")
@metrics_router.get(
    "/metrics/knowledge-base",
    response_model=KnowledgeBaseStatsResponse,
    summary="Knowledge base aggregated stats",
)
async def get_knowledge_base_stats(
    request: Request,
    user: TokenPayload = Depends(require_viewer_or_above),
) -> KnowledgeBaseStatsResponse:
    """Return aggregated KB stats across all research sessions."""
    state = request.app.state
    if not hasattr(state, "db_engine"):
        return KnowledgeBaseStatsResponse(
            total_sessions=0, total_sources=0, total_embeddings=0
        )
    from src.db.engine import get_session_factory
    from src.db.tables import ResearchSessionRow

    sf = get_session_factory(state.db_engine)
    async with sf() as db:
        result = await db.execute(
            select(
                func.count(ResearchSessionRow.id),
                func.coalesce(
                    func.sum(ResearchSessionRow.findings_count), 0
                ),
                func.coalesce(
                    func.sum(ResearchSessionRow.indexed_count), 0
                ),
            )
        )
        row = result.one()
    return KnowledgeBaseStatsResponse(
        total_sessions=row[0],
        total_sources=row[1],
        total_embeddings=row[2],
    )


async def _avg_research_time(state: object) -> str:
    """Compute average research session duration as a string."""
    if not hasattr(state, "db_engine"):
        return "0m"
    from src.db.engine import get_session_factory
    from src.db.tables import ResearchSessionRow

    sf = get_session_factory(state.db_engine)
    async with sf() as db:
        result = await db.execute(
            select(
                func.avg(ResearchSessionRow.duration_seconds)
            ).where(ResearchSessionRow.duration_seconds.is_not(None))
        )
        avg_seconds = result.scalar()
    if avg_seconds is None or avg_seconds == 0:
        return "0m"
    minutes = avg_seconds / 60
    if minutes < 1:
        return f"{int(avg_seconds)}s"
    return f"{minutes:.1f}m"
