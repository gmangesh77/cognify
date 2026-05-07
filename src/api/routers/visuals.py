"""Visual-generation HTTP API.

Phase 1 (VISUAL-004): exposes the visual-style catalogue, persona register,
and banned-cliché block as a single boot-time fetch for the frontend
(`GET /api/v1/visuals/styles`).

Phase 4 (VISUAL-007): adds the Studio API endpoints used by the
frontend Visual Studio panel:

- `POST /visuals/plan`              — plan ImageSpecs for an article cover
                                       and optionally one section.
- `POST /visuals/render`            — render a single ImageSpec.
- `POST /visuals/upload`            — multipart upload of a brand asset.
- `POST /visuals/fetch-from-url`    — SSRF-guarded fetch of a remote image.
- `POST /visuals/section-html-refine` — Claude-driven HTML refinement of
                                         a section.

All non-public endpoints require auth (editor or admin RBAC). Each
mutating endpoint is rate-limited via slowapi.
"""

from __future__ import annotations

import base64
from typing import Literal

import structlog
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi import status as http_status
from langchain_anthropic import ChatAnthropic
from pydantic import BaseModel, ConfigDict, Field

from src.api.auth.schemas import TokenPayload
from src.api.dependencies import require_editor_or_above
from src.api.rate_limiter import limiter
from src.config.settings import Settings
from src.models.content_pipeline import SectionDraft
from src.models.research import TopicInput
from src.models.visual import ImageSpec
from src.services.visuals import init_registry as init_visual_registry
from src.services.visuals.banned_cliches import BANNED_CLICHES_BLOCK
from src.services.visuals.cost import aggregate_cost
from src.services.visuals.image_planner import (
    plan_article_cover,
    plan_section_images,
)
from src.services.visuals.object_storage import (
    ObjectStorage,
    StoredObject,
    make_object_key,
    select_object_storage,
)
from src.services.visuals.persona_directions import (
    DEFAULT_PERSONA,
    PERSONA_VISUAL_DIRECTIONS,
)
from src.services.visuals.prompt_composer import build_prompt
from src.services.visuals.providers.base import ImageProvider, ImageProviderError
from src.services.visuals.registry import ImageProviderRegistry
from src.services.visuals.safe_http import (
    FetchedImage,
    HostBlocked,
    MimeRejected,
    SafeHttpError,
    SafeHttpFetcher,
    SchemeRejected,
    SizeExceeded,
)
from src.services.visuals.section_html_refiner import (
    SectionHtmlRefineResult,
    refine_section_html,
)
from src.services.visuals.visual_styles import (
    ROLE_STYLE_DEFAULTS,
    VISUAL_STYLES,
    planner_catalogue_block,
)

logger = structlog.get_logger()

visuals_router = APIRouter(prefix="/visuals")


# ---------------------------------------------------------------------------
# /visuals/styles  (Phase 1)
# ---------------------------------------------------------------------------


class StyleEntry(BaseModel):
    key: str
    label: str
    category: Literal["photo", "illustration", "editorial", "technical"]
    default_aspect: Literal["16:9", "1:1", "4:3", "3:4", "4:5"]
    short_desc: str
    prompt_fragment: str


class PersonaEntry(BaseModel):
    key: str
    direction: str


class StylesResponse(BaseModel):
    styles: list[StyleEntry]
    role_defaults: dict[str, str]
    personas: list[PersonaEntry]
    default_persona: str
    banned_cliches_block: str
    planner_catalogue_block: str


@visuals_router.get("/styles", response_model=StylesResponse)
async def get_visual_styles() -> StylesResponse:
    """Return the full visual-style catalogue, persona register, and cliché block.

    Single source of truth (ADR-005). The frontend boots, calls this once,
    and caches. There is no mirrored TypeScript catalogue — everything in
    this response is owned by `src/services/visuals/`.
    """
    return StylesResponse(
        styles=[StyleEntry.model_validate(entry) for entry in VISUAL_STYLES.values()],
        role_defaults=dict(ROLE_STYLE_DEFAULTS),
        personas=[
            PersonaEntry(key=key, direction=direction)
            for key, direction in PERSONA_VISUAL_DIRECTIONS.items()
        ],
        default_persona=DEFAULT_PERSONA,
        banned_cliches_block=BANNED_CLICHES_BLOCK,
        planner_catalogue_block=planner_catalogue_block(),
    )


