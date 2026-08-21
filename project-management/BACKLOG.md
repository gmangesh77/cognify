# Product Backlog: Cognify

## Backlog Prioritization
Ordered by business value and dependency. MoSCoW priority: **Must**, **Should**, **Could**, **Won't** (this release).

> **Note**: Completed tickets are shown in compact tables. Full acceptance criteria for done items live in their linked spec/plan files. See `PROGRESS.md` for branch names and PR numbers.

---

## Completed Epics

### Epic 0: Design System & UI/UX — DONE
**Goal**: Establish a consistent design system and finalize all screen designs in Pencil before frontend implementation.

**Design file**: `pencil_designs/cognify.pen` (Pencil Desktop)

| Ticket | Title | Priority | SP | Plan | Spec |
|--------|-------|----------|---:|------|------|
| DESIGN-001 | Design System Setup | Must | 3 | [plan](../docs/superpowers/plans/2026-03-13-design-001-design-system-setup.md) | [spec](../docs/superpowers/specs/2026-03-13-design-001-design-system-setup.md) |
| DESIGN-002 | Reusable Components | Must | 5 | — | — |
| DESIGN-003 | Dashboard Screen | Must | 3 | — | — |
| DESIGN-004 | Topic Discovery Screen | Must | 3 | — | — |
| DESIGN-005 | Article View Screen | Must | 3 | — | — |
| DESIGN-006 | Research Sessions Screen | Should | 3 | — | — |
| DESIGN-007 | Publishing Screen | Should | 3 | — | — |
| DESIGN-008 | Settings Screen | Must | 5 | — | — |
| DESIGN-009 | Login & Auth Screens | Must | 2 | — | — |

### Epic 1: Trend Discovery Engine — DONE
**Goal**: Automatically discover trending topics in a configured domain from multiple data sources.

| Ticket | Title | Priority | SP | Plan | Spec |
|--------|-------|----------|---:|------|------|
| TREND-001 | Google Trends Integration | Must | 5 | [plan](../docs/superpowers/plans/2026-03-13-trend-001-google-trends-integration.md) | [spec](../docs/superpowers/specs/2026-03-13-trend-001-google-trends-integration-design.md) |
| TREND-002 | Reddit Trend Source | Must | 5 | [plan](../docs/superpowers/plans/2026-03-14-trend-002-reddit-trend-source.md) | [spec](../docs/superpowers/specs/2026-03-14-trend-002-reddit-trend-source-design.md) |
| TREND-003 | Hacker News Integration | Must | 3 | [plan](../docs/superpowers/plans/2026-03-13-trend-003-hackernews-integration.md) | [spec](../docs/superpowers/specs/2026-03-13-trend-003-hackernews-integration-design.md) |
| TREND-004 | NewsAPI Integration | Should | 3 | [plan](../docs/superpowers/plans/2026-03-15-trend-004-newsapi-integration.md) | [spec](../docs/superpowers/specs/2026-03-15-trend-004-newsapi-integration-design.md) |
| TREND-005 | arXiv Paper Feed | Should | 3 | [plan](../docs/superpowers/plans/2026-03-15-trend-005-arxiv-paper-feed.md) | [spec](../docs/superpowers/specs/2026-03-15-trend-005-arxiv-paper-feed-design.md) |
| TREND-006 | Topic Ranking & Dedup | Must | 8 | [plan](../docs/superpowers/plans/2026-03-13-trend-006-topic-ranking-dedup.md) | [spec](../docs/superpowers/specs/2026-03-13-trend-006-topic-ranking-dedup-design.md) |

### Epic 8: Architecture Foundation — DONE
**Goal**: Establish core contracts and patterns identified in the Architecture Modularity Review.

**Reference**: [`docs/architecture/ARCHITECTURE_MODULARITY_REVIEW.md`](../docs/architecture/ARCHITECTURE_MODULARITY_REVIEW.md)

| Ticket | Title | Priority | SP | Plan | Spec |
|--------|-------|----------|---:|------|------|
| ARCH-001 | CanonicalArticle Model & Contracts | Must | 3 | [plan](../docs/superpowers/plans/2026-03-17-arch-001-canonical-article-contracts.md) | [spec](../docs/superpowers/specs/2026-03-17-arch-001-canonical-article-contracts-design.md) |
| ARCH-002 | TrendSource Protocol & Registry | Should | 5 | [plan](../docs/superpowers/plans/2026-03-20-arch-002-trendsource-protocol-registry.md) | [spec](../docs/superpowers/specs/2026-03-20-arch-002-trendsource-protocol-registry-design.md) |

