# Progress Tracker: Cognify

> **Purpose**: Single source of truth for ticket status. New Claude Code sessions should read this file to understand what's done, in progress, and pending. Updated after each ticket is completed.
>
> **Convention**: Each completed or in-progress ticket links to its plan and spec files in `docs/superpowers/`. The backlog (`BACKLOG.md`) contains full acceptance criteria; this file tracks status only.

---

## Status Legend


| Status      | Meaning                                                     |
| ----------- | ----------------------------------------------------------- |
| Done        | Merged or ready to merge — all tests passing, code reviewed |
| In Progress | Active development on a feature branch                      |
| Planned     | Spec and/or plan written, not yet started                   |
| Backlog     | In BACKLOG.md but no spec/plan yet                          |


---

## Epic 0: Design System & UI/UX

| Ticket     | Title                                    | Status  | Branch | Plan | Spec |
| ---------- | ---------------------------------------- | ------- | ------ | ---- | ---- |
| DESIGN-001 | Design System Setup                      | Done | `feature/API-003-rbac-authorization` | [plan](../docs/superpowers/plans/2026-03-13-design-001-design-system-setup.md) | [spec](../docs/superpowers/specs/2026-03-13-design-001-design-system-setup.md) |
| DESIGN-002 | Reusable Components                      | Done | `feature/API-003-rbac-authorization` | — | — |
| DESIGN-003 | Dashboard Screen — Final Design          | Done | `feature/API-003-rbac-authorization` | — | — |
| DESIGN-004 | Topic Discovery Screen — Final Design    | Done | `feature/API-003-rbac-authorization` | — | — |
| DESIGN-005 | Article View Screen — Final Design       | Done | `feature/API-003-rbac-authorization` | — | — |
| DESIGN-006 | Research Sessions Screen — Final Design  | Done | `feature/API-003-rbac-authorization` | — | — |
| DESIGN-007 | Publishing Screen — Final Design         | Done | `feature/API-003-rbac-authorization` | — | — |
| DESIGN-008 | Settings Screen — Final Design           | Done | `feature/API-003-rbac-authorization` | — | — |
| DESIGN-009 | Login & Auth Screens                     | Done | `feature/API-003-rbac-authorization` | — | — |

**Design file:** `pencil_designs/cognify.pen` — all screens redesigned with design system variables, reusable components, and polished layouts.

---

## Epic 7: API & Authentication


| Ticket  | Title                     | Status  | Branch                          | Plan                                                                  | Spec                                                                         |
| ------- | ------------------------- | ------- | ------------------------------- | --------------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| API-001 | FastAPI Application Setup | Done    | `feature/API-001-fastapi-setup` | [plan](../docs/superpowers/plans/2026-03-12-api-001-fastapi-setup.md) | [spec](../docs/superpowers/specs/2026-03-12-api-001-fastapi-setup-design.md) |
| API-002 | JWT Authentication        | Done    | `feature/API-002-jwt-authentication` | [plan](../docs/superpowers/plans/2026-03-13-api-002-jwt-authentication.md) | [spec](../docs/superpowers/specs/2026-03-12-api-002-jwt-authentication-design.md) |
| API-003 | RBAC Authorization        | Done    | `feature/API-003-rbac-authorization` | [plan](../docs/superpowers/plans/2026-03-13-api-003-rbac-authorization.md) | [spec](../docs/superpowers/specs/2026-03-13-api-003-rbac-authorization-design.md) |


## Epic 1: Trend Discovery Engine


| Ticket    | Title                     | Status  | Branch | Plan | Spec |
| --------- | ------------------------- | ------- | ------ | ---- | ---- |
| TREND-001 | Google Trends Integration | Done | `feature/TREND-001-google-trends-integration` | [plan](../docs/superpowers/plans/2026-03-13-trend-001-google-trends-integration.md) | [spec](../docs/superpowers/specs/2026-03-13-trend-001-google-trends-integration-design.md) |
| TREND-002 | Reddit Trend Source       | Done | `feature/TREND-002-reddit-trend-source` | [plan](../docs/superpowers/plans/2026-03-14-trend-002-reddit-trend-source.md) | [spec](../docs/superpowers/specs/2026-03-14-trend-002-reddit-trend-source-design.md) |
| TREND-003 | Hacker News Integration   | Done | `feature/TREND-003-hackernews-integration` | [plan](../docs/superpowers/plans/2026-03-13-trend-003-hackernews-integration.md) | [spec](../docs/superpowers/specs/2026-03-13-trend-003-hackernews-integration-design.md) |
| TREND-004 | NewsAPI Integration       | Done | `feature/TREND-004-newsapi-integration` | [plan](../docs/superpowers/plans/2026-03-15-trend-004-newsapi-integration.md) | [spec](../docs/superpowers/specs/2026-03-15-trend-004-newsapi-integration-design.md) |
| TREND-005 | arXiv Paper Feed          | Done | `feature/TREND-005-arxiv-paper-feed` | [plan](../docs/superpowers/plans/2026-03-15-trend-005-arxiv-paper-feed.md) | [spec](../docs/superpowers/specs/2026-03-15-trend-005-arxiv-paper-feed-design.md) |
| TREND-006 | Topic Ranking & Dedup     | Done | `feature/TREND-006-topic-ranking-dedup` | [plan](../docs/superpowers/plans/2026-03-13-trend-006-topic-ranking-dedup.md) | [spec](../docs/superpowers/specs/2026-03-13-trend-006-topic-ranking-dedup-design.md) |


## Epic 8: Architecture Foundation


| Ticket   | Title                                  | Status  | Branch | Plan | Spec |
| -------- | -------------------------------------- | ------- | ------ | ---- | ---- |
| ARCH-001 | CanonicalArticle Model & Contracts     | Done | `feature/ARCH-001-canonical-article-contracts` | [plan](../docs/superpowers/plans/2026-03-17-arch-001-canonical-article-contracts.md) | [spec](../docs/superpowers/specs/2026-03-17-arch-001-canonical-article-contracts-design.md) |
| ARCH-002 | TrendSource Protocol & Registry        | Done | `feature/ARCH-002-trendsource-protocol-registry` | [plan](../docs/superpowers/plans/2026-03-20-arch-002-trendsource-protocol-registry.md) | [spec](../docs/superpowers/specs/2026-03-20-arch-002-trendsource-protocol-registry-design.md) |


## Epic 2: Multi-Agent Research Pipeline