# ---------------------------------------------------------------------------
# Shared schemas
# ---------------------------------------------------------------------------


class _SectionInput(BaseModel):
    """Section context for the planner.

    A subset of `SectionDraft` — we don't expose pipeline internals to the
    frontend; the studio passes back what it needs the planner to see.
    """

    section_index: int = Field(ge=0)
    title: str = Field(min_length=1)
    body_markdown: str = Field(min_length=1)


class _TopicInput(BaseModel):
    """Topic context for the planner."""

    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    domain: str = Field(min_length=1)


# ---------------------------------------------------------------------------
# /visuals/plan
# ---------------------------------------------------------------------------


class PlanRequest(BaseModel):
    """Plan ImageSpecs for an article cover + optional section."""

    topic: _TopicInput
    section: _SectionInput | None = None
    article_summary: str = Field(min_length=1, max_length=1000)
    page_art_direction: str | None = None
    audience_persona: str | None = None
    target_audience: str | None = None
    brand_context: str | None = None
    max_images_per_section: int = Field(default=4, ge=0, le=8)
    plan_cover: bool = True


class PlanResponse(BaseModel):
    cover: ImageSpec | None
    section_specs: list[ImageSpec] = Field(default_factory=list)


@visuals_router.post("/plan", response_model=PlanResponse)
@limiter.limit("20/minute")
async def plan_visuals(
    request: Request,
    body: PlanRequest,
    user: TokenPayload = Depends(require_editor_or_above),
) -> PlanResponse:
    """Plan an article cover + optionally one section's image specs."""
    settings: Settings = request.app.state.settings
    llm = _get_studio_llm(settings)
    cover: ImageSpec | None = None
    if body.plan_cover:
        cover = await plan_article_cover(
            article_title=body.topic.title,
            article_summary=body.article_summary,
            article_domain=body.topic.domain,
            page_art_direction=body.page_art_direction,
            audience_persona=body.audience_persona,
            llm=llm,
        )
    section_specs: list[ImageSpec] = []
    if body.section is not None and body.max_images_per_section > 0:
        section_draft = SectionDraft(
            section_index=body.section.section_index,
            title=body.section.title,
            body_markdown=body.section.body_markdown,
            word_count=len(body.section.body_markdown.split()),
            citations_used=[],
        )
        topic = _planner_topic(body.topic)
        section_specs = await plan_section_images(
            section=section_draft,
            article_topic=topic,
            page_art_direction=body.page_art_direction,
            brand_context=body.brand_context,
            audience_persona=body.audience_persona,
            target_audience=body.target_audience,
            max_images=body.max_images_per_section,
            llm=llm,
        )
    return PlanResponse(cover=cover, section_specs=section_specs)


# ---------------------------------------------------------------------------
# /visuals/render
# ---------------------------------------------------------------------------


class RenderRequest(BaseModel):
    """Render one ImageSpec via the configured provider stack."""

    spec: ImageSpec
    page_direction: str | None = None
    section_override: str | None = None
    refine_note: str | None = None
    prompt_override: str | None = None
    provider: Literal["gemini_flash", "gemini_3_pro", "imagen_4", "dalle_3"] | None = (
        None
    )


class RenderResponse(BaseModel):
    """Render result. URL-first when MinIO emits one; base64 fallback."""

    model_config = ConfigDict(populate_by_name=True)

    image_url: str | None
    image_base64: str | None
    spec_id: str
    width: int
    height: int
    mime_type: str
    provider: str
    model_name: str = Field(alias="model")
    cost_usd: float | None
    latency_ms: int


