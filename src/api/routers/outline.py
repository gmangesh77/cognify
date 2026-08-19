"""Outline review, approval, and session-cancellation endpoints.

Lets an editor review/edit the LLM-generated outline before section
drafting runs (gated by `require_outline_approval`), and cancel an
in-flight research/content pipeline (AUTHOR-002, Task 4).
"""

from __future__ import annotations

from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.status import HTTP_202_ACCEPTED

from src.api.auth.schemas import TokenPayload
from src.api.dependencies import require_editor_or_above, require_viewer_or_above
from src.api.errors import ServiceUnavailableError
from src.api.rate_limiter import limiter
from src.api.routers.research import _get_research_service_readonly, _get_session_tasks
from src.api.routers.research_pipeline import PipelineDeps, _run_drafting_pipeline
from src.api.schemas.outline import (
    OutlineResponse,
    RegenerateOutlineRequest,
    SessionActionResponse,
)
from src.models.content_pipeline import ArticleDraft, ArticleOutline
from src.models.session_events import TERMINAL_STATUSES
from src.services.content.outline_gate import OutlineGateService
from src.services.research import SessionDetail

logger = structlog.get_logger()

outline_router = APIRouter()


def _parse_uuid(value: str) -> UUID:
    try:
        return UUID(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid session id") from exc


def _get_outline_gate(request: Request) -> OutlineGateService:
    gate = getattr(request.app.state, "outline_gate", None)
    if gate is None:
        raise ServiceUnavailableError(
            message="Outline review is not configured for this deployment."
        )
    return gate  # type: ignore[no-any-return]


def _to_response(draft: ArticleDraft) -> OutlineResponse:
    if draft.outline is None:
        raise HTTPException(status_code=404, detail="Draft has no outline yet")
    return OutlineResponse(
        draft_id=draft.id,
        session_id=draft.session_id,
        status=str(draft.status),
        outline=draft.outline,
    )


async def _require_awaiting_review(request: Request, session_id: UUID) -> SessionDetail:
    svc = _get_research_service_readonly(request)
    detail = await svc.get_session(session_id)
    if detail.session.status != "awaiting_outline_review":
        raise HTTPException(
            status_code=409,
            detail=(
                f"Session status is {detail.session.status!r}, expected "
                "'awaiting_outline_review'"
            ),
        )
    return detail


@limiter.limit("30/minute")
@outline_router.get(
    "/research/sessions/{session_id}/outline",
    response_model=OutlineResponse,
)
async def get_outline(
    request: Request,
    session_id: str,
    user: TokenPayload = Depends(require_viewer_or_above),
) -> OutlineResponse:
    gate = _get_outline_gate(request)
    draft = await gate.get_outline(_parse_uuid(session_id))
    return _to_response(draft)


@limiter.limit("30/minute")
@outline_router.put(
    "/research/sessions/{session_id}/outline",
    response_model=OutlineResponse,
)
async def update_outline(
    request: Request,
    session_id: str,
    body: ArticleOutline,
    user: TokenPayload = Depends(require_editor_or_above),
) -> OutlineResponse:
    sid = _parse_uuid(session_id)
    await _require_awaiting_review(request, sid)
    gate = _get_outline_gate(request)
    try:
        draft = await gate.update_outline(sid, body)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc).split("; ")) from exc
    return _to_response(draft)


@limiter.limit("5/minute")
@outline_router.post(
    "/research/sessions/{session_id}/outline/regenerate",
    response_model=OutlineResponse,
)
async def regenerate_outline(
    request: Request,
    session_id: str,
    body: RegenerateOutlineRequest,
    user: TokenPayload = Depends(require_editor_or_above),
) -> OutlineResponse:
    sid = _parse_uuid(session_id)
    await _require_awaiting_review(request, sid)
    gate = _get_outline_gate(request)
    draft = await gate.regenerate_outline(sid, body.instruction)
    return _to_response(draft)


@limiter.limit("10/minute")
@outline_router.post(
    "/research/sessions/{session_id}/outline/approve",
    response_model=SessionActionResponse,
    status_code=HTTP_202_ACCEPTED,
)
async def approve_outline(
    request: Request,
    session_id: str,
    user: TokenPayload = Depends(require_editor_or_above),
) -> SessionActionResponse:
    sid = _parse_uuid(session_id)
    await _require_awaiting_review(request, sid)
    svc = _get_research_service_readonly(request)
    # Flip the status synchronously (not inside the background task) so a
    # second approve request racing right behind this one sees
    # "generating_article" (not "awaiting_outline_review") and 409s at the
    # _require_awaiting_review check above. _run_drafting_pipeline sets the
    # same status again once it starts, which is harmless.
    await svc.update_session_status(sid, "generating_article")
    deps = PipelineDeps(
        research_svc=svc,
        content_svc=getattr(request.app.state, "content_service", None),
        outline_gate=_get_outline_gate(request),
    )
    registry = _get_session_tasks(request)
    try:
        registry.spawn(sid, _run_drafting_pipeline(deps, sid))
    except RuntimeError as exc:
        # Belt-and-suspenders: a true concurrent race (both requests pass
        # the awaiting-review check before either writes the status
        # change) is still closed here, since the registry only ever
        # tracks one running task per session.
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    logger.info("outline_approved", session_id=str(sid))
    return SessionActionResponse(session_id=sid, status="generating_article")


@limiter.limit("10/minute")
@outline_router.post(
    "/research/sessions/{session_id}/cancel",
    response_model=SessionActionResponse,
)
async def cancel_session(
    request: Request,
    session_id: str,
    user: TokenPayload = Depends(require_editor_or_above),
) -> SessionActionResponse:
    sid = _parse_uuid(session_id)
    svc = _get_research_service_readonly(request)
    detail = await svc.get_session(sid)
    if detail.session.status in TERMINAL_STATUSES:
        raise HTTPException(status_code=409, detail="Session is already terminal")
    registry = _get_session_tasks(request)
    registry.cancel(sid)
    await svc.update_session_status(sid, "cancelled")
    logger.info("session_cancelled", session_id=str(sid))
    return SessionActionResponse(session_id=sid, status="cancelled")
