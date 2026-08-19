"""Research session API endpoints."""

from uuid import UUID

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from starlette.status import HTTP_201_CREATED

from src.api.auth.schemas import TokenPayload
from src.api.dependencies import require_editor_or_above, require_viewer_or_above
from src.api.errors import ServiceUnavailableError
from src.api.rate_limiter import limiter
from src.api.schemas.research import (
    AgentStepResponse,
    CreateResearchSessionRequest,
    CreateResearchSessionResponse,
    PaginatedResearchSessions,
    ResearchSessionResponse,
    ResearchSessionSummary,
)
from src.services.research import ResearchService

logger = structlog.get_logger()

research_router = APIRouter()


def _make_output_summary(output_data: dict[str, object]) -> str | None:
    if not output_data:
        return None
    if "error" in output_data:
        return f"Error: {output_data['error']}"
    if "facet_count" in output_data:
        return f"{output_data['facet_count']} facets planned"
    if "sources_found" in output_data:
        return f"{output_data['sources_found']} sources found"
    if "embeddings_created" in output_data:
        return f"{output_data['embeddings_created']} embeddings created"
    if "is_complete" in output_data:
        status = "Complete" if output_data["is_complete"] else "Incomplete"
        return f"Evaluation: {status}"
    if "total_sources" in output_data:
        return f"{output_data['total_sources']} total sources"
    if "sections" in output_data:
        return f"{output_data['sections']} sections outlined"
    if "sections_drafted" in output_data:
        return f"{output_data['sections_drafted']} sections drafted"
    if "word_count" in output_data:
        return f"{output_data['word_count']} words"
    if "seo_generated" in output_data:
        return "SEO metadata generated"
    if "done" in output_data:
        return "Complete"
    return None


def _get_research_service_readonly(request: Request) -> ResearchService:
    """Get research service for read operations (list, detail)."""
    if not hasattr(request.app.state, "research_service"):
        raise ServiceUnavailableError(message="Research service not configured.")
    return request.app.state.research_service  # type: ignore[no-any-return]


def _get_research_service(request: Request) -> ResearchService:
    """Get research service for write operations (create session)."""
    svc = _get_research_service_readonly(request)
    if type(svc._orchestrator).__name__ in ("NoOpOrchestrator", "_NoOpOrchestrator"):
        raise ServiceUnavailableError(
            message=(
                "LLM pipeline not configured. "
                "Set COGNIFY_ANTHROPIC_API_KEY to enable article generation."
            )
        )
    return svc


@limiter.limit("3/minute")
@research_router.post(
    "/research/sessions",
    response_model=CreateResearchSessionResponse,
    status_code=HTTP_201_CREATED,
)
async def create_research_session(
    request: Request,
    body: CreateResearchSessionRequest,
    background_tasks: BackgroundTasks,
    user: TokenPayload = Depends(require_editor_or_above),
) -> CreateResearchSessionResponse:
    svc = _get_research_service(request)
    settings = request.app.state.settings
    require_outline_approval = (
        body.require_outline_approval
        if body.require_outline_approval is not None
        else settings.require_outline_approval
    )
    session = await svc.start_session(
        body.topic_id,
        target_audience=body.target_audience,
        content_tone=body.content_tone,
        preferred_angle=body.preferred_angle,
        keywords=body.keywords,
        topic_description_override=body.topic_description_override,
        structural_diagram_mode=body.structural_diagram_mode,
        require_outline_approval=require_outline_approval,
    )
    topic = await svc.get_topic(body.topic_id)
    # Enrich topic with session context so the research planner can use
    # audience/tone/angle/keywords to tailor search queries.
    description = body.topic_description_override or topic.description
    topic = topic.model_copy(
        update={
            "description": description,
            "target_audience": body.target_audience,
            "content_tone": body.content_tone,
            "preferred_angle": body.preferred_angle,
            "keywords": tuple(body.keywords) if body.keywords else None,
        }
    )
    content_svc = getattr(request.app.state, "content_service", None)
    background_tasks.add_task(
        _run_full_pipeline,
        svc,
        content_svc,
        session.id,
        topic,
    )
    return CreateResearchSessionResponse(
        session_id=session.id,
        status=session.status,
        started_at=session.started_at,
    )


async def _run_full_pipeline(
    research_svc: ResearchService,
    content_svc: object | None,
    session_id: "UUID",
    topic: object,
) -> None:
    """Research → Content generation pipeline."""
    await research_svc.run_and_finalize(session_id, topic)
    detail = await research_svc.get_session(session_id)
    if detail.session.status != "complete":
        logger.warning(
            "skipping_content_pipeline",
            session_id=str(session_id),
            reason=f"research status={detail.session.status}",
        )
        return
    if content_svc is None or not hasattr(content_svc, "generate_full_article"):
        logger.warning(
            "skipping_content_pipeline",
            session_id=str(session_id),
            reason="content_service not available",
        )
        return
    await research_svc.update_session_status(session_id, "generating_article")
    try:
        await content_svc.generate_full_article(session_id)  # type: ignore[union-attr]
        await research_svc.update_session_status(session_id, "article_complete")
    except Exception as exc:
        logger.error(
            "content_pipeline_failed",
            session_id=str(session_id),
            error=str(exc),
            exc_info=True,
        )
        await research_svc.update_session_status(session_id, "article_failed")


@limiter.limit("30/minute")
@research_router.get(
    "/research/sessions/{session_id}",
    response_model=ResearchSessionResponse,
)
async def get_research_session(
    request: Request,
    session_id: str,
    user: TokenPayload = Depends(require_viewer_or_above),
) -> ResearchSessionResponse:
    svc = _get_research_service_readonly(request)
    detail = await svc.get_session(UUID(session_id))
    s = detail.session
    steps = [
        AgentStepResponse(
            step_name=st.step_name,
            status=st.status,
            duration_ms=st.duration_ms,
            started_at=st.started_at,
            completed_at=st.completed_at,
            output_summary=_make_output_summary(st.output_data),
        )
        for st in detail.steps
    ]
    return ResearchSessionResponse(
        session_id=s.id,
        topic_id=s.topic_id,
        topic_title=s.topic_title,
        status=s.status,
        round_count=s.round_count,
        findings_count=s.findings_count,
        sources_count=s.findings_count,
        embeddings_count=s.indexed_count,
        duration_seconds=s.duration_seconds,
        started_at=s.started_at,
        completed_at=s.completed_at,
        steps=steps,
        require_outline_approval=s.require_outline_approval,
    )


@limiter.limit("30/minute")
@research_router.get(
    "/research/sessions",
    response_model=PaginatedResearchSessions,
)
async def list_research_sessions(
    request: Request,
    user: TokenPayload = Depends(require_viewer_or_above),
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
) -> PaginatedResearchSessions:
    svc = _get_research_service_readonly(request)
    result = await svc.list_sessions(status, page, size)
    items = [
        ResearchSessionSummary(
            session_id=s.id,
            topic_id=s.topic_id,
            status=s.status,
            round_count=s.round_count,
            findings_count=s.findings_count,
            sources_count=s.findings_count,
            embeddings_count=s.indexed_count,
            topic_title=s.topic_title,
            duration_seconds=s.duration_seconds,
            started_at=s.started_at,
        )
        for s in result.items
    ]
    return PaginatedResearchSessions(
        items=items, total=result.total, page=result.page, size=result.size
    )
