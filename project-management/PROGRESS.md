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
| VISUAL-004  | Phase 1 — Style catalogue + Provider abstraction + MinIO + SSRF guard                                | Done        | `claude/vibrant-chatterjee-1115a8` (worktree)       | [plan](../docs/superpowers/plans/2026-05-06-visual-generation-improvement-plan.md) §11.1 | [brief](../docs/superpowers/specs/2026-05-06-visual-studio-pencil-design-brief.md) |
| VISUAL-005  | Phase 2 — Persona-aware planner + pipeline nodes                                                     | Done        | `claude/vibrant-chatterjee-1115a8` (worktree)       | [plan](../docs/superpowers/plans/2026-05-06-visual-generation-improvement-plan.md) §11.2 | — |
| VISUAL-006  | Phase 3 — Markdown injection + multi-platform publishing                                             | Done        | `claude/vibrant-chatterjee-1115a8` (worktree)       | [plan](../docs/superpowers/plans/2026-05-06-visual-generation-improvement-plan.md) §11.3 | — |
| VISUAL-007  | Phase 4 — Studio API (plan/render/refine/upload/fetch-url/section-html-refine)                       | Done        | `claude/vibrant-chatterjee-1115a8` (worktree)       | [plan](../docs/superpowers/plans/2026-05-06-visual-generation-improvement-plan.md) §11.4 | — |
| VISUAL-008  | Phase 5 — Frontend Visual Studio (chip rails, spec cards, HTML refine, gallery)                      | Done        | `claude/vibrant-chatterjee-1115a8` (worktree)       | [plan](../docs/superpowers/plans/2026-05-06-visual-generation-improvement-plan.md) §11.5 | [brief](../docs/superpowers/specs/2026-05-06-visual-studio-pencil-design-brief.md) — Visual Studio panel + SpecCard / StyleChipRail / UsageBadge / SectionHtmlRefinePanel / SavedAssetGallery / ImageImportModal mounted in article-detail. Backend `GET /visuals/saved` aggregates from `canonical_articles.visuals[]`. `enable_image_planner` default flipped to True. Playwright E2E deferred (no Playwright in repo yet — covered by Vitest component + integration tests). |
| VISUAL-009  | Phase 6 — MinIO production rollout + cost dashboard                                                  | Done        | `claude/vibrant-chatterjee-1115a8` (worktree)       | [plan](../docs/superpowers/plans/2026-05-06-visual-generation-improvement-plan.md) §11.6 | [runbook](../docs/deployment/visual-storage-rollout.md) |
| VISUAL-010  | Phase 7 — Saved-asset gallery + audience-persona Settings UI                                         | Planned     | —                                                   | [plan](../docs/superpowers/plans/2026-05-06-visual-generation-improvement-plan.md) §11.7 | — |
| VISUAL-011  | Phase 8 — Per-section content editing (text + AI rewrite + history)                                  | Planned     | —                                                   | [plan](../docs/superpowers/plans/2026-05-06-visual-generation-improvement-plan.md) §11.8 | [brief Screen 9](../docs/superpowers/specs/2026-05-06-visual-studio-pencil-design-brief.md) |


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

---

## How to Update This File

When starting a ticket:

1. Change status to **In Progress**, fill in the branch name
2. Link the plan/spec files once created

When completing a ticket:

1. Change status to **Done**
2. Ensure plan/spec links are present
3. Update the corresponding entry in `BACKLOG.md` with `— DONE` suffix and status/plan/spec fields