| Ticket       | Title                          | Status  | Branch | Plan | Spec |
| ------------ | ------------------------------ | ------- | ------ | ---- | ---- |
| RESEARCH-001 | Agent Orchestrator (LangGraph) | Done | `feature/RESEARCH-001-agent-orchestrator` | [plan](../docs/superpowers/plans/2026-03-17-research-001-agent-orchestrator.md) | [spec](../docs/superpowers/specs/2026-03-17-research-001-agent-orchestrator-design.md) |
| RESEARCH-002 | Web Search Agent               | Done | `feature/RESEARCH-002-web-search-agent` | [plan](../docs/superpowers/plans/2026-03-17-research-002-web-search-agent.md) | [spec](../docs/superpowers/specs/2026-03-17-research-002-web-search-agent-design.md) |
| RESEARCH-003 | RAG Pipeline (Milvus)          | Done | `feature/RESEARCH-003-rag-pipeline` | [plan](../docs/superpowers/plans/2026-03-17-research-003-rag-pipeline.md) | [spec](../docs/superpowers/specs/2026-03-17-research-003-rag-pipeline-design.md) |
| RESEARCH-004 | Literature Review Agent        | Done | `feature/RESEARCH-004-literature-review-agent` | [plan](../docs/superpowers/plans/2026-03-21-research-004-literature-review-agent.md) | [spec](../docs/superpowers/specs/2026-03-21-research-004-literature-review-agent-design.md) |
| RESEARCH-005 | Research Session Tracking      | Done | `feature/RESEARCH-005-research-session-tracking` | [plan](../docs/superpowers/plans/2026-03-21-research-005-research-session-tracking.md) | [spec](../docs/superpowers/specs/2026-03-21-research-005-research-session-tracking-design.md) |

**Stubs from RESEARCH-001 to replace:**
- ~~RESEARCH-002: Replace `stub_research_agent` with real web search agent~~ — Done (`WebSearchAgent` in `src/agents/research/web_search.py`)
- ~~RESEARCH-003: RAG pipeline~~ — Done (MilvusService, MilvusRetriever, TokenChunker, index_findings node)
- Future Celery ticket: Replace `AsyncIODispatcher` in `src/services/task_dispatch.py` with `CeleryDispatcher` (deferred from RESEARCH-003).
- Future infra ticket: Replace `MemorySaver` with `PostgresSaver` in orchestrator. Replace in-memory repositories in `src/services/research.py` with real PostgreSQL repos.


## Epic 3: Content Generation Pipeline


| Ticket      | Title                       | Status  | Branch | Plan | Spec |
| ----------- | --------------------------- | ------- | ------ | ---- | ---- |
| CONTENT-001 | Article Outline Generation  | Done | `feature/CONTENT-001-article-outline` | [plan](../docs/superpowers/plans/2026-03-18-content-001-article-outline.md) | [spec](../docs/superpowers/specs/2026-03-18-content-001-article-outline-design.md) |
| CONTENT-002 | Section-by-Section Drafting | Done | `feature/CONTENT-002-section-drafting` | [plan](../docs/superpowers/plans/2026-03-19-content-002-section-drafting.md) | [spec](../docs/superpowers/specs/2026-03-19-content-002-section-drafting-design.md) |
| CONTENT-003 | SEO & AI Discoverability    | Done | `feature/CONTENT-003-seo-ai-discoverability` | [plan](../docs/superpowers/plans/2026-03-19-content-003-seo-ai-discoverability.md) | [spec](../docs/superpowers/specs/2026-03-19-content-003-seo-ai-discoverability-design.md) |
| CONTENT-004 | Citation Management         | Done | `feature/CONTENT-004-citation-management` | [plan](../docs/superpowers/plans/2026-03-19-content-004-citation-management.md) | [spec](../docs/superpowers/specs/2026-03-19-content-004-citation-management-design.md) |
| CONTENT-005 | CanonicalArticle Assembly   | Done | `feature/CONTENT-005-canonical-article-assembly` | [plan](../docs/superpowers/plans/2026-03-20-content-005-canonical-article-assembly.md) | [spec](../docs/superpowers/specs/2026-03-20-content-005-canonical-article-assembly-design.md) |
| CONTENT-006 | Content Humanization        | Done | `feature/CONTENT-006-content-humanization` | [plan](../docs/superpowers/plans/2026-03-20-content-006-content-humanization.md) | [spec](../docs/superpowers/specs/2026-03-20-content-006-content-humanization-design.md) |


## Epic 4: Visual Asset Generation


| Ticket     | Title                      | Status  | Branch | Plan | Spec |
| ---------- | -------------------------- | ------- | ------ | ---- | ---- |
| VISUAL-001 | Data Chart Generation      | Done | `feature/VISUAL-001-data-chart-generation` | [plan](../docs/superpowers/plans/2026-03-21-visual-001-data-chart-generation.md) | [spec](../docs/superpowers/specs/2026-03-21-visual-001-data-chart-generation-design.md) |
| VISUAL-002 | AI Illustration Generation | Done | `feature/VISUAL-002-ai-illustration-generation` | [plan](../docs/superpowers/plans/2026-03-22-visual-002-ai-illustration-generation.md) | [spec](../docs/superpowers/specs/2026-03-22-visual-002-ai-illustration-generation-design.md) |
| VISUAL-003 | Diagram Generation         | Done | `feature/VISUAL-003-diagram-generation` | [plan](../docs/superpowers/plans/2026-03-22-visual-003-diagram-generation.md) | [spec](../docs/superpowers/specs/2026-03-22-visual-003-diagram-generation-design.md) |


## Epic 5: Multi-Platform Publishing


| Ticket      | Title                 | Status  | Branch | Plan | Spec |
| ----------- | --------------------- | ------- | ------ | ---- | ---- |
| PUBLISH-001 | Ghost CMS Integration | Done | `feature/PUBLISH-003-medium-integration` | — | — |
| PUBLISH-002 | WordPress Integration | Backlog | —      | —    | —    |
| PUBLISH-003 | Medium Integration    | Done | `feature/PUBLISH-003-medium-integration` | — | — |
| PUBLISH-004 | LinkedIn Integration  | Done | `feature/PUBLISH-004-linkedin-integration` | — | — |
| PUBLISH-005 | Publication Tracking  | Done | `feature/PUBLISH-005-publication-tracking` | [plan](../docs/superpowers/plans/2026-03-27-publish-005-publication-tracking.md) | [spec](../docs/superpowers/specs/2026-03-27-publish-005-publication-tracking-design.md) |


## Epic 6: Dashboard & Configuration