### Epic 2: Multi-Agent Research Pipeline — DONE
**Goal**: Autonomously research a selected topic using parallel AI agents with RAG.

| Ticket | Title | Priority | SP | Plan | Spec |
|--------|-------|----------|---:|------|------|
| RESEARCH-001 | Agent Orchestrator (LangGraph) | Must | 13 | [plan](../docs/superpowers/plans/2026-03-17-research-001-agent-orchestrator.md) | [spec](../docs/superpowers/specs/2026-03-17-research-001-agent-orchestrator-design.md) |
| RESEARCH-002 | Web Search Agent | Must | 8 | [plan](../docs/superpowers/plans/2026-03-17-research-002-web-search-agent.md) | [spec](../docs/superpowers/specs/2026-03-17-research-002-web-search-agent-design.md) |
| RESEARCH-003 | RAG Pipeline (Milvus) | Must | 8 | [plan](../docs/superpowers/plans/2026-03-17-research-003-rag-pipeline.md) | [spec](../docs/superpowers/specs/2026-03-17-research-003-rag-pipeline-design.md) |
| RESEARCH-004 | Literature Review Agent | Should | 5 | [plan](../docs/superpowers/plans/2026-03-21-research-004-literature-review-agent.md) | [spec](../docs/superpowers/specs/2026-03-21-research-004-literature-review-agent-design.md) |
| RESEARCH-005 | Research Session Tracking | Must | 5 | [plan](../docs/superpowers/plans/2026-03-21-research-005-research-session-tracking.md) | [spec](../docs/superpowers/specs/2026-03-21-research-005-research-session-tracking-design.md) |

### Epic 3: Content Generation Pipeline — DONE
**Goal**: Generate high-quality, SEO-optimized, AI-discoverable long-form articles from research findings.

| Ticket | Title | Priority | SP | Plan | Spec |
|--------|-------|----------|---:|------|------|
| CONTENT-001 | Article Outline Generation | Must | 5 | [plan](../docs/superpowers/plans/2026-03-18-content-001-article-outline.md) | [spec](../docs/superpowers/specs/2026-03-18-content-001-article-outline-design.md) |
| CONTENT-002 | Section-by-Section Drafting | Must | 8 | [plan](../docs/superpowers/plans/2026-03-19-content-002-section-drafting.md) | [spec](../docs/superpowers/specs/2026-03-19-content-002-section-drafting-design.md) |
| CONTENT-003 | SEO & AI Discoverability | Must | 8 | [plan](../docs/superpowers/plans/2026-03-19-content-003-seo-ai-discoverability.md) | [spec](../docs/superpowers/specs/2026-03-19-content-003-seo-ai-discoverability-design.md) |
| CONTENT-004 | Citation Management | Must | 5 | [plan](../docs/superpowers/plans/2026-03-19-content-004-citation-management.md) | [spec](../docs/superpowers/specs/2026-03-19-content-004-citation-management-design.md) |
| CONTENT-005 | CanonicalArticle Assembly | Must | 5 | [plan](../docs/superpowers/plans/2026-03-20-content-005-canonical-article-assembly.md) | [spec](../docs/superpowers/specs/2026-03-20-content-005-canonical-article-assembly-design.md) |
| CONTENT-006 | Content Humanization | Must | 5 | [plan](../docs/superpowers/plans/2026-03-20-content-006-content-humanization.md) | [spec](../docs/superpowers/specs/2026-03-20-content-006-content-humanization-design.md) |

### Epic 4: Visual Asset Generation — DONE
**Goal**: Automatically create charts, diagrams, and illustrations for articles.

| Ticket | Title | Priority | SP | Plan | Spec |
|--------|-------|----------|---:|------|------|
| VISUAL-001 | Data Chart Generation | Must | 5 | [plan](../docs/superpowers/plans/2026-03-21-visual-001-data-chart-generation.md) | [spec](../docs/superpowers/specs/2026-03-21-visual-001-data-chart-generation-design.md) |
| VISUAL-002 | AI Illustration Generation | Should | 5 | [plan](../docs/superpowers/plans/2026-03-22-visual-002-ai-illustration-generation.md) | [spec](../docs/superpowers/specs/2026-03-22-visual-002-ai-illustration-generation-design.md) |
| VISUAL-003 | Diagram Generation | Could | 3 | [plan](../docs/superpowers/plans/2026-03-22-visual-003-diagram-generation.md) | [spec](../docs/superpowers/specs/2026-03-22-visual-003-diagram-generation-design.md) |

