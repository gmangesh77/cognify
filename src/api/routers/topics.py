import structlog
from fastapi import APIRouter, Depends, Request

from src.api.auth.schemas import TokenPayload
from src.api.dependencies import require_role
from src.api.errors import ServiceUnavailableError
from src.api.rate_limiter import limiter
from src.api.schemas.topics import RankTopicsRequest, RankTopicsResponse
from src.services.embeddings import EmbeddingService
from src.services.topic_ranking import TopicRankingService

logger = structlog.get_logger()

topics_router = APIRouter()


def _get_embedding_service(request: Request) -> EmbeddingService:
    if not hasattr(request.app.state, "embedding_service"):
        request.app.state.embedding_service = EmbeddingService(
            model_name=request.app.state.settings.embedding_model,
        )
    return request.app.state.embedding_service


def _get_ranking_service(request: Request) -> TopicRankingService:
    return TopicRankingService(
        settings=request.app.state.settings,
        embedding_service=_get_embedding_service(request),
    )


@limiter.limit("10/minute")  # type: ignore[untyped-decorator]
@topics_router.post(
    "/topics/rank",
    response_model=RankTopicsResponse,
    summary="Rank and deduplicate topics",
)
async def rank_topics(
    request: Request,
    body: RankTopicsRequest,
    user: TokenPayload = Depends(require_role("admin", "editor")),
) -> RankTopicsResponse:
    service = _get_ranking_service(request)
    try:
        return await service.rank_and_deduplicate(body)
    except OSError as exc:
        logger.error(
            "embedding_model_failed",
            model_name=request.app.state.settings.embedding_model,
            error=str(exc),
        )
        raise ServiceUnavailableError(
            code="embedding_service_unavailable",
            message="Embedding service is not available",
        ) from exc
