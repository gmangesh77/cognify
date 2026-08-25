"""SSE progress stream + article lookup for a research/article session (AUTHOR-001)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from src.api.auth.schemas import TokenPayload
from src.api.dependencies import require_viewer_or_above
from src.api.rate_limiter import limiter
from src.api.routers.research import _get_research_service_readonly
from src.services.session_events import TailOptions, tail_session

session_events_router = APIRouter()

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",
    "Connection": "keep-alive",
}


def _tail_options(request: Request) -> TailOptions:
    s = request.app.state.settings
    return TailOptions(
        poll_seconds=s.session_events_poll_seconds,
        keepalive_seconds=s.session_events_keepalive_seconds,
        complete_grace_seconds=s.session_events_complete_grace_seconds,
        max_seconds=s.session_events_max_seconds,
    )


def _parse_uuid(value: str) -> UUID:
    try:
        return UUID(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid session id") from exc


# Route decorator OUTERMOST or slowapi never evaluates the limit
# (AUTHOR-006 lesson).
@session_events_router.get("/research/sessions/{session_id}/events")
@limiter.limit("30/minute")
async def stream_session_events(
    request: Request,
    session_id: str,
    user: TokenPayload = Depends(require_viewer_or_above),
) -> StreamingResponse:
    svc = _get_research_service_readonly(request)
    sid = _parse_uuid(session_id)

    async def gen() -> AsyncIterator[str]:
        async for event in tail_session(svc, sid, _tail_options(request)):
            if await request.is_disconnected():
                return
            yield event.to_sse()

    return StreamingResponse(
        gen(), media_type="text/event-stream", headers=_SSE_HEADERS
    )


@session_events_router.get("/research/sessions/{session_id}/article")
@limiter.limit("60/minute")
async def get_session_article(
    request: Request,
    session_id: str,
    user: TokenPayload = Depends(require_viewer_or_above),
) -> dict[str, str]:
    """Resolve the article a session produced — via the DRAFT's real
    session id (L-013). Real articles store the TOPIC id in
    `provenance.research_session_id`, so the old provenance-keyed
    `find_by_session` never matched live data (dead View-article button);
    it remains only as a fallback for draft-less legacy rows."""
    sid = _parse_uuid(session_id)
    repos = getattr(request.app.state, "content_repos", None)
    if repos is not None:
        draft = await repos.drafts.find_latest_by_session(sid)
        if draft is not None and draft.article_id is not None:
            return {"article_id": str(draft.article_id)}
    repo = getattr(request.app.state, "article_repo", None)
    article = await repo.find_by_session(sid) if repo else None
    if article is None:
        raise HTTPException(status_code=404, detail="No article for session")
    return {"article_id": str(article.id)}