### Epic 6: Dashboard & Configuration — DONE
**Goal**: Provide a web dashboard for monitoring, configuration, and manual control.

| Ticket | Title | Priority | SP | Plan | Spec |
|--------|-------|----------|---:|------|------|
| DASH-001 | Dashboard Overview | Must | 8 | [plan](../docs/superpowers/plans/2026-03-15-dash-001-dashboard-overview.md) | [spec](../docs/superpowers/specs/2026-03-15-dash-001-dashboard-overview-design.md) |
| DASH-002 | Topic Discovery Screen | Must | 5 | [plan](../docs/superpowers/plans/2026-03-20-dash-002-topic-discovery-screen.md) | [spec](../docs/superpowers/specs/2026-03-20-dash-002-topic-discovery-screen-design.md) |
| DASH-003 | Article View & Preview | Must | 5 | [plan](../docs/superpowers/plans/2026-03-21-dash-003-article-view-preview.md) | [spec](../docs/superpowers/specs/2026-03-21-dash-003-article-view-preview-design.md) |
| DASH-004 | Research Sessions Screen | Should | 5 | [plan](../docs/superpowers/plans/2026-03-21-dash-004-research-sessions-screen.md) | [spec](../docs/superpowers/specs/2026-03-21-dash-004-research-sessions-screen-design.md) |
| DASH-005 | Settings & Configuration | Must | 8 | [plan](../docs/superpowers/plans/2026-03-21-dash-005-settings-configuration.md) | [spec](../docs/superpowers/specs/2026-03-20-dash-005-settings-configuration-design.md) |

### Epic 7: API & Authentication — DONE
**Goal**: RESTful API with JWT authentication and role-based access control.

| Ticket | Title | Priority | SP | Plan | Spec |
|--------|-------|----------|---:|------|------|
| API-001 | FastAPI Application Setup | Must | 5 | [plan](../docs/superpowers/plans/2026-03-12-api-001-fastapi-setup.md) | [spec](../docs/superpowers/specs/2026-03-12-api-001-fastapi-setup-design.md) |
| API-002 | JWT Authentication | Must | 5 | [plan](../docs/superpowers/plans/2026-03-13-api-002-jwt-authentication.md) | [spec](../docs/superpowers/specs/2026-03-12-api-002-jwt-authentication-design.md) |
| API-003 | RBAC Authorization | Must | 5 | [plan](../docs/superpowers/plans/2026-03-13-api-003-rbac-authorization.md) | [spec](../docs/superpowers/specs/2026-03-13-api-003-rbac-authorization-design.md) |

### Epic 9: Infrastructure & Integration (4/5 done)
**Goal**: Replace in-memory stubs with real PostgreSQL persistence and wire frontend to backend APIs.

**Completed:**

| Ticket | Title | Priority | SP | Plan | Spec |
|--------|-------|----------|---:|------|------|
| INFRA-001a | PostgreSQL Persistence (Foundation) | Must | — | [plan](../docs/superpowers/plans/2026-03-22-infra-001a-database-foundation.md) | [spec](../docs/superpowers/specs/2026-03-22-infra-001a-database-foundation-design.md) |
| INFRA-001b | Topic Persistence & Cross-Scan Dedup | Must | — | [plan](../docs/superpowers/plans/2026-03-22-infra-001b-topic-persistence.md) | [spec](../docs/superpowers/specs/2026-03-22-infra-001b-topic-persistence-design.md) |
| INFRA-002 | Frontend-Backend API Integration | Must | 8 | [plan](../docs/superpowers/plans/2026-03-22-infra-002-frontend-api-integration.md) | [spec](../docs/superpowers/specs/2026-03-22-infra-002-frontend-api-integration-design.md) |
| INFRA-003 | Wire Real LLM Orchestrator | Must | 5 | — | — |
| INFRA-004 | Settings Backend CRUD | Must | 8 | [plan](../docs/superpowers/plans/2026-03-24-infra-004-settings-backend-crud.md) | — |

*(INFRA-001 originally 13 SP, split into 001a + 001b)*

---

## Active Backlog

### Epic 5: Multi-Platform Publishing (4/5 done)
**Goal**: Publish articles to multiple platforms with correct formatting and metadata.

**Completed:** PUBLISH-001 (Ghost CMS), PUBLISH-003 (Medium) — PR #43, PUBLISH-004 (LinkedIn) — PR #48, PUBLISH-005 (Publication Tracking)

