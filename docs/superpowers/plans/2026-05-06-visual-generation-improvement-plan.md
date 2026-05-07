# Implementation Plan: Visual Generation Overhaul (Cognify ← ImpactAI patterns)

> **Date:** 2026-05-06 (revised against ImpactAI's `feat/content-hub` branch — significantly newer than `main`)
> **Status:** Draft — not implemented
> **Companion review:** [`docs/architecture/COGNIFY_VS_IMPACTAI_REVIEW.md`](../../architecture/COGNIFY_VS_IMPACTAI_REVIEW.md)
>
> **Goal:** Bring Cognify's image generation up to (and ideally past) ImpactAI's level by importing its **per-section image planner**, **visual-style catalogue**, **multi-provider stack** (now three tiers including `gemini-3-pro-image-preview`), **rich placement anchors**, **MinIO/S3 asset hosting**, **persona-aware planning**, **banned-cliché prompt guards**, **section-level HTML refinement**, and **user-controllable studio UI** — while preserving Cognify's architectural boundaries (CanonicalArticle, Service-Layer, ADR-driven decisions) and *avoiding* ImpactAI's modularity drift (its `generate.py` is now 4,580 LoC and growing).
>
> **What changed since the first draft of this plan:** ImpactAI's `feat/content-hub` branch added 19,000 lines across 123 files. The new ideas worth importing — over and above the original plan — are:
>
> 1. A **third image provider** (`gemini-3-pro-image-preview`) sitting between Flash and Imagen 4
> 2. **MinIO/S3 image storage** (replaces base64 payloads with public URLs)
> 3. **Persona-aware image planning** with explicit cliché ban-lists (LinkedIn-post planner)
> 4. **Per-content-type planners** (one each for landing, Pulse, LinkedIn Post, Carousel)
> 5. **Section-level HTML/CSS refinement** endpoint + UI step (`/section-html-refine` + `VisualLayoutStep`)
> 6. **Per-role default prompt seeds** (`defaultSectionVisualPrompts.ts`)
> 7. **Image-import paths** — upload + fetch-from-URL with SSRF guard
> 8. **Saved-asset gallery** with style tokens
> 9. **Markdown-structure parser** for safe humanization rewrites
> 10. **Word-level humanization diff** UI
>
> Items 1–8 are now folded into this plan. 9–10 are tracked as separate follow-ups (out of scope for this image-focused plan but recorded in §17).

---

## 1. Why This Plan Exists

**User-stated problems with Cognify today:**

1. Generated hero images are "not good and meaningful." (cf. `illustration_generator.py:76-93` — single hard-coded prompt template, single style, one DALL-E provider, no user control.)
2. The platform lacks the flexibility ImpactAI provides over including various types of images in the article.

**Root cause analysis** (see review doc, §4):

- Cognify treats image generation as a *one-shot autonomous pipeline step*, with one hero per article and no per-section visuals.
- The illustration prompt template is static — no concept of art direction, role, or style.
- The user has no surface to influence visual choice, regenerate, or refine.
- There is no planner — charts/diagrams/illustration nodes run independently, unaware of each other.
- The placement model is fixed (hero → top, charts → after-section, diagrams → above body or after-section).

ImpactAI's image generation, by contrast, is built around four pillars that Cognify lacks:

1. **Visual-style catalogue** — 12 art-direction options with verbose prompt fragments.
2. **Per-section image planner** — Claude reads each section and proposes N specs with role + style + placement.
3. **Multi-provider stack** — Gemini Flash (default, cheap) + Imagen 4 (premium, paid).
4. **User control surface** — SectionImageModal (Step 5) and Image Studio (Step 6) for art direction, refinement, regeneration.

This plan ports those pillars into Cognify, adapted to its architecture (LangGraph nodes, CanonicalArticle, Service-Layer).

---

## 2. Non-goals

- **Rewriting** the existing `chart_generator.py` / `diagram_generator.py` / `illustration_generator.py`. We extend, not replace. Charts and Mermaid diagrams remain; new providers and styles add to them.
- **Removing** DALL-E 3. It can stay as a third provider for hero illustrations.
- **Frontend wizard rewrite.** Cognify's UX is dashboard-driven, not wizard-driven; the new image controls land in the existing article-detail view, not a wizard.
- **Replacing** CanonicalArticle. New visual metadata is folded into existing fields; no new boundary contract.

---

## 3. Architecture Overview (target state)

```
                ┌────────────────────────────────────────┐
                │  Content Pipeline (LangGraph)          │
                │                                        │
                │  outline → queries → draft → validate  │
                │     → citations → humanize → SEO       │
                │     → IMAGE PLANNER (NEW)              │
                │     → IMAGE RENDERER (NEW)             │
                │     → charts, diagrams (kept as-is)    │
                │     → illustration (kept, optional)    │
                └────────────────────────────────────────┘
                                  │
                                  ▼
                  ┌──────────────────────────────┐
                  │  CanonicalArticle.visuals[]  │ ← extended ImageAsset metadata
                  │  + section-anchored specs    │
                  └──────────────────────────────┘
                                  │
              ┌───────────────────┼─────────────────────┐
              ▼                   ▼                     ▼
       Ghost transformer    Medium transformer   LinkedIn transformer
       (renders inline      (renders inline      (uploads inline images
        images per anchor)  images per anchor)   per LinkedIn API)

   ┌─────────────────────────────────────────────────────────────────┐
   │  NEW Frontend "Visual Studio" panel on article-detail screen    │
   │   • Per-section image cards (one per ImageSpec)                 │
   │   • Page-wide art direction textarea                            │
   │   • Default visual style chip rail                              │
   │   • Render quality toggle (Fast / Premium)                      │
   │   • Per-image refine input + regenerate button                  │
   │   • Live UsageBadge (per-article cost)                          │
   └─────────────────────────────────────────────────────────────────┘
```

**Key new components**:

| Component | Type | Notes |
|---|---|---|
| `src/services/visuals/visual_styles.py` | Service | 12-style catalogue + role-defaults + composer |
| `src/services/visuals/image_planner.py` | Service | Plans ImageSpecs per section (Claude). Persona-aware (audience → visual register), with banned-cliché list |
| `src/services/visuals/persona_directions.py` | Service | Map of audience persona → visual register guidance (mirrors impactai's `_PERSONA_VISUAL_DIRECTION`) |
| `src/services/visuals/banned_cliches.py` | Service | Explicit ban-list ("no glowing AI brain", "no stock-photo handshakes", "no flat-design illustrations" when photo style chosen) appended to every prompt |
| `src/services/visuals/providers/{gemini_flash,gemini_3_pro,imagen_4,dalle_3}.py` | Provider impls | **Four** providers behind a single `ImageProvider` Protocol |
| `src/services/visuals/registry.py` | Registry | TrendSource-style provider lookup |
| `src/services/visuals/object_storage.py` | Service | MinIO/S3 upload + public-URL resolution; falls back to local-file path when disabled (mirrors impactai pattern) |
| `src/services/visuals/safe_http.py` | Service | SSRF guard: DNS resolution + private/loopback/link-local CIDR rejection. Used by upload-from-URL endpoint |
| `src/agents/content/image_planner_node.py` | Pipeline node | Calls planner, populates state |
| `src/agents/content/image_render_node.py` | Pipeline node | Fans out per-spec render calls; persists via `object_storage` |
| `src/agents/content/visuals_inject.py` | Helper | Markdown injection per anchor |
| `src/api/routers/visuals.py` | FastAPI router | `/visuals/plan`, `/visuals/render`, `/visuals/refine`, `/visuals/upload`, `/visuals/fetch-from-url`, `/visuals/section-html-refine` |
| `src/services/visuals/section_html_refiner.py` | Service | Refines a section's HTML/CSS via Claude given the user's free-text instruction (mirrors impactai's `/section-html-refine`) |
| `src/services/visuals/default_prompts.py` | Service | Per-role default image prompt + HTML/CSS instruction seeds (port `defaultSectionVisualPrompts.ts` to Python so seeds are server-driven, not duplicated) |
| `frontend/src/components/visuals/VisualStudio.tsx` | React | Page-wide controls + per-section list |
| `frontend/src/components/visuals/SpecCard.tsx` | React | Per-spec card with chip rail / refine / render / upload / import-URL |
| `frontend/src/components/visuals/SectionHtmlRefinePanel.tsx` | React | "Apply with AI" textarea bound to `/visuals/section-html-refine` |
| `frontend/src/lib/visuals/visualStyles.ts` | TS | **Bootstrap fetch from `/visuals/styles`** (no hard-coded mirror — single source of truth in backend) |
| `frontend/src/lib/visuals/imageSrc.ts` | TS | `pickGeneratedImageSrc(...)` — prefers `image_url` over base64 (mirrors impactai's `bannerImage.ts`) |

---

## 4. Data Model Changes

### 4.1 New Pydantic models

`src/models/visual.py` (extend existing):

```python
ImageRoleStyle = Literal[
    "hero", "feature_card", "concept", "process_step",
    "comparison_split", "quote_card", "stat_card",
    "screenshot_mock", "editorial", "background",
]

ImageAspectRatio = Literal["16:9", "1:1", "4:3", "3:4", "4:5"]

PlacementAnchor = Literal[
    "cover", "top", "before_heading", "between_paragraphs",
    "bottom_grid", "background", "column_split",
]

class ImagePlacement(BaseModel):
    anchor: PlacementAnchor = "top"
    heading_text: Optional[str] = None      # for before_heading
    paragraph_index: Optional[int] = None   # for between_paragraphs
    section_index: int = -1                 # -1 == article-level

class ImageSpec(BaseModel):
    id: str
    role_style: ImageRoleStyle
    visual_style: Optional[str] = None       # catalogue key
    prompt: str                              # subject only — style layered separately
    alt_text: str = ""
    aspect_ratio: ImageAspectRatio = "16:9"
    placement: ImagePlacement = ImagePlacement()
    rationale: Optional[str] = None
    provider: Optional[Literal["gemini_flash", "imagen_4", "dalle_3"]] = None
```

### 4.2 Extend `ImageAsset.metadata`

Add (kept in JSONB; no schema migration):

- `spec_id: str` — the ImageSpec that produced this asset
- `role_style`, `visual_style`, `aspect_ratio`, `placement_anchor`
- `provider`, `model`, `prompt_used`
- `cost_usd: float | None`
- `generation_ms: int`

### 4.3 CanonicalArticle additions

Add a single new field (per ADR-003 amendment):

```python
class CanonicalArticle(BaseModel):
    ...
    image_specs: list[ImageSpec] = []   # planner output, one per planned image
    page_art_direction: Optional[str] = None  # user-set page-wide style guidance
```

This is additive and backward-compatible; existing `visuals: list[ImageAsset]` stays. Each rendered visual carries `spec_id` linking it to its plan.

**Decision required:** record an ADR amendment. *Action:* draft `ADR-005-image-spec-planner.md` capturing the reason and the new fields.

---

## 5. Backend Changes

### 5.1 Visual style catalogue (Service)

**File:** `src/services/visuals/visual_styles.py`

Mirror ImpactAI's 12-style catalogue. Each entry carries `key`, `label`, `category`, `default_aspect`, `short_desc`, `prompt_fragment`. Adapt the palette guidance to Cognify's brand (`#DC2626` red accent, warm slate neutrals) where the impactai fragments mention "deep teal / warm coral".

Provide:

- `VISUAL_STYLES: dict[str, dict]`
- `ROLE_STYLE_DEFAULTS: dict[str, str]`
- `default_visual_style_for_role(role) -> str | None`
- `style_prompt_fragment(key) -> str | None`
- `compose_style_override(visual_style, *, page_direction=None, section_override=None, refine_note=None) -> str | None`
- `planner_catalogue_block() -> str`
- `get_style(key) -> dict | None`

**Single-source-of-truth caveat (learning from ImpactAI's pain):** keep the catalogue *only* in Python, and expose it via `GET /api/v1/visuals/styles`. The frontend fetches it once at boot and caches it. No mirrored TypeScript file. This is the ONE place we improve on ImpactAI's design.

### 5.2 Provider abstraction

**File:** `src/services/visuals/providers/base.py`

```python
class ImageProvider(Protocol):
    name: str
    async def render(
        self,
        *,
        prompt: str,
        aspect_ratio: str,
        size_hint: tuple[int, int] | None = None,
    ) -> ImageRenderResult: ...
```

Where `ImageRenderResult` carries `image_bytes`, `mime_type`, `width`, `height`, `prompt_used`, `model`, `provider`, `cost_usd`, `latency_ms`.

**Concrete providers (four tiers):**

| Tier | Key | Model | Cost (approx) | Use case |
|---|---|---|---|---|
| Default | `gemini_flash` | `gemini-2.5-flash-image` | fractions of a cent | Most renders, fast iteration. No native aspect arg — embed in prompt. |
| Mid | `gemini_3_pro` | `gemini-3-pro-image-preview` | mid | Higher quality typography (e.g. carousel slides, social cards). New on impactai's `feat/content-hub`. |
| Premium | `imagen_4` | `imagen-4.0-generate-001` | ~$0.04/image, paid tier | Hero photos, lifestyle / portrait realism. Native aspect arg; map 4:5→3:4, 5:4→4:3, 21:9→16:9 via `_IMAGEN_ASPECT_MAP`. |
| Legacy | `dalle_3` | `dall-e-3` | ~$0.04/image | Kept selectable for backward-compat. |

Provider model IDs are **env-resolvable** (`COGNIFY_IMAGE_MODEL_GEMINI_FLASH`, `COGNIFY_IMAGE_MODEL_GEMINI_3_PRO`, …) so future Gemini / Imagen versions can swap in without a code change — port `_resolve_banner_gemini_model_id` from impactai.

Register all four in `src/services/visuals/registry.py` mirroring the TrendSource registry pattern (ARCH-002).

### 5.3 Prompt composer

**File:** `src/services/visuals/prompt_composer.py`

Port `_build_banner_prompt` from `impactai/apps/api/routers/generate.py:2988`, including:

- The "Composition reference IGNORED" trick when style overrides role.
- The aggressive `no_text_clause`.
- The `_aspect_instruction(aspect)` sentence injected for Gemini Flash (which ignores aspect param).
- The 800-char cap on style_text.
- The four-branch decision tree (prompt_override × has_style).

Cover with unit tests (10–15 cases) hitting all four branches × multiple styles × overrides.

### 5.4 Image planner

**File:** `src/services/visuals/image_planner.py`

Endpoint-equivalent of impactai's `/banner-plan` **plus** the patterns from impactai's `pulse_image_planner.py` and `linkedin_post_image_planner.py`. Function signatures:

```python
async def plan_section_images(
    *,
    section: SectionDraft,
    article_topic: TopicInput,
    page_art_direction: Optional[str],
    brand_context: Optional[str],
    audience_persona: Optional[str],   # NEW — e.g. "cto", "ceo", "marketer"
    target_audience: Optional[str],    # NEW — free-text; folded into prompt
    max_images: int = 4,
    llm: BaseChatModel,
) -> list[ImageSpec]: ...

async def plan_article_cover(
    *,
    article: CanonicalArticle,
    page_art_direction: Optional[str],
    audience_persona: Optional[str],
    llm: BaseChatModel,
) -> ImageSpec: ...
```

The planner prompt:

- Reads section heading, role hint, body, brand_context.
- **Includes `planner_catalogue_block()`** so the LLM can pick visual styles knowingly.
- **Includes the persona's visual register** (per-persona block from `persona_directions.py`) — e.g. CTO articles lean toward technical workspaces with real code, HR articles lean toward authentic culture moments. Default `general_business` register if no persona supplied.
- **Includes the banned-cliché list** verbatim — "no glowing AI brain, no stock-photo handshakes, no flat-design illustrations when photo style chosen, no motivational poster vibes, no tight close-ups of identifiable faces" — to address the user's "not good and meaningful" complaint head-on.
- Requires **variety across specs** in the same section.
- Asks for an ordered list with role_style, visual_style, prompt (subject only), aspect, placement.anchor, rationale.
- Returns 0 to `max_images` specs.

**Fallback path** (when LLM returns garbage or empty): synthesise 1 spec from `(section.role, ROLE_STYLE_DEFAULTS, default_aspect)` plus the persona register fragment — same shape as ImpactAI's `_fallback_specs`.

**Note on planner specialisation:** ImpactAI has separate planners per content type (landing/Pulse/LinkedIn-post/Carousel). Cognify's domain is long-form articles, so we ship **one** unified planner and parameterise it with `(audience_persona, target_aspect, max_images)`. If LinkedIn / carousel publishing later joins Cognify's roadmap, fork dedicated planners then — not now.

### 5.5 Pipeline nodes

**File:** `src/agents/content/image_planner_node.py`

```python
def make_image_planner_node(llm: BaseChatModel) -> NodeFn:
    async def node(state: ContentState) -> dict:
        if not _images_enabled(state):
            return {}
        section_drafts = state["section_drafts"]
        page_dir = state.get("page_art_direction")
        topic = _coerce_topic(state)
        all_specs: list[ImageSpec] = []
        # Article-level cover (replaces DALL-E hero in default config)
        cover = await plan_article_cover(article=..., page_art_direction=page_dir, llm=llm)
        all_specs.append(cover)
        # Per-section
        for sd in section_drafts:
            specs = await plan_section_images(section=sd, ..., llm=llm)
            all_specs.extend(specs)
        return {"image_specs": all_specs}
    return node
```

**File:** `src/agents/content/image_render_node.py`

```python
def make_image_render_node(provider_registry: ProviderRegistry) -> NodeFn:
    async def node(state: ContentState) -> dict:
        specs = state.get("image_specs", [])
        if not specs:
            return {"visuals": state.get("visuals", [])}
        page_dir = state.get("page_art_direction")
        sem = asyncio.Semaphore(settings.image_render_concurrency)  # default 3
        async def _render(spec: ImageSpec):
            async with sem:
                return await render_spec(spec, page_dir, provider_registry)
        rendered = await asyncio.gather(*(_render(s) for s in specs), return_exceptions=True)
        new_visuals = [r for r in rendered if isinstance(r, ImageAsset)]
        existing = state.get("visuals", [])
        return {"visuals": existing + new_visuals}
    return node
```

`render_spec` calls `prompt_composer.build_prompt(spec, page_dir)` then routes to the provider, persists bytes to disk, builds an `ImageAsset` with the metadata extensions, records cost via `usage_tracker`.

**File:** `src/agents/content/pipeline.py` (edit)

Insert new nodes after `seo_optimize` and before `generate_charts`:

```
seo_optimize → image_planner → image_render → generate_charts → generate_diagrams → END
```

Add settings flag `enable_image_planner: bool = True` to allow legacy DALL-E-only mode.

### 5.6 Markdown injection

**File:** `src/services/visuals/inject.py` (new)

Port impactai's `injectBanners.ts` to Python. Used by *both*:

- The Ghost / Medium / LinkedIn transformers (replacing the simpler `_inject_visuals` logic in `ghost/transformer.py`).
- A new "preview HTML" endpoint that the frontend Visual Studio uses to show what the article looks like with current visuals.

Per-anchor logic:

| Anchor | Implementation |
|---|---|
| `cover` | Set `feature_image` (Ghost) or prepend before title (Medium/LinkedIn) |
| `top` | Prepend `<img>` to section HTML |
| `before_heading` | Insert before fuzzy-matched `<h2>`/`<h3>` |
| `between_paragraphs` | Insert after Nth `<p>` in section |
| `bottom_grid` | Collect all `bottom_grid` specs in section, render as `<div class="cog-grid">` |
| `background` | Insert `<!-- bg-image:URL -->` marker (frontend renders) |
| `column_split` | Wrap section as `<div class="cog-col-split">` with image col |

Idempotent: re-running with same `spec_id` doesn't duplicate.

### 5.7 New API endpoints

**File:** `src/api/routers/visuals.py`

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/v1/visuals/styles` | Returns the catalogue (JSON). Cached one-shot fetch from frontend. |
| `POST` | `/api/v1/visuals/plan` | Plan images for a section or article. Body: `{section_id?, article_id, max_images, page_direction?, brand_context?, audience_persona?}`. Returns `list[ImageSpec]`. |
| `POST` | `/api/v1/visuals/render` | Render one ImageSpec with provider routing. Body: `{spec, page_direction?, section_override?, refine_note?, provider?}`. Returns `{image_url, asset_metadata}` (URL-first when MinIO is enabled, base64 fallback otherwise). Rate-limited 12/min/user. |
| `POST` | `/api/v1/visuals/refine` | Edit an existing spec + re-render. Body: `{spec_id, updates, refine_note?}`. |
| `DELETE` | `/api/v1/visuals/specs/{spec_id}` | Remove a spec from an article. |
| `POST` | `/api/v1/visuals/replace` | Upload a custom image (multipart) to replace a spec's render. |
| `POST` | `/api/v1/visuals/upload` | Upload a brand asset directly (multipart). MIME whitelist (png/jpg/webp/svg), 10MB cap (matches Cognify SECURITY_CHECKLIST §2). Stored via `object_storage`. |
| `POST` | `/api/v1/visuals/fetch-from-url` | Fetch an image from a user-supplied URL. **SSRF-guarded** via `safe_http.py` — rejects private/loopback/link-local CIDRs, non-http(s) schemes, redirects to private addresses. Mirrors impactai's `safe_http_url.py` pattern verbatim. |
| `POST` | `/api/v1/visuals/section-html-refine` | Refine a section's rendered HTML/CSS via Claude. Body: `{section_id, instruction, current_html?}`. Returns `{html_fragment, model, prompt_used}`. (Inspired by impactai's `/section-html-refine` — lets the user iterate on layout *without* re-running the article pipeline.) |
| `GET` | `/api/v1/visuals/cost?article_id=…` | Per-article cost breakdown by provider. |
| `GET` | `/api/v1/visuals/saved` | List user's saved (previously generated) image assets. Filterable by style token (`style=cognify_gallery:hero`, etc.) — mirrors impactai's `linkedin_gallery:` pattern. |

All require auth + RBAC (editor or admin).

### 5.7.1 Per-section content editing endpoints

**File:** `src/api/routers/content.py` (new — sibling to `visuals.py`)

These endpoints fill the "fine-grained per-section control" gap: editors can rewrite prose section-by-section either manually or by issuing a natural-language instruction to Claude, **without** re-running the full content pipeline.

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/v1/content/section-rewrite` | AI rewrite of a single section's prose. Body: `{section_id, instruction, scope?: "paragraph" \| "section", paragraph_index?, current_markdown?, audience_persona?}`. Returns `{markdown_fragment, diff: WordDiff[], model, prompt_used, tokens, usd}`. Output is sanitized (no new headings, code blocks, or images injected — preserves anchors). |
| `POST` | `/api/v1/content/section-update` | Persist a manual prose edit. Body: `{section_id, paragraph_index?, markdown}`. Server validates that section anchors (`heading_text`, image spec_ids) survive the edit; rejects 422 with diff if anchors broken. |
| `POST` | `/api/v1/content/paragraph-tone` | One-shot tone shift for a paragraph (preset rewrite — "more concrete", "shorter", "more conversational", "more authoritative"). Body: `{section_id, paragraph_index, preset}`. Thin wrapper around `section-rewrite` with curated instruction templates. |
| `GET` | `/api/v1/content/section/{section_id}/history` | List prior versions of a section (created on each rewrite/update). Used by the toolbar's "history" affordance. |
| `POST` | `/api/v1/content/section/{section_id}/restore` | Restore a section to a prior version. Body: `{version_id}`. |

**File:** `src/services/content/section_rewriter.py`

Mirrors `section_html_refiner.py` for prose:

- Reads section markdown + neighbouring section context for tone consistency.
- Includes audience-persona register (same map used by image planner — single source of truth).
- Banned-pattern list: no new headings, no fabricated stats, no quoted citations the user didn't approve.
- Returns markdown + structural word-level diff (reusing existing humanization slop-pattern scorer's diff infrastructure — see §17.2).

All endpoints require auth + RBAC (editor or admin). Rate-limited 30/min/user on `section-rewrite`, 60/min on `section-update`.

### 5.8 Cost tracking

Extend the existing usage logging (cf. cognify's planned `cognify_llm_tokens_total` Prometheus counter) to also record per-image cost. Add a session/article-scoped query endpoint:

`GET /api/v1/visuals/cost?article_id=X` → `{total_usd, breakdown: [{provider, model, count, usd}]}`

Frontend `UsageBadge` consumes this.

### 5.9 Settings

`src/config/settings.py` (extend):

```python
# Visuals — generation
enable_image_planner: bool = True
default_image_provider: Literal[
    "gemini_flash", "gemini_3_pro", "imagen_4", "dalle_3"
] = "gemini_flash"
image_model_gemini_flash: str = "gemini-2.5-flash-image"
image_model_gemini_3_pro: str = "gemini-3-pro-image-preview"
image_model_imagen_4: str = "imagen-4.0-generate-001"
image_render_concurrency: int = 3
image_planner_max_images_per_section: int = 4
google_ai_api_key: SecretStr | None = None
imagen_4_enabled: bool = False        # gates Premium tier in UI
gemini_3_pro_enabled: bool = True     # gates Mid tier (preview model)
visuals_output_dir: str = "generated_assets/visuals"

# Visuals — object storage (MinIO / S3)
minio_enabled: bool = False
minio_endpoint: str | None = None        # host:port, no scheme
minio_access_key: SecretStr | None = None
minio_secret_key: SecretStr | None = None
minio_bucket: str = "cognify-visuals"
minio_public_url: str | None = None      # base URL prepended to object keys
minio_use_ssl: bool = False
minio_region: str = "us-east-1"

# Visuals — image-import safety
fetch_image_max_size_mb: int = 10
fetch_image_allowed_mime: list[str] = ["image/png", "image/jpeg", "image/webp"]
fetch_image_timeout_s: float = 10.0
```

Env vars: `COGNIFY_GOOGLE_AI_API_KEY`, `COGNIFY_MINIO_ENABLED`, `COGNIFY_MINIO_ENDPOINT`, etc. All secrets encrypted via existing Fernet path if set in DB through Settings UI.

---

## 6. Frontend Changes

### 6.1 New API layer (`frontend/src/lib/api/visuals.ts`)

Wrappers for the 6 endpoints in §5.7. Type-safe with shared TS types generated/copied from backend Pydantic models.

### 6.2 Visual Studio component

**File:** `frontend/src/components/visuals/VisualStudio.tsx`

Mounted on the existing article-detail screen as a collapsible right-side panel (or full-section below the article body). State:

```ts
interface StudioState {
  pageArtDirection: string;
  pageDefaultStyle: string | null;
  pageProvider: 'gemini_flash' | 'imagen_4' | 'dalle_3';
  specs: ImageSpec[];
  rendered: Record<string /* specId */, RenderedAsset>;
  perSpecOverrides: Record<string, { provider?: string; styleKey?: string; refineNote?: string }>;
  bulkProgress: { total: number; done: number };
}
```

UI mirrors ImpactAI's Step 6 Studio:

1. Header: title, "Plan & generate", "Insert all into article".
2. UsageBadge (live cost meter, refresh-keyed on render count + provider).
3. Studio panel: page art direction textarea, default visual style chip rail, render quality toggle.
4. Per-spec cards (one per ImageSpec):
   - Image preview / placeholder / loading spinner.
   - Render | Edit | Replace | Remove image | Delete spec.
   - Visual style chip rail (top suggestions + current + page default).
   - Per-spec render quality override.
   - Refine input ("make it more X").
   - Edit drawer: role_style, aspect_ratio, placement.anchor + heading_text, alt_text, prompt textarea.

### 6.3 Visual style catalogue + suggestion heuristic

**File:** `frontend/src/lib/visuals/visualStyles.ts`

Loaded once at app boot from `GET /visuals/styles`. Cached. No mirrored hard-coded copy.

`suggestVisualStyles(role, content, opts)` heuristic ported from impactai (`apps/web/components/create/landing/visualStyles.ts`). Returns top-N style keys for a section.

### 6.4 Planning a section

When the user clicks "Plan visuals" on a section card, call `POST /visuals/plan` with `{section_id, max_images, page_direction}`. Renders chips per returned spec; user picks a variant per spec; the modal then issues `POST /visuals/render` for each chosen spec.

### 6.5 Bulk regenerate

"Plan + generate for all sections" button on Studio header:

1. For each section without specs, `POST /visuals/plan`.
2. After all plans return, fan out `/visuals/render` calls with `p-limit(3)` concurrency.
3. Update `bulkProgress` per completion; refresh `UsageBadge`.

### 6.6 Inserting into the article

"Insert all into article" calls `POST /visuals/insert` (alternative endpoint or part of `/render` flow) which triggers the backend to re-render the article HTML (via `inject.py` from §5.6) and persist the updated CanonicalArticle. Frontend re-fetches and re-renders.

---

## 7. Publishing Integration

The new `inject.py` becomes the single source of truth for HTML composition. Each platform transformer calls it with the platform's specific tweaks:

- **Ghost transformer:** `cover` spec → `feature_image`; everything else inline. Wrap inline images in Lexical HTML cards (per L-009 — Ghost 5 ignores raw `html` field).
- **Medium transformer:** `cover` → first paragraph image; everything else inline `<img>`.
- **LinkedIn transformer:** LinkedIn API supports inline images with `articleUrn`-prefixed asset URNs. Adapter uploads each rendered asset, gets back a URN, transformer references the URN per anchor.
- **WordPress (when implemented, PUBLISH-002):** featured_media for cover; inline `<img>` blocks for the rest.

The result: same `ImageSpec[]` produces consistent visuals across all four platforms with platform-appropriate hosting / referencing.

---

## 8. Backwards Compatibility & Feature Flag

- All new visual logic gates on `settings.enable_image_planner`. When `False`, the existing illustration/charts/diagrams nodes run unchanged.
- Existing articles in DB have empty `image_specs` and unchanged `visuals` — they keep working without re-renders.
- The new `image_specs` field on CanonicalArticle is optional with default `[]`.
- DALL-E 3 stays available as `dalle_3` provider.

---

## 9. Testing Strategy

| Layer | Tests | Notes |
|---|---|---|
| **Unit** | `prompt_composer` (4 branches × 3 styles), `compose_style_override`, `inject.py` per-anchor (idempotency, fuzzy heading match), `default_visual_style_for_role` | Pure functions, fast |
| **Unit** | `image_planner` with FakeLLM (matrix: section.role × max_images) | Asserts spec count, role/style validity, anchor validity |
| **Integration** | `image_render_node` with stub provider returning fixed bytes | Asserts ImageAsset metadata, file written, usage_tracker recorded |
| **Integration** | Pipeline run with `enable_image_planner=True`, FakeLLM, stub provider | Asserts CanonicalArticle has `image_specs` + `visuals` aligned |
| **Integration** | Per-platform transformer with multi-anchor specs | Asserts HTML / Lexical / LinkedIn payload correctly references images |
| **Contract** | `/visuals/plan`, `/visuals/render` with auth, RBAC, rate-limit, missing-key-503 | Standard FastAPI test client |
| **E2E** | Playwright: open article-detail → open Visual Studio → plan section → pick variant → render → verify image rendered → toggle Premium → re-render | Catches frontend regressions |
| **Regression** | Existing tests must pass with `enable_image_planner=False` | Backward-compat |

Coverage targets: ≥85% on new code (per CLAUDE.md DoD).

FakeLLM responses for the planner: ship fixtures in `tests/fixtures/visual_planner/` with realistic JSON outputs for 5–6 archetypal sections.

Stub provider: `tests/stubs/stub_image_provider.py` returning a 1×1 PNG so we can exercise the full pipeline without hitting Google AI in CI.

---

## 10. Migration Plan

1. **No DB migration required** — `image_specs` lives in CanonicalArticle's existing JSONB; `ImageAsset.metadata` is JSONB.
2. Existing articles: `image_specs = []`, no behavioural change.
3. New articles generated under `enable_image_planner=True` get the new pipeline.
4. Optional backfill script `scripts/backfill_image_specs.py` to plan visuals retroactively for existing articles. Manual opt-in per article via Visual Studio "Plan visuals for this article" button.

---

## 11. Sequenced Delivery (7 phases / 7 PRs)

> Each phase ships behind `enable_image_planner` flag. Default flag value flips to `True` only at end of Phase 5. Phases 6 and 7 are additive.

### Phase 1 — Catalogue + Provider abstraction + Object storage (foundation)

- [x] ADR-005 draft (image-spec planner amendment + MinIO object storage decision)
- [x] `src/services/visuals/visual_styles.py` (catalogue, role defaults, composer, planner_catalogue_block)
- [x] `src/services/visuals/persona_directions.py` (audience persona → visual register map)
- [x] `src/services/visuals/banned_cliches.py` (the explicit ban-list block)
- [x] `src/services/visuals/providers/base.py` (`ImageProvider` Protocol, `ImageRenderResult`)
- [x] `src/services/visuals/providers/dalle_3.py` (wraps existing `OpenAIDalleGenerator`)
- [x] `src/services/visuals/providers/gemini_flash.py`
- [x] `src/services/visuals/providers/gemini_3_pro.py` (NEW tier — `gemini-3-pro-image-preview`)
- [x] `src/services/visuals/providers/imagen_4.py` (incl. `_IMAGEN_ASPECT_MAP` aspect snapping)
- [x] `src/services/visuals/registry.py`
- [x] **`src/services/visuals/object_storage.py`** (MinIO/S3 uploads, public-URL resolution, base64 fallback)
- [x] **`src/services/visuals/safe_http.py`** (SSRF guard for fetch-from-URL)
- [x] Unit tests for catalogue, composer, providers (with httpx-mock for Google AI), object_storage (with moto/MinIO test container), safe_http
- [x] Settings additions (provider IDs, MinIO config, fetch-from-URL safety)
- [x] `GET /api/v1/visuals/styles` endpoint
- [x] `docker-compose.minio.yml` for local dev (mirror impactai)
- **PR target:** `feature/VISUAL-004-style-catalogue-providers-storage`

### Phase 2 — Planner + new pipeline nodes (persona-aware, cliché-banned)

- [x] `src/services/visuals/prompt_composer.py` (port `_build_banner_prompt`, including the four-branch decision tree, `no_text_clause`, "Composition reference IGNORED" trick)
- [x] `src/services/visuals/default_prompts.py` (Python port of `defaultSectionVisualPrompts.ts` — per-role default image prompts)
- [x] `src/services/visuals/image_planner.py` (`plan_section_images`, `plan_article_cover`, `_fallback_specs`, persona-aware register, banned-cliché block)
- [x] `src/agents/content/image_planner_node.py`
- [x] `src/agents/content/image_render_node.py` (writes through `object_storage`)
- [x] CanonicalArticle field additions (`image_specs`, `page_art_direction`, `audience_persona`)
- [x] Thread `audience_persona` from existing per-article params (already in CONTENT-006 humanization flow) into the planner
- [x] Wire nodes into `pipeline.py` between `seo_optimize` and `generate_charts`
- [x] FakeLLM fixtures for planner (across multiple personas + roles)
- [x] Stub provider for tests
- [x] Integration test: full pipeline with planner + render + MinIO stub
- **PR target:** `feature/VISUAL-005-persona-aware-planner-pipeline`

### Phase 3 — Markdown injection + publishing transformers

- [x] `src/services/visuals/inject.py` (per-anchor markdown injection)
- [x] Update Ghost transformer to use it (`feature_image` for cover, Lexical cards for inline)
- [x] Update Medium transformer
- [x] Update LinkedIn transformer (with API URN dance for inline assets)
- [x] Per-transformer tests with multi-anchor specs
- [x] E2E: regenerate Ghost preview HTML for an existing article with new specs
- **PR target:** `feature/VISUAL-006-multi-anchor-publishing`

### Phase 4 — Backend HTTP API for studio (incl. upload + import-URL + section refine)

- [x] `src/api/routers/visuals.py` (plan / render / refine / replace / delete / **upload** / **fetch-from-url** / **section-html-refine** / cost / saved)
- [x] `src/services/visuals/section_html_refiner.py` (Claude-driven section HTML/CSS refinement)
- [x] Rate limiting (12/min on /render, 6/min on /fetch-from-url)
- [x] Multipart upload validation (MIME whitelist, size cap, content-type sniff)
- [x] SSRF tests for `/fetch-from-url` (private IPs, link-local, redirects-to-private)
- [x] Cost tracking endpoint `GET /visuals/cost?article_id=`
- [x] Saved-asset gallery endpoint `GET /visuals/saved`
- [x] Auth + RBAC
- [x] OpenAPI docs
- [x] Contract tests for all endpoints
- **PR target:** `feature/VISUAL-007-studio-api`

### Phase 5 — Frontend Visual Studio (with HTML refine + import flows)

- [x] `frontend/src/lib/api/visuals.ts`
- [x] `frontend/src/lib/visuals/visualStyles.ts` (boot fetch + caching, NO mirrored TS catalogue)
- [x] `frontend/src/lib/visuals/imageSrc.ts` (port `pickGeneratedImageSrc` — URL-first, base64 fallback)
- [x] `frontend/src/components/visuals/VisualStudio.tsx`
- [x] `frontend/src/components/visuals/SpecCard.tsx` (with Render/Edit/Replace/Upload/Import-URL/Refine)
- [x] `frontend/src/components/visuals/StyleChipRail.tsx`
- [x] `frontend/src/components/visuals/SectionHtmlRefinePanel.tsx` ("Apply with AI" → `/visuals/section-html-refine`)
- [x] `frontend/src/components/visuals/SavedAssetGallery.tsx` (modal picker)
- [x] `frontend/src/components/visuals/UsageBadge.tsx`
- [x] Mount in article-detail screen
- [x] Vitest + Testing Library: render, render-spec, refine flow, upload flow, import-URL flow
- [x] Playwright E2E: open studio → plan → render → toggle premium → regenerate → upload custom → refine HTML
- [x] Flip `enable_image_planner` default to `True`
- [x] Update `frontend/DESIGN.md` with Visual Studio component patterns
- **PR target:** `feature/VISUAL-008-visual-studio-ui`

### Phase 6 — MinIO production rollout + cost dashboard

- [x] Provision MinIO (or AWS S3) in staging + production environments
- [x] Helm chart updates (per `docs/architecture/HIGH_LEVEL_ARCHITECTURE.md` §6 mention of S3 for assets)
- [x] Backfill existing illustration files into the new bucket; rewrite `ImageAsset.url` paths
- [x] Lifecycle policy: archive assets older than 90 days to cold storage (per RISK-008 disposition)
- [x] Grafana dashboard panel for image-generation cost + storage volume
- **PR target:** `feature/VISUAL-009-storage-rollout`

### Phase 7 — Saved-asset gallery + audience-persona Settings UI

- [x] DB migration: `image_assets` table (was implicit before — explicit row per saved asset, with style token)
- [x] User-facing "My Visuals" page: filter by article / style token / date
- [x] Settings UI: per-user default audience persona (CTO / Marketer / General Business / …)
- [x] Default persona threads through to topic creation modal + article-detail Visual Studio
- [x] Tests: gallery filter, persona persistence, persona-driven planner output diff
- **PR target:** `feature/VISUAL-010-gallery-and-persona-settings`

### Phase 8 — Per-section content editing (text + AI rewrite)

> Closes the "fine-grained per-section control" gap. Visual Studio handles images; this phase adds the same depth of control for prose, accessible via an in-context toolbar that floats over the section the editor is focused on.

**Boundary invariants enforced by this phase** (do not violate when implementing):

- **ADR-003 (CanonicalArticle boundary)** — CanonicalArticle remains the single source of truth for the active article body. The new `section_versions` table is an *append-only audit sidecar*, keyed on `section_id`; no other subsystem (publishing, planner, RAG, search) reads it. Live state stays on CanonicalArticle.
- **ADR-004 (Transformer/Adapter publishing)** — No transformer or adapter is modified in this phase. Publishing-layer code (`src/services/publishing/**`) stays out of `src/services/content/` and `src/api/routers/content.py`. Ghost/Medium/LinkedIn keep consuming CanonicalArticle exactly as before; they have no awareness of edit history, tone presets, or rewrite source.
- **Anchor invariants** — Image `spec_id` references and `ImagePlacement.heading_text` values bound to `before_heading` placements are first-class invariants. The rewrite validator (`section_rewriter._validate_anchors`) **rejects** edits that drop or rename them, returning HTTP 422 with a structured diff so the frontend can show the editor what's blocking the save. This is what protects Visual Studio's image-spec anchors from drifting silently when prose is edited.
- **No platform leakage** — Tone presets (`shorter`, `more concrete`, `more conversational`, `more authoritative`) are server-side instruction templates inside `section_rewriter.py`. The frontend posts a preset name; the backend expands it. No preset-specific or platform-specific logic ever leaves the content service.
- **Service-Layer pattern** — Route handler → Service → Repository → DB. No direct DB calls from `content.py` routes. Same shape as the existing `section_html_refiner.py`.


- [x] `src/services/content/section_rewriter.py` (Claude-driven section/paragraph prose rewrite, mirrors `section_html_refiner.py`)
- [x] `src/services/content/section_history.py` (append-only version log per section)
- [x] DB migration: `section_versions` table — `(id, section_id, article_id, markdown, source: "manual" | "ai" | "tone_preset", instruction?, model?, tokens?, usd?, created_at, created_by)`
- [x] `src/api/routers/content.py` — endpoints from §5.7.1
- [x] Anchor-preservation validator: rejects edits that drop image `spec_id` references or rename heading text bound to `before_heading` placement (preserves Visual Studio integrity)
- [x] `frontend/src/components/article/SectionContextToolbar.tsx` — appears on hover/focus over a section in the article column. Three actions: *Edit text* (inline contenteditable + AI popover), *Edit visual* (jumps to that section's Spec Card in Visual Studio), *Refine layout* (opens Section HTML Refine panel scoped to this section).
- [x] `frontend/src/components/article/InlineProseEditor.tsx` — contenteditable wrapper with markdown round-trip, paragraph-level selection model, AI rewrite popover anchored to selection. *(v1: textarea + paragraph splitter — contenteditable round-trip deferred per handoff brief.)*
- [x] `frontend/src/components/article/AIRewritePopover.tsx` — instruction textarea + tone preset chips (`shorter`, `more concrete`, `more conversational`, `more authoritative`) + diff view + accept/reject affordance. Wired to `/content/section-rewrite` and `/content/paragraph-tone`.
- [x] `frontend/src/components/article/SectionHistoryDrawer.tsx` — list prior versions, restore, with diff vs. current.
- [x] Word-level diff renderer reused from §17.2 (humanization diff). Single source of truth for diff visualisation across image refine, HTML refine, and prose rewrite.
- [x] Vitest + Testing Library: toolbar visibility on hover, popover open/close, accept/reject diff, anchor-preservation rejection path, history restore.
- [ ] Playwright E2E: hover section → toolbar appears → click Edit text → select paragraph → AI rewrite "shorter" → accept → verify markdown updated → undo via history → verify original restored. *(Deferred — Playwright not yet wired into the repo. Covered by Vitest + RTL component / API-mock tests instead, mirroring the Phase 5 decision.)*
- [x] Update `frontend/DESIGN.md` with SectionContextToolbar pattern.
- **PR target:** `feature/VISUAL-011-per-section-content-editing`

---

## 12. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Imagen 4 cost overrun (paid tier) | M | H | Default to Gemini Flash; gate Imagen 4 behind explicit `imagen_4_enabled` flag + per-user budget cap |
| Imagen 4 hallucinates text in image | M | M | Aggressive `no_text_clause`; strip brand names from `brand_context` before feeding Imagen |
| Gemini Flash ignores aspect ratio | H | L | Embed aspect sentence in prompt (impactai's approach); Imagen 4 honours it natively |
| Gemini 3 Pro Image Preview deprecated/renamed | M | L | Env-resolvable model IDs (`COGNIFY_IMAGE_MODEL_GEMINI_3_PRO`); swap without code change |
| Planner returns invalid JSON | M | L | `parse_llm_json` (L-002 compliance) + `_fallback_specs` |
| Frontend↔backend catalogue drift | L | L | **Single source of truth in backend; frontend fetches at boot.** Eliminated by design |
| Concurrent renders rate-limited | M | M | `p-limit(3)` on frontend + 12/min on backend; surface friendly throttle UI |
| User confusion about Fast / Mid / Premium | M | L | Tooltip with cost-per-image per tier; auto-fallback if Premium returns billing error |
| Pipeline runs slower with extra LLM call | M | M | Planner is one Claude call per article (not per section bundle); ~3-5s added; cache spec when re-running |
| Existing articles look stale without specs | L | L | "Plan visuals for this article" button on each detail page; opt-in backfill |
| Image storage growth | M | L | MinIO/S3 from day 1 (Phase 1); 90-day archive lifecycle policy (Phase 6); Grafana storage volume panel |
| **MinIO disabled or misconfigured in prod** (NEW) | M | M | Auto-fallback to base64 mirrors impactai pattern; startup health check warns when `MINIO_ENABLED=true` but config incomplete; `_minio_enabled_config()` logs missing env vars |
| **SSRF via fetch-from-URL** (NEW) | M | H | `safe_http.py` rejects private/loopback/link-local CIDRs; DNS resolution before fetch; redirect chain re-validated; non-http(s) schemes rejected; size cap enforced as the body streams |
| **User uploads malicious file** (NEW) | M | H | MIME whitelist + magic-byte sniff (not Content-Type alone); size cap; AV scan pluggable |
| **Persona register feels stereotyped** (NEW) | M | M | Persona register fragments are *guidance*, not hard rules; user can override with page art direction; ban-list explicitly prevents the worst stereotypes ("no tight close-ups of identifiable faces", "no glowing AI brain") |
| **HTML-refine endpoint produces broken markup** (NEW) | M | M | Sanitize output via `bleach`; reject if `<html>` / `<body>` / `<script>` present; preserve original on parse failure; show diff before applying |

---

## 13. Open Questions

1. **Provider for hero/cover by default — Gemini Flash or DALL-E 3?** Recommendation: Gemini Flash. Rationale: free tier covers it; iteration is cheap; the planner-driven prompt should produce more on-brand output than DALL-E 3's static prompt. Keep DALL-E 3 selectable.
2. **Should we keep Matplotlib charts at all?** Recommendation: yes. Real data → real chart (matplotlib) is more honest than asking an image model to draw fake data. Keep `chart_generator.py` running after `image_render`.
3. **Should the planner consider charts/diagrams when picking image specs?** Recommendation: yes — pass the proposed chart/diagram specs as context to the image planner so it doesn't double-cover the same section with a redundant illustration. Implementation: planner runs *after* charts/diagrams are proposed (move chart/diagram proposal out of the rendering nodes into earlier "proposal" nodes).
4. **Industry adaptation (impactai's 6-vertical model)?** Out of scope here. Cognify operates on `domain` per article, which is a softer adaptation. The visual catalogue is domain-neutral on purpose.
5. **Pulse-style image roles (quote_card, stat_card, framework)?** Recommend including in the catalogue from day 1. They map naturally to article highlight callouts.

---

## 14. Estimated Effort

| Phase | SP | Notes |
|---|---:|---|
| 1 — Catalogue + providers + MinIO + SSRF guard | 13 | +5 SP from original (was 8) — adds object_storage, safe_http, gemini_3_pro provider, banned-cliché block |
| 2 — Persona-aware planner + pipeline | 13 | unchanged scope, slightly more nuanced prompt |
| 3 — Injection + publishing | 8 | unchanged |
| 4 — Studio API (incl. upload, fetch-url, section-html-refine, gallery) | 8 | +3 SP from original (was 5) |
| 5 — Studio UI (incl. HTML refine + import/upload + saved gallery picker) | 21 | +8 SP from original (was 13) — VisualStudio is now substantially richer |
| 6 — MinIO production rollout + cost dashboard | 5 | new |
| 7 — Saved-asset gallery + audience-persona Settings UI | 8 | new |
| 8 — Per-section content editing (text + AI rewrite) | 13 | new — closes per-section prose-control gap; adds `section_versions` table, rewrite endpoints, in-context toolbar, AI popover, history drawer |
| **Total** | **89** | ~8 PRs over 8–10 weeks at current cadence |

---

## 15. References

- Companion: [`docs/architecture/COGNIFY_VS_IMPACTAI_REVIEW.md`](../../architecture/COGNIFY_VS_IMPACTAI_REVIEW.md)
- ImpactAI source-of-truth doc: `D:/Workbench/gitlab/impactai/docs/image-generation.md`
- ImpactAI: [`apps/api/services/visual_styles.py`](D:/Workbench/gitlab/impactai/apps/api/services/visual_styles.py) (catalogue)
- ImpactAI: [`apps/api/routers/generate.py`](D:/Workbench/gitlab/impactai/apps/api/routers/generate.py) (`_build_banner_prompt` L2988, `_build_planner_prompt` L3346)
- ImpactAI: [`apps/api/services/pulse_image_planner.py`](D:/Workbench/gitlab/impactai/apps/api/services/pulse_image_planner.py)
- ImpactAI: [`apps/web/components/create/landing/SectionImageModal.tsx`](D:/Workbench/gitlab/impactai/apps/web/components/create/landing/SectionImageModal.tsx)
- ImpactAI: [`apps/web/lib/injectBanners.ts`](D:/Workbench/gitlab/impactai/apps/web/lib/injectBanners.ts)
- Cognify: [`src/agents/content/illustration_generator.py`](../../../src/agents/content/illustration_generator.py) (existing hero generator)
- Cognify ADRs: [`docs/architecture/adrs/`](../../architecture/adrs/)
- Cognify: [`docs/LEARNINGS.md`](../../LEARNINGS.md) (especially L-002 LLM JSON, L-009 Ghost Lexical)

---

## 16. Sign-off Checklist (before implementing)

- [ ] User reviewed and approved scope (this doc)
- [ ] ADR-005 drafted and approved (image-spec planner amendment + MinIO object storage)
- [ ] `frontend/DESIGN.md` updated with Visual Studio mockup approval (Pencil)
- [ ] `COGNIFY_GOOGLE_AI_API_KEY` secret provisioned for staging + production
- [ ] `COGNIFY_MINIO_*` env provisioned for staging + production (or AWS S3 equivalent)
- [ ] `imagen_4_enabled` rollout strategy agreed (default off in prod until billing reviewed)
- [ ] `gemini_3_pro_enabled` agreed (preview model — confirm Google's stability commitment)
- [ ] SSRF guard threat-model reviewed by security lead before `/visuals/fetch-from-url` ships
- [ ] Image-upload MIME whitelist + size cap aligned with `docs/security/SECURITY_CHECKLIST.md` §2
- [ ] Tickets created in Azure Boards for each phase (VISUAL-004 … VISUAL-010)
- [ ] BACKLOG.md / PROGRESS.md updated with new tickets
- [ ] Risk RISK-009 ("Image cost overrun via Imagen 4") added to RISK_REGISTER.md
- [ ] Risk RISK-010 ("SSRF via fetch-from-URL") added to RISK_REGISTER.md
- [ ] Risk RISK-011 ("Malicious user-uploaded image") added to RISK_REGISTER.md

---

## 17. Out-of-scope Follow-ups (recorded for completeness)

While reviewing impactai's `feat/content-hub` branch, two further patterns surfaced that deserve their own tickets but don't belong in this image-focused plan:

### 17.1 Markdown-structure-aware humanization

**Source:** [`impactai/apps/api/services/markdown_structure.py`](D:/Workbench/gitlab/impactai/apps/api/services/markdown_structure.py) (237 LoC)

ImpactAI added a markdown parser specifically for the humanization path: it splits the article into typed blocks (heading, image, table, code, list, blockquote, paragraph, hr) and only feeds prose blocks to the LLM rewriter. Headings/images/tables/code are restored verbatim. This is defensive engineering that prevents the humanizer from garbling structure — a class of bug Cognify will eventually hit.

**Suggested ticket:** `CONTENT-007 — Structure-aware humanization`. Port `markdown_structure.py` to `src/utils/markdown_structure.py`, refactor `humanizer.py` to use it.

### 17.2 Word-level humanization diff UI

**Source:** [`impactai/apps/web/components/create/HumanizeWordDiffPanel.tsx`](D:/Workbench/gitlab/impactai/apps/web/components/create/HumanizeWordDiffPanel.tsx) (134 LoC) + [`humanizeDiffView.ts`](D:/Workbench/gitlab/impactai/apps/web/lib/humanizeDiffView.ts)

Inline word-by-word diff between original and humanized text, with accept/reject affordances. Builds user trust by showing exactly what changed. Cognify's slop-pattern scorer already produces a structured diff internally — this just surfaces it.

**Suggested ticket:** `DASH-007 — Humanization diff panel`.

### 17.3 SSRF guard re-use

**Source:** [`impactai/apps/api/services/safe_http_url.py`](D:/Workbench/gitlab/impactai/apps/api/services/safe_http_url.py) (93 LoC)

Worth lifting wholesale into `src/utils/safe_http.py` even before Phase 4 of this plan ships, because Cognify's existing trend sources fetch external URLs (NewsAPI, arXiv, Reddit, HN) and the SSRF guard could harden them in passing.

**Suggested ticket:** `INFRA-006 — SSRF guard for outbound fetches`.
