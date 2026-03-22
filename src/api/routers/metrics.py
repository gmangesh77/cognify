"""Dashboard metrics endpoint."""

import structlog
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

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
    if hasattr(state, "topic_repo"):
        _, topic_count = await state.topic_repo.list_by_domain(
            "", 1, 0,
        )
    if hasattr(state, "article_repo"):
        _, article_count = await state.article_repo.list(1, 0)
    return DashboardMetricsResponse(
        topics_discovered=MetricValue(value=topic_count),
        articles_generated=MetricValue(value=article_count),
        avg_research_time=MetricValue(value="0m"),
        published=MetricValue(value=0),
    )
