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

### Epic 5: Multi-Platform Publishing (3/5 done)
**Goal**: Publish articles to multiple platforms with correct formatting and metadata.

**Completed:** PUBLISH-001 (Ghost CMS), PUBLISH-003 (Medium) — PR #43, PUBLISH-005 (Publication Tracking)

#### PUBLISH-002: WordPress Integration [Should]
**As a** publisher, **I want** articles published to WordPress, **so that** I can reach my WordPress audience.
- **Acceptance Criteria**:
  - Creates post via WordPress REST API
  - Uploads featured image
  - Sets categories and tags
  - Handles authentication via Application Password
- **Story Points**: 5

#### PUBLISH-004: LinkedIn Integration [Could]
**As a** publisher, **I want** articles shared on LinkedIn, **so that** professional audience is reached.
- **Acceptance Criteria**:
  - Posts article to LinkedIn page via Marketing API
  - Includes title, excerpt, cover image, and link
  - OAuth2 authentication flow
- **Story Points**: 5

---

### Epic 9: Infrastructure (remaining)

#### INFRA-005: Frontend Status Alignment [Should]
**As a** user, **I want** all session statuses displayed correctly, **so that** the Research page doesn't crash on unexpected statuses.
- **Acceptance Criteria**:
  - Frontend `SessionStatus` type includes all backend statuses: planning, researching, evaluating, running, complete, completed, failed
  - `SessionStatusBadge`, `SessionCard` progress bar, and `SessionFilters` handle all statuses
  - Session detail polling works for active sessions (researching, evaluating)
  - Dashboard "Recent Articles" and "Trending Topics" show real data with correct text colors
- **Story Points**: 3
- **Note**: Partially fixed (StatusBadge crash resolved), but filter tabs and progress bar logic still assume 4 statuses

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
| **Publishing** | **5** | **3** | **2** | **10** |
| Dashboard & Config | 5 | 5 | 0 | 0 |
| API & Auth | 3 | 3 | 0 | 0 |
| **Infrastructure** | **5** | **4** | **1** | **3** |
| **Total** | **49** | **46** | **3** | **13** |

**Velocity**: 246 SP completed across 9 epics. 13 SP remaining (3 tickets).