@visuals_router.post("/render", response_model=RenderResponse)
@limiter.limit("12/minute")
async def render_spec(
    request: Request,
    body: RenderRequest,
    user: TokenPayload = Depends(require_editor_or_above),
) -> RenderResponse:
    """Render a single ImageSpec with provider routing + persistence."""
    settings: Settings = request.app.state.settings
    registry = _get_studio_registry(request, settings)
    storage = _get_studio_storage(request, settings)
    provider_key = body.provider or settings.default_image_provider
    provider = _resolve_provider(provider_key, registry)
    if provider is None:
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                f"image provider '{provider_key}' is not registered "
                "(missing credentials)"
            ),
        )

    prompt = build_prompt(
        spec=body.spec,
        prompt_override=body.prompt_override,
        page_direction=body.page_direction,
        section_override=body.section_override,
        refine_note=body.refine_note,
    )
    try:
        result = await provider.render(
            prompt=prompt,
            aspect_ratio=body.spec.aspect_ratio,
        )
    except ImageProviderError as exc:
        logger.warning("studio_render_failed", spec_id=body.spec.id, error=str(exc))
        raise HTTPException(
            status_code=http_status.HTTP_502_BAD_GATEWAY,
            detail=f"render failed: {exc}",
        ) from exc

    stored = await _persist_render(
        storage=storage,
        spec_id=body.spec.id,
        image_bytes=result.image_bytes,
        mime_type=result.mime_type,
    )
    image_url = stored.url
    image_b64: str | None = None
    if image_url is None:
        # No public URL (LocalDisk in dev) — fall back to base64.
        image_b64 = base64.b64encode(result.image_bytes).decode("ascii")

    return RenderResponse(
        image_url=image_url,
        image_base64=image_b64,
        spec_id=body.spec.id,
        width=result.width,
        height=result.height,
        mime_type=result.mime_type,
        provider=result.provider,
        model=result.model,
        cost_usd=result.cost_usd,
        latency_ms=result.latency_ms,
    )


# ---------------------------------------------------------------------------
# /visuals/upload
# ---------------------------------------------------------------------------


class UploadResponse(BaseModel):
    image_url: str | None
    object_key: str
    size_bytes: int
    mime_type: str


_UPLOAD_ALLOWED_MIME = frozenset(
    {"image/png", "image/jpeg", "image/webp", "image/svg+xml"}
)
_UPLOAD_MAGIC = (
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"RIFF", "image/webp"),  # WebP starts with RIFF…WEBP
)


@visuals_router.post("/upload", response_model=UploadResponse)
@limiter.limit("12/minute")
async def upload_brand_asset(
    request: Request,
    file: UploadFile = File(...),  # noqa: B008 — FastAPI default-arg pattern
    label: str | None = Form(None),
    user: TokenPayload = Depends(require_editor_or_above),
) -> UploadResponse:
    """Upload a brand asset (png/jpg/webp/svg, ≤ 10MB)."""
    settings: Settings = request.app.state.settings
    storage = _get_studio_storage(request, settings)

    declared = (file.content_type or "").lower().split(";")[0].strip()
    if declared not in _UPLOAD_ALLOWED_MIME:
        raise HTTPException(
            status_code=http_status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"content-type '{declared}' is not allowed",
        )
    max_bytes = settings.fetch_image_max_size_mb * 1024 * 1024
    contents = await file.read(max_bytes + 1)
    if len(contents) > max_bytes:
        raise HTTPException(
            status_code=http_status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"upload exceeds {settings.fetch_image_max_size_mb}MB limit",
        )
    if not contents:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="empty upload body",
        )
    sniffed_mime = _sniff_mime(contents, declared)
    if sniffed_mime != declared and declared != "image/svg+xml":
        # SVG is text; we accept the declared content-type when it matches
        # the allowlist. For binary types, sniff must agree.
        raise HTTPException(
            status_code=http_status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                f"content-type '{declared}' does not match sniffed '{sniffed_mime}'"
            ),
        )

    ext = _ext_for_mime(declared)
    base_key = make_object_key(spec_id="upload", ext=ext)
    key = f"uploads/{user.sub}/{base_key}"
    if label:
        # Carry label as a tag in the key so the saved gallery (Phase 7) can
        # filter without round-tripping through DB.
        key = f"{key}#label={_safe_label(label)}"
    stored = await storage.put(key=key, content=contents, content_type=declared)
    return UploadResponse(
        image_url=stored.url,
        object_key=stored.key,
        size_bytes=stored.size_bytes,
        mime_type=stored.content_type,
    )


