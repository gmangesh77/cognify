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
| ARCH-002 | TrendSource Protocol & Registry        | Backlog | —      | —    | —    |


## Epic 2: Multi-Agent Research Pipeline


| Ticket       | Title                          | Status  | Branch | Plan | Spec |
| ------------ | ------------------------------ | ------- | ------ | ---- | ---- |
| RESEARCH-001 | Agent Orchestrator (LangGraph) | Done | `feature/RESEARCH-001-agent-orchestrator` | [plan](../docs/superpowers/plans/2026-03-17-research-001-agent-orchestrator.md) | [spec](../docs/superpowers/specs/2026-03-17-research-001-agent-orchestrator-design.md) |
| RESEARCH-002 | Web Search Agent               | Done | `feature/RESEARCH-002-web-search-agent` | [plan](../docs/superpowers/plans/2026-03-17-research-002-web-search-agent.md) | [spec](../docs/superpowers/specs/2026-03-17-research-002-web-search-agent-design.md) |
| RESEARCH-003 | RAG Pipeline (Milvus)          | Done | `feature/RESEARCH-003-rag-pipeline` | [plan](../docs/superpowers/plans/2026-03-17-research-003-rag-pipeline.md) | [spec](../docs/superpowers/specs/2026-03-17-research-003-rag-pipeline-design.md) |
| RESEARCH-004 | Literature Review Agent        | Backlog | —      | —    | —    |
| RESEARCH-005 | Research Session Tracking      | Backlog | —      | —    | —    |

**Stubs from RESEARCH-001 to replace:**
- ~~RESEARCH-002: Replace `stub_research_agent` with real web search agent~~ — Done (`WebSearchAgent` in `src/agents/research/web_search.py`)
- ~~RESEARCH-003: RAG pipeline~~ — Done (MilvusService, MilvusRetriever, TokenChunker, index_findings node)
- Future Celery ticket: Replace `AsyncIODispatcher` in `src/services/task_dispatch.py` with `CeleryDispatcher` (deferred from RESEARCH-003).
- Future infra ticket: Replace `MemorySaver` with `PostgresSaver` in orchestrator. Replace in-memory repositories in `src/services/research.py` with real PostgreSQL repos.


## Epic 3: Content Generation Pipeline


| Ticket      | Title                       | Status  | Branch | Plan | Spec |
| ----------- | --------------------------- | ------- | ------ | ---- | ---- |
| CONTENT-001 | Article Outline Generation  | Backlog | —      | —    | —    |
| CONTENT-002 | Section-by-Section Drafting | Backlog | —      | —    | —    |
| CONTENT-003 | SEO Optimization            | Backlog | —      | —    | —    |
| CONTENT-004 | Citation Management         | Backlog | —      | —    | —    |


## Epic 4: Visual Asset Generation


| Ticket     | Title                      | Status  | Branch | Plan | Spec |
| ---------- | -------------------------- | ------- | ------ | ---- | ---- |
| VISUAL-001 | Data Chart Generation      | Backlog | —      | —    | —    |
| VISUAL-002 | AI Illustration Generation | Backlog | —      | —    | —    |
| VISUAL-003 | Diagram Generation         | Backlog | —      | —    | —    |


## Epic 5: Multi-Platform Publishing


| Ticket      | Title                 | Status  | Branch | Plan | Spec |
| ----------- | --------------------- | ------- | ------ | ---- | ---- |
| PUBLISH-001 | Ghost CMS Integration | Backlog | —      | —    | —    |
| PUBLISH-002 | WordPress Integration | Backlog | —      | —    | —    |
| PUBLISH-003 | Medium Integration    | Backlog | —      | —    | —    |
| PUBLISH-004 | LinkedIn Integration  | Backlog | —      | —    | —    |
| PUBLISH-005 | Publication Tracking  | Backlog | —      | —    | —    |


## Epic 6: Dashboard & Configuration


| Ticket   | Title                    | Status  | Branch | Plan | Spec |
| -------- | ------------------------ | ------- | ------ | ---- | ---- |
| DASH-001 | Dashboard Overview       | Done | `feature/DASH-001-dashboard-overview` | [plan](../docs/superpowers/plans/2026-03-15-dash-001-dashboard-overview.md) | [spec](../docs/superpowers/specs/2026-03-15-dash-001-dashboard-overview-design.md) |
| DASH-002 | Topic Discovery Screen   | Backlog | —      | —    | —    |
| DASH-003 | Article View & Preview   | Backlog | —      | —    | —    |
| DASH-004 | Research Sessions Screen | Backlog | —      | —    | —    |
| DASH-005 | Settings & Configuration | Backlog | —      | —    | —    |


---

## How to Update This File

When starting a ticket:

1. Change status to **In Progress**, fill in the branch name
2. Link the plan/spec files once created

When completing a ticket:

1. Change status to **Done**
2. Ensure plan/spec links are present
3. Update the corresponding entry in `BACKLOG.md` with `— DONE` suffix and status/plan/spec fields

