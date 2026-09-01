from collections.abc import Mapping

import structlog
from fastapi import APIRouter, Depends, Request

from src.agents.prompts import bind_prompt_overrides
from src.api.auth.schemas import TokenPayload
from src.api.dependencies import require_editor_or_above, require_role
from src.api.errors import NotFoundError, ServiceUnavailableError
from src.api.prompt_scope import load_prompt_overrides
from src.api.rate_limiter import limiter
from src.api.schemas.topic_analysis import (
    AnalyzeTopicRequest,
    ManualTopicCreateRequest,
    ManualTopicResult,
    TopicAnalysisResult,
)
from src.api.schemas.topics import (
    PaginatedTopics,
    PersistTopicsRequest,
    PersistTopicsResponse,
    RankTopicsRequest,
    RankTopicsResponse,
)
from src.services.embeddings import EmbeddingService
from src.services.topic_analyzer import TopicAnalyzer
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
        body.ranked_topics,
        body.domain,
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
    try:
        repo = request.app.state.topic_repo
        items, total = await repo.list_by_domain(domain, page, size)
        return PaginatedTopics(
            items=items,
            total=total,
            page=page,
            size=size,
        )
    except Exception as exc:
        logger.error("list_topics_failed", error=str(exc), domain=domain)
        return PaginatedTopics(items=[], total=0, page=page, size=size)


@limiter.limit("5/minute")
@topics_router.post(
    "/topics/analyze",
    response_model=TopicAnalysisResult,
    summary="Analyze a topic title and suggest metadata",
)
async def analyze_topic(
    request: Request,
    body: AnalyzeTopicRequest,
    user: TokenPayload = Depends(require_editor_or_above),
    overrides: Mapping[str, str] = Depends(load_prompt_overrides),
) -> TopicAnalysisResult:
    llm = getattr(request.app.state, "drafting_llm", None)
    if llm is None:
        raise ServiceUnavailableError(
            message="LLM not configured. Set COGNIFY_ANTHROPIC_API_KEY."
        )
    domains: list[str] = []
    domain_repo = getattr(request.app.state, "domain_config_repo", None)
    if domain_repo is not None:
        domains = await domain_repo.list_domain_names()
    analyzer = TopicAnalyzer(llm=llm)
    with bind_prompt_overrides(overrides):
        return await analyzer.analyze(
            title=body.title,
            configured_domains=domains or None,
            regenerate_field=body.regenerate_field,
            current_values=body.current_values,
        )


@limiter.limit("10/minute")
@topics_router.post(
    "/topics",
    response_model=ManualTopicResult,
    summary="Create a manual topic",
    status_code=201,
)
async def create_manual_topic(
    request: Request,
    body: ManualTopicCreateRequest,
    user: TokenPayload = Depends(require_editor_or_above),
) -> ManualTopicResult:
    """Create a topic manually (not from trend scanning).

    Checks for an exact title duplicate unless *force_create* is True.
    Returns the existing topic with ``is_duplicate=True`` if one is found.
    """
    topic_repo = request.app.state.topic_repo
    persistence_svc = request.app.state.topic_persistence_service

    if not body.force_create:
        existing_id = await persistence_svc.find_duplicate_by_title(
            body.title, body.domain
        )
        if existing_id is not None:
            existing, _ = await topic_repo.list_by_domain(body.domain, 1, 500)
            match = next((t for t in existing if t.id == existing_id), None)
            if match:
                return ManualTopicResult(
                    topic=match,
                    is_duplicate=True,
                    duplicate_of=str(existing_id),
                )

    topic_id = await topic_repo.create_manual(body)
    new_items, _ = await topic_repo.list_by_domain(body.domain, 1, 500)
    created = next((t for t in new_items if t.id == topic_id), None)
    if created is None:
        raise NotFoundError(f"Topic {topic_id} created but not retrievable")
    return ManualTopicResult(topic=created, is_duplicate=False)
