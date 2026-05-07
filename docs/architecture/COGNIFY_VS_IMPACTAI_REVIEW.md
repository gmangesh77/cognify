# Architecture Review: Cognify vs ImpactAI (ContentAI)

> **Date:** 2026-05-06 (updated to reflect ImpactAI's `feat/content-hub` branch — significantly newer than `main`)
> **Scope:** Side-by-side architectural comparison of Cognify (`D:\Workbench\github\cognify`, branch `develop` → worktree on `claude/vibrant-chatterjee-1115a8`) and ImpactAI (`D:\Workbench\gitlab\impactai`, branch **`feat/content-hub`**).
> **Purpose:** Determine which project is architecturally superior across all dimensions, including flexibility, modularity, testability, observability, and extensibility — and identify what each project should learn from the other.
>
> **Note on the diff vs `main`:** `feat/content-hub` adds ~19,000 lines across 123 files (per `git diff main..feat/content-hub --stat`). The biggest additions: a brand-new **VisualLayoutStep** wizard (1,169 lines of section-level HTML/CSS + image refinement), a **MinIO/S3 object-storage layer** (398 lines), a **dedicated LinkedIn Post image planner** (294 lines), a **markdown structure parser** for safe humanization (237 lines), a **landing-page HTML builder** (2,798 lines), per-role visual prompt templates, carousel design presets, persona-aware visual direction, word-level humanization diffs, and a third image provider — `gemini-3-pro-image-preview`. The findings below incorporate these additions.

---

## 1. Executive Summary

| Dimension | Cognify | ImpactAI | Winner |
|---|---|---|---|
| **System architecture** | Multi-agent (LangGraph), service-layer, canonical-boundary | Wizard-driven, monolithic FastAPI, frontend-state-heavy | **Cognify** |
| **Domain depth** | Trend → Research → CanonicalArticle → Multi-platform Publish | 4-step Topic → Generate → Humanize → SEO + 6 industry verticals | **Tied** (different scopes) |
| **Image generation flexibility** | 1 hero (DALL-E 3, fixed prompt), no user control | 12 visual styles × **3 providers** × **4 dedicated planners** (landing, Pulse, LinkedIn Post, Carousel) × **4 wizards' worth of UI** + MinIO-backed asset hosting | **ImpactAI (gap is now 5–10× larger than `main` showed)** |
| **Content humanization** | Slop-pattern scorer + rewrite node | Multi-mode/intensity humanizer with 5-detector simulation **+ markdown-structure-aware rewriting + word-level inline diff UI** | **ImpactAI** |
| **Multi-platform publishing** | 4 transformer/adapter pairs (Ghost, Medium, LinkedIn) + tracking | DOCX/PDF/Carousel-PDF + **dedicated LinkedIn Post & Pulse rendering paths**; no Ghost/WP/Medium adapters | **Cognify** (still — ImpactAI's content-hub work targets LinkedIn-only) |
| **Asset hosting / image URLs** | Local file system → API-served paths | **MinIO/S3 object storage with public URLs**; falls back to base64; per-image normalisation | **ImpactAI (new on `feat/content-hub`)** |
| **Per-content-type planners** | One generic content pipeline | **4 specialised planners**: landing (`generate.py:_build_planner_prompt`), Pulse (`pulse_image_planner.py`), LinkedIn Post (`linkedin_post_image_planner.py`), Carousel (`carousel_planner.py`) | **ImpactAI** |
| **Modularity & boundaries** | CanonicalArticle ADR, Service-layer pattern, TrendSource Protocol | Direct router → service calls, mixed concerns | **Cognify** |
| **Testing maturity** | 953 backend + 250 frontend, FakeLLM strategy, TestContainers | Backend tests present (`apps/api/tests`), no frontend test infra found | **Cognify** |
| **Observability** | structlog, OpenTelemetry, SLOs/SLIs documented, Prometheus plan | Basic logging, `usage_tracker` cost meter | **Cognify** |
| **Security posture** | Encrypted API-key storage, Fernet, RBAC, ADR-driven | Demo-mode auth + Supabase + JWT, simpler model | **Cognify** |
| **CI/CD** | GitHub Actions + Docker + Makefile + Helm plan | Docker Compose only | **Cognify** |
| **Infrastructure** | PostgreSQL + Milvus + Redis + Celery + S3 | PostgreSQL + Supabase + (planned) Celery + Redis | **Cognify** |
| **AI workflow sophistication** | Multi-agent parallel research, RAG via Milvus, citation grounding | Single Claude call per step, no RAG | **Cognify** |
| **User-facing flexibility & UX** | Headless pipeline + dashboard surfaces | 7-step interactive wizard with per-step refinement | **ImpactAI** |
| **Extensibility (extension points)** | Protocols + Registry (TrendSource), ADR culture | Frontend↔backend mirrored catalogues, prompt templates | **Cognify** |
| **Cost & LLM economics** | Cost monitoring planned in observability spec | `usage_tracker` live, per-session UsageBadge | **ImpactAI** (live), **Cognify** (planned) |
| **Documentation & ADRs** | 4 ADRs, comprehensive `docs/` tree, LEARNINGS.md | Two domain docs + handoff docs | **Cognify** |

**Bottom line:** Cognify is the architecturally superior platform overall — better separation of concerns, deeper agent orchestration, multi-platform publishing, more complete observability/security/testing strategy, and a more rigorous decision-record culture. **ImpactAI wins decisively in two specific places: image generation flexibility/UX and the interactive wizard authoring experience.** Cognify should adopt ImpactAI's image-planner pattern and visual-style catalogue (see the companion [Visual Generation Improvement Plan](../superpowers/plans/2026-05-06-visual-generation-improvement-plan.md)).

---

## 2. Codebase Topology

### 2.1 Cognify

```
src/
  agents/          LangGraph orchestrator + research/content/visual agents (graph nodes)
    content/       outline → queries → draft → validate → citations → humanize → SEO → charts → diagrams → illustration
    research/      web_search, literature_review (parallel via dispatcher)
  pipelines/       trend discovery, research, content gen, visual gen wrappers
  services/        topic ranking, SEO, content, research, milvus, publishing/{ghost,medium,linkedin,wordpress}
  api/             FastAPI routes, middleware, auth (JWT RS256 + RBAC)
  models/          Pydantic models (content, research, visual, settings) + SQLAlchemy tables
  db/              engine, repositories, Alembic migrations
  config/          pydantic-settings (COGNIFY_* env prefix)
  utils/           structlog setup, parse_llm_json, key_resolver (Fernet)
frontend/          Next.js 15 + React 19 + TS dashboard (app router, hooks/, components/, types/)
docs/architecture/ HIGH_LEVEL_ARCHITECTURE.md + 4 ADRs
```

**Architectural anchor:** [`CanonicalArticle`](../../src/models/content.py) — the central platform-neutral contract between content generation and publishing. ADR-003 mandates this boundary; ADR-004 formalises the Transformer/Adapter pattern per platform.

### 2.2 ImpactAI

```
apps/
  api/             FastAPI (Python)
    routers/       analytics, auth, content, generate (4,580 LoC), humanize, landing, seo,
                   settings, wizards (with /pulse-image-plan, /linkedin-post-image-plan,
                   /carousel-plan, /carousel-pdf, /case-study-outline, /whitepaper-outline,
                   /data-table, /variants, /faq-suggest, /linkedin-assist), …
    services/      carousel_pdf, carousel_planner, content_strategy, detection,
                   humanize_*, landing_*, pulse_image_planner (319 LoC),
                   linkedin_post_image_planner (294 LoC, new),
                   markdown_structure (237 LoC, new — humanization-safe parser),
                   object_storage (398 LoC, new — MinIO/S3),
                   safe_http_url (93 LoC, new — SSRF guard for fetch-image-from-url),
                   seo_*, variant_generator, visual_styles, …
    models/        banner.py, carousel.py, content.py, humanize.py, landing.py,
                   section_html_refine.py (new), prompts.py, seo.py
    migrations/    raw SQL (e.g. 001_saved_infographics_image_url.sql)
    tasks/         Celery tasks (incl. batch_humanize)
    templates/     PDF / letterhead / carousel templates
  web/             Next.js 14 frontend
    components/create/   wizard screens (Web/LinkedIn-Post/Pulse/Whitepaper/Carousel/CaseStudy/Faq/Product),
                         + VisualLayoutStep.tsx (1,169 LoC, new — section HTML/CSS + image refinement),
                         + LinkedInPostFeedMedia.tsx, LinkedInGalleryPickerModal.tsx,
                         + HumanizeWordDiffPanel.tsx (word-level humanizer diff UI),
                         + landing/{SectionImageModal, visualStyles}
    lib/                 buildLandingHtml (2,798 LoC, new), defaultSectionVisualPrompts (176 LoC, new),
                         carouselVisualStyle, bannerImage (MinIO-aware src picker), injectBanners,
                         linkedinPostBriefAutos, linkedinPulseBriefAutos, linkedinWizardImageGallery,
                         humanizeDiffView, dataUrlHtml, normalizeFeedPostText, formatGeneratedMarkdown,
                         landingFooterPreset, companyLandingChrome, …
    public/wireframes/   23 roles × 71 variant SVGs (problem, process, services_overview, trust_bar,
                         hero, usp, …) — substantial visual catalogue refresh on this branch
docs/              README, image-generation, landing-page-sections (3 files)
docker-compose.minio.yml  MinIO bucket for image assets (new)
```

**Architectural anchor:** No formal boundary contract. The wizard *itself* — its 7 (or 4) ordered steps and shared state — is the de-facto architecture. Backend routers map ~1:1 to wizard steps.

---

## 3. Domain Architecture

### 3.1 Pipeline Shapes

**Cognify (autonomous, multi-stage):**

```
Trend Sources (5 plugins) → Topic Ranking → User picks topic →
  Orchestrator (LangGraph) → Research Agents (parallel, RAG via Milvus) →
  Writer Agent (outline → queries → draft → validate → citations → humanize → SEO →
    charts → illustration → diagrams) →
  CanonicalArticle (PG + S3) →
  Publishing Service → [Ghost | Medium | LinkedIn | WordPress] Transformer + Adapter
```

**ImpactAI (interactive, wizard-driven):**

```
User selects industry + content type →
  Wizard Step 1 (type) → Step 2 (topic, keywords, tone, length) →
  Step 3 (Generate via Claude SSE streaming) →
  Step 4 (Variant pick — for landing pages) →
  Step 5 (Section drafting + per-section ImageModal) →
  Step 6 (Image Studio — page-wide art direction, bulk render, per-spec controls) →
  Step 7 (Review + Export DOCX/PDF / Publish to single sink)

  Parallel paths: Humanizer (mode × intensity) + SEO Optimizer
```

### 3.2 Architectural patterns at play

| Pattern | Cognify | ImpactAI |
|---|---|---|
| Multi-agent orchestration | ✅ LangGraph StateGraph w/ checkpointing | ❌ Linear API calls per wizard step |
| RAG (vector DB) | ✅ Milvus + token-chunked embeddings | ❌ Plain Claude calls |
| Service Layer | ✅ Routes → Service → Repository → DB | ⚠️ Mostly Routes → Service, but routes also embed orchestration |
| Boundary contract | ✅ CanonicalArticle | ❌ Per-format ad-hoc (markdown, PDF, DOCX) |
| Transformer/Adapter for sinks | ✅ Per platform | ❌ Single sink (DOCX/PDF or copy) |
| Plugin protocol + registry | ✅ TrendSource Protocol (ADR-002 / ARCH-002) | ❌ |
| Mirrored frontend↔backend catalogues | ❌ (not needed) | ✅ Visual styles, role styles (with the manual sync caveat) |
| Wireframe-variant short-circuit | ❌ | ✅ Pre-baked `image_specs` per variant skip the planner |

### 3.3 Where each shines

- **Cognify wins on autonomy:** the platform discovers topics, researches them in parallel, and produces a publication-ready CanonicalArticle without continuous user input. The agent orchestration with checkpointing is genuinely powerful and rare.
- **ImpactAI wins on craft:** the wizard treats content production as a hands-on craft, with art-direction controls, per-image refinement chats, and bulk-regenerate with provider toggles. A user actively shaping their output gets dramatically more leverage in ImpactAI.

---

## 4. Image Generation: A Deep Comparison

This is where the two projects diverge most. The user's frustration with Cognify's images is rooted in **architectural decisions**, not implementation bugs.

### 4.1 Generators

| | Cognify | ImpactAI (`feat/content-hub`) |
|---|---|---|
| Hero / cover | DALL-E 3 (`illustration_generator.py`, ~116 LOC) | **Three providers**: `gemini_flash` (default, `gemini-2.5-flash-image`), `gemini_3_pro_image_preview` (LinkedIn short-post lane), `imagen_4` (premium photo realism) — env-driven model resolution via `_resolve_banner_gemini_model_id()` |
| Per-section images | ❌ none | ✅ N specs per section, planned by Claude — **and** per-section HTML/CSS layout refinement via `VisualLayoutStep` |
| Charts | Matplotlib (bar/line/pie) | `/data-table` endpoint generates whitepaper/case-study charts; carousel planner places "metric callouts" |
| Diagrams | Mermaid via mmdc CLI (6 types) | Frameworks rendered as styled images by Gemini/Imagen; SVG wireframes back the variant picker (71 variants across 23 roles) |
| Style providers | None — single hard-coded prompt | 12 visual styles + **8 LinkedIn-post styles** (data_moment, process_scene, contrast, milestone, strategic, insight, bold_take, editorial) + **6 Pulse role styles** + **8 carousel design presets** + composable overrides |
| Aspect ratios | Fixed 16:9 hero (1600×900) | 5 (`16:9`, `1:1`, `4:3`, `3:4`, `4:5` — including 1080×1350 LinkedIn document-carousel proportions) per spec, with a per-aspect `_aspect_instruction` sentence and an Imagen-specific aspect-snap map |
| Asset hosting | Local file paths, served via API | **MinIO/S3 uploads** with public URLs; `pickGeneratedImageSrc()` falls back to base64 when MinIO disabled; auto-detected dev mode via `MINIO_ANONYMOUS_DOWNLOAD` |
| Image *imports* | ❌ none | `/upload-image` (multipart) + `/fetch-image-from-url` (with `safe_http_url.py` SSRF guard) — user can drop in their own brand assets |
| Saved gallery | ❌ none | "Saved Infographics" page with `linkedin_gallery:` style tokens (`pulse:placement:role`, `post:image`, `post:carousel:slide_N`) for retrieval |

### 4.2 Prompting & art direction

**Cognify** ([`illustration_generator.py:76-93`](../../src/agents/content/illustration_generator.py)):

```python
_PROMPT_TEMPLATE = (
    "You are an expert art director at a premium tech publication...\n"
    "- Modern, visually striking digital illustration — NOT a stock photo\n"
    "- Abstract or conceptual representation of the topic\n"
    "- Style: blend of 3D render and flat design, cinematic lighting\n"
    "- NO text, NO photorealistic human faces, NO charts/graphs/diagrams\n"
    ...
)
```

One template, one style, every article. The user has no lever to pull. The output is "cinematic abstract tech art" forever.

**ImpactAI** ([`visual_styles.py`](../../docs/comparisons/impactai-visual_styles.py)):

- **12 catalogued visual styles** (lifestyle_photo, studio_portrait, environmental_team, flat_illustration, isometric_3d, editorial_collage, screenshot_mock, dashboard_card, gradient_abstract, geometric_pattern, dark_cta_band, before_after_split). Each ships a verbose `prompt_fragment` covering medium, palette, lighting, composition, plus an aggressive no-text guard.
- **Role-style defaults map** (`ROLE_STYLE_DEFAULTS`) — for each layout role, a sensible default visual style. So a `hero` defaults to `lifestyle_photo`; a `feature_card` defaults to `isometric_3d`.
- **Composable overrides** ([`_build_banner_prompt`](D:/Workbench/gitlab/impactai/apps/api/routers/generate.py)):
  1. **Page direction** (textarea, applies to whole page)
  2. **Visual style fragment** (style key → catalogue)
  3. **Section override** (per-section refinement)
  4. **Refine note** (per-image chat input)

  Layered into a single style_override and led with `Art direction: …` so the model weights it heavily.
- **"Composition reference IGNORED" trick** for safely combining role prompt (composition) with visual-style verbs (medium/palette).

### 4.3 Planning intelligence

**Cognify:** No planner. The hero is generated from `(title, summary, domain)`. Charts are picked from a one-shot LLM call asking "any data here?" (max 3). Diagrams from "any concepts here?" (max 5). Each generator is independent and unaware of the others.

**ImpactAI (`feat/content-hub`):** **Four dedicated planners**, one per content type, each Claude-backed and JSON-only:

| Planner | File | Purpose |
|---|---|---|
| Landing page | `routers/generate.py:_build_planner_prompt` (called by `/banner-plan`) | Per-section ordered ImageSpecs — role_style, visual_style, aspect, placement, prompt — with required variety across specs in the same section. Knows the entire 12-style catalogue via `planner_catalogue_block()`. |
| LinkedIn Pulse Article | `services/pulse_image_planner.py` (319 LoC) | Whole-article planner: 1 cover + 2–4 inline visuals across `pulse_concept`, `pulse_quote_card`, `pulse_side_by_side`, `pulse_framework`, `pulse_stat_card`. Persona-aware (CTO leans technical, HR leans culture). |
| LinkedIn Post (single image) | `services/linkedin_post_image_planner.py` (294 LoC, **new on this branch**) | One photorealistic editorial image per post. **Persona-aware visual register** — CEO → boardroom/skyline, CTO → engineering workspace + real code on dark monitors, HR → candid culture, BizDev → deal rooms. **Explicitly bans clichés** ("glowing AI brain", stock-photo handshakes, motivational poster vibes, flat-design illustrations). Each style is a real photographable scene with specified lighting, framing, depth of field, and palette. |
| Carousel deck | `services/carousel_planner.py` (was 71 LoC, now 204 — substantially upgraded) | Plans an N-slide carousel with `design_preset` (linkedin_case_study, linkedin_minimal, linkedin_bold_metrics, tech_product, finance_trust, healthcare_calm, edu_learning, retail_consumer) → maps to a "visual lane" fragment per slide. |

This is the heart of the user's complaint. **ImpactAI plans visuals; Cognify guesses.** Worse, **ImpactAI plans different *kinds* of visuals for different *kinds* of content** — landing-section visuals, pulse covers, LinkedIn post photos, and carousel slides each have their own dedicated planner with content-aware rules.

### 4.4 Placement

**Cognify:**

- Hero → top of article (in `feature_image` field for Ghost; first `<img>` for HTML output).
- Charts → after the source section (or end if `source_section` invalid).
- Diagrams → above article body (if `section_index = -1`) or after their source section.

Logic lives in [`ghost/transformer.py:_inject_visuals`](../../src/services/publishing/ghost/transformer.py). One placement axis: "where the chart belongs in the article."

**ImpactAI:** 7 placement anchors, all routed through [`injectBanners.ts`](D:/Workbench/gitlab/impactai/apps/web/lib/injectBanners.ts):

| Anchor | Behaviour |
|---|---|
| `top` | Image prepended to the section. |
| `before_heading` | Inserted before a fuzzy-matched heading. |
| `bottom_grid` | Multiple images rendered as an HTML grid at section end. |
| `cover` | Prepended above the article title (Pulse). |
| `between_paragraphs` | Inserted after paragraph N (Pulse). |
| `background` | Full-bleed background marker (rendered by SVG layer). |
| `column_split` | Wraps section as 2-column with image on one side. |

This means a section can carry a hero photo at top, a stat card after paragraph 2, and a feature-card grid at the bottom — all coherently.

### 4.5 User control surface

**Cognify:** None. The pipeline runs end-to-end; the user sees the final article. They cannot influence visual choice, regenerate a specific image, or change style.

**ImpactAI (`feat/content-hub`):**

- **Step 5 SectionImageModal:** opens per section, plans 2–3 specs, renders variants per spec (often trying multiple visual styles in parallel), user picks one per slot.
- **Step 6 Image Studio:** page-wide art direction (free-text), default visual style chip rail, render-quality toggle (now **Fast / Mid / Premium** — Gemini Flash / Gemini 3 Pro Image Preview / Imagen 4) with per-spec override, bulk regenerate, plus per-card Refine input.
- **NEW Visual Layout Step (`VisualLayoutStep.tsx`, 1,169 LoC):** a wizard step *between* generation and review where the user can:
  - Switch between section tabs + an "append chrome" tab.
  - Apply role-aware AI seeds via `defaultSectionVisualPrompts.ts` (per-role HTML/CSS instruction templates for hero, trust_bar, stats_strip, services_overview, problem, features, benefits, social_proof, process, methodology, pricing, trust, faq, cta, lead_capture, comparison, case_study, integrations, use_cases, usp, industries_served, team, resources).
  - **Refine the section's HTML/CSS itself** with `/section-html-refine` (a new Pydantic endpoint with its own model). The user types "make it more spacious / use a 3-column grid / add a trust strip" and the LLM rewrites the HTML fragment for that single section.
  - Generate per-section banner images inline with role-tuned default prompts (`buildDefaultImagePrompt`) — fed back into the same in-place HTML.
  - **Import an image from a URL** (`/fetch-image-from-url`, SSRF-guarded) or **upload one** (`/upload-image`) — letting the user drop a brand asset onto a section.
  - Live iframe preview that re-renders on each AI pass.
- **LinkedIn-specific surfaces:**
  - `LinkedInPostFeedMedia.tsx` — feed-card preview that adapts to single-image vs carousel.
  - `LinkedInGalleryPickerModal.tsx` — pull a previously generated image from the user's saved gallery (filter via `linkedinWizardImageGallery.ts` style tokens).
- **Word-level humanization diff:** `HumanizeWordDiffPanel.tsx` + `humanizeDiffView.ts` show every word-level change the humanizer made — the user can accept/reject inline.
- **Per-image affordances:** Edit (role/aspect/anchor/heading-text/alt/prompt), Replace (file upload), Import URL, Remove image, Delete spec, Refine.

Three orders of magnitude more flexibility — and the gap widened sharply between `main` and `feat/content-hub`.

### 4.6 Cost economics

**ImpactAI:** Live `UsageBadge` reads `GET /usage/session/:id` and aggregates token counts and image counts per session. The user *sees* what they're spending in real time.

**Cognify:** No per-session cost meter. Observability spec mentions Prometheus token counters but they aren't surfaced to the user.

---

## 5. Content Generation: Quality Levers

| Lever | Cognify | ImpactAI |
|---|---|---|
| Outline quality | LangGraph node, structured Pydantic schema | Single Claude call per section |
| Source grounding (RAG) | ✅ Milvus retrieval per section | ❌ None |
| Citation management | ✅ Dedicated `citation_manager.py` with global citations + section refs | ❌ Inline only |
| Humanization | `humanize_node` + slop-pattern scorer + slop-phrase removal | Mode × intensity × 7-step pipeline + 5-tool detector simulation |
| SEO | `seo_optimizer.py` node + AI-discoverability node | `seo_brief.py` + on-page checklist + keyword density + SERP preview + 4-tab UI |
| Validation | Per-section validation node with redraft of shortest section | None — output stored as-is |
| Prompt variants | One template per node (parameterised) | 6 industries × 6 content types × 4 tones × 4 lengths = matrix-driven |
| Length control | `target_word_count` per section | Wizard preset (Short/Medium/Long/Pillar) |

**Net:** Cognify produces *grounded, cited, validated* articles with structural quality controls. ImpactAI produces *industry-tuned, undetectable, SEO-checklist-passing* articles with loud, marketable quality signals (the "94% → 3% bypass" gauge).

These are different products optimising for different jobs. But the techniques transfer cleanly: Cognify could borrow ImpactAI's mode-and-intensity humanizer dial, and ImpactAI could borrow Cognify's RAG grounding.

---

## 6. Cross-Cutting Concerns

### 6.1 Modularity & boundaries

**Cognify (strong):**

- ADR-003: CanonicalArticle as content↔publishing boundary
- ADR-004: Transformer/Adapter for each publishing platform
- ADR-001: LangGraph as the agent-orchestration choice
- ADR-002: Milvus as the vector DB
- TrendSource Protocol + Registry (ARCH-002)
- Service-Layer Pattern enforced (CLAUDE.md: "No direct DB calls from route handlers")
- Pydantic-settings centralisation; everything COGNIFY_-prefixed

**ImpactAI (weaker — and on `feat/content-hub` the gap widened):**

- Visual-style catalogue is mirrored frontend↔backend with no codegen and no startup validation (`docs/image-generation.md §10.1`: "Symptom of drift: backend silently drops the style and you get the role's BANNER_ROLE_PROMPTS style instead of the user's chosen one").
- `routers/generate.py` is now **4,580 lines** (up from 3,825 on `main`) mixing endpoints, prompt construction, provider routing, MinIO upload calls, carousel art-direction, LinkedIn post art-direction, refinement endpoints, and HTTP plumbing.
- `routers/wizards.py` likewise grew to host the four new planner endpoints (`/pulse-image-plan`, `/linkedin-post-image-plan`, `/carousel-plan`, `/carousel-pdf`) plus content-type-specific outline/variant/poll/link-caption/data-table/faq endpoints — currently 18+ endpoints in one file.
- `apps/web/lib/buildLandingHtml.ts` is **2,798 lines** of HTML/CSS generation for landing-page sections — a giant pure module that's nonetheless one file. Splitting per role would help.
- `apps/web/components/create/LinkedInPostCreateScreen.tsx` is **2,552 lines** (was ~1,400 on `main`) — the pattern of "wizard-as-architecture" is starting to fail.
- No formal boundary contract — exporter logic for DOCX/PDF/Carousel-PDF lives in `services/`, but article shape itself is implicit and now even more split between Web/LinkedIn-Post/Pulse/Carousel paths.
- New: a **markdown-structure parser** (`services/markdown_structure.py`, 237 LoC) was needed for the humanization pipeline because previously the LLM was garbling headings, tables, images, and lists when rewriting prose. This is good defensive engineering, but the fact it had to be added retroactively suggests structure-preservation wasn't designed in.

### 6.2 Testing

| | Cognify | ImpactAI |
|---|---|---|
| Backend tests | 953 (pytest, FakeLLM strategy) | Present (`apps/api/tests`), count not asserted |
| Frontend tests | 250 (Vitest + Testing Library) | Not surfaced |
| Test pyramid documented | ✅ `docs/testing/TEST_STRATEGY.md` | ❌ |
| TestContainers for integration | ✅ Postgres/Redis/Milvus | ❌ |
| FakeLLM fixtures | ✅ Recorded responses | ⚠️ Likely mocked ad-hoc |
| Coverage thresholds | ≥80% on new code, ≥70% overall | Not specified |
| Multi-stage CI | ✅ Lint → Unit → Integration → Security → E2E | Not present |

**Cognify's testing maturity is significantly higher.** This matters in the long run — every time ImpactAI adds a wizard step or visual style, the regression risk is unbounded; in Cognify, the test pyramid catches it.

### 6.3 Observability

| | Cognify | ImpactAI |
|---|---|---|
| Structured logging | ✅ structlog + correlation_id + sensitive-field redaction | ⚠️ Python `logging` module |
| Tracing | ✅ OpenTelemetry plan (every span named: api.request, agent.research, llm.call, vectordb.query, …) | ❌ |
| Metrics | ✅ Prometheus plan (`cognify_*` namespace, ~13 application metrics) | ⚠️ `usage_tracker` cost only |
| SLIs/SLOs | ✅ Documented (`OBSERVABILITY_PLAN.md`) | ❌ |
| Dashboards | ✅ Grafana plan | ❌ |
| Health endpoints | ✅ `/api/v1/health` + readiness probe | Basic |
| Cost meter (user-visible) | ❌ | ✅ UsageBadge per session |

### 6.4 Security

| | Cognify | ImpactAI |
|---|---|---|
| Auth | JWT RS256 + refresh-token rotation + RBAC (admin/editor/viewer) | Supabase Auth + JWT (HS256), demo-mode fallback |
| API-key storage | ✅ Fernet encryption at rest, runtime key resolver | env vars + `user_settings` table (no encryption mention) |
| RBAC | Three roles enforced at middleware | Single-user mostly |
| Security checklist | ✅ `docs/security/SECURITY_CHECKLIST.md` (10 sections) | ❌ |
| Secret scanning | ✅ `detect-secrets` in CI | ❌ |
| Sensitive log redaction | ✅ structlog field filtering | ❌ |

### 6.5 CI/CD & infrastructure

**Cognify:** GitHub Actions matrix (lint → unit → integration → security → coverage → E2E), Docker Compose full-stack + test compose, Helm charts planned, Makefile, branch strategy documented (`feature/* → develop → staging → main`).

**ImpactAI:** Docker Compose for postgres locally, no CI workflows surfaced in the repo root. Deployment notes mention Vercel + Railway.

### 6.6 Data & state

**Cognify:** PostgreSQL 16 (with Alembic migrations), Milvus for vectors, Redis for cache + Celery broker, S3 for assets, JSONB for flexible metadata. CanonicalArticle persisted to PG + S3.

**ImpactAI:** PostgreSQL with `schema.sql` (and `schema.docker.sql` for vanilla Postgres). Supabase optional. No vector DB, no Redis at the moment in code surface (Celery is "Phase 2 plan").

---

## 7. UX & Authoring Experience

This is ImpactAI's strongest dimension and Cognify's weakest.

| Aspect | Cognify | ImpactAI |
|---|---|---|
| Authoring style | Headless pipeline + dashboard | 7-step interactive wizard |
| Per-step refinement | Limited (custom topic entry, per-article params) | Built into every step |
| Image authoring | None | SectionImageModal + Image Studio + per-card refinements |
| Industry adaptation | Single-domain | 6 industries reconfiguring colours, content types, tones, compliance, sample data, ROI calc |
| Compliance UX | None (generic) | Banners for Healthcare/Finance |
| Iteration speed on a single article | Low — re-run the pipeline | High — refine in place |
| Live cost feedback | None | UsageBadge (live per session) |
| AI detection feedback | None | 5-detector grid with before/after animation |

**ImpactAI's UX is the product.** It's hard to overstate how much of its value lives in the wizard's tactility — the chip pickers, the chat-refine inputs, the bulk-regenerate, the studio strips. Cognify's UX ambition right now is "let users run the autonomous pipeline" — a different (and equally valid) bet, but a less hands-on one.

---

## 8. Extensibility: How easy is it to add X?

| Task | Cognify steps | ImpactAI steps |
|---|---|---|
| Add a new trend source | 1 (implement TrendSource protocol, register in registry) | N/A |
| Add a new publishing platform | 2 (Transformer + Adapter, register in PublishingService) | N/A |
| Add a new visual style | N/A (no catalogue) | 2 (frontend `visualStyles.ts` + backend `visual_styles.py`) — but with sync caveat |
| Add a new image provider | Touch `illustration_generator.py`, hook into nodes, update settings | 3 (router handler + frontend type + UI toggle in WebPageCreate + SectionImageModal) |
| Add a new chart type | Add to `ChartType` enum + `render_chart` switch | N/A |
| Add a new placement anchor | N/A | 5 (model + frontend type + injector + UI + planner prompt) |
| Add a new content type | Open new node | Add to industries map + wizard step |
| Add a new agent | Add to LangGraph (with state, edges, retry) | N/A |

**Cognify's extension model is more rigorous (protocols, registries, ADRs). ImpactAI's is more pragmatic (mirrored catalogues, prompt templates).** Both have legitimate trade-offs, but Cognify's scales better as the team and platform grow.

---

## 9. What Each Should Adopt From the Other

### 9.1 Cognify should adopt from ImpactAI

1. **Per-section image planner** (banner-plan endpoint pattern)
2. **Visual-style catalogue** (12 styles × verbose prompt fragments)
3. **Role-style ↔ visual-style orthogonal axes** (composition vs art-direction)
4. **Composable style override layers** (page direction + style + section override + refine note)
5. **Multi-provider image stack** — now **three** tiers: Gemini Flash (default, cheap), `gemini-3-pro-image-preview` (mid, used for LinkedIn short-post images on `feat/content-hub`), Imagen 4 (premium, paid)
6. **Placement anchors** (top, before_heading, between_paragraphs, bottom_grid, background, column_split, cover)
7. **User-driven image authoring UI** (SectionImageModal pattern + Image Studio panel)
8. **Live cost meter** (UsageBadge equivalent for the dashboard)
9. **Industry-tuned humanizer modes** (mode × intensity dial)
10. **AI-detector simulation** (or real detector integration) as a quality signal
11. **MinIO/S3 object storage** for generated images — replaces base64 payloads in API responses with public URLs, with auto-fallback to base64 when storage is unavailable. Significant performance and DB-size win.
12. **Persona-aware image planning** (LinkedIn-style: CEO/CTO/HR/BizDev personas drive distinct visual registers + an explicit ban-list of clichés). Cognify could carry "audience" through to the image planner the same way.
13. **Markdown-structure parser** for the humanization rewrite path (`markdown_structure.py`) — preserves headings/images/tables/code/lists so the LLM only rewrites prose. Solves a real bug Cognify will eventually hit.
14. **Per-role HTML/CSS prompt seeds** (`defaultSectionVisualPrompts.ts`) — content-type-aware default instructions for "make this section look like X" so the user starts from a useful prompt, not a blank textarea.
15. **Section-level HTML refinement endpoint** (`/section-html-refine`) — lets the user iterate on layout per section without re-running the full pipeline. A natural extension of Cognify's article-detail flow.
16. **Word-level humanization diff** (`HumanizeWordDiffPanel.tsx`) — exposes every word the humanizer changed so the user can accept/reject inline. Solves trust-the-rewrite anxiety.
17. **Image-import paths** — `/upload-image` (multipart) and `/fetch-image-from-url` (SSRF-guarded via `safe_http_url.py`). Lets users drop their own brand assets into the article.
18. **Saved-asset gallery** with style tokens (`linkedin_gallery:` prefix scheme) — lets users reuse previously generated visuals across articles.
19. **`safe_http_url` SSRF guard** — Cognify already validates URLs at the Pydantic boundary, but `safe_http_url.py` is a tighter pattern (DNS resolution + private/loopback/link-local CIDR rejection) worth adopting wholesale before shipping any user-supplied-URL feature.
20. **Banned-cliché lists in image prompts** — explicit "no glowing AI brain, no stock-photo handshakes, no flat-design illustrations" guidance addresses the user's "not good and meaningful" complaint head-on.

The companion document — [`Visual Generation Improvement Plan`](../superpowers/plans/2026-05-06-visual-generation-improvement-plan.md) — turns items 1–18 into a concrete, sequenced plan.

### 9.2 ImpactAI should adopt from Cognify

1. **CanonicalArticle-style boundary contract** between authoring and publishing
2. **Transformer/Adapter per output format** (DOCX, PDF, future Ghost/WP/Medium/LinkedIn)
3. **Codegen or single-source-of-truth for the visual-style catalogue** (eliminate the fe↔be sync trap documented in `docs/image-generation.md §10.1`)
4. **Service-layer discipline** (extract the 3,825-line `routers/generate.py` into services)
5. **ADR culture** (decisions get recorded, not just implemented)
6. **Multi-stage CI** (lint → unit → integration → security → E2E)
7. **Multi-platform publishing** (currently DOCX/PDF only — wide gap)
8. **RAG grounding** (Milvus + per-section retrieval) for factual quality
9. **Structured logging + correlation IDs**
10. **Encrypted API-key storage** (Fernet at rest)

---

## 10. Verdict

> **Cognify is the architecturally superior platform overall.** It has clearer boundaries, deeper agent orchestration, real multi-platform publishing, a more mature testing/observability/security posture, and a documented decision-record culture.
>
> **ImpactAI is the better product *for hands-on content authoring*.** Its wizard is a model of tactile, iterative content creation, and its image generation stack is in a different league from Cognify's — flexible, controllable, and economically transparent.

The two projects are not really competitors; they target different jobs. But Cognify has clear, well-scoped opportunities to import ImpactAI's image-generation ideas without compromising its architectural strengths. Conversely, ImpactAI would benefit from importing Cognify's boundary discipline — its growing catalogue of wizards (Web/LinkedIn Pulse/Whitepaper/Carousel/CaseStudy/FAQ/Product) is starting to strain the "wizard-as-architecture" pattern, and a Canonical-style abstraction would help.

---

## Appendix A — File-Size Sanity Check

Selected files surfaced during the review (line counts):

Numbers below reflect ImpactAI's `feat/content-hub` branch (not `main`).

| File | LoC | Notes |
|---|---:|---|
| `impactai/apps/api/routers/generate.py` | **4,580** | up from 3,825 on `main` (+949 LoC) |
| `impactai/apps/web/lib/buildLandingHtml.ts` | **2,798** | new on this branch |
| `impactai/apps/web/components/create/LinkedInPostCreateScreen.tsx` | **2,552+** | grew ~1,150 LoC |
| `impactai/apps/api/services/landing_variants.py` | 1,623 | rewrote 660 LoC on this branch |
| `impactai/apps/web/components/create/VisualLayoutStep.tsx` | **1,169** | new on this branch |
| `impactai/apps/web/components/create/LinkedInPulseCreateScreen.tsx` | grew ~1,690 LoC | |
| `impactai/apps/api/routers/wizards.py` | grew ~688 LoC | new endpoints concentrated here |
| `impactai/apps/api/services/object_storage.py` | **398** | new on this branch (MinIO) |
| `impactai/apps/api/services/linkedin_post_image_planner.py` | **294** | new on this branch |
| `impactai/apps/api/services/markdown_structure.py` | **237** | new on this branch |
| `impactai/apps/web/lib/defaultSectionVisualPrompts.ts` | **176** | new on this branch |
| `impactai/apps/api/services/pulse_image_planner.py` | 319 | up from 275 |
| `impactai/apps/api/services/visual_styles.py` | 272 | unchanged |
| `impactai/apps/api/models/banner.py` | 140 | unchanged |
| `cognify/src/agents/content/illustration_generator.py` | 116 | unchanged |
| `cognify/src/agents/content/chart_generator.py` | 128 | unchanged |
| `cognify/src/agents/content/diagram_generator.py` | 140 | unchanged |
| `cognify/src/models/visual.py` | 51 | unchanged |

Cognify's CLAUDE.md mandates "all files < 200 lines"; ImpactAI's `generate.py` would fail Cognify's standard 22× over (was 19× on `main`). The `buildLandingHtml.ts` (2,798 LoC) and `LinkedInPostCreateScreen.tsx` (2,552 LoC) are equally over the bar. This is a strong leading indicator that ImpactAI's modularity is *worsening* as features are added — exactly the pattern Cognify's protocol-and-registry approach is designed to avoid.

## Appendix B — References

- `docs/architecture/HIGH_LEVEL_ARCHITECTURE.md` — Cognify system design
- `docs/architecture/adrs/ADR-003-canonical-article-boundary.md` — Canonical contract
- `docs/architecture/adrs/ADR-004-publishing-transformer-adapter-pattern.md` — Publishing pattern
- `D:/Workbench/gitlab/impactai/docs/image-generation.md` — ImpactAI image-gen reference (the most useful single document in either project for understanding the image stack)
- `D:/Workbench/gitlab/impactai/PRODUCT_SCOPE.md` — ImpactAI product spec
- Companion: [`docs/superpowers/plans/2026-05-06-visual-generation-improvement-plan.md`](../superpowers/plans/2026-05-06-visual-generation-improvement-plan.md)
