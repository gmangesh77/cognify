"""Per-section prose editing API (VISUAL-011 / Phase 8).

Sibling to `visuals.py`. Owns the editor's fine-grained prose-control
surface — section/paragraph rewrite, manual save, tone presets, history
listing, and restore. The active article body still lives on
`CanonicalArticle.body_markdown`; the `section_versions` table is an
append-only audit sidecar consumed by the history drawer.

Boundary invariants enforced here:
- Auth + RBAC (editor or admin) on every endpoint.
- Server-side prompt expansion for tone presets — frontend posts
  `{ "preset": "shorter" }`, the backend expands to the curated
  instruction template before calling Claude.
- Anchor preservation. Every persistence path runs the validator and
  returns HTTP 422 with a structured violation list when an edit drops
  a `data-spec-id` marker or renames a heading bound to a
  `before_heading` placement.
- Service-Layer pattern. Route handlers depend on
  `SectionHistoryService` and the rewriter — no direct DB calls.
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi import status as http_status
from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel, ConfigDict, Field

from src.api.auth.schemas import TokenPayload
from src.api.dependencies import require_editor_or_above
from src.api.rate_limiter import limiter
from src.api.routers.content_shared import (
    WordDiffEntry,
    anchor_violation_http,
    get_history_service,
)
from src.config.settings import Settings
from src.services.content.humanize_preview import preview_humanization
from src.services.content.section_history import (
    AnchorViolationError,
    ArticleNotFoundError,
    SectionNotFoundError,
)
from src.services.content.section_history_contracts import (
    make_section_id,
    parse_section_id,
)
from src.services.content.section_rewriter import (
    TONE_PRESETS,
    RewriteScope,
    TonePreset,
    expand_tone_preset,
    rewrite_section_prose,
)

logger = structlog.get_logger()

content_router = APIRouter(prefix="/content")


# ---------------------------------------------------------------------------
# /content/section-rewrite
# ---------------------------------------------------------------------------


class SectionRewriteRequest(BaseModel):
    section_id: str = Field(min_length=3, max_length=80)
    instruction: str = Field(min_length=1, max_length=2000)
    scope: RewriteScope = "section"
    paragraph_index: int | None = Field(default=None, ge=0)
    current_markdown: str | None = Field(default=None, max_length=20000)
    audience_persona: str | None = Field(default=None, max_length=60)


class SectionRewriteResponse(BaseModel):
    section_id: str
    markdown_fragment: str
    diff: list[WordDiffEntry]
    model_name: str = Field(alias="model")
    prompt_used: str
    instruction: str
    tokens_input: int | None
    tokens_output: int | None
    usd: float | None

    model_config = ConfigDict(populate_by_name=True)


@content_router.post("/section-rewrite", response_model=SectionRewriteResponse)
@limiter.limit("30/minute")
async def section_rewrite(
    request: Request,
    body: SectionRewriteRequest,
    user: TokenPayload = Depends(require_editor_or_above),
) -> SectionRewriteResponse:
    """Apply Claude-driven prose refinement to one section / paragraph."""
    history = get_history_service(request)
    current_md = body.current_markdown
    if current_md is None:
        article_id, section_index = _parse_or_400(body.section_id)
        try:
            _, section = await history.get_section_markdown(article_id, section_index)
        except ArticleNotFoundError as exc:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"article not found: {exc}",
            ) from exc
        except SectionNotFoundError as exc:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=str(exc),
            ) from exc
        current_md = section.text

    llm = _get_content_llm(request)
    result = await rewrite_section_prose(
        section_id=body.section_id,
        instruction=body.instruction,
        current_markdown=current_md,
        scope=body.scope,
        paragraph_index=body.paragraph_index,
        audience_persona=body.audience_persona,
        llm=llm,
    )
    return SectionRewriteResponse(
        section_id=body.section_id,
        markdown_fragment=result.markdown_fragment,
        diff=[WordDiffEntry.from_op(op) for op in result.diff],
        model=result.model,
        prompt_used=result.prompt_used,
        instruction=result.instruction,
        tokens_input=result.tokens_input,
        tokens_output=result.tokens_output,
        usd=result.usd,
    )


# ---------------------------------------------------------------------------
# /content/section-update
# ---------------------------------------------------------------------------


class SectionUpdateRequest(BaseModel):
    section_id: str = Field(min_length=3, max_length=80)
    markdown: str = Field(min_length=1, max_length=20000)
    source: Literal["manual", "ai", "tone_preset", "restore", "regenerate"] = "manual"
    instruction: str | None = Field(default=None, max_length=2000)


class SectionUpdateResponse(BaseModel):
    section_id: str
    version_id: str
    persisted_markdown: str


@content_router.post("/section-update", response_model=SectionUpdateResponse)
@limiter.limit("60/minute")
async def section_update(
    request: Request,
    body: SectionUpdateRequest,
    user: TokenPayload = Depends(require_editor_or_above),
) -> SectionUpdateResponse:
    """Persist a section edit. Validates anchors, appends version row."""
    history = get_history_service(request)
    article_id, section_index = _parse_or_400(body.section_id)
    try:
        result = await history.persist_section_update(
            article_id=article_id,
            section_index=section_index,
            new_section_markdown=body.markdown,
            source=body.source,
            instruction=body.instruction,
            created_by=user.sub,
        )
    except ArticleNotFoundError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"article not found: {exc}",
        ) from exc
    except SectionNotFoundError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except AnchorViolationError as exc:
        raise anchor_violation_http(exc) from exc
    return SectionUpdateResponse(
        section_id=body.section_id,
        version_id=str(result.version_id),
        persisted_markdown=result.new_section_markdown,
    )


# ---------------------------------------------------------------------------
# /content/paragraph-tone
# ---------------------------------------------------------------------------


class ParagraphToneRequest(BaseModel):
    section_id: str = Field(min_length=3, max_length=80)
    paragraph_index: int = Field(ge=0)
    preset: TonePreset
    current_markdown: str | None = Field(default=None, max_length=20000)
    audience_persona: str | None = Field(default=None, max_length=60)


@content_router.post("/paragraph-tone", response_model=SectionRewriteResponse)
@limiter.limit("30/minute")
async def paragraph_tone(
    request: Request,
    body: ParagraphToneRequest,
    user: TokenPayload = Depends(require_editor_or_above),
) -> SectionRewriteResponse:
    """Thin wrapper around `section_rewrite` that expands a tone preset."""
    if body.preset not in TONE_PRESETS:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"unknown tone preset: {body.preset}",
        )
    instruction = expand_tone_preset(body.preset)
    rewrite = SectionRewriteRequest(
        section_id=body.section_id,
        instruction=instruction,
        scope="paragraph",
        paragraph_index=body.paragraph_index,
        current_markdown=body.current_markdown,
        audience_persona=body.audience_persona,
    )
    result: SectionRewriteResponse = await section_rewrite(request, rewrite, user)
    return result


# ---------------------------------------------------------------------------
# /content/section/{id}/history
# ---------------------------------------------------------------------------


class SectionVersionEntry(BaseModel):
    id: str
    section_id: str
    section_index: int
    source: str
    instruction: str | None
    markdown: str
    model_name: str | None = Field(alias="model")
    tokens_input: int | None
    tokens_output: int | None
    usd: float | None
    created_at: str
    created_by: str | None

    model_config = ConfigDict(populate_by_name=True)


class SectionHistoryResponse(BaseModel):
    section_id: str
    versions: list[SectionVersionEntry]


@content_router.get(
    "/section/{section_id}/history", response_model=SectionHistoryResponse
)
@limiter.limit("60/minute")
async def section_history_list(
    request: Request,
    section_id: str,
    limit: int = 50,
    user: TokenPayload = Depends(require_editor_or_above),
) -> SectionHistoryResponse:
    """List prior versions of a section, newest first."""
    history = get_history_service(request)
    try:
        parse_section_id(section_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    bounded = max(1, min(limit, 200))
    versions = await history.list_history(section_id, bounded)
    return SectionHistoryResponse(
        section_id=section_id,
        versions=[
            SectionVersionEntry(
                id=str(v.id),  # type: ignore[attr-defined]
                section_id=v.section_id,  # type: ignore[attr-defined]
                section_index=v.section_index,  # type: ignore[attr-defined]
                source=v.source,  # type: ignore[attr-defined]
                instruction=v.instruction,  # type: ignore[attr-defined]
                markdown=v.markdown,  # type: ignore[attr-defined]
                model=v.model,  # type: ignore[attr-defined]
                tokens_input=v.tokens_input,  # type: ignore[attr-defined]
                tokens_output=v.tokens_output,  # type: ignore[attr-defined]
                usd=v.usd,  # type: ignore[attr-defined]
                created_at=v.created_at.isoformat(),  # type: ignore[attr-defined]
                created_by=v.created_by,  # type: ignore[attr-defined]
            )
            for v in versions
        ],
    )


# ---------------------------------------------------------------------------
# /content/section/{id}/restore
# ---------------------------------------------------------------------------


class SectionRestoreRequest(BaseModel):
    version_id: str = Field(min_length=8)


@content_router.post(
    "/section/{section_id}/restore", response_model=SectionUpdateResponse
)
@limiter.limit("30/minute")
async def section_restore(
    request: Request,
    section_id: str,
    body: SectionRestoreRequest,
    user: TokenPayload = Depends(require_editor_or_above),
) -> SectionUpdateResponse:
    """Restore a section to a prior version."""
    history = get_history_service(request)
    try:
        parse_section_id(section_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    try:
        version_uuid = UUID(body.version_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"invalid version_id: {body.version_id}",
        ) from exc
    try:
        result = await history.restore(
            section_id=section_id,
            version_id=version_uuid,
            created_by=user.sub,
        )
    except (ArticleNotFoundError, SectionNotFoundError) as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except AnchorViolationError as exc:
        raise anchor_violation_http(exc) from exc
    return SectionUpdateResponse(
        section_id=section_id,
        version_id=str(result.version_id),
        persisted_markdown=result.new_section_markdown,
    )


# ---------------------------------------------------------------------------
# /content/humanize-preview  (DASH-007)
# ---------------------------------------------------------------------------


class HumanizePreviewRequest(BaseModel):
    section_id: str = Field(min_length=3, max_length=80)
    title: str = Field(default="Section", max_length=200)
    current_markdown: str | None = Field(default=None, max_length=20000)


class SlopScoreEntry(BaseModel):
    score: int
    rating: str
    violation_count: int


class HumanizePreviewResponse(BaseModel):
    section_id: str
    original: str
    rewritten: str
    diff: list[WordDiffEntry]
    score_before: SlopScoreEntry
    score_after: SlopScoreEntry
    llm_called: bool
    model_name: str | None = Field(default=None, alias="model")

    model_config = ConfigDict(populate_by_name=True)


@content_router.post("/humanize-preview", response_model=HumanizePreviewResponse)
@limiter.limit("20/minute")
async def humanize_preview(
    request: Request,
    body: HumanizePreviewRequest,
    user: TokenPayload = Depends(require_editor_or_above),
) -> HumanizePreviewResponse:
    """Run a one-shot humanization pass and return the diff for review.

    The result is preview-only — to persist, the frontend POSTs the
    `rewritten` markdown through `/content/section-update`, which runs
    the anchor-preservation validator and appends a version row.
    """
    history = get_history_service(request)
    article_id, section_index = _parse_or_400(body.section_id)
    current_md = body.current_markdown
    if current_md is None:
        try:
            _, section = await history.get_section_markdown(article_id, section_index)
        except ArticleNotFoundError as exc:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"article not found: {exc}",
            ) from exc
        except SectionNotFoundError as exc:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=str(exc),
            ) from exc
        current_md = section.text

    llm = _get_content_llm(request)
    preview = await preview_humanization(
        section_index=section_index,
        title=body.title,
        markdown=current_md,
        llm=llm,
    )
    return HumanizePreviewResponse(
        section_id=body.section_id,
        original=preview.original,
        rewritten=preview.rewritten,
        diff=[WordDiffEntry.from_op(op) for op in preview.diff],
        score_before=SlopScoreEntry(
            score=preview.score_before.score,
            rating=preview.score_before.rating,
            violation_count=len(preview.score_before.violations),
        ),
        score_after=SlopScoreEntry(
            score=preview.score_after.score,
            rating=preview.score_after.rating,
            violation_count=len(preview.score_after.violations),
        ),
        llm_called=preview.llm_called,
        model=preview.model,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_or_400(section_id: str) -> tuple[UUID, int]:
    try:
        return parse_section_id(section_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


def _get_content_llm(request: Request) -> BaseChatModel:
    """Prefer the pipeline's (tracked) LLM so rewrite + regenerate share cost tracking.

    NOTE: when `content_service` deps are present, section-rewrite and
    humanize-preview inherit the pipeline model config (incl.
    `max_tokens=4096`) instead of the 30 s ad-hoc ChatAnthropic below;
    the fallback path is unchanged.
    """
    service = getattr(request.app.state, "content_service", None)
    llm = getattr(getattr(service, "deps", None), "llm", None)
    if llm is not None:
        return llm  # type: ignore[no-any-return]
    return _build_anthropic_llm(request.app.state.settings)


def _build_anthropic_llm(settings: Settings) -> ChatAnthropic:
    """Fallback Claude model for prose rewrites (no ContentService on app.state)."""
    from pydantic import SecretStr

    return ChatAnthropic(
        model_name=settings.anthropic_model,
        api_key=SecretStr(settings.anthropic_api_key),
        timeout=30.0,
        stop=None,
        max_retries=2,
    )


# Helper exposed for tests / ad-hoc shell use.
make_section_id = make_section_id

__all__ = ["content_router", "make_section_id"]
