"""POST /articles/{id}/repurpose/linkedin[/publish] (AUTHOR-013).

Turns a CanonicalArticle into a standalone LinkedIn post draft the editor
reviews/edits in a modal, then publishes through the `linkedin_post`
platform via `PublishingService.publish`'s `content_override` seam
(ADR-004: this router never builds platform payloads itself — it only
supplies the override text; the pure `LinkedInPostTransformer` and the
`PublishingService` own everything else).

Mirrors `article_metadata.py::regenerate_seo_field` for the prompt-
override binding / tracked-LLM-step pattern (L-013: session id resolved
via `ArticleDraftRepository.find_by_article_id`, never the provenance
research_session_id which is the topic id).
"""

from __future__ import annotations

from collections.abc import Mapping
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from starlette.status import HTTP_201_CREATED

from src.agents.prompts import bind_prompt_overrides
from src.api.auth.schemas import TokenPayload
from src.api.dependencies import require_editor_or_above
from src.api.errors import ServiceUnavailableError
from src.api.prompt_scope import load_prompt_overrides
from src.api.rate_limiter import limiter
from src.api.routers.canonical_articles import _get_content_service
from src.api.schemas.publishing import PublishResponse
from src.models.content import CanonicalArticle
from src.services.content import ContentService
from src.services.publishing.linkedin.repurpose import (
    LinkedInPostDraft,
    RepurposeInput,
    repurpose_to_linkedin,
)
from src.utils.tracked_llm import current_session_id, current_step_name

logger = structlog.get_logger()

linkedin_repurpose_router = APIRouter()


class LinkedInRepurposeRequest(BaseModel):
    instruction: str | None = Field(default=None, max_length=500)


class LinkedInPostDraftResponse(BaseModel):
    article_id: UUID
    hook: str
    beats: list[str]
    cta: str
    hashtags: list[str]
    text: str
    char_count: int
    slop_score: int
    slop_rating: str
    model: str
    truncated: bool


class LinkedInPublishRequest(BaseModel):
    text: str = Field(min_length=1, max_length=3000)


async def _repurpose(
    svc: ContentService, article: CanonicalArticle, instruction: str | None
) -> LinkedInPostDraft:
    """One tracked LLM call; bound to the draft's REAL session id (L-013)."""
    llm = svc.deps.llm
    if llm is None:
        raise ServiceUnavailableError(
            message="LLM not configured. Set COGNIFY_ANTHROPIC_API_KEY."
        )
    inp = RepurposeInput(article=article, instruction=instruction)
    draft = await svc.repos.drafts.find_by_article_id(article.id)
    if draft is None:
        return await repurpose_to_linkedin(inp, llm)
    session_token = current_session_id.set(draft.session_id)
    step_token = current_step_name.set("linkedin_repurpose")
    try:
        return await repurpose_to_linkedin(inp, llm)
    finally:
        current_step_name.reset(step_token)
        current_session_id.reset(session_token)


@linkedin_repurpose_router.post(
    "/articles/{article_id}/repurpose/linkedin",
    response_model=LinkedInPostDraftResponse,
    summary="Repurpose an article into a LinkedIn post draft (not persisted)",
)
@limiter.limit("10/minute")
async def repurpose_linkedin(
    request: Request,
    article_id: UUID,
    body: LinkedInRepurposeRequest,
    user: TokenPayload = Depends(require_editor_or_above),
    overrides: Mapping[str, str] = Depends(load_prompt_overrides),
) -> LinkedInPostDraftResponse:
    svc = _get_content_service(request)
    article = await svc.get_article(article_id)
    with bind_prompt_overrides(overrides):
        draft = await _repurpose(svc, article, body.instruction)
    return LinkedInPostDraftResponse(article_id=article_id, **draft.model_dump())


@linkedin_repurpose_router.post(
    "/articles/{article_id}/repurpose/linkedin/publish",
    response_model=PublishResponse,
    status_code=HTTP_201_CREATED,
    summary="Publish an edited LinkedIn post draft",
)
@limiter.limit("5/minute")
async def publish_linkedin_post(
    request: Request,
    article_id: UUID,
    body: LinkedInPublishRequest,
    user: TokenPayload = Depends(require_editor_or_above),
) -> PublishResponse:
    publishing_service = request.app.state.publishing_service
    if "linkedin_post" not in publishing_service._platforms:
        raise ServiceUnavailableError(
            code="platform_unavailable", message="LinkedIn is not connected"
        )
    result = await publishing_service.publish(
        article_id, "linkedin_post", content_override=body.text
    )
    return PublishResponse(
        article_id=result.article_id,
        platform=result.platform,
        status=result.status,
        external_id=result.external_id,
        external_url=result.external_url,
        published_at=result.published_at,
        error_message=result.error_message,
    )


__all__ = ["linkedin_repurpose_router"]