# ---------------------------------------------------------------------------
# /visuals/fetch-from-url
# ---------------------------------------------------------------------------


class FetchUrlRequest(BaseModel):
    url: str = Field(min_length=1)


class FetchUrlResponse(BaseModel):
    image_url: str | None
    object_key: str
    final_url: str
    mime_type: str
    size_bytes: int


@visuals_router.post("/fetch-from-url", response_model=FetchUrlResponse)
@limiter.limit("6/minute")
async def fetch_from_url(
    request: Request,
    body: FetchUrlRequest,
    user: TokenPayload = Depends(require_editor_or_above),
) -> FetchUrlResponse:
    """Fetch a remote image with SSRF defence and persist it."""
    settings: Settings = request.app.state.settings
    storage = _get_studio_storage(request, settings)
    fetcher = SafeHttpFetcher(
        max_size_bytes=settings.fetch_image_max_size_mb * 1024 * 1024,
        allowed_mime=list(settings.fetch_image_allowed_mime),
        timeout_s=settings.fetch_image_timeout_s,
    )
    try:
        fetched: FetchedImage = await fetcher.fetch_image(body.url)
    except SchemeRejected as exc:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    except HostBlocked as exc:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"host blocked: {exc}",
        ) from exc
    except MimeRejected as exc:
        raise HTTPException(
            status_code=http_status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=str(exc),
        ) from exc
    except SizeExceeded as exc:
        raise HTTPException(
            status_code=http_status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=str(exc),
        ) from exc
    except SafeHttpError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_502_BAD_GATEWAY,
            detail=f"fetch failed: {exc}",
        ) from exc

    ext = _ext_for_mime(fetched.mime_type)
    base_key = make_object_key(spec_id="imported", ext=ext)
    key = f"imports/{user.sub}/{base_key}"
    stored = await storage.put(
        key=key, content=fetched.bytes, content_type=fetched.mime_type
    )
    return FetchUrlResponse(
        image_url=stored.url,
        object_key=stored.key,
        final_url=fetched.url,
        mime_type=fetched.mime_type,
        size_bytes=fetched.size_bytes,
    )


# ---------------------------------------------------------------------------
# /visuals/section-html-refine
# ---------------------------------------------------------------------------


class SectionHtmlRefineRequest(BaseModel):
    section_id: str = Field(min_length=1)
    instruction: str = Field(min_length=1, max_length=2000)
    current_html: str = Field(min_length=1, max_length=20000)


class SectionHtmlRefineResponse(BaseModel):
    section_id: str
    html_fragment: str
    model_name: str = Field(alias="model")
    prompt_used: str

    model_config = ConfigDict(populate_by_name=True)


@visuals_router.post("/section-html-refine", response_model=SectionHtmlRefineResponse)
@limiter.limit("20/minute")
async def section_html_refine(
    request: Request,
    body: SectionHtmlRefineRequest,
    user: TokenPayload = Depends(require_editor_or_above),
) -> SectionHtmlRefineResponse:
    """Apply Claude-driven refinement to a section's HTML."""
    settings: Settings = request.app.state.settings
    llm = _get_studio_llm(settings)
    result: SectionHtmlRefineResult = await refine_section_html(
        section_id=body.section_id,
        instruction=body.instruction,
        current_html=body.current_html,
        llm=llm,
    )
    return SectionHtmlRefineResponse(
        section_id=body.section_id,
        html_fragment=result.html_fragment,
        model=result.model,
        prompt_used=result.prompt_used,
    )


# ---------------------------------------------------------------------------
# /visuals/cost
# ---------------------------------------------------------------------------


class CostBreakdownEntry(BaseModel):
    """One provider's slice of the article cost roll-up."""

    provider: str
    model: str
    count: int
    total_usd: float
    avg_latency_ms: int


