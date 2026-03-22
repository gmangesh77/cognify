# INFRA-002: Frontend-Backend API Integration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire all remaining frontend hooks to real backend APIs — article list/detail, dashboard metrics, dashboard topics, and Generate Article action.

**Architecture:** Add 2 backend endpoints (`GET /articles`, `GET /metrics`), create frontend API client functions, replace mock data in hooks with TanStack Query API calls. Thin mapping functions convert between backend schemas and frontend types.

**Tech Stack:** FastAPI, SQLAlchemy async, Next.js 15, TanStack Query, TypeScript

**Spec:** `docs/superpowers/specs/2026-03-22-infra-002-frontend-api-integration-design.md`

**Worktree:** `D:/Workbench/github/cognify-infra-002` on branch `feature/INFRA-002-frontend-api-integration`

---

## File Structure

### New Files

| File | Responsibility | ~Lines |
|------|---------------|--------|
| `src/api/routers/metrics.py` | Dashboard metrics endpoint | ~50 |
| `frontend/src/lib/api/articles.ts` | Article API functions | ~40 |
| `frontend/src/lib/api/metrics.ts` | Metrics API function | ~20 |

### Modified Files

| File | Change |
|------|--------|
| `src/api/routers/canonical_articles.py` | Add `GET /articles` list endpoint |
| `src/db/repositories.py` | Add `PgArticleRepository.list()` method |
| `src/api/main.py` | Register metrics router, wire metric queries |
| `frontend/src/hooks/use-article-list.ts` | Wire to real API |
| `frontend/src/hooks/use-article.ts` | Wire to real API |
| `frontend/src/hooks/use-metrics.ts` | Wire to real API |
| `frontend/src/hooks/use-topics.ts` | Wire to real `GET /topics` |
| `frontend/src/app/(dashboard)/topics/page.tsx` | Wire Generate Article to `POST /research/sessions` |
| `frontend/src/lib/api/trends.ts` | Add `createResearchSession()` function |

---

## Task 1: Backend — Article List Endpoint and Metrics Endpoint

**Files:**
- Modify: `src/db/repositories.py` — add `PgArticleRepository.list()`
- Modify: `src/api/routers/canonical_articles.py` — add `GET /articles`
- Create: `src/api/routers/metrics.py` — dashboard metrics
- Modify: `src/api/main.py` — register metrics router

- [ ] **Step 1: Add list method to PgArticleRepository**

In `src/db/repositories.py`, add to `PgArticleRepository`:

```python
async def list(
    self, page: int = 1, size: int = 20,
) -> tuple[list[CanonicalArticle], int]:
    """List all articles, newest first."""
    async with self._sf() as session:
        count_q = select(func.count()).select_from(
            CanonicalArticleRow,
        )
        total = (await session.execute(count_q)).scalar_one()
        q = (
            select(CanonicalArticleRow)
            .order_by(CanonicalArticleRow.generated_at.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
        rows = (await session.execute(q)).scalars().all()
        return [self._to_model(r) for r in rows], total
```

- [ ] **Step 2: Add GET /articles endpoint**

In `src/api/routers/canonical_articles.py`, add:

```python
from src.api.schemas.articles import PaginatedArticlesResponse

@limiter.limit("30/minute")
@canonical_articles_router.get(
    "/articles",
    response_model=PaginatedArticlesResponse,
    summary="List all articles",
)
async def list_articles(
    request: Request,
    page: int = 1,
    size: int = 20,
    user: TokenPayload = Depends(require_role("admin", "editor", "viewer")),
) -> PaginatedArticlesResponse:
    repo = request.app.state.article_repo
    items, total = await repo.list(page, size)
    return PaginatedArticlesResponse(
        items=[CanonicalArticleResponse.from_article(a) for a in items],
        total=total,
        page=page,
        size=size,
    )
```

Add schema to `src/api/schemas/articles.py`:
```python
class PaginatedArticlesResponse(BaseModel):
    items: list[CanonicalArticleResponse]
    total: int
    page: int
    size: int
```

Wire `article_repo` on app.state in lifespan (if not already there).

- [ ] **Step 3: Create metrics endpoint**

Create `src/api/routers/metrics.py`:

```python
"""Dashboard metrics endpoint."""

import structlog
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from src.api.auth.schemas import TokenPayload
from src.api.dependencies import require_role
from src.api.rate_limiter import limiter

logger = structlog.get_logger()

metrics_router = APIRouter()


class MetricValue(BaseModel):
    value: int | str
    trend: int = 0
    direction: str = "up"


class DashboardMetricsResponse(BaseModel):
    topics_discovered: MetricValue
    articles_generated: MetricValue
    avg_research_time: MetricValue
    published: MetricValue


@limiter.limit("30/minute")
@metrics_router.get(
    "/metrics",
    response_model=DashboardMetricsResponse,
    summary="Dashboard overview metrics",
)
async def get_metrics(
    request: Request,
    user: TokenPayload = Depends(require_role("admin", "editor", "viewer")),
) -> DashboardMetricsResponse:
    db = request.app.state
    topic_count = 0
    article_count = 0
    avg_time = "0m"
    if hasattr(db, "topic_repo"):
        _, topic_count = await db.topic_repo.list_by_domain("", 1, 0)
    if hasattr(db, "article_repo"):
        _, article_count = await db.article_repo.list(1, 0)
    return DashboardMetricsResponse(
        topics_discovered=MetricValue(value=topic_count),
        articles_generated=MetricValue(value=article_count),
        avg_research_time=MetricValue(value=avg_time),
        published=MetricValue(value=0),
    )
```

Note: `list_by_domain("")` with empty domain needs to handle "all domains" — may need to adjust the query. If it doesn't work, create a simple `count_all()` method instead.

- [ ] **Step 4: Register metrics router in main.py**

In `src/api/main.py`, add:
```python
from src.api.routers.metrics import metrics_router
# In _register_routers():
app.include_router(metrics_router, prefix=settings.api_v1_prefix)
```

Also ensure `article_repo` is on `app.state` in the lifespan.

- [ ] **Step 5: Run backend tests**

Run: `cd D:/Workbench/github/cognify-infra-002 && uv run pytest tests/unit/ -q --tb=short 2>&1 | tail -5`

- [ ] **Step 6: Commit**

```bash
cd D:/Workbench/github/cognify-infra-002
git add src/db/repositories.py src/api/routers/canonical_articles.py src/api/routers/metrics.py src/api/schemas/articles.py src/api/main.py
git commit -m "feat(infra-002): add GET /articles and GET /metrics backend endpoints"
```

---

## Task 2: Frontend — Article API Client and Hooks

**Files:**
- Create: `frontend/src/lib/api/articles.ts`
- Modify: `frontend/src/hooks/use-article-list.ts`
- Modify: `frontend/src/hooks/use-article.ts`

- [ ] **Step 1: Create articles API client**

Create `frontend/src/lib/api/articles.ts`:

```typescript
import { apiClient } from "./client";

export interface ArticleResponse {
  id: string;
  title: string;
  subtitle: string | null;
  body_markdown: string;
  summary: string;
  key_claims: string[];
  content_type: string;
  domain: string;
  ai_generated: boolean;
  generated_at: string;
  seo: { title: string; description: string; keywords: string[] };
  citations: { index: number; title: string; url: string; authors: string[]; published_at: string | null }[];
  visuals: { id: string; url: string; caption: string | null; alt_text: string | null }[];
  provenance: { research_session_id: string; primary_model: string; drafting_model: string };
  authors: string[];
}

export interface PaginatedArticles {
  items: ArticleResponse[];
  total: number;
  page: number;
  size: number;
}

export async function fetchArticles(page = 1, size = 20): Promise<PaginatedArticles> {
  const { data } = await apiClient.get<PaginatedArticles>("/articles", { params: { page, size } });
  return data;
}

export async function fetchArticle(id: string): Promise<ArticleResponse> {
  const { data } = await apiClient.get<ArticleResponse>(`/articles/${id}`);
  return data;
}
```

- [ ] **Step 2: Wire useArticleList to real API**

Replace `frontend/src/hooks/use-article-list.ts`:

```typescript
import { useQuery } from "@tanstack/react-query";
import { fetchArticles } from "@/lib/api/articles";
import type { ArticleListItem } from "@/types/articles";
import type { ArticleResponse } from "@/lib/api/articles";

function toListItem(a: ArticleResponse): ArticleListItem {
  return {
    id: a.id,
    title: a.title,
    summary: a.summary,
    status: "complete",
    domain: a.domain,
    wordCount: a.body_markdown.split(/\s+/).length,
    generatedAt: a.generated_at,
  };
}

export function useArticleList() {
  const query = useQuery({
    queryKey: ["article-list"],
    queryFn: async () => {
      try {
        const result = await fetchArticles(1, 20);
        return { articles: result.items.map(toListItem) };
      } catch {
        // Fallback to empty if API unavailable
        return { articles: [] as ArticleListItem[] };
      }
    },
    staleTime: 60 * 1000,
  });
  return { articles: query.data?.articles ?? [] };
}
```

