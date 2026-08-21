"""POST /content/section-regenerate (AUTHOR-004, program plan §5.5).

Lives in its own module because `content.py` is already over the
200-line cap; mounted on the same `/content` prefix. Uses the shared
helpers in `content_shared.py` so the 422 anchor-violation payload is
byte-identical to `/content/section-update`. The LLM comes from
`app.state.content_service.deps` (TrackedChatModel → Pipeline Debug).

422 semantics: the service re-prefixes the original H2 and carries every
`data-spec-id` block by position, so a regenerate can never itself drop
the heading or a spec-id marker. The only anchor violation this route can
produce is `heading_text` — an image spec bound to a heading the article
no longer has. A `spec_id` violation only arises on the accept side
(`/content/section-update`) when the editor removes a carried figure.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi import status as http_status
from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel, Field

from src.api.auth.schemas import TokenPayload
from src.api.dependencies import require_editor_or_above
from src.api.rate_limiter import limiter
from src.api.routers.content_shared import (
    WordDiffEntry,
    anchor_violation_http,
    get_history_service,
)
from src.services.content.section_history import (
    AnchorViolationError,
    ArticleNotFoundError,
    SectionNotFoundError,
)
from src.services.content.section_history_contracts import VersionRepoProtocol
from src.services.content.section_regenerate import SectionRegenerateService
from src.services.content.section_regenerate_models import (
    DraftContextMissingError,
    RegenerateCommand,
    RegenerateDeps,
    RegenerateResult,
)
from src.services.content_repositories import ContentRepositories
from src.services.milvus_retriever import MilvusRetriever

logger = structlog.get_logger()

content_regenerate_router = APIRouter(prefix="/content")

_REGENERATE_ERRORS = (
    ArticleNotFoundError,
    SectionNotFoundError,
    DraftContextMissingError,
    AnchorViolationError,
)


class SectionRegenerateRequest(BaseModel):
    article_id: UUID
    section_index: int = Field(ge=0, le=500, description="0-based H2 (outline) index")
    instruction: str | None = Field(default=None, max_length=2000)


class SectionRegenerateResponse(BaseModel):
    section_id: str
    section_index: int
    markdown: str
    diff: list[WordDiffEntry]
    version_id: str
    model: str
    word_count: int
    tokens_input: int | None = None
    tokens_output: int | None = None
    instruction: str | None = None


@dataclass(frozen=True)
class _RegenerateState:
    llm: BaseChatModel
    repos: ContentRepositories
    versions: VersionRepoProtocol
    retriever: MilvusRetriever | None


@content_regenerate_router.post(
    "/section-regenerate", response_model=SectionRegenerateResponse
)
@limiter.limit("10/minute")
async def section_regenerate(
    request: Request,
    body: SectionRegenerateRequest,
    user: TokenPayload = Depends(require_editor_or_above),
) -> SectionRegenerateResponse:
    """Redraft one section; returns candidate markdown + diff (body untouched)."""
    service = _get_regenerate_service(request)
    try:
        result = await service.regenerate(_command(body, user))
    except _REGENERATE_ERRORS as exc:
        raise _map_regenerate_error(exc) from exc
    return _to_response(body, result)


def _command(body: SectionRegenerateRequest, user: TokenPayload) -> RegenerateCommand:
    return RegenerateCommand(
        article_id=body.article_id,
        section_index=body.section_index,
        instruction=body.instruction,
        created_by=user.sub,
    )


def _map_regenerate_error(exc: Exception) -> HTTPException:
    """404 not found / 409 no draft context / 422 anchor violation (shared shape)."""
    if isinstance(exc, AnchorViolationError):
        return anchor_violation_http(exc)
    if isinstance(exc, DraftContextMissingError):
        return HTTPException(http_status.HTTP_409_CONFLICT, str(exc))
    return HTTPException(http_status.HTTP_404_NOT_FOUND, str(exc))


def _to_response(
    body: SectionRegenerateRequest, result: RegenerateResult
) -> SectionRegenerateResponse:
    return SectionRegenerateResponse(
        section_id=result.section_id,
        section_index=result.section_index,
        markdown=result.markdown,
        diff=[WordDiffEntry.from_op(op) for op in result.diff],
        version_id=str(result.version_id),
        model=result.model,
        word_count=result.word_count,
        tokens_input=result.tokens_input,
        tokens_output=result.tokens_output,
        instruction=body.instruction,
    )


def _resolve_regenerate_state(request: Request) -> _RegenerateState:
    """Read app.state; 503 when the LLM, content repos or version repo are missing."""
    state = request.app.state
    deps = getattr(getattr(state, "content_service", None), "deps", None)
    llm = getattr(deps, "llm", None)
    repos = getattr(state, "content_repos", None)
    versions = getattr(state, "section_version_repo", None)
    if llm is None or repos is None or versions is None:
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="section regenerate is not configured",
        )
    return _RegenerateState(
        llm=llm,
        repos=repos,
        versions=versions,
        retriever=getattr(deps, "retriever", None),
    )


def _get_regenerate_service(request: Request) -> SectionRegenerateService:
    state = _resolve_regenerate_state(request)
    return SectionRegenerateService(
        RegenerateDeps(
            history=get_history_service(request),
            versions=state.versions,
            drafts=state.repos.drafts,
            research=state.repos.research,
            llm=state.llm,
            retriever=state.retriever,
        )
    )


__all__ = ["content_regenerate_router"]
