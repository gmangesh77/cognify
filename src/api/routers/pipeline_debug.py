"""Pipeline debug API endpoints for inspecting pipeline execution."""

from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, Query, Request

from src.api.auth.schemas import TokenPayload
from src.api.dependencies import require_viewer_or_above
from src.api.errors import NotFoundError
from src.api.rate_limiter import limiter
from src.api.schemas.pipeline_debug import (
    DebugSessionSummary,
    DebugStepResponse,
    LlmCallResponse,
    PaginatedDebugSessions,
    PipelineDebugResponse,
)

logger = structlog.get_logger()

pipeline_debug_router = APIRouter()


@pipeline_debug_router.get(
    "/debug/sessions",
    response_model=PaginatedDebugSessions,
    summary="List sessions for pipeline debugging",
)
@limiter.limit("30/minute")
async def list_debug_sessions(
    request: Request,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    user: TokenPayload = Depends(require_viewer_or_above),
) -> PaginatedDebugSessions:
    """List research sessions with step/LLM call counts."""
    session_repo = _get_session_repo(request)
    step_repo = _get_step_repo(request)
    llm_repo = _get_llm_repo(request)

    session_list, total = await session_repo.list(
        status=None, page=page, size=size
    )
    items = []
    for s in session_list:
        steps = await step_repo.list_by_session(s.id)
        llm_calls = await llm_repo.list_by_session(s.id) if llm_repo else []
        items.append(
            DebugSessionSummary(
                session_id=s.id,
                topic_title=s.topic_title,
                status=s.status,
                started_at=s.started_at,
                duration_seconds=s.duration_seconds,
                step_count=len(steps),
                llm_call_count=len(llm_calls),
            )
        )
    return PaginatedDebugSessions(
        items=items, total=total, page=page, size=size
    )


@pipeline_debug_router.get(
    "/debug/sessions/{session_id}",
    response_model=PipelineDebugResponse,
    summary="Get full pipeline trace for a session",
)
@limiter.limit("30/minute")
async def get_pipeline_debug(
    request: Request,
    session_id: UUID,
    user: TokenPayload = Depends(require_viewer_or_above),
) -> PipelineDebugResponse:
    """Return session with all steps and their LLM calls."""
    session_repo = _get_session_repo(request)
    step_repo = _get_step_repo(request)
    llm_repo = _get_llm_repo(request)

    session = await session_repo.get(session_id)
    if session is None:
        raise NotFoundError(f"Session {session_id} not found")

    steps_raw = await step_repo.list_by_session(session_id)
    all_llm_calls = await llm_repo.list_by_session(session_id) if llm_repo else []

    # Group LLM calls by step_id
    calls_by_step: dict[UUID, list[LlmCallResponse]] = {}
    orphan_calls: list[LlmCallResponse] = []
    for c in all_llm_calls:
        resp = _to_llm_call_response(c)
        if c.step_id:
            calls_by_step.setdefault(c.step_id, []).append(resp)
        else:
            orphan_calls.append(resp)

    debug_steps = []
    for step in steps_raw:
        step_calls = calls_by_step.get(step.id, [])
        debug_steps.append(
            DebugStepResponse(
                id=step.id,
                step_name=step.step_name,
                status=step.status,
                input_data=step.input_data or {},
                output_data=step.output_data or {},
                duration_ms=step.duration_ms,
                started_at=step.started_at,
                completed_at=step.completed_at,
                llm_calls=step_calls,
            )
        )

    total_input = sum(c.input_tokens or 0 for c in all_llm_calls)
    total_output = sum(c.output_tokens or 0 for c in all_llm_calls)

    return PipelineDebugResponse(
        session_id=session.id,
        topic_title=session.topic_title,
        topic_domain=session.topic_domain,
        status=session.status,
        started_at=session.started_at,
        completed_at=session.completed_at,
        duration_seconds=session.duration_seconds,
        target_audience=session.target_audience,
        content_tone=session.content_tone,
        preferred_angle=session.preferred_angle,
        steps=debug_steps,
        total_llm_calls=len(all_llm_calls),
        total_input_tokens=total_input,
        total_output_tokens=total_output,
    )


@pipeline_debug_router.get(
    "/debug/sessions/{session_id}/llm-calls",
    response_model=list[LlmCallResponse],
    summary="List all LLM calls for a session",
)
@limiter.limit("30/minute")
async def list_session_llm_calls(
    request: Request,
    session_id: UUID,
    user: TokenPayload = Depends(require_viewer_or_above),
) -> list[LlmCallResponse]:
    """Flat list of all LLM calls for a session, sorted by time."""
    llm_repo = _get_llm_repo(request)
    if llm_repo is None:
        return []
    calls = await llm_repo.list_by_session(session_id)
    return [_to_llm_call_response(c) for c in calls]


def _to_llm_call_response(c: object) -> LlmCallResponse:
    return LlmCallResponse(
        id=c.id,  # type: ignore[union-attr]
        step_id=c.step_id,  # type: ignore[union-attr]
        call_name=c.call_name,  # type: ignore[union-attr]
        model_name=c.model_name,  # type: ignore[union-attr]
        prompt_messages=c.prompt_messages,  # type: ignore[union-attr]
        response_content=c.response_content,  # type: ignore[union-attr]
        input_tokens=c.input_tokens,  # type: ignore[union-attr]
        output_tokens=c.output_tokens,  # type: ignore[union-attr]
        duration_ms=c.duration_ms,  # type: ignore[union-attr]
        error=c.error,  # type: ignore[union-attr]
        started_at=c.started_at,  # type: ignore[union-attr]
        completed_at=c.completed_at,  # type: ignore[union-attr]
    )


def _get_session_repo(request: Request):  # type: ignore[no-untyped-def]
    return request.app.state.research_service._repos.sessions


def _get_step_repo(request: Request):  # type: ignore[no-untyped-def]
    return request.app.state.research_service._repos.steps


def _get_llm_repo(request: Request):  # type: ignore[no-untyped-def]
    return getattr(request.app.state, "llm_call_repo", None)
