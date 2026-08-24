"""Usage endpoints: cost roll-up per session and per article (AUTHOR-005).

Read-only. The article route resolves the session ONLY through
``ArticleDraftRepository.find_by_article_id`` → ``draft.session_id`` —
never ``provenance.research_session_id``, which holds the topic id (L-013).
"""

from __future__ import annotations

from typing import cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request

from src.api.auth.schemas import TokenPayload
from src.api.dependencies import require_viewer_or_above
from src.api.rate_limiter import limiter
from src.api.schemas.usage import SessionUsageResponse, to_usage_response
from src.services.content_repositories import ArticleDraftRepository
from src.services.usage import compute_session_usage, effective_pricing
from src.utils.llm_call_repo import LlmCallRepository

usage_router = APIRouter()


def _llm_repo(request: Request) -> LlmCallRepository:
    repo = getattr(request.app.state, "llm_call_repo", None)
    if repo is None:
        raise HTTPException(
            status_code=503, detail="LLM call tracking is not configured"
        )
    return cast(LlmCallRepository, repo)


def _draft_repo(request: Request) -> ArticleDraftRepository:
    repos = getattr(request.app.state, "content_repos", None)
    if repos is None:
        raise HTTPException(
            status_code=503, detail="Content repositories are not configured"
        )
    return cast(ArticleDraftRepository, repos.drafts)


async def _session_usage(request: Request, session_id: UUID) -> SessionUsageResponse:
    calls = await _llm_repo(request).list_by_session(session_id)
    draft = await _draft_repo(request).find_latest_by_session(session_id)
    visuals = draft.visuals if draft else []
    pricing = effective_pricing(request.app.state.settings.llm_pricing_json)
    return to_usage_response(session_id, compute_session_usage(calls, visuals, pricing))


@usage_router.get(
    "/research/sessions/{session_id}/usage",
    response_model=SessionUsageResponse,
    summary="Token/image cost roll-up for a research session",
)
@limiter.limit("60/minute")
async def get_session_usage(
    request: Request,
    session_id: UUID,
    user: TokenPayload = Depends(require_viewer_or_above),
) -> SessionUsageResponse:
    return await _session_usage(request, session_id)


@usage_router.get(
    "/articles/{article_id}/usage",
    response_model=SessionUsageResponse,
    summary="Token/image cost roll-up for the session that produced an article",
)
@limiter.limit("60/minute")
async def get_article_usage(
    request: Request,
    article_id: UUID,
    user: TokenPayload = Depends(require_viewer_or_above),
) -> SessionUsageResponse:
    draft = await _draft_repo(request).find_by_article_id(article_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="No draft found for this article")
    return await _session_usage(request, draft.session_id)