class CostResponse(BaseModel):
    """Aggregate cost for a single article."""

    article_id: str
    total_usd: float
    image_count: int
    breakdown: list[CostBreakdownEntry]


@visuals_router.get("/cost", response_model=CostResponse)
@limiter.limit("60/minute")
async def get_article_cost(
    request: Request,
    article_id: str,
    user: TokenPayload = Depends(require_editor_or_above),
) -> CostResponse:
    """Per-article cost breakdown, summed from `ImageAsset.metadata.cost_usd`.

    Drives the UsageBadge on the Visual Studio panel. Pure read — no DB
    writes, no provider calls. Returns 404 when the article does not exist.
    """
    repo = getattr(request.app.state, "article_repo", None)
    if repo is None:
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="article repository is not configured",
        )
    from uuid import UUID

    try:
        parsed_id = UUID(article_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"invalid article_id: {article_id}",
        ) from exc

    article = await repo.get(parsed_id)
    if article is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"article {article_id} not found",
        )
    breakdown = aggregate_cost(article.visuals)
    return CostResponse(
        article_id=article_id,
        total_usd=breakdown.total_usd,
        image_count=breakdown.image_count,
        breakdown=[
            CostBreakdownEntry(
                provider=e.provider,
                model=e.model,
                count=e.count,
                total_usd=e.total_usd,
                avg_latency_ms=e.avg_latency_ms,
            )
            for e in breakdown.breakdown
        ],
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _planner_topic(topic: _TopicInput) -> TopicInput:
    """Build a TopicInput from the user-supplied dict (planner needs it)."""
    from uuid import uuid4

    return TopicInput(
        id=uuid4(),
        title=topic.title,
        description=topic.description,
        domain=topic.domain,
    )


def _resolve_provider(
    name: str, registry: ImageProviderRegistry
) -> ImageProvider | None:
    if registry.has(name):
        return registry.get(name)
    return None


def _get_studio_llm(settings: Settings) -> ChatAnthropic:
    """Build a Claude chat model for studio planning + refinement."""
    from pydantic import SecretStr

    return ChatAnthropic(
        model_name=settings.anthropic_model,
        api_key=SecretStr(settings.anthropic_api_key),
        timeout=30.0,
        stop=None,
        max_retries=2,
    )


def _get_studio_registry(request: Request, settings: Settings) -> ImageProviderRegistry:
    """Resolve (or lazily build) the provider registry for studio renders."""
    cached = getattr(request.app.state, "visual_provider_registry", None)
    if cached is not None:
        return cached  # type: ignore[no-any-return]
    registry = init_visual_registry(settings)
    request.app.state.visual_provider_registry = registry
    return registry


def _get_studio_storage(request: Request, settings: Settings) -> ObjectStorage:
    cached = getattr(request.app.state, "visual_object_storage", None)
    if cached is not None:
        return cached  # type: ignore[no-any-return]
    storage = select_object_storage(settings)
    request.app.state.visual_object_storage = storage
    return storage


async def _persist_render(
    *,
    storage: ObjectStorage,
    spec_id: str,
    image_bytes: bytes,
    mime_type: str,
) -> StoredObject:
    ext = _ext_for_mime(mime_type)
    key = make_object_key(spec_id=spec_id, ext=ext)
    return await storage.put(
        key=f"renders/{key}",
        content=image_bytes,
        content_type=mime_type,
    )


def _ext_for_mime(mime_type: str) -> str:
    return {
        "image/png": "png",
        "image/jpeg": "jpg",
        "image/webp": "webp",
        "image/svg+xml": "svg",
    }.get(mime_type, "png")


def _sniff_mime(contents: bytes, declared: str) -> str:
    head = contents[:16]
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if len(contents) >= 12 and contents[:4] == b"RIFF" and contents[8:12] == b"WEBP":
        return "image/webp"
    if declared == "image/svg+xml" and b"<svg" in contents[:200].lower():
        return "image/svg+xml"
    return "application/octet-stream"


def _safe_label(label: str) -> str:
    return "".join(ch for ch in label if ch.isalnum() or ch in "-_")[:40]


__all__ = ["visuals_router"]
