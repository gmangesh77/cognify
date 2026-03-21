"""Research session API endpoints."""

from uuid import UUID

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from starlette.status import HTTP_201_CREATED

from src.api.auth.schemas import TokenPayload
from src.api.dependencies import require_editor_or_above, require_viewer_or_above
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
    return None


def _get_research_service(request: Request) -> ResearchService:
    return request.app.state.research_service  # type: ignore[no-any-return]


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
    session = await svc.start_session(body.topic_id)
    topic = await svc.get_topic(body.topic_id)
    background_tasks.add_task(svc.run_and_finalize, session.id, topic)
    return CreateResearchSessionResponse(
        session_id=session.id,
        status=session.status,
        started_at=session.started_at,
    )


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
    svc = _get_research_service(request)
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
    svc = _get_research_service(request)
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