| Ticket   | Title                    | Status  | Branch | Plan | Spec |
| -------- | ------------------------ | ------- | ------ | ---- | ---- |
| DASH-001 | Dashboard Overview       | Done | `feature/DASH-001-dashboard-overview` | [plan](../docs/superpowers/plans/2026-03-15-dash-001-dashboard-overview.md) | [spec](../docs/superpowers/specs/2026-03-15-dash-001-dashboard-overview-design.md) |
| DASH-002 | Topic Discovery Screen   | Done | `feature/DASH-002-topic-discovery-screen` | [plan](../docs/superpowers/plans/2026-03-20-dash-002-topic-discovery-screen.md) | [spec](../docs/superpowers/specs/2026-03-20-dash-002-topic-discovery-screen-design.md) |
| DASH-003 | Article View & Preview   | Done | `feature/DASH-003-article-view-preview` | [plan](../docs/superpowers/plans/2026-03-21-dash-003-article-view-preview.md) | [spec](../docs/superpowers/specs/2026-03-21-dash-003-article-view-preview-design.md) |
| DASH-004 | Research Sessions Screen | Done | `feature/DASH-004-research-sessions-screen` | [plan](../docs/superpowers/plans/2026-03-21-dash-004-research-sessions-screen.md) | [spec](../docs/superpowers/specs/2026-03-21-dash-004-research-sessions-screen-design.md) |
| DASH-005 | Settings & Configuration | Done | `feature/DASH-005-settings-configuration` | [plan](../docs/superpowers/plans/2026-03-21-dash-005-settings-configuration.md) | [spec](../docs/superpowers/specs/2026-03-20-dash-005-settings-configuration-design.md) |
| DASH-006 | Frontend-Backend API Integration | Done | Superseded by INFRA-002 (PR #34) | — | — |


## Epic 9: Infrastructure & Integration


| Ticket    | Title                              | Status  | Branch | Plan | Spec |
| --------- | ---------------------------------- | ------- | ------ | ---- | ---- |
| INFRA-001a | PostgreSQL Persistence (Foundation) | Done | `feature/INFRA-001-postgresql-persistence` | [plan](../docs/superpowers/plans/2026-03-22-infra-001a-database-foundation.md) | [spec](../docs/superpowers/specs/2026-03-22-infra-001a-database-foundation-design.md) |
| INFRA-001b | Topic Persistence & Cross-Scan Dedup | Done | `feature/INFRA-001b-topic-persistence` | [plan](../docs/superpowers/plans/2026-03-22-infra-001b-topic-persistence.md) | [spec](../docs/superpowers/specs/2026-03-22-infra-001b-topic-persistence-design.md) |
| INFRA-002 | Frontend-Backend API Integration   | Done | `feature/INFRA-002-frontend-api-integration` | [plan](../docs/superpowers/plans/2026-03-22-infra-002-frontend-api-integration.md) | [spec](../docs/superpowers/specs/2026-03-22-infra-002-frontend-api-integration-design.md) |
| INFRA-003 | Wire Real LLM Orchestrator          | Done | `feature/INFRA-003-wire-llm-orchestrator` | — | — |
| INFRA-004 | Settings Backend CRUD               | Done | `feature/INFRA-004-settings-backend-crud` | [plan](../docs/superpowers/plans/2026-03-24-infra-004-settings-backend-crud.md) | — |
| INFRA-005 | Frontend Status Alignment           | Done | `feature/INFRA-005-frontend-status-alignment` | — | — |


## Epic 10: Visual Generation Overhaul

> Imports impactai's per-section image planner, multi-provider stack, MinIO storage, SSRF-guarded import, and adds per-section prose editing — while preserving CanonicalArticle (ADR-003) and Transformer/Adapter (ADR-004) boundaries. See [implementation plan](../docs/superpowers/plans/2026-05-06-visual-generation-improvement-plan.md) and [Pencil design brief](../docs/superpowers/specs/2026-05-06-visual-studio-pencil-design-brief.md).

| Ticket      | Title                                                                                                | Status      | Branch                                              | Plan | Spec |
| ----------- | ---------------------------------------------------------------------------------------------------- | ----------- | --------------------------------------------------- | ---- | ---- |
| VISUAL-004  | Phase 1 — Style catalogue + Provider abstraction + MinIO + SSRF guard                                | Done        | `feature/EPIC-10-visual-generation` (PR #54)        | [plan](../docs/superpowers/plans/2026-05-06-visual-generation-improvement-plan.md) §11.1 | [brief](../docs/superpowers/specs/2026-05-06-visual-studio-pencil-design-brief.md) |
| VISUAL-005  | Phase 2 — Persona-aware planner + pipeline nodes                                                     | Done        | `feature/EPIC-10-visual-generation` (PR #54)        | [plan](../docs/superpowers/plans/2026-05-06-visual-generation-improvement-plan.md) §11.2 | — |
| VISUAL-006  | Phase 3 — Markdown injection + multi-platform publishing                                             | Done        | `feature/EPIC-10-visual-generation` (PR #54)        | [plan](../docs/superpowers/plans/2026-05-06-visual-generation-improvement-plan.md) §11.3 | — |
| VISUAL-007  | Phase 4 — Studio API (plan/render/refine/upload/fetch-url/section-html-refine)                       | Done        | `feature/EPIC-10-visual-generation` (PR #54)        | [plan](../docs/superpowers/plans/2026-05-06-visual-generation-improvement-plan.md) §11.4 | — |
| VISUAL-008  | Phase 5 — Frontend Visual Studio (chip rails, spec cards, HTML refine, gallery)                      | Done        | `feature/EPIC-10-visual-generation` (PR #54)        | [plan](../docs/superpowers/plans/2026-05-06-visual-generation-improvement-plan.md) §11.5 | [brief](../docs/superpowers/specs/2026-05-06-visual-studio-pencil-design-brief.md) — Visual Studio panel + SpecCard / StyleChipRail / UsageBadge / SectionHtmlRefinePanel / SavedAssetGallery / ImageImportModal mounted in article-detail. Backend `GET /visuals/saved` aggregates from `canonical_articles.visuals[]`. `enable_image_planner` default flipped to True. Playwright E2E deferred (no Playwright in repo yet — covered by Vitest component + integration tests). |
| VISUAL-009  | Phase 6 — MinIO production rollout + cost dashboard                                                  | Done        | `feature/EPIC-10-visual-generation` (PR #54)        | [plan](../docs/superpowers/plans/2026-05-06-visual-generation-improvement-plan.md) §11.6 | [runbook](../docs/deployment/visual-storage-rollout.md) |
| VISUAL-010  | Phase 7 — Saved-asset gallery + audience-persona Settings UI                                         | Done        | `feature/EPIC-10-visual-generation` (PR #54)        | [plan](../docs/superpowers/plans/2026-05-06-visual-generation-improvement-plan.md) §11.7 | — Persona persistence (`general_configs.default_audience_persona`), `image_asset_tags` table + Alembic migration, tag endpoints, Settings UI persona selector, top-level `/saved-visuals` page. Persona threads from settings → article-detail Visual Studio. |
| VISUAL-011  | Phase 8 — Per-section content editing (text + AI rewrite + history)                                  | Done        | `feature/EPIC-10-visual-generation` (PR #54)        | [plan](../docs/superpowers/plans/2026-05-06-visual-generation-improvement-plan.md) §11.8 | [brief Screen 9](../docs/superpowers/specs/2026-05-06-visual-studio-pencil-design-brief.md) — `section_rewriter.py` (Claude prose rewrite + persona register + banned-pattern block), append-only `section_versions` table + repo, `/content/section-rewrite|section-update|paragraph-tone|history|restore` endpoints with anchor validator (422 on dropped `data-spec-id` / renamed `before_heading` titles), word-level diff helper reused across image/HTML/prose refine, `SectionContextToolbar` + `InlineProseEditor` + `AIRewritePopover` + `SectionHistoryDrawer` mounted on article-detail. Playwright deferred — covered by Vitest + Testing Library. |


## Epic 11: Supervised Authoring

> Planned 2026-08-19 from the August Cognify-vs-ImpactAI review. Program plan: [`2026-08-19-epic-11-supervised-authoring-plan.md`](../docs/superpowers/plans/2026-08-19-epic-11-supervised-authoring-plan.md); rationale: [`COGNIFY_VS_IMPACTAI_REVIEW_2026-08.md`](../docs/architecture/COGNIFY_VS_IMPACTAI_REVIEW_2026-08.md). Each ticket gets its own TDD plan when started. Sign-off checklist (plan §12) must be completed before Phase A code.

| Ticket | Title | Status | Branch | Plan | Spec |
| ------ | ----- | ------ | ------ | ---- | ---- |
| ADR-006/007 | ADRs: supervised pipeline; Brief contract | Done | `feature/AUTHOR-001-pipeline-events` | [program plan](../docs/superpowers/plans/2026-08-19-epic-11-supervised-authoring-plan.md) | [review](../docs/architecture/COGNIFY_VS_IMPACTAI_REVIEW_2026-08.md) |
| AUTHOR-001 | Live session progress (SSE) + session route + auto-navigate | Done (merged to develop `06439e9`, 2026-08-19) | `feature/AUTHOR-001-pipeline-events` | [plan](../docs/superpowers/plans/2026-08-19-author-001-session-events-sse.md) | review §6 #1 |
| AUTHOR-002 | Outline approval gate + cancel | Done (PR #73 → develop `30f1a36`, 2026-08-19) | `feature/AUTHOR-002-outline-gate` | [plan](../docs/superpowers/plans/2026-08-19-author-002-outline-gate.md) | review §6 #2 |
| AUTHOR-003 | Brief model + Generate modal rework | Done (PR #74 → develop `740af60`, 2026-08-21; migration `b3c7e1f9a2d4`; live smoke passed) | `feature/AUTHOR-003-brief` | [plan](../docs/superpowers/plans/2026-08-20-author-003-brief.md) | ADR-007; review §6 #3 |
| AUTHOR-004 | Per-section regenerate (+ L-013 section-id contract fix) | Done (PR #76 → develop `7ef590c`, 2026-08-21; **grew 3 → 5 SP**: every existing edit/rewrite/history flow addressed the wrong section, fixed at the root as Task 1) | `feature/AUTHOR-004-section-regenerate` | [plan](../docs/superpowers/plans/2026-08-21-author-004-section-regenerate.md) | program plan §5.5; review §6 #4 |
| AUTHOR-005 | Usage/cost badge | Done (PR #77 → develop `4a92b97`, 2026-08-24) | `feature/AUTHOR-005-usage` | [plan](../docs/superpowers/plans/2026-08-24-author-005-usage.md) | program plan §5.6; review §6 #5 |
| INFRA-007 | CeleryDispatcher + worker | Done (PR #78 → develop `c724f35`, 2026-08-24) | `feature/INFRA-007-celery` | [plan](../docs/superpowers/plans/2026-08-24-infra-007-celery-worker.md) | program plan §9 Phase A; review §5 |
| AUTHOR-006 | Article metadata editor + autosave | In Progress (2026-08-24) | `feature/AUTHOR-006-metadata` | [plan](../docs/superpowers/plans/2026-08-24-author-006-metadata-editor.md) | program plan §5.7, §6; review §6 #6/#7 |
| AUTHOR-007 | Article status + filters + Resume | Planned | — | program plan §4.4 | review §6 #10 |
| AUTHOR-008 | Length + content type budgets | Planned | — | program plan §9 Phase B | review §6 #8 |
| AUTHOR-009 | Humanize per-pass streaming | Planned | — | program plan §9 Phase B | review §6 #9 |
| AUTHOR-010 | Model tiering per step | Planned | — | program plan §5.8 | review §6 #14 |
| INFRA-008 | Warm-up, role re-check, toaster, file splits | Planned | — | program plan §5.9–5.10 | review §6 #15/#16 |
| AUTHOR-011 | Persona voice engine v1 | Planned | — | program plan §5.11 | review §6 #12 |
| AUTHOR-012 | Prompt registry + overrides | Planned | — | program plan §5.11 | review §6 #13 |
| AUTHOR-013 | LinkedIn repurpose | Planned | — | program plan §5.11 | review §6 #20 |
| AUTHOR-014 | Playwright create-article flow | Planned | — | program plan §7 | — |

> **RESUME HERE (2026-08-24):** steps 1–3 of the 2026-08-21 EOD checklist are DONE; AUTHOR-005 is the active ticket.
> 1. ✅ **Stack rebuilt on `536438e`** (`docker compose up --build -d`, 2026-08-24 ~12:17 IST). All three image IDs advanced (api `506da798`, worker `3b144fbf`, frontend `940b70b7`); frontend image verified to contain the AUTHOR-004 code (`section-regenerate` present in built chunk) — no `--no-cache` needed this time. DB stays at `c4d8e2f1a9b7` (no migration in #76). API healthy.
> 2. ✅ **Live smoke of AUTHOR-004 + L-013 PASSED** (driven via Playwright MCP on the OAuth article `fa6e798a`): hover section 2 → Edit text shows section 2's markdown (the L-013 fix); Regenerate with instruction → "364 words · claude-sonnet-4-6" + word-level diff → Accept → section re-rendered, neighbours untouched, 3 figures intact, persisted across reload; History drawer shows "Regenerated" ×2 (candidate 12:30:40 + applied 12:31:27, instruction on both); second Regenerate → Reject → section byte-identical, nothing persisted; `llm_calls` has exactly 2 `section_regenerate` rows (one per regenerate run), keyed by real session ids. Testing gotcha for AUTHOR-014: there is one `role="toolbar"` **per section** in the DOM — always scope queries to the hovered section's wrapper, or you hit section 1's toolbar (looked exactly like the pre-fix bug).
> 3. ✅ **L-013 post-deploy audit run (2026-08-24)**: query 1 (pre-fix non-manual section_versions) → **0 rows**; query 3 (Studio visual `section_index` drift) → **0 rows**; query 2 (duplicated-H2 bodies) → **1 hit**: article `8f7bbdd1` ("Agentic AI and Orchestration") — a pre-fix manual save on `section_id …:1` (2026-08-21 10:21 UTC) had overwritten md-slot 1 ("From Chatbots to Agents", outline 0) with the ReAct section's markdown, duplicating ReAct and destroying section 0. **Repaired in place**: restored the original section 0 from `article_drafts.section_drafts[0].body_markdown` via SQL UPDATE; body now matches the outline (7 sections + References), audit query 2 returns 0 rows, verified in the UI.
> 4. ✅ **AUTHOR-005 (usage/cost badge) COMPLETE** on `feature/AUTHOR-005-usage` (same day): `GET /research/sessions/{id}/usage` + `GET /articles/{id}/usage` (viewer+, 60/min; article route resolves via `find_by_article_id → draft.session_id`, L-013), pure `compute_session_usage` in `src/services/usage.py` (token cost from `COGNIFY_LLM_PRICING_JSON` over `DEFAULT_LLM_PRICING`, model-prefix keyed; image cost/count from recorded `metadata.cost_usd` via `aggregate_cost` — deliberate deviation from program plan §4.5, no settings-priced images), `UsageBadge` extended (`label`/`tokens`/`images`, backward compatible) and mounted in the session-progress header (10s poll while active + one refetch on terminal) and article-sidebar Usage card. Tests 1653 backend / 542 frontend, 0 failures. **Live smoke passed**: `/articles/fa6e798a…/usage` returned `cost_usd=0.452689` exactly matching the hand-computed SQL (46,338 in / 18,245 out @ $3/$15 per Mtok + $0.04 image); both badges rendered live with the per-op breakdown incl. `section_regenerate ×2`. Code-reviewed (no Critical/Important code issues; minors fixed in `1eecd5d`). **Follow-up to file**: article usage reads `draft.visuals` only — Studio-inserted renders live on `canonical_articles.visuals` and are not counted, so the sidebar badge and the Visual Studio panel badge (client-computed, also labeled "this article" per Pencil) can disagree; consider a visuals union (dedupe by asset id) + Studio badge label review. Azure Boards has no Epic 11 work items — nothing to close. Next ticket: **INFRA-007** (CeleryDispatcher + worker wiring, program plan §9 Phase A). *(AUTHOR-005 merged same day: PR #77 → develop `4a92b97`.)*
> 5. ✅ **INFRA-007 (Celery pipeline dispatch + worker) COMPLETE** on `feature/INFRA-007-celery` (same day, PR pending review): `COGNIFY_TASK_DISPATCH` (`inprocess` default = byte-identical, `celery` = worker; Literal so a typo fails at boot); `PipelineDispatcher` seam (`src/services/pipeline_dispatch.py`, lazily built + mode-selected in `src/api/routers/research_pipeline.py`); runners moved to `src/services/pipeline_runner.py`; service factory `src/services/bootstrap.py` + `bootstrap_builders.py` (extracted from `_lifespan`; incl. API-key resolution + LlmConfig overlay — **note: `_lifespan` still builds inline, convergence is a follow-up**); Celery tasks build services inside the task's own event loop (asyncpg pools bind to the running loop — found live, fixed) with fresh contextvars per task; **cooperative cancellation**: `ContentGraphDeps.cancel_check` before every content node + `_drive_to_completion` entry guard + **"cancelled" is terminal by intent** (`update_session_status`/`_persist_success`/`_persist_failure`/worker `_mark_failed` never overwrite it — celery-mode cancel sticks even during research); `acks_late` OFF (Redis visibility-timeout redelivery would duplicate non-idempotent runs); worker image gets the HF pre-bake + celery CMD; compose: shared `generated_assets` volume + redis env; `/health` checks redis+celery in celery mode only. Tests 1683 backend / 542 frontend, 0 failures; AUTHOR-002 outline/cancel tests pass UNMODIFIED. **Live smoke (celery mode) passed**: full article generated on the worker (~3.5 min, API quiet, visuals served via shared volume, `llm_calls` attributed); cancel during drafting → worker stops (`pipeline_cancelled_mid_run`), status stays `cancelled`; health `redis: ok, celery: ok`; flipped back to inprocess → identical to before. Code-reviewed (no Critical; Importants fixed in `134777c`). **Known limitations (documented, PR body)**: worker image has no Node/Chromium (worker-side mermaid→PNG falls back to client render; Ghost PNG publishing runs on the API); `CeleryDispatcher` has no `is_running` (duplicate-approve closed by the sync status write); `outline/regenerate` still runs its LLM call on the request path.
>
> Follow-up tickets still to open (not started): lifespan↔bootstrap convergence (one construction path — INFRA-008 candidate); worker mermaid→PNG (Node/Chromium layer or MinIO-only mode); job status store behind `GET /jobs/{id}` (review §6 #18, pair with Celery); `Provenance.research_session_id` is the topic id at the source (`graph_state.py` → `seo_node.py`; AUTHOR-001's `articles.find_by_session` relies on it — fix both together); humanize pass on regenerated prose (AUTHOR-009); `content.py` / `section_rewriter.py` / `main.py` / `services/content/__init__.py` / `db/repositories.py` >200 lines (INFRA-008); `RegeneratePopover` has no Escape/focus-trap; `hasPreamble()` vs backend `split_sections` on `###`-first bodies; Studio section list includes the References tail; `word_count` measured on raw LLM text; `/health` reports redis/milvus/celery `unavailable` while the app works; 13 pre-existing `tsc` errors in untouched settings/test files; AUTHOR-003 leftovers (PATCH /briefs can't clear nullable fields, `audience_persona` missing from `ResearchSessionResponse`).
>
> **Resume note (2026-08-21, evening — AUTHOR-004 finish, superseded by the block above):** AUTHOR-004 complete on `feature/AUTHOR-004-section-regenerate` — `POST /content/section-regenerate` (editor+, 10/min; one tracked LLM call bound to `draft.session_id` with `step_name=section_regenerate`; candidate `section_versions` row `source=regenerate`; accept via section-update), `draft_one_section` extracted graph-free, Regenerate toolbar action + `RegeneratePopover` (diff accept/reject), `page.tsx`/`article-content.tsx` split under 200 lines. **L-013** fixed at the root: the public `section_id` is now `{article_id}:{outline_index}` everywhere (`md_index_for()` is the only conversion) — before this, every Edit text / AI rewrite / history / restore flow addressed the section *before* the one clicked. Tests: 1632 backend / 532 frontend, 0 failures. Live smoke of regenerate not yet run (do it after merge + image rebuild: hover section 2 → Edit text shows section 2; Regenerate → diff → Accept; History shows 'Regenerated' ×2; `/pipeline-debug` shows one `section_regenerate` call). **Post-deploy audit (L-013):** run the three SQL queries in `docs/LEARNINGS.md` L-013 once and record. **Follow-up tickets to open:** (1) `Provenance.research_session_id` is the topic id at the source (`graph_state.py` → `seo_node.py`); AUTHOR-001's `articles.find_by_session` relies on it, so fix both together; (2) humanize pass on regenerated prose (AUTHOR-009); (3) `content.py` / `section_rewriter.py` / `main.py` / `services/content/__init__.py` / `db/repositories.py` still >200 lines (INFRA-008); (4) review minors left open: `RegeneratePopover` dialog has no Escape/focus-trap, `hasPreamble()` vs backend `split_sections` disagree on `###`-first bodies, Studio section list includes the References tail, `word_count` is measured on raw LLM text. Next ticket: **AUTHOR-005** (usage/cost badge, program plan §5.6 — `llm_calls` rows for regenerate are already keyed by the real session id).
>
> **Resume note (2026-08-21, later):** AUTHOR-003 merged (PR #74, `740af60`). Stack rebuilt on `develop`, DB at `b3c7e1f9a2d4`, Anthropic key working. **Live smoke of AUTHOR-002 + AUTHOR-003 PASSED** (Generate modal → save-as-brief → `awaiting_outline_review` → edit heading → Approve & write → `article_complete`; brief reused from the picker on a second topic; `Provenance.brief_id` set; edited heading in the article) — but only after finding and fixing a real bug: `research_sessions.status` was `VARCHAR(20)` and `awaiting_outline_review` is 23 chars, so the gate failed live with `StringDataRightTruncationError`. Fix + migration `c4d8e2f1a9b7` + regression test in **PR #75** (`fix/AUTHOR-002-status-column-width`, worktree `.claude/worktrees/fix-status-width`). The running api container has the migration + `tables.py` hot-copied in; **after merging #75 rebuild the api image** (`docker compose up --build -d api`). Observed follow-ups: `Provenance.research_session_id` holds the content graph's `state["session_id"]`, not the `research_sessions` row id (pre-existing, shared across articles) — should point at the real session; `/health` reports redis/milvus/celery `unavailable` while the app works (check probes). Chrome-extension clicks did not register on `/topics` (programmatic clicks did) — not a product bug as far as seen, but AUTHOR-014 Playwright should confirm real clicks. Next ticket: **AUTHOR-004**.
>
> **Resume note (2026-08-21):** AUTHOR-003 (Brief) is complete on `feature/AUTHOR-003-brief` — `briefs` table + `/briefs` CRUD/duplicate, `brief_id`/`save_as_brief` on session create (inline > brief > default, L-012), `Provenance.brief_id`, `suggested_brief` from `/topics/analyze`, Generate modal with brief picker / content type / length / save-as-brief. **Deploy step:** the Docker stack was down during finish — run `uv run alembic upgrade head` (→ `b3c7e1f9a2d4`) and the Task 3 integration test (`tests/integration/db/test_pg_briefs.py`) once it is up. Review follow-ups deliberately left out of scope (file as tickets): PATCH /briefs cannot clear a nullable field (`exclude_none`), `audience_persona` missing from `ResearchSessionResponse`, `content_type`/`length_target` not yet consumed by the pipeline (AUTHOR-008), brief created before `start_session` (non-transactional), `src/models/brief.py` imports persona keys from `src/services/visuals`, `research.py` router over the 200-line budget, 13 pre-existing `tsc` errors in untouched settings/test files. Next ticket: **AUTHOR-004** (per-section regenerate, program plan §5.5).
>
> **Previous resume note (2026-08-19 EOD):** AUTHOR-001 (`06439e9`) and AUTHOR-002 (PR #73, `30f1a36`) are merged to `develop`. Local Docker stack runs the AUTHOR-002 images and the DB is migrated to `a9d4e2f7c1b8`. **Open item:** the stack's Anthropic key returns 401 "API key is invalid" — refresh it (Settings → API Keys, or `COGNIFY_ANTHROPIC_API_KEY` + restart api) before running any generation; then do the deferred live smoke of the outline gate (create session with "Review outline before drafting" → `/research/{id}` shows the review step → edit → Approve & write → article; Cancel on an active session). Next ticket: **AUTHOR-003** (Brief) — write its task plan from the program plan §4.1/§5.4 + ADR-007, worktree `feature/AUTHOR-003-brief` off `develop`.

## Cross-Cutting Work (non-ticket)

| Item | Status | Date | Description |
| ---- | ------ | ---- | ----------- |
| Structured Logging Improvements | Done | 2026-03-25 | Sensitive field redaction, repository/Milvus/middleware logging, pool_pre_ping. PR #40 |
| CI/CD & Dockerization | Done | 2026-03-25 | Dockerfiles (api, worker, frontend), docker-compose (full stack + test), GitHub Actions (ci.yml, cd.yml), Makefile |
| Frontend Test Fixes | Done | 2026-03-25 | Fixed 22 stale frontend tests (status labels, filter values, API mocking, default filters) |
| TypeScript Build Fixes | Done | 2026-03-26 | Article status type, keywordMap index signature, login page Suspense boundary |
| Secure API Key Encryption | Done | 2026-03-26 | Fernet encryption at rest, runtime key resolution (DB overrides .env), delete UI, expanded services. PR #42 |
| Publishing Service + Ghost & Medium | Done | 2026-03-26 | PublishingService orchestrator, Ghost Transformer/Adapter (JWT auth), Medium Transformer/Adapter (mock-only), publish API endpoint. PR #43 |
| Security Hardening | Done | 2026-03-27 | Env var substitution in docker-compose, debug defaults to false, encryption key enforced in production, CORS restricted, Fernet key validation. PR #44 |
| Ghost Publishing Fixes | Done | 2026-03-27 | Wire frontend publish to backend API, Lexical format for Ghost 5, static asset serving, citation linkification, key resolver crash fix. Commits `25e8b1c`, `be68912` |
| References Rendering & Timeouts | Done | 2026-03-27 | Strip raw References from markdown (Ghost + frontend), clean HTML reference list, increase trend API timeouts to 120s. Commit `be68912` |
| Custom Topic Entry | Done | 2026-03-31 | Manual topic creation with LLM auto-fill, per-article params (audience, tone, angle) threaded through content pipeline, CreateTopicModal + useTopicAnalysis hook, GenerateArticleModal per-article customization. PR #49. [plan](../docs/superpowers/plans/2026-03-30-custom-topic-entry.md), [spec](../docs/superpowers/specs/2026-03-30-custom-topic-entry-design.md) |
| Pipeline Debug UI (AB#16789) | Done | 2026-04-09 | Full pipeline observability: `llm_calls` table + TrackedChatModel wrapper (captures all 13 LLM call sites via contextvars), debug API endpoints, /pipeline-debug page with step timeline + expandable LLM prompt/response viewer. Merged via PR #50, commit `7d8207e`. |
| Dashboard & Research Fixes (AB#16748, AB#16749, AB#16751) | Done | 2026-04-06 | Trend registry rebuilt after key resolution (fixes NewsAPI 401), dashboard metrics return real published/research counts, Knowledge Base panel fetches aggregated stats from new `/metrics/knowledge-base` endpoint. Reddit/NewsAPI registration guarded on missing credentials. Merged via PR #50, commits `3112cc9`, `606a533`. |
| Generate Article Modal Rework | Done | 2026-04-09 | Description/Keywords fields editable with regenerate buttons, audience/tone/angle/keywords now actually propagate through planner, outliner, section drafter, and SEO optimizer (previously accepted but ignored). New `research_sessions.keywords` and `topic_description_override` columns. PR #50, commit `cd89ff4`. |
| Hero Image Canonical Sizing | Done | 2026-04-10 | Every generated hero image is center-cropped and resized to exactly 1600x900 via Pillow (LANCZOS) for consistent Ghost list-card and detail-page rendering. New HERO_CANONICAL_* constants + `_normalize_hero_image()` helper. PR #51, commit `d4d526b`. |
| Mermaid Diagram In-Article Rendering (AB#16957) | Done | 2026-04-13 | Preserve raw `mermaid_syntax` end-to-end (DiagramSpec → ImageAsset metadata → API response → frontend), expand DiagramType enum (class/state/ER/pie/journey), lift 0-2 cap to 0-5 contextual, add `mermaid.js` client renderer + inline placement in `ArticleContent`. Ghost PNG path preserved. Merged via PR #52, commit `c5cac0b` (merge `e5ddcd7`). Follow-up to VISUAL-003 (AB#16720). |
| INFRA-006 — SSRF guard reuse for trend sources | Done | 2026-05-07 | Extracted scheme + host-CIDR validation from `services/visuals/safe_http.py` into reusable `src/utils/safe_url.py`. arXiv / HN / NewsAPI clients now reject misconfigured `COGNIFY_*_BASE_URL` (ftp://, embedded credentials) at construction time. 21 new tests; existing 31 safe_http tests still green. Merged via PR #55, commit `42cd3e5`. |
| CONTENT-007 — Structure-aware humanization | Done | 2026-05-07 | Ported impactai's `markdown_structure` to `src/utils/markdown_structure.py` with typed `MarkdownBlock` dataclass (content / list / blockquote / heading / image / code_block / hr / table). `humanizer.rewrite_section` now sends only prose blocks to the LLM via a `<<<BLOCK>>>` sentinel and slots responses back into original block shapes — headings, code, images, tables, HRs survive verbatim. Falls back to original on sentinel-count mismatch. 19 new tests; existing humanizer tests untouched. Merged via PR #55, commit `42cd3e5`. |
| DASH-007 — Humanization diff panel | Done | 2026-05-07 | New `src/services/content/humanize_preview.py` runs fix → score → optional rewrite, returns word-level diff + before/after slop scores. New `POST /api/v1/content/humanize-preview` endpoint (editor-or-admin RBAC, 20/min rate limit). Frontend `HumanizationDiffPanel.tsx` mounts next to the AI rewrite popover; reuses the `WordDiffView` from VISUAL-011 (single-source-of-truth diff renderer across image/HTML/prose refine + humanization). 8 new tests. Merged via PR #55, commit `42cd3e5`. |
| Playwright E2E scaffolding | Done (MVP) | 2026-05-07 | `@playwright/test` devDep, `frontend/playwright.config.ts` (chromium, webServer = `npm run dev`), one passing smoke test, opt-in CI lane in `.github/workflows/e2e.yml` (workflow_dispatch + `e2e` PR label + main push). `frontend/tests/e2e/README.md` documents the deferred VISUAL-008 (plan→render→refine) and VISUAL-011 (per-section AI rewrite + history restore) flows that should land on top of this scaffold. Merged via PR #55, commit `42cd3e5`. |
| `.env` flake fix in test_key_resolver | Done | 2026-05-07 | `uv run` auto-loads the worktree's `.env` into `os.environ`, leaking real `COGNIFY_NEWSAPI_API_KEY` through pydantic-settings (`_env_file=None` alone wasn't enough). Test fixture now monkeypatch.delenv's every `COGNIFY_*` key the test doesn't set explicitly. Backend unit suite goes 1400/0 (was 1346/1). Merged via PR #55, commit `42cd3e5`. |
| Visual Studio hero hoisting (PR #64) | Done | 2026-05-25 | Fixed `pick_cover_visual` to recognize `role_style="hero"` (Visual Studio renders) and refactored cover-skip from spec_id string comparison to object identity. Plus ruff format on `test_multi_anchor_visuals` to unblock CI. Merged via PR #64, commits `c4149e3` + `9562e6f`. |
| Visuals — gpt-image-1 + planner owns visuals (PR #65) | Done | 2026-05-25 | DALL-E provider migrated to `gpt-image-1` (dall-e-3 no longer accessible on newer OpenAI accounts; `response_format` 400'd unconditionally). chart_node merge bug (`{"visuals": new}` → `existing + new`) fixed. When `enable_image_planner=True`, legacy chart/diagram/illustration nodes bypassed entirely so the new pipeline alone owns article imagery. 1413→1419 unit tests. Merged via PR #65, commits `bf70a7f` + `cd38a4b`. |
| Visuals — cap at 3 per article + interleave fix (PR #66) | Done | 2026-05-26 | Dashboard preview was stacking every planner-rendered visual at the top (25 on a 7-section article). Three layered root causes: (1) no per-article cap — `image_planner_max_images_per_section` 4→1 + new `image_planner_max_total_images=3` enforced post-planning via `_truncate_to_total` (drops per-section heroes, prefers concept/diagram/process roles); (2) frontend `article-content.tsx` bucketed by legacy `metadata.source_section` while planner stamps `metadata.section_index`; (3) the real blocker — `useArticle` `toDetail` mapper rebuilt visual metadata with only the 3 legacy diagram fields, silently dropping `section_index`/`placement_anchor`/`role_style` before they reached the component (found via React-fiber inspection). Verified live through the UI: fresh agentic-AI topic → planner `planned=9 kept=3` → 1 hero on top + 2 illustrations interleaved in §1/§2, zero bar charts. Merged via PR #66 (commits `6e59711`, `354a248`, `c7776ff`). **Deploy gotcha:** `docker compose build frontend` reused a cached Next `.next` compilation (identical chunk hash, stale code) — needed `--no-cache` to ship frontend changes. |
| Visuals — diagram labels + render timeout (PR #67) | Done | 2026-05-26 | Section diagrams rendered as unlabeled boxes. Made the prompt rendering clause role-aware: structural roles (concept/process_step/comparison_split/stat_card/screenshot_mock) get `LABELED_DIAGRAM_CLAUSE` (require legible labels, override style "no text"); illustrative roles keep `NO_TEXT_CLAUSE`. Fixed `technical_diagram`/`blueprint` styles to request labels. Raised `illustration_timeout`/`image_provider_timeout` 30→120s (gpt-image-1 with labels exceeds 30s). Merged via PR #67. |
| Visuals — reader-facing captions (PR #69) | Done | 2026-05-26 | Figcaptions showed planner `rationale` ("…gives technical readers…", "Fallback hero cover."). Added `ImageSpec.caption` (short title); planner emits it as a plain title (no reader/prose meta); `image_render_node` uses `spec.caption` not `rationale`; hero/background get no caption; `LABELED_DIAGRAM_CLAUSE` no longer bakes a title into the image. **NOTE:** originally PR #68 stacked on #67 — merged into #67's branch instead of develop, so re-targeted as PR #69 → develop. **Lesson: don't stack PRs in this repo — a stacked PR merges into its base branch, not develop. One PR at a time off develop.** |
| Embedding model baked into api image (fix in-process generation freeze) | Done | 2026-06-03 | **Incident:** an article generation froze the whole API for ~1h19m — every page (dashboard, articles) went empty because all requests hung. Root cause: generation runs **in-process** (Celery worker still a placeholder → AsyncIODispatcher), and the RAG step's `EmbeddingService` (`src/services/embeddings.py`, synchronous `SentenceTransformer(...)`) tried to download `all-MiniLM-L6-v2` from HF Hub on a fresh image with an empty, unmounted cache. Unauthenticated → rate-limited → the download stalled mid-way (340 KB of ~90 MB) and blocked the single asyncio event loop indefinitely. **Fix:** `Dockerfile.api` now pre-bakes the model into the image at build time (`HF_HOME=/opt/hf-cache`, downloaded right after the venv copy so the ~90 MB layer caches independently of source changes) and sets `HF_HUB_OFFLINE=1` + `TRANSFORMERS_OFFLINE=1` so runtime loads purely from the baked cache — zero network, no etag ping, no download. **Verified** with `docker run --network none`: model loads in 0.5s (`load_duration_ms=485`), embeds dim=384, exit 0. Recovery for the live incident: restarted the frozen api (data was intact — 8 articles/9 topics), marked the orphaned `planning` session `failed`. Branch `fix/hf-embedding-cache`. **Known deeper issue (separate ticket):** generation still runs on the API event loop, so embedding `.encode()` briefly blocks all requests during generation — real fix is offloading to a threadpool / wiring Celery. |
| Mermaid render — server-side PNG + log fix (VISUAL-012 follow-ups) | Done | 2026-06-03 | Closed both VISUAL-012 follow-ups. **(1) mermaid-cli in api image:** `Dockerfile.api` now installs Node 20 (NodeSource) + Debian `chromium` + `npm ci` so `/app/node_modules/.bin/mmdc` resolves at runtime (was absent → server-side Mermaid→PNG silently failed, dashboard client-rendered only). `render_mermaid` passes `-p puppeteer-config.json` (`{"args":["--no-sandbox","--disable-setuid-sandbox"]}`) since Chromium can't sandbox as the non-root `cognify` user in-container; `PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium` + `PUPPETEER_SKIP_DOWNLOAD=true`. Verified in a throwaway image mirroring the runtime layer: as `cognify`, Node 20.20.2 + Chromium 148 rendered a valid 4.8KB PNG (exit 0). **(2) misleading log:** `_render_mermaid_asset` logged `rendered=bool(url)` — always true because `url` falls back to the object key before any render attempt. Now tracks a `png_rendered` flag (true only after mmdc succeeds, PNG exists, and storage.put returns) and logs `rendered=png_rendered, fallback=not png_rendered`. 2 new tests (`tests/unit/agents/content/test_image_render_node.py`). **Test-hang note:** the suite hangs locally when `COGNIFY_ANTHROPIC_API_KEY` is set in `.env` — `create_app()` runs at import and eagerly builds a Milvus-connecting orchestrator that blocks on `pymilvus._wait_for_channel_ready` when Milvus/Docker is down. CI has no key (NoOp orchestrator) so it passes. Run unit tests with the key blanked. Branch `fix/mermaid-render-log`. |
| Visuals — Mermaid diagram toggle (VISUAL-012, PR #70) | Done | 2026-05-26 | Per-article "Diagram style" select (AI illustration \| Mermaid) in Generate modal. `structural_diagram_mode` threaded request→session→DB (col + migration `e7c1a9d3f8b2`)→pipeline→planner. Planner attaches `mermaid_syntax` to structural specs (concept/process_step/comparison_split) when mode=mermaid; render node renders mermaid→PNG (falls back to syntax-only client render); hero/editorial stay diffusion. Frontend diagram bucketing keys on `section_index ?? source_section`. Verified live: OAuth article → crisp Mermaid sequence + role diagrams in sections, hero diffusion. Plan: `docs/superpowers/plans/2026-05-26-visual-012-mermaid-diagram-toggle.md`. **Follow-ups: both DONE 2026-06-03 (see "Mermaid render — server-side PNG + log fix" row below).** |

---

## How to Update This File

When starting a ticket:

1. Change status to **In Progress**, fill in the branch name
2. Link the plan/spec files once created

When completing a ticket:

1. Change status to **Done**
2. Ensure plan/spec links are present
3. Update the corresponding entry in `BACKLOG.md` with `— DONE` suffix and status/plan/spec fields

