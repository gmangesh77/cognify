import structlog
from fastapi import APIRouter, Depends, Request

from src.api.auth.schemas import TokenPayload
from src.api.dependencies import require_role
from src.api.errors import ServiceUnavailableError
from src.api.rate_limiter import limiter
from src.api.schemas.topics import (
    PaginatedTopics,
    PersistTopicsRequest,
    PersistTopicsResponse,
    RankTopicsRequest,
    RankTopicsResponse,
)
from src.services.embeddings import EmbeddingService
from src.services.topic_ranking import TopicRankingService

logger = structlog.get_logger()

topics_router = APIRouter()


def _get_embedding_service(request: Request) -> EmbeddingService:
    if not hasattr(request.app.state, "embedding_service"):
        request.app.state.embedding_service = EmbeddingService(
            model_name=request.app.state.settings.embedding_model,
        )
    service: EmbeddingService = request.app.state.embedding_service
    return service


def _get_ranking_service(request: Request) -> TopicRankingService:
    return TopicRankingService(
        settings=request.app.state.settings,
        embedding_service=_get_embedding_service(request),
    )


@limiter.limit("10/minute")
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


@limiter.limit("5/minute")
@topics_router.post(
    "/topics/persist",
    response_model=PersistTopicsResponse,
    summary="Persist ranked topics with cross-scan dedup",
)
async def persist_topics(
    request: Request,
    body: PersistTopicsRequest,
    user: TokenPayload = Depends(require_role("admin", "editor")),
) -> PersistTopicsResponse:
    svc = request.app.state.topic_persistence_service
    result = await svc.persist_ranked_topics(
        body.ranked_topics, body.domain,
    )
    return PersistTopicsResponse(
        new_count=result.new_count,
        updated_count=result.updated_count,
        total_persisted=result.total_persisted,
        topic_ids=result.topic_ids,
    )


@topics_router.get(
    "/topics",
    response_model=PaginatedTopics,
    summary="List persisted topics by domain",
)
async def list_topics(
    request: Request,
    domain: str = "",
    page: int = 1,
    size: int = 20,
) -> PaginatedTopics:
    if not hasattr(request.app.state, "topic_repo"):
        return PaginatedTopics(items=[], total=0, page=page, size=size)
    repo = request.app.state.topic_repo
    items, total = await repo.list_by_domain(domain, page, size)
    return PaginatedTopics(
        items=items, total=total, page=page, size=size,
    )
