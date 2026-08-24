"""Research session API endpoints."""

from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, Query, Request
from starlette.status import HTTP_201_CREATED

from src.api.auth.schemas import TokenPayload
from src.api.dependencies import require_editor_or_above, require_viewer_or_above
from src.api.errors import ServiceUnavailableError
from src.api.rate_limiter import limiter
from src.api.routers.research_params import (
    ParamSources,
    inline_brief_create,
    resolve_session_params,
)
from src.api.routers.research_pipeline import get_pipeline_dispatcher
from src.api.schemas.research import (
    AgentStepResponse,
    CreateResearchSessionRequest,
    CreateResearchSessionResponse,
    PaginatedResearchSessions,
    ResearchSessionResponse,
    ResearchSessionSummary,
)
from src.models.brief import Brief
from src.models.research import TopicInput
from src.models.research_db import ResearchSession
from src.models.session_params import SessionParams
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
    user: TokenPayload = Depends(require_editor_or_above),
) -> CreateResearchSessionResponse:
    svc = _get_research_service(request)
    brief = await _load_or_save_brief(request, body, user.sub)
    params = resolve_session_params(
        ParamSources(body, brief, request.app.state.settings.require_outline_approval)
    )
    session = await svc.start_session(body.topic_id, params)
    topic = await _enrich_topic(svc, body.topic_id, params)
    try:
        _spawn_pipeline(request, session, topic)
    except Exception as exc:
        # Broker down in celery mode: don't leave the session orphaned
        # in "planning" — the SSE stream would hang to its timeout.
        await svc.update_session_status(session.id, "failed")
        raise ServiceUnavailableError(
            message="Pipeline dispatch failed. Check the task broker."
        ) from exc
    return CreateResearchSessionResponse(
        session_id=session.id,
        status=session.status,
        started_at=session.started_at,
    )


async def _load_or_save_brief(
    request: Request, body: CreateResearchSessionRequest, owner_id: str
) -> Brief | None:
    """Resolve `brief_id` (404 if not the caller's) or auto-create one when
    `save_as_brief` is set. Returns None for the plain inline path."""
    brief_svc = request.app.state.brief_service
    if body.brief_id is not None:
        return await brief_svc.get(owner_id, body.brief_id)  # type: ignore[no-any-return]
    if body.save_as_brief:
        topic = await _get_research_service_readonly(request).get_topic(body.topic_id)
        gate = request.app.state.settings.require_outline_approval
        data = inline_brief_create(body, topic.title, gate)
        return await brief_svc.create(owner_id, data)  # type: ignore[no-any-return]
    return None


async def _enrich_topic(
    svc: ResearchService, topic_id: UUID, params: SessionParams
) -> TopicInput:
    """Overlay per-session context so the research planner can tailor
    its search queries to the requested audience/tone/angle/keywords."""
    topic = await svc.get_topic(topic_id)
    return topic.model_copy(
        update={
            "description": params.topic_description_override or topic.description,
            "target_audience": params.target_audience,
            "content_tone": params.content_tone,
            "preferred_angle": params.preferred_angle,
            "keywords": tuple(params.keywords) if params.keywords else None,
        }
    )


def _spawn_pipeline(
    request: Request, session: ResearchSession, topic: TopicInput
) -> None:
    get_pipeline_dispatcher(request).dispatch_full_pipeline(session.id, topic)


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
        brief_id=s.brief_id,
        content_type=s.content_type,
        length_target=s.length_target,
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