#### PUBLISH-002: WordPress Integration [Should]
**As a** publisher, **I want** articles published to WordPress, **so that** I can reach my WordPress audience.
- **Acceptance Criteria**:
  - Creates post via WordPress REST API
  - Uploads featured image
  - Sets categories and tags
  - Handles authentication via Application Password
- **Story Points**: 5

#### ~~PUBLISH-004: LinkedIn Integration [Could]~~ — DONE (PR #48)
**As a** publisher, **I want** articles shared on LinkedIn, **so that** professional audience is reached.
- **Acceptance Criteria**:
  - Posts article to LinkedIn page via Marketing API
  - Includes title, excerpt, cover image, and link
  - OAuth2 authentication flow
- **Story Points**: 5

---

### Epic 9: Infrastructure — DONE

All Infrastructure tickets complete. INFRA-005 (Frontend Status Alignment) merged via PR #46.

---

### Epic 10: Visual Generation Overhaul

**Goal**: Bring image generation up to and past impactai's `feat/content-hub` patterns — per-section image planner, multi-provider stack (gemini_flash / gemini_3_pro / imagen_4 / dalle_3), MinIO/S3 storage, SSRF-guarded URL import, persona-aware planning, banned-cliché prompt guard, section-level HTML refinement, **per-section prose editing**. All while preserving CanonicalArticle (ADR-003) and Transformer/Adapter (ADR-004) boundaries.

**Plan**: [`docs/superpowers/plans/2026-05-06-visual-generation-improvement-plan.md`](../docs/superpowers/plans/2026-05-06-visual-generation-improvement-plan.md)
**Pencil brief**: [`docs/superpowers/specs/2026-05-06-visual-studio-pencil-design-brief.md`](../docs/superpowers/specs/2026-05-06-visual-studio-pencil-design-brief.md)
**Architecture review**: [`docs/architecture/COGNIFY_VS_IMPACTAI_REVIEW.md`](../docs/architecture/COGNIFY_VS_IMPACTAI_REVIEW.md)

| Ticket      | Title                                                                          | Priority | SP | Status |
|-------------|--------------------------------------------------------------------------------|----------|---:|--------|
| VISUAL-004  | Phase 1 — Style catalogue + provider abstraction + MinIO + SSRF guard          | Must     | 13 | DONE   |
| VISUAL-005  | Phase 2 — Persona-aware planner + pipeline nodes                               | Must     | 13 | DONE   |
| VISUAL-006  | Phase 3 — Markdown injection + multi-platform publishing transformers          | Must     |  8 | DONE   |
| VISUAL-007  | Phase 4 — Studio API (plan/render/refine/upload/fetch-url/section-html-refine) | Must     |  8 | DONE   |
| VISUAL-008  | Phase 5 — Frontend Visual Studio (chip rails, spec cards, HTML refine)         | Must     | 21 | DONE   |
| VISUAL-009  | Phase 6 — MinIO production rollout + cost dashboard                            | Should   |  5 | DONE   |
| VISUAL-010  | Phase 7 — Saved-asset gallery + audience-persona Settings UI                   | Should   |  8 | DONE   |
| VISUAL-011  | Phase 8 — Per-section content editing (text + AI rewrite + history)            | Should   | 13 | DONE   |

Per-phase acceptance criteria are documented in the implementation plan (§11). Boundary invariants (ADR-003, ADR-004) are enforced as called out per phase.

**Phase 5 (VISUAL-008) note on Playwright E2E**: the plan §11.5 calls for Playwright coverage of the plan → render → refine flow. Playwright is not yet wired into the repo (no browsers, no CI lane, no fixtures). VISUAL-008 ships equivalent coverage via Vitest component + integration tests; the Playwright scaffolding itself is tracked as a follow-up alongside the broader testing-infrastructure work.

---

### Epic 11: Supervised Authoring — PLANNED

**Goal**: Turn the blind 2–5 min pipeline into a supervised, streaming, resumable authoring flow (brief → outline gate → streamed sections → per-section regenerate → cost visibility → drafts/resume), importing ImpactAI's *authoring model* on Cognify's LangGraph/service-layer spine.

**Plan**: [`docs/superpowers/plans/2026-08-19-epic-11-supervised-authoring-plan.md`](../docs/superpowers/plans/2026-08-19-epic-11-supervised-authoring-plan.md)
**Spec / rationale**: [`docs/architecture/COGNIFY_VS_IMPACTAI_REVIEW_2026-08.md`](../docs/architecture/COGNIFY_VS_IMPACTAI_REVIEW_2026-08.md) §4, §6