- [ ] **Step 3: Wire useArticle to real API**

Replace `frontend/src/hooks/use-article.ts`:

```typescript
import { useQuery } from "@tanstack/react-query";
import { fetchArticle } from "@/lib/api/articles";
import type { ArticleDetail } from "@/types/articles";
import type { ArticleResponse } from "@/lib/api/articles";

function toDetail(a: ArticleResponse): ArticleDetail {
  return {
    id: a.id,
    title: a.title,
    subtitle: a.subtitle ?? "",
    summary: a.summary,
    body: a.body_markdown,
    status: "complete",
    domain: a.domain,
    wordCount: a.body_markdown.split(/\s+/).length,
    generatedAt: a.generated_at,
    citations: a.citations.map((c) => ({
      index: c.index,
      title: c.title,
      url: c.url,
    })),
    workflowSteps: [],
    seo: {
      title: a.seo.title,
      description: a.seo.description,
      keywords: a.seo.keywords,
    },
  };
}

export function useArticle(id: string) {
  const query = useQuery({
    queryKey: ["article", id],
    queryFn: async () => {
      try {
        const result = await fetchArticle(id);
        return { article: toDetail(result) };
      } catch {
        return { article: null };
      }
    },
    staleTime: 5 * 60 * 1000,
  });
  return { article: query.data?.article ?? null };
}
```

- [ ] **Step 4: Commit**

```bash
cd D:/Workbench/github/cognify-infra-002
git add frontend/src/lib/api/articles.ts frontend/src/hooks/use-article-list.ts frontend/src/hooks/use-article.ts
git commit -m "feat(infra-002): wire article list and detail hooks to real API"
```

---

## Task 3: Frontend — Metrics, Topics, and Generate Article

**Files:**
- Create: `frontend/src/lib/api/metrics.ts`
- Modify: `frontend/src/hooks/use-metrics.ts`
- Modify: `frontend/src/hooks/use-topics.ts`
- Modify: `frontend/src/app/(dashboard)/topics/page.tsx`
- Modify: `frontend/src/lib/api/trends.ts`

- [ ] **Step 1: Create metrics API client**

Create `frontend/src/lib/api/metrics.ts`:

```typescript
import { apiClient } from "./client";
import type { DashboardMetrics } from "@/types/api";

export async function fetchMetrics(): Promise<DashboardMetrics> {
  const { data } = await apiClient.get<DashboardMetrics>("/metrics");
  return data;
}
```

- [ ] **Step 2: Wire useMetrics**

Replace `frontend/src/hooks/use-metrics.ts`:

```typescript
import { useQuery } from "@tanstack/react-query";
import type { DashboardMetrics } from "@/types/api";
import { fetchMetrics } from "@/lib/api/metrics";
import { mockMetrics } from "@/lib/mock/metrics";

export function useMetrics() {
  return useQuery({
    queryKey: ["metrics"],
    queryFn: async () => {
      try {
        return await fetchMetrics();
      } catch {
        // Fallback to mock if API unavailable
        return mockMetrics;
      }
    },
    staleTime: 60 * 1000,
    refetchInterval: 60 * 1000,
  });
}
```

- [ ] **Step 3: Wire useTopics to persisted topics**

Replace `frontend/src/hooks/use-topics.ts`:

```typescript
import { useQuery } from "@tanstack/react-query";
import type { RankedTopic } from "@/types/api";
import { fetchPersistedTopics } from "@/lib/api/trends";
import type { PersistedTopic } from "@/lib/api/trends";

function toRankedTopic(t: PersistedTopic): RankedTopic {
  const hoursAgo = (Date.now() - new Date(t.discovered_at).getTime()) / 3600000;
  let trend_status: RankedTopic["trend_status"] = "steady";
  if (t.velocity >= 50 && (t.composite_score ?? 0) >= 80) trend_status = "trending";
  else if (t.velocity >= 30) trend_status = "rising";
  else if (hoursAgo <= 24) trend_status = "new";

  return {
    title: t.title,
    description: t.description,
    source: t.source,
    external_url: t.external_url,
    trend_score: t.trend_score,
    discovered_at: t.discovered_at,
    velocity: t.velocity,
    domain_keywords: [],
    composite_score: t.composite_score ?? t.trend_score,
    rank: t.rank ?? 0,
    source_count: t.source_count,
    domain: t.domain,
    trend_status,
  };
}

export function useTopics() {
  return useQuery({
    queryKey: ["topics"],
    queryFn: async () => {
      try {
        const result = await fetchPersistedTopics("", 1, 10);
        return result.items.map(toRankedTopic);
      } catch {
        return [] as RankedTopic[];
      }
    },
    staleTime: 5 * 60 * 1000,
    refetchInterval: 5 * 60 * 1000,
  });
}
```

Note: empty domain `""` fetches across all domains for the dashboard. The `list_by_domain` backend method may need to handle empty domain as "all". Adjust the query if needed.

- [ ] **Step 4: Add createResearchSession to trends API**

In `frontend/src/lib/api/trends.ts`, add:

```typescript
export interface CreateSessionResponse {
  session_id: string;
  status: string;
  started_at: string;
}

export async function createResearchSession(topicId: string): Promise<CreateSessionResponse> {
  const { data } = await apiClient.post<CreateSessionResponse>("/research/sessions", {
    topic_id: topicId,
  });
  return data;
}
```

- [ ] **Step 5: Wire Generate Article button**

In `frontend/src/app/(dashboard)/topics/page.tsx`, replace the `handleConfirm` function:

```typescript
  async function handleConfirm() {
    const topic = modalTopic;
    closeModal();
    if (!topic) return;
    setToast(`Starting research for "${topic.title}"...`);
    try {
      await createResearchSession(topic.title);
      setToast(`Research started for "${topic.title}". Check Research page for progress.`);
    } catch {
      setToast(`Failed to start research for "${topic.title}".`);
    }
    setTimeout(() => setToast(null), 5000);
  }
```

Add import: `import { createResearchSession } from "@/lib/api/trends";`

Note: The current `POST /research/sessions` expects `topic_id` (UUID), but scanned topics from the frontend don't have UUIDs (they come from the rank response). The persist endpoint saves them with UUIDs, but those aren't returned to the frontend. This may need the persist response to return topic IDs, or the research endpoint to accept topic title instead. Handle gracefully — if it fails, show error toast.

- [ ] **Step 6: Run frontend tests**

Run: `cd D:/Workbench/github/cognify-infra-002/frontend && npm install && npx vitest run 2>&1 | tail -10`

Fix any test failures (hooks changed signatures, may need test updates).

- [ ] **Step 7: Commit**

```bash
cd D:/Workbench/github/cognify-infra-002
git add frontend/src/lib/api/metrics.ts frontend/src/hooks/use-metrics.ts frontend/src/hooks/use-topics.ts frontend/src/app/\(dashboard\)/topics/page.tsx frontend/src/lib/api/trends.ts
git commit -m "feat(infra-002): wire metrics, topics, and generate article to real APIs"
```

---

## Task 4: Test Updates and Final Verification

- [ ] **Step 1: Update frontend tests for changed hooks**

The `use-article-list.test.ts`, `use-article.test.ts`, and `use-metrics.test.ts` tests may need updating since the hooks now call real APIs. Add mocks for the API modules similar to how `use-scan-topics.test.ts` mocks `@/lib/api/trends`.

- [ ] **Step 2: Run full frontend test suite**

Run: `cd D:/Workbench/github/cognify-infra-002/frontend && npx vitest run 2>&1 | tail -10`

- [ ] **Step 3: Run full backend test suite**

Run: `cd D:/Workbench/github/cognify-infra-002 && uv run pytest tests/unit/ -q --tb=short 2>&1 | tail -5`

- [ ] **Step 4: Run lint**

Run: `cd D:/Workbench/github/cognify-infra-002 && uv tool run ruff check src/api/routers/metrics.py src/api/routers/canonical_articles.py 2>&1`

- [ ] **Step 5: Fix issues and commit**

```bash
cd D:/Workbench/github/cognify-infra-002
git add -A && git commit -m "fix(infra-002): update tests for real API hooks"
```
