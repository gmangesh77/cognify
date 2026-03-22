# INFRA-002: Frontend-Backend API Integration — Design Specification

> **Date**: 2026-03-22
> **Status**: Approved
> **Ticket**: INFRA-002
> **Depends on**: INFRA-001a (Done), INFRA-001b (Done)

---

## 1. Overview

Wire remaining frontend hooks to real backend APIs so all pages show live data instead of mock. Covers article listing, article detail, dashboard metrics, dashboard topics, and the "Generate Article" action.

Settings CRUD (14 endpoints) deferred to a separate ticket.

---

## 2. Scope

| Hook / Feature | Current | After |
|---------------|---------|-------|
| `useArticleList()` | Mock 4 articles | Calls `GET /articles` |
| `useArticle(id)` | Mock lookup | Calls existing `GET /articles/{id}` |
| `useMetrics()` | Mock numbers | Calls `GET /metrics` |
| `useTopics()` | Mock 25 topics | Calls `GET /topics` (persisted topics) |
| Generate Article button | Toast only | Calls `POST /research/sessions` |

**Out of scope:** Settings page (stays mock), Publishing page (placeholder).

---

## 3. New Backend Endpoints

### 3a. `GET /api/v1/articles` — List articles

Add to `src/api/routers/canonical_articles.py`:

- Query params: `page` (default 1), `size` (default 20)
- Returns paginated `CanonicalArticleResponse[]`
- Requires: extend `PgArticleRepository` with `list(page, size)` method

### 3b. `GET /api/v1/metrics` — Dashboard metrics

Add new router `src/api/routers/metrics.py`:

- Aggregates counts from DB: topic count, article count, session count, avg research duration
- Returns `DashboardMetricsResponse`
- Queries: `SELECT COUNT(*) FROM topics`, `SELECT COUNT(*) FROM canonical_articles`, `SELECT AVG(duration_seconds) FROM research_sessions WHERE status='complete'`

---

## 4. Frontend Changes

### 4a. `useArticleList()` — wire to `GET /articles`

Replace mock with TanStack Query calling `GET /articles`. Map `CanonicalArticleResponse` → `ArticleListItem` frontend type.

### 4b. `useArticle(id)` — wire to `GET /articles/{id}`

Replace mock lookup with API call. Map `CanonicalArticleResponse` → `ArticleDetail` frontend type.

### 4c. `useMetrics()` — wire to `GET /metrics`

Replace mock with API call. Backend returns real counts.

### 4d. `useTopics()` — wire to `GET /topics`

Replace mock with API call to `GET /topics?domain=&page=1&size=10`. Used on dashboard for "Trending Topics" panel.

### 4e. Generate Article — wire `onConfirm`

In `topics/page.tsx`, change `handleConfirm` from toast-only to calling `POST /research/sessions` with the topic. Show toast with session status.

---

## 5. Type Mapping

Frontend types don't match backend schemas exactly. Need thin mapping functions:

- `CanonicalArticleResponse` → `ArticleListItem` (extract id, title, summary, status, domain, wordCount, generatedAt)
- `CanonicalArticleResponse` → `ArticleDetail` (fuller mapping with body, citations, workflow steps)
- `PersistedTopic` → `RankedTopic` (already similar, add trend_status derivation)

---

## 6. File Summary

| File | Type | Change |
|------|------|--------|
| `src/api/routers/canonical_articles.py` | Modified | Add `GET /articles` list endpoint |
| `src/api/routers/metrics.py` | New | Dashboard metrics endpoint |
| `src/db/repositories.py` | Modified | Add `PgArticleRepository.list()` |
| `src/api/main.py` | Modified | Register metrics router |
| `frontend/src/lib/api/articles.ts` | New | API functions for articles |
| `frontend/src/lib/api/metrics.ts` | New | API function for metrics |
| `frontend/src/hooks/use-article-list.ts` | Modified | Wire to real API |
| `frontend/src/hooks/use-article.ts` | Modified | Wire to real API |
| `frontend/src/hooks/use-metrics.ts` | Modified | Wire to real API |
| `frontend/src/hooks/use-topics.ts` | Modified | Wire to real API |
| `frontend/src/app/(dashboard)/topics/page.tsx` | Modified | Wire Generate Article |
| Tests | New + modified | ~80 lines |