| Ticket | Title | Priority | SP | Phase |
|--------|-------|----------|---:|-------|
| ADR-006/007 | ADRs: supervised pipeline (event bus + outline gate); Brief as authoring contract | Must | 1 | A |
| AUTHOR-001 | Live session progress (SSE, DB-tailing) + SessionProgress + session route + auto-navigate — **DONE** (`06439e9`) | Must | 8 | A |
| AUTHOR-002 | Outline approval gate (half-graphs, `awaiting_outline_review`, outline endpoints, cancel, OutlineReviewStep; flagged) — **DONE** (PR #73) | Must | 8 | A |
| AUTHOR-003 | Brief model/CRUD + Generate modal rework (picker, length, content type, save-as-brief) — **DONE** (`feature/AUTHOR-003-brief`, 2026-08-21) | Must | 5 | A |
| AUTHOR-004 | Per-section regenerate-with-feedback (endpoint + toolbar + diff accept) | Must | 3 | A |
| AUTHOR-005 | Session/article usage endpoint + pricing settings + UsageBadge | Should | 3 | A |
| INFRA-007 | CeleryDispatcher + worker wiring for the full pipeline | Must | 5 | A |
| AUTHOR-006 | PATCH article metadata + header/SEO editor + refetch + autosave | Should | 5 | B |
| AUTHOR-007 | Article status (draft/in_review/approved/published) + list filters + Resume | Should | 3 | B |
| AUTHOR-008 | Length target + content type through outliner (word budgets) | Should | 3 | B |
| AUTHOR-009 | Humanize per-pass streaming + sentence-level accept/reject | Could | 3 | B |
| AUTHOR-010 | Model tiering per step | Could | 2 | B |
| INFRA-008 | Embedding warm-up w/ graceful degradation; live role re-check; shared toaster; split >200-line files | Should | 4 | B |
| AUTHOR-011 | Persona voice engine v1 (fingerprint → prompt → score → fix; flagged) | Could | 13 | C |
| AUTHOR-012 | Prompt registry + per-user overrides + Settings tab | Could | 5 | C |
| AUTHOR-013 | LinkedIn repurpose transformer + modal | Could | 5 | C |
| AUTHOR-014 | Playwright create-article flow (mocked SSE) | Should | 2 | C |

Per-phase acceptance criteria are in the plan §9. Feature flags default to current behaviour (`COGNIFY_REQUIRE_OUTLINE_APPROVAL=false`).

---

## Backlog Summary

| Epic | Total | Done | Remaining | Points (remaining) |
|------|------:|-----:|----------:|--------------------:|
| Design System & UI/UX | 9 | 9 | 0 | 0 |
| Trend Discovery | 6 | 6 | 0 | 0 |
| Architecture Foundation | 2 | 2 | 0 | 0 |
| Research Pipeline | 5 | 5 | 0 | 0 |
| Content Generation | 6 | 6 | 0 | 0 |
| Visual Assets | 3 | 3 | 0 | 0 |
| **Publishing** | **5** | **4** | **1** | **5** |
| Dashboard & Config | 5 | 5 | 0 | 0 |
| API & Auth | 3 | 3 | 0 | 0 |
| Infrastructure | 5 | 5 | 0 | 0 |
| **Visual Generation Overhaul** | **8** | **8** | **0** | **0** |
| **Supervised Authoring (Epic 11)** | **17** | **4** | **13** | **~56** |
| **Total** | **74** | **60** | **14** | **~61** |

**Velocity update (2026-05-07)**: Epic 10 (Visual Generation Overhaul)
fully shipped — VISUAL-004 through VISUAL-011 (89 SP) merged to
`develop` via PR #54 (`feature/EPIC-10-visual-generation`). Five
follow-ups (INFRA-006, CONTENT-007, DASH-007, Playwright scaffold,
.env flake fix) merged via PR #55 (`chore/post-epic-10-housekeeping`).
The only remaining ticket in the entire backlog is PUBLISH-002
(5 SP, WordPress integration).

**Velocity**: 365 SP completed across 12 epics (Epic 11: ADR-006/007 + AUTHOR-001 + AUTHOR-002 = 17 SP on 2026-08-19; AUTHOR-003 = 5 SP on 2026-08-21). Remaining: PUBLISH-002 (5 SP) + Epic 11 (~56 SP).
