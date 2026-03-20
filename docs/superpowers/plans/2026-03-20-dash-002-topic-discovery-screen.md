# DASH-002: Topic Discovery Screen — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Topic Discovery page — a filterable, paginated grid of topic cards with progressive scan loading and article generation modal.

**Architecture:** Replace the `/topics` placeholder page with a full implementation using composable hooks (`useScanTopics`, `useTopicFilters`, `useTopicPagination`, `useTopicDiscovery`) and 5 new components (`TopicCard`, `FilterBar`, `ScanProgressBanner`, `TopicPagination`, `GenerateArticleModal`). All data starts as mock; API calls are stubbed for future backend integration.

**Tech Stack:** Next.js 15, React 19, TypeScript, Tailwind v4, shadcn/ui, TanStack Query, Vitest, React Testing Library

**Spec:** `docs/superpowers/specs/2026-03-20-dash-002-topic-discovery-screen-design.md`

**Worktree:** `D:/Workbench/github/cognify-dash-002` (branch: `feature/DASH-002-topic-discovery-screen`)

---

## File Impact Summary

### New Files
| File | Purpose |
|------|---------|
| `frontend/src/types/sources.ts` | `SOURCE_LABELS` constant and `SourceName` type |
| `frontend/src/hooks/use-topic-pagination.ts` | Pagination math hook |
| `frontend/src/hooks/use-topic-pagination.test.ts` | Tests for pagination hook |
| `frontend/src/hooks/use-topic-filters.ts` | Client-side filter hook |
| `frontend/src/hooks/use-topic-filters.test.ts` | Tests for filter hook |
| `frontend/src/hooks/use-scan-topics.ts` | Scan lifecycle hook (mock) |
| `frontend/src/hooks/use-scan-topics.test.ts` | Tests for scan hook |
| `frontend/src/hooks/use-topic-discovery.ts` | Thin orchestrator hook |
| `frontend/src/hooks/use-topic-discovery.test.ts` | Tests for orchestrator hook |
| `frontend/src/components/topics/topic-card.tsx` | Single topic card component |
| `frontend/src/components/topics/topic-card.test.tsx` | Tests for TopicCard |
| `frontend/src/components/topics/scan-progress-banner.tsx` | Scan progress + partial failure |
| `frontend/src/components/topics/scan-progress-banner.test.tsx` | Tests for ScanProgressBanner |
| `frontend/src/components/topics/topic-pagination.tsx` | Page controls component |
| `frontend/src/components/topics/topic-pagination.test.tsx` | Tests for TopicPagination |
| `frontend/src/components/topics/filter-bar.tsx` | Filter controls + topic count |
| `frontend/src/components/topics/filter-bar.test.tsx` | Tests for FilterBar |
| `frontend/src/components/topics/generate-article-modal.tsx` | Confirmation modal |
| `frontend/src/components/topics/generate-article-modal.test.tsx` | Tests for modal |

### Modified Files
| File | Changes |
|------|---------|
| `frontend/src/types/api.ts` | Add `TopicFilters`, `TimeRange`, `ScanState`, `GenerateArticleResponse` |
| `frontend/src/types/domain.ts` | Add `DOMAIN_KEYWORDS` constant |
| `frontend/src/lib/mock/topics.ts` | Expand from 5 to 25 mock topics |
| `frontend/src/app/(dashboard)/topics/page.tsx` | Replace placeholder with full page |

---

## Task 1: Types & Constants

**Files:**
- Modify: `frontend/src/types/api.ts`
- Modify: `frontend/src/types/domain.ts`
- Create: `frontend/src/types/sources.ts`

- [ ] **Step 1: Add topic discovery types to `api.ts`**

Add after the `ApiError` interface at the end of `frontend/src/types/api.ts`:

```typescript
export type TimeRange = "1h" | "24h" | "7d" | "30d" | "all";

export interface TopicFilters {
  sources: string[];
  timeRange: TimeRange;
  domain: string;
}

export interface ScanState {
  isScanning: boolean;
  completedSources: number;
  totalSources: number;
  failedSources: string[];
}

export interface GenerateArticleResponse {
  task_id: string;
  status: "queued";
  estimated_time_seconds: number;
}
```

- [ ] **Step 2: Add `DOMAIN_KEYWORDS` to `domain.ts`**

Add after the `getDomainLabel` function in `frontend/src/types/domain.ts`:

```typescript
export const DOMAIN_KEYWORDS: Record<DomainName, string[]> = {
  cybersecurity: ["cybersecurity", "security", "infosec", "threat", "vulnerability"],
  "ai-ml": ["artificial intelligence", "machine learning", "deep learning", "AI", "ML"],
  cloud: ["cloud computing", "AWS", "Azure", "GCP", "kubernetes"],
  devops: ["devops", "CI/CD", "infrastructure", "deployment", "SRE"],
};
```

- [ ] **Step 3: Create `sources.ts`**

Create `frontend/src/types/sources.ts`:

```typescript
export const SOURCE_NAMES = [
  "google_trends",
  "reddit",
  "hackernews",
  "newsapi",
  "arxiv",
] as const;

export type SourceName = (typeof SOURCE_NAMES)[number];

export const SOURCE_LABELS: Record<SourceName, string> = {
  google_trends: "Google Trends",
  reddit: "Reddit",
  hackernews: "Hacker News",
  newsapi: "NewsAPI",
  arxiv: "arXiv",
};

export function getSourceLabel(source: string): string {
  return SOURCE_LABELS[source as SourceName] ?? source;
}
```

- [ ] **Step 4: Commit**

```bash
cd D:/Workbench/github/cognify-dash-002
git add frontend/src/types/api.ts frontend/src/types/domain.ts frontend/src/types/sources.ts
git commit -m "feat(dash-002): add topic discovery types, domain keywords, source labels"
```

---

## Task 2: Expand Mock Data

**Files:**
- Modify: `frontend/src/lib/mock/topics.ts`

- [ ] **Step 1: Expand mock topics to 25 entries**

Replace `frontend/src/lib/mock/topics.ts` with 25 topics covering all 5 sources, multiple domains, all 4 trend statuses, varied scores (30-98), and varied `discovered_at` times spanning the last 7 days. This provides enough data for pagination testing (3 pages of 10).

Key diversity requirements:
- Sources: at least 4 each of `google_trends`, `reddit`, `hackernews`, `newsapi`, `arxiv`
- Domains: mix of `cybersecurity`, `ai-ml`, `cloud`, `devops`
- Trend statuses: mix of `trending`, `new`, `rising`, `steady`
- Scores: range from 30 to 98
- Times: spread across last 7 days for time range filter testing
- Ranks: 1-25

- [ ] **Step 2: Commit**

```bash
cd D:/Workbench/github/cognify-dash-002
git add frontend/src/lib/mock/topics.ts
git commit -m "feat(dash-002): expand mock topics to 25 for pagination and filter testing"
```

---

## Task 3: `useTopicPagination` Hook (TDD)

**Files:**
- Create: `frontend/src/hooks/use-topic-pagination.test.ts`
- Create: `frontend/src/hooks/use-topic-pagination.ts`

- [ ] **Step 1: Write failing tests**

Create `frontend/src/hooks/use-topic-pagination.test.ts`:

```typescript
import { describe, it, expect } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useTopicPagination } from "./use-topic-pagination";

const items = Array.from({ length: 25 }, (_, i) => ({ id: i }));

describe("useTopicPagination", () => {
  it("returns first page of 10 items", () => {
    const { result } = renderHook(() => useTopicPagination(items));
    expect(result.current.paginatedItems).toHaveLength(10);
    expect(result.current.page).toBe(1);
    expect(result.current.totalPages).toBe(3);
  });

  it("navigates to page 2", () => {
    const { result } = renderHook(() => useTopicPagination(items));
    act(() => result.current.setPage(2));
    expect(result.current.page).toBe(2);
    expect(result.current.paginatedItems).toHaveLength(10);
    expect(result.current.paginatedItems[0]).toEqual({ id: 10 });
  });

  it("last page has partial items", () => {
    const { result } = renderHook(() => useTopicPagination(items));
    act(() => result.current.setPage(3));
    expect(result.current.paginatedItems).toHaveLength(5);
  });

  it("clamps to valid page range", () => {
    const { result } = renderHook(() => useTopicPagination(items));
    act(() => result.current.setPage(99));
    expect(result.current.page).toBe(3);
    act(() => result.current.setPage(0));
    expect(result.current.page).toBe(1);
  });

  it("resets to page 1 when items change", () => {
    const { result, rerender } = renderHook(
      ({ items }) => useTopicPagination(items),
      { initialProps: { items } },
    );
    act(() => result.current.setPage(3));
    rerender({ items: items.slice(0, 5) });
    expect(result.current.page).toBe(1);
    expect(result.current.totalPages).toBe(1);
  });

  it("handles empty items", () => {
    const { result } = renderHook(() => useTopicPagination([]));
    expect(result.current.paginatedItems).toHaveLength(0);
    expect(result.current.totalPages).toBe(0);
    expect(result.current.page).toBe(1);
  });
});
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `cd D:/Workbench/github/cognify-dash-002/frontend && npx vitest run src/hooks/use-topic-pagination.test.ts`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `use-topic-pagination.ts`**

Create `frontend/src/hooks/use-topic-pagination.ts`:

```typescript
import { useState, useMemo, useEffect, useRef } from "react";

const PAGE_SIZE = 10;

export function useTopicPagination<T>(items: T[]) {
  const [page, setPageRaw] = useState(1);
  const totalPages = Math.ceil(items.length / PAGE_SIZE);
  const prevItemsRef = useRef(items);

  useEffect(() => {
    if (prevItemsRef.current !== items) {
      setPageRaw(1);
      prevItemsRef.current = items;
    }
  }, [items]);

  const setPage = (n: number) => {
    setPageRaw(Math.max(1, Math.min(n, totalPages || 1)));
  };

  const paginatedItems = useMemo(() => {
    const start = (page - 1) * PAGE_SIZE;
    return items.slice(start, start + PAGE_SIZE);
  }, [items, page]);

  return { paginatedItems, page, totalPages, setPage };
}
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `cd D:/Workbench/github/cognify-dash-002/frontend && npx vitest run src/hooks/use-topic-pagination.test.ts`
Expected: All 6 tests pass.

- [ ] **Step 5: Commit**

```bash
cd D:/Workbench/github/cognify-dash-002
git add frontend/src/hooks/use-topic-pagination.ts frontend/src/hooks/use-topic-pagination.test.ts
git commit -m "feat(dash-002): add useTopicPagination hook with TDD"
```

---

## Task 4: `useTopicFilters` Hook (TDD)

**Files:**
- Create: `frontend/src/hooks/use-topic-filters.test.ts`
- Create: `frontend/src/hooks/use-topic-filters.ts`

- [ ] **Step 1: Write failing tests**

Create `frontend/src/hooks/use-topic-filters.test.ts`:

```typescript
import { describe, it, expect } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useTopicFilters } from "./use-topic-filters";
import type { RankedTopic } from "@/types/api";

const now = new Date().toISOString();
const twoDaysAgo = new Date(Date.now() - 2 * 86400000).toISOString();
const tenDaysAgo = new Date(Date.now() - 10 * 86400000).toISOString();

const topics: RankedTopic[] = [
  { title: "A", source: "reddit", domain: "cybersecurity", discovered_at: now, trend_status: "trending" } as RankedTopic,
  { title: "B", source: "hackernews", domain: "ai-ml", discovered_at: twoDaysAgo, trend_status: "new" } as RankedTopic,
  { title: "C", source: "reddit", domain: "cybersecurity", discovered_at: tenDaysAgo, trend_status: "steady" } as RankedTopic,
];

describe("useTopicFilters", () => {
  it("returns all topics with default filters", () => {
    const { result } = renderHook(() => useTopicFilters(topics));
    expect(result.current.filteredTopics).toHaveLength(3);
  });

  it("filters by source", () => {
    const { result } = renderHook(() => useTopicFilters(topics));
    act(() => result.current.setFilters({ sources: ["reddit"] }));
    expect(result.current.filteredTopics).toHaveLength(2);
  });

  it("filters by domain", () => {
    const { result } = renderHook(() => useTopicFilters(topics));
    act(() => result.current.setFilters({ domain: "ai-ml" }));
    expect(result.current.filteredTopics).toHaveLength(1);
    expect(result.current.filteredTopics[0].title).toBe("B");
  });

  it("filters by time range", () => {
    const { result } = renderHook(() => useTopicFilters(topics));
    act(() => result.current.setFilters({ timeRange: "24h" }));
    expect(result.current.filteredTopics).toHaveLength(1);
    expect(result.current.filteredTopics[0].title).toBe("A");
  });

  it("combines filters", () => {
    const { result } = renderHook(() => useTopicFilters(topics));
    act(() => result.current.setFilters({ sources: ["reddit"], domain: "cybersecurity", timeRange: "all" }));
    expect(result.current.filteredTopics).toHaveLength(2);
  });

  it("empty sources means all sources", () => {
    const { result } = renderHook(() => useTopicFilters(topics));
    act(() => result.current.setFilters({ sources: [] }));
    expect(result.current.filteredTopics).toHaveLength(3);
  });
});
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `cd D:/Workbench/github/cognify-dash-002/frontend && npx vitest run src/hooks/use-topic-filters.test.ts`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `use-topic-filters.ts`**

Create `frontend/src/hooks/use-topic-filters.ts`:

```typescript
import { useState, useMemo } from "react";
import type { RankedTopic, TopicFilters } from "@/types/api";

const TIME_RANGE_MS: Record<string, number> = {
  "1h": 3600000,
  "24h": 86400000,
  "7d": 604800000,
  "30d": 2592000000,
};

const DEFAULT_FILTERS: TopicFilters = {
  sources: [],
  timeRange: "7d",
  domain: "",
};

export function useTopicFilters(topics: RankedTopic[]) {
  const [filters, setFiltersState] = useState<TopicFilters>(DEFAULT_FILTERS);

  const setFilters = (update: Partial<TopicFilters>) => {
    setFiltersState((prev) => ({ ...prev, ...update }));
  };

  const filteredTopics = useMemo(() => {
    const now = Date.now();
    return topics.filter((t) => {
      if (filters.sources.length > 0 && !filters.sources.includes(t.source)) return false;
      if (filters.domain && t.domain !== filters.domain) return false;
      if (filters.timeRange !== "all") {
        const ms = TIME_RANGE_MS[filters.timeRange];
        if (ms && now - new Date(t.discovered_at).getTime() > ms) return false;
      }
      return true;
    });
  }, [topics, filters]);

  return { filteredTopics, filters, setFilters };
}
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `cd D:/Workbench/github/cognify-dash-002/frontend && npx vitest run src/hooks/use-topic-filters.test.ts`
Expected: All 6 tests pass.

- [ ] **Step 5: Commit**

```bash
cd D:/Workbench/github/cognify-dash-002
git add frontend/src/hooks/use-topic-filters.ts frontend/src/hooks/use-topic-filters.test.ts
git commit -m "feat(dash-002): add useTopicFilters hook with TDD"
```

---

## Task 5: `useScanTopics` Hook (TDD)

**Files:**
- Create: `frontend/src/hooks/use-scan-topics.test.ts`
- Create: `frontend/src/hooks/use-scan-topics.ts`

This hook manages the scan lifecycle. For the mock-first approach, it returns mock data with simulated delay instead of calling real APIs. The scan flow simulates progressive loading.

- [ ] **Step 1: Write failing tests**

Create `frontend/src/hooks/use-scan-topics.test.ts`:

```typescript
import { describe, it, expect, vi } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { useScanTopics } from "./use-scan-topics";

describe("useScanTopics", () => {
  it("starts with empty topics and idle scan state", () => {
    const { result } = renderHook(() => useScanTopics());
    expect(result.current.topics).toHaveLength(0);
    expect(result.current.scanState.isScanning).toBe(false);
  });

  it("sets isScanning to true during scan", async () => {
    const { result } = renderHook(() => useScanTopics());
    act(() => { result.current.startScan("cybersecurity"); });
    expect(result.current.scanState.isScanning).toBe(true);
  });

  it("populates topics after scan completes", async () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => useScanTopics());
    act(() => { result.current.startScan("cybersecurity"); });
    await act(async () => { vi.advanceTimersByTime(3000); });
    await waitFor(() => {
      expect(result.current.scanState.isScanning).toBe(false);
    });
    expect(result.current.topics.length).toBeGreaterThan(0);
    vi.useRealTimers();
  });

  it("tracks completed sources during scan", async () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => useScanTopics());
    act(() => { result.current.startScan("cybersecurity"); });
    expect(result.current.scanState.totalSources).toBe(5);
    await act(async () => { vi.advanceTimersByTime(3000); });
    await waitFor(() => {
      expect(result.current.scanState.completedSources).toBe(5);
    });
    vi.useRealTimers();
  });
});
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `cd D:/Workbench/github/cognify-dash-002/frontend && npx vitest run src/hooks/use-scan-topics.test.ts`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `use-scan-topics.ts`**

Create `frontend/src/hooks/use-scan-topics.ts`. This uses mock data with staggered timeouts to simulate progressive loading:

```typescript
import { useState, useCallback, useRef } from "react";
import type { RankedTopic, ScanState } from "@/types/api";
import { mockTopics } from "@/lib/mock/topics";
import { SOURCE_NAMES } from "@/types/sources";

const INITIAL_SCAN: ScanState = {
  isScanning: false,
  completedSources: 0,
  totalSources: 5,
  failedSources: [],
};

function deriveTrendStatus(topic: RankedTopic): RankedTopic["trend_status"] {
  const hoursAgo = (Date.now() - new Date(topic.discovered_at).getTime()) / 3600000;
  if (topic.velocity >= 50 && topic.composite_score >= 80) return "trending";
  if (topic.velocity >= 30) return "rising";
  if (hoursAgo <= 24) return "new";
  return "steady";
}

export function useScanTopics() {
  const [topics, setTopics] = useState<RankedTopic[]>([]);
  const [scanState, setScanState] = useState<ScanState>(INITIAL_SCAN);
  const abortRef = useRef<AbortController | null>(null);

  const startScan = useCallback(async (domain: string) => {
    abortRef.current?.abort();
    abortRef.current = new AbortController();
    setScanState({ ...INITIAL_SCAN, isScanning: true });
    setTopics([]);

    // Mock: simulate staggered source completions
    const perSource = SOURCE_NAMES.map((_, i) =>
      new Promise<void>((resolve) =>
        setTimeout(() => {
          setScanState((s) => ({ ...s, completedSources: s.completedSources + 1 }));
          resolve();
        }, (i + 1) * 400),
      ),
    );

    await Promise.all(perSource);

    // Mock: filter by domain and enrich with derived fields
    const filtered = mockTopics
      .filter((t) => t.domain === domain || domain === "")
      .map((t) => ({ ...t, trend_status: deriveTrendStatus(t) }));

    setTopics(filtered);
    setScanState((s) => ({ ...s, isScanning: false }));
  }, []);

  return { topics, scanState, startScan };
}
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `cd D:/Workbench/github/cognify-dash-002/frontend && npx vitest run src/hooks/use-scan-topics.test.ts`
Expected: All 4 tests pass.

- [ ] **Step 5: Commit**

```bash
cd D:/Workbench/github/cognify-dash-002
git add frontend/src/hooks/use-scan-topics.ts frontend/src/hooks/use-scan-topics.test.ts
git commit -m "feat(dash-002): add useScanTopics hook with mock progressive loading"
```

---

## Task 6: `useTopicDiscovery` Orchestrator Hook (TDD)

**Files:**
- Create: `frontend/src/hooks/use-topic-discovery.test.ts`
- Create: `frontend/src/hooks/use-topic-discovery.ts`

- [ ] **Step 1: Write failing tests**

Create `frontend/src/hooks/use-topic-discovery.test.ts`:

```typescript
import { describe, it, expect } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useTopicDiscovery } from "./use-topic-discovery";
import type { RankedTopic } from "@/types/api";

describe("useTopicDiscovery", () => {
  it("starts with null modalTopic", () => {
    const { result } = renderHook(() => useTopicDiscovery());
    expect(result.current.modalTopic).toBeNull();
  });

  it("opens and closes modal", () => {
    const { result } = renderHook(() => useTopicDiscovery());
    const fakeTopic: RankedTopic = {
      title: "Test", description: "", source: "reddit", external_url: "",
      trend_score: 50, discovered_at: new Date().toISOString(), velocity: 10,
      domain_keywords: [], composite_score: 50, rank: 1, source_count: 1,
      domain: "cybersecurity", trend_status: "steady",
    };
    act(() => result.current.openModal(fakeTopic));
    expect(result.current.modalTopic).toEqual(fakeTopic);
    act(() => result.current.closeModal());
    expect(result.current.modalTopic).toBeNull();
  });

  it("exposes scan state from useScanTopics", () => {
    const { result } = renderHook(() => useTopicDiscovery());
    expect(result.current.scanState.isScanning).toBe(false);
  });

  it("exposes filter state", () => {
    const { result } = renderHook(() => useTopicDiscovery());
    expect(result.current.filters.timeRange).toBe("7d");
  });

  it("exposes pagination state", () => {
    const { result } = renderHook(() => useTopicDiscovery());
    expect(result.current.page).toBe(1);
  });
});
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `cd D:/Workbench/github/cognify-dash-002/frontend && npx vitest run src/hooks/use-topic-discovery.test.ts`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `use-topic-discovery.ts`**

Create `frontend/src/hooks/use-topic-discovery.ts`:

```typescript
import { useState, useCallback } from "react";
import type { RankedTopic } from "@/types/api";
import { useScanTopics } from "./use-scan-topics";
import { useTopicFilters } from "./use-topic-filters";
import { useTopicPagination } from "./use-topic-pagination";

export function useTopicDiscovery() {
  const { topics, scanState, startScan } = useScanTopics();
  const { filteredTopics, filters, setFilters } = useTopicFilters(topics);
  const { paginatedItems, page, totalPages, setPage } = useTopicPagination(filteredTopics);

  const [modalTopic, setModalTopic] = useState<RankedTopic | null>(null);
  const openModal = useCallback((t: RankedTopic) => setModalTopic(t), []);
  const closeModal = useCallback(() => setModalTopic(null), []);

  return {
    topics: paginatedItems,
    totalTopics: filteredTopics.length,
    scanState,
    startScan,
    filters,
    setFilters,
    page,
    totalPages,
    setPage,
    modalTopic,
    openModal,
    closeModal,
  };
}
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `cd D:/Workbench/github/cognify-dash-002/frontend && npx vitest run src/hooks/use-topic-discovery.test.ts`
Expected: All 5 tests pass.

- [ ] **Step 5: Commit**

```bash
cd D:/Workbench/github/cognify-dash-002
git add frontend/src/hooks/use-topic-discovery.ts frontend/src/hooks/use-topic-discovery.test.ts
git commit -m "feat(dash-002): add useTopicDiscovery orchestrator hook"
```

---

## Task 7: `TopicCard` Component (TDD)

**Files:**
- Create: `frontend/src/components/topics/topic-card.test.tsx`
- Create: `frontend/src/components/topics/topic-card.tsx`

- [ ] **Step 1: Write failing tests**

Create `frontend/src/components/topics/topic-card.test.tsx`:

```typescript
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { TopicCard } from "./topic-card";
import type { RankedTopic } from "@/types/api";

const mockTopic: RankedTopic = {
  title: "AI-Powered Phishing Detection",
  description: "New machine learning approaches to detecting sophisticated phishing attacks",
  source: "google_trends",
  external_url: "",
  trend_score: 94,
  discovered_at: new Date().toISOString(),
  velocity: 55,
  domain_keywords: ["phishing", "ai"],
  composite_score: 94,
  rank: 1,
  source_count: 3,
  domain: "cybersecurity",
  trend_status: "trending",
};

describe("TopicCard", () => {
  it("renders topic title", () => {
    render(<TopicCard topic={mockTopic} onRequestGeneration={vi.fn()} />);
    expect(screen.getByText("AI-Powered Phishing Detection")).toBeInTheDocument();
  });

  it("renders description", () => {
    render(<TopicCard topic={mockTopic} onRequestGeneration={vi.fn()} />);
    expect(screen.getByText(/machine learning approaches/)).toBeInTheDocument();
  });

  it("renders composite score", () => {
    render(<TopicCard topic={mockTopic} onRequestGeneration={vi.fn()} />);
    expect(screen.getByText("94")).toBeInTheDocument();
  });

  it("renders trend badge", () => {
    render(<TopicCard topic={mockTopic} onRequestGeneration={vi.fn()} />);
    expect(screen.getByText("Trending")).toBeInTheDocument();
  });

  it("renders source label", () => {
    render(<TopicCard topic={mockTopic} onRequestGeneration={vi.fn()} />);
    expect(screen.getByText("Google Trends")).toBeInTheDocument();
  });

  it("calls onRequestGeneration when Generate Article is clicked", () => {
    const handler = vi.fn();
    render(<TopicCard topic={mockTopic} onRequestGeneration={handler} />);
    fireEvent.click(screen.getByText("Generate Article"));
    expect(handler).toHaveBeenCalledWith(mockTopic);
  });
});
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `cd D:/Workbench/github/cognify-dash-002/frontend && npx vitest run src/components/topics/topic-card.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `topic-card.tsx`**

Create `frontend/src/components/topics/topic-card.tsx`:

```tsx
import { TrendBadge } from "@/components/common/trend-badge";
import { DomainBadge } from "@/components/common/domain-badge";
import { getSourceLabel } from "@/types/sources";
import type { RankedTopic } from "@/types/api";

interface TopicCardProps {
  topic: RankedTopic;
  onRequestGeneration: (topic: RankedTopic) => void;
}

function formatTimeAgo(dateStr: string): string {
  const hours = Math.floor((Date.now() - new Date(dateStr).getTime()) / 3600000);
  if (hours < 1) return "Just now";
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

export function TopicCard({ topic, onRequestGeneration }: TopicCardProps) {
  return (
    <div className="flex flex-col justify-between rounded-lg border border-neutral-200 bg-white p-5 shadow-sm transition-shadow hover:shadow-md">
      <div>
        <div className="flex items-start justify-between">
          <TrendBadge variant={topic.trend_status} />
          <span className="text-sm font-semibold text-neutral-500">
            Score: <span className="text-neutral-900">{topic.composite_score}</span>
          </span>
        </div>
        <h3 className="mt-3 font-heading text-base font-semibold text-neutral-900">
          {topic.title}
        </h3>
        <p className="mt-1.5 line-clamp-2 text-sm text-neutral-500">
          {topic.description}
        </p>
      </div>
      <div className="mt-4 flex items-center justify-between">
        <div className="flex items-center gap-2 text-xs text-neutral-400">
          <DomainBadge domain={topic.domain} />
          <span>{getSourceLabel(topic.source)}</span>
          <span>{formatTimeAgo(topic.discovered_at)}</span>
        </div>
        <button
          onClick={() => onRequestGeneration(topic)}
          className="text-sm font-medium text-primary hover:underline"
        >
          Generate Article
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `cd D:/Workbench/github/cognify-dash-002/frontend && npx vitest run src/components/topics/topic-card.test.tsx`
Expected: All 6 tests pass.

- [ ] **Step 5: Commit**

```bash
cd D:/Workbench/github/cognify-dash-002
git add frontend/src/components/topics/topic-card.tsx frontend/src/components/topics/topic-card.test.tsx
git commit -m "feat(dash-002): add TopicCard component with TDD"
```

---

## Task 8: `ScanProgressBanner` Component (TDD)

**Files:**
- Create: `frontend/src/components/topics/scan-progress-banner.test.tsx`
- Create: `frontend/src/components/topics/scan-progress-banner.tsx`

- [ ] **Step 1: Write failing tests**

Create `frontend/src/components/topics/scan-progress-banner.test.tsx`:

```typescript
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ScanProgressBanner } from "./scan-progress-banner";

describe("ScanProgressBanner", () => {
  it("shows scanning progress with 0 completed", () => {
    render(<ScanProgressBanner isScanning={true} completedSources={0} totalSources={5} failedSources={[]} />);
    expect(screen.getByText(/0 of 5 sources complete/)).toBeInTheDocument();
  });

  it("shows scanning progress mid-scan", () => {
    render(<ScanProgressBanner isScanning={true} completedSources={3} totalSources={5} failedSources={[]} />);
    expect(screen.getByText(/3 of 5 sources complete/)).toBeInTheDocument();
  });

  it("shows partial failure warning after scan", () => {
    render(<ScanProgressBanner isScanning={false} completedSources={5} totalSources={5} failedSources={["reddit"]} />);
    expect(screen.getByText(/1 of 5 sources failed/)).toBeInTheDocument();
  });

  it("renders nothing when idle with no failures", () => {
    const { container } = render(
      <ScanProgressBanner isScanning={false} completedSources={0} totalSources={5} failedSources={[]} />,
    );
    expect(container.firstChild).toBeNull();
  });
});
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `cd D:/Workbench/github/cognify-dash-002/frontend && npx vitest run src/components/topics/scan-progress-banner.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `scan-progress-banner.tsx`**

Create `frontend/src/components/topics/scan-progress-banner.tsx`:

```tsx
interface ScanProgressBannerProps {
  isScanning: boolean;
  completedSources: number;
  totalSources: number;
  failedSources: string[];
}

export function ScanProgressBanner({ isScanning, completedSources, totalSources, failedSources }: ScanProgressBannerProps) {
  const hasFailures = !isScanning && failedSources.length > 0;

  if (!isScanning && !hasFailures) return null;

  if (hasFailures) {
    return (
      <div className="rounded-lg border border-accent/30 bg-accent-light px-4 py-3 text-sm text-accent">
        {failedSources.length} of {totalSources} sources failed to respond. Results may be incomplete.
      </div>
    );
  }

  const pct = Math.round((completedSources / totalSources) * 100);
  return (
    <div className="rounded-lg border border-info/30 bg-info-light px-4 py-3">
      <div className="flex items-center justify-between text-sm text-info">
        <span>Scanning... {completedSources} of {totalSources} sources complete</span>
        <span>{pct}%</span>
      </div>
      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-info/20">
        <div className="h-full rounded-full bg-info transition-all" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `cd D:/Workbench/github/cognify-dash-002/frontend && npx vitest run src/components/topics/scan-progress-banner.test.tsx`
Expected: All 3 tests pass.

- [ ] **Step 5: Commit**

```bash
cd D:/Workbench/github/cognify-dash-002
git add frontend/src/components/topics/scan-progress-banner.tsx frontend/src/components/topics/scan-progress-banner.test.tsx
git commit -m "feat(dash-002): add ScanProgressBanner component with TDD"
```

---

## Task 9: `TopicPagination` Component (TDD)

**Files:**
- Create: `frontend/src/components/topics/topic-pagination.test.tsx`
- Create: `frontend/src/components/topics/topic-pagination.tsx`

- [ ] **Step 1: Write failing tests**

Create `frontend/src/components/topics/topic-pagination.test.tsx`:

```typescript
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { TopicPagination } from "./topic-pagination";

describe("TopicPagination", () => {
  it("renders page info", () => {
    render(<TopicPagination currentPage={1} totalPages={5} onPageChange={vi.fn()} />);
    expect(screen.getByText("Page 1 of 5")).toBeInTheDocument();
  });

  it("disables Previous on first page", () => {
    render(<TopicPagination currentPage={1} totalPages={5} onPageChange={vi.fn()} />);
    expect(screen.getByText("Previous")).toBeDisabled();
  });

  it("disables Next on last page", () => {
    render(<TopicPagination currentPage={5} totalPages={5} onPageChange={vi.fn()} />);
    expect(screen.getByText("Next")).toBeDisabled();
  });

  it("calls onPageChange with next page", () => {
    const handler = vi.fn();
    render(<TopicPagination currentPage={2} totalPages={5} onPageChange={handler} />);
    fireEvent.click(screen.getByText("Next"));
    expect(handler).toHaveBeenCalledWith(3);
  });

  it("calls onPageChange with previous page", () => {
    const handler = vi.fn();
    render(<TopicPagination currentPage={3} totalPages={5} onPageChange={handler} />);
    fireEvent.click(screen.getByText("Previous"));
    expect(handler).toHaveBeenCalledWith(2);
  });

  it("renders nothing when totalPages is 0", () => {
    const { container } = render(
      <TopicPagination currentPage={1} totalPages={0} onPageChange={vi.fn()} />,
    );
    expect(container.firstChild).toBeNull();
  });
});
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `cd D:/Workbench/github/cognify-dash-002/frontend && npx vitest run src/components/topics/topic-pagination.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `topic-pagination.tsx`**

Create `frontend/src/components/topics/topic-pagination.tsx`:

```tsx
import { Button } from "@/components/ui/button";
import { ChevronLeft, ChevronRight } from "lucide-react";

interface TopicPaginationProps {
  currentPage: number;
  totalPages: number;
  onPageChange: (page: number) => void;
}

export function TopicPagination({ currentPage, totalPages, onPageChange }: TopicPaginationProps) {
  if (totalPages <= 0) return null;

  return (
    <div className="flex items-center justify-center gap-4 pt-4">
      <Button
        variant="outline"
        size="sm"
        disabled={currentPage <= 1}
        onClick={() => onPageChange(currentPage - 1)}
      >
        <ChevronLeft className="mr-1 h-4 w-4" />
        Previous
      </Button>
      <span className="text-sm text-neutral-500">
        Page {currentPage} of {totalPages}
      </span>
      <Button
        variant="outline"
        size="sm"
        disabled={currentPage >= totalPages}
        onClick={() => onPageChange(currentPage + 1)}
      >
        Next
        <ChevronRight className="ml-1 h-4 w-4" />
      </Button>
    </div>
  );
}
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `cd D:/Workbench/github/cognify-dash-002/frontend && npx vitest run src/components/topics/topic-pagination.test.tsx`
Expected: All 6 tests pass.

- [ ] **Step 5: Commit**

```bash
cd D:/Workbench/github/cognify-dash-002
git add frontend/src/components/topics/topic-pagination.tsx frontend/src/components/topics/topic-pagination.test.tsx
git commit -m "feat(dash-002): add TopicPagination component with TDD"
```

---

## Task 10: `FilterBar` Component (TDD)

**Files:**
- Create: `frontend/src/components/topics/filter-bar.test.tsx`
- Create: `frontend/src/components/topics/filter-bar.tsx`

- [ ] **Step 1: Write failing tests**

Create `frontend/src/components/topics/filter-bar.test.tsx`:

```typescript
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { FilterBar } from "./filter-bar";
import type { TopicFilters } from "@/types/api";

const defaultFilters: TopicFilters = { sources: [], timeRange: "7d", domain: "" };

describe("FilterBar", () => {
  it("renders topic count", () => {
    render(<FilterBar filters={defaultFilters} onFilterChange={vi.fn()} topicCount={42} />);
    expect(screen.getByText("42 Topics Found")).toBeInTheDocument();
  });

  it("shows All Sources when no sources selected", () => {
    render(<FilterBar filters={defaultFilters} onFilterChange={vi.fn()} topicCount={0} />);
    expect(screen.getByText("All Sources")).toBeInTheDocument();
  });

  it("shows domain selector with All Domains default", () => {
    render(<FilterBar filters={defaultFilters} onFilterChange={vi.fn()} topicCount={0} />);
    expect(screen.getByText("All Domains")).toBeInTheDocument();
  });

  it("calls onFilterChange when domain changes", () => {
    const handler = vi.fn();
    render(<FilterBar filters={defaultFilters} onFilterChange={handler} topicCount={0} />);
    fireEvent.change(screen.getByDisplayValue("All Domains"), { target: { value: "cybersecurity" } });
    expect(handler).toHaveBeenCalledWith({ domain: "cybersecurity" });
  });

  it("calls onFilterChange when time range changes", () => {
    const handler = vi.fn();
    render(<FilterBar filters={defaultFilters} onFilterChange={handler} topicCount={0} />);
    fireEvent.change(screen.getByDisplayValue("Last 7 Days"), { target: { value: "24h" } });
    expect(handler).toHaveBeenCalledWith({ timeRange: "24h" });
  });

  it("toggles source selection in multi-select", () => {
    const handler = vi.fn();
    render(<FilterBar filters={defaultFilters} onFilterChange={handler} topicCount={0} />);
    fireEvent.click(screen.getByText("All Sources"));
    fireEvent.click(screen.getByText("Reddit"));
    expect(handler).toHaveBeenCalledWith({ sources: ["reddit"] });
  });
});
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `cd D:/Workbench/github/cognify-dash-002/frontend && npx vitest run src/components/topics/filter-bar.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `filter-bar.tsx`**

Create `frontend/src/components/topics/filter-bar.tsx`. Use native `<select>` elements styled with Tailwind for simplicity. The source multi-select uses a dropdown with checkboxes:

```tsx
import { useState, useRef, useEffect } from "react";
import type { TopicFilters } from "@/types/api";
import { SOURCE_NAMES, SOURCE_LABELS } from "@/types/sources";
import { DOMAIN_LABELS, type DomainName } from "@/types/domain";

interface FilterBarProps {
  filters: TopicFilters;
  onFilterChange: (update: Partial<TopicFilters>) => void;
  topicCount: number;
}

const TIME_OPTIONS = [
  { value: "1h", label: "Last Hour" },
  { value: "24h", label: "Last 24 Hours" },
  { value: "7d", label: "Last 7 Days" },
  { value: "30d", label: "Last 30 Days" },
  { value: "all", label: "All Time" },
] as const;

function SourceMultiSelect({ selected, onChange }: { selected: string[]; onChange: (s: string[]) => void }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const label = selected.length === 0 ? "All Sources" : `${selected.length} selected`;

  const toggle = (source: string) => {
    const next = selected.includes(source)
      ? selected.filter((s) => s !== source)
      : [...selected, source];
    onChange(next);
  };

  return (
    <div ref={ref} className="relative">
      <button onClick={() => setOpen(!open)} className="flex h-9 items-center gap-2 rounded-lg border border-neutral-200 bg-white px-3 text-sm text-neutral-700">
        {label}
      </button>
      {open && (
        <div className="absolute left-0 top-full z-10 mt-1 w-48 rounded-lg border border-neutral-200 bg-white py-1 shadow-md">
          {SOURCE_NAMES.map((name) => (
            <label key={name} className="flex cursor-pointer items-center gap-2 px-3 py-1.5 text-sm hover:bg-neutral-50">
              <input type="checkbox" checked={selected.includes(name)} onChange={() => toggle(name)} className="rounded" />
              {SOURCE_LABELS[name]}
            </label>
          ))}
        </div>
      )}
    </div>
  );
}

export function FilterBar({ filters, onFilterChange, topicCount }: FilterBarProps) {
  return (
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-3">
        <SourceMultiSelect selected={filters.sources} onChange={(sources) => onFilterChange({ sources })} />
        <select
          value={filters.timeRange}
          onChange={(e) => onFilterChange({ timeRange: e.target.value as TopicFilters["timeRange"] })}
          className="h-9 rounded-lg border border-neutral-200 bg-white px-3 text-sm text-neutral-700"
        >
          {TIME_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
        <select
          value={filters.domain}
          onChange={(e) => onFilterChange({ domain: e.target.value })}
          className="h-9 rounded-lg border border-neutral-200 bg-white px-3 text-sm text-neutral-700"
        >
          <option value="">All Domains</option>
          {(Object.keys(DOMAIN_LABELS) as DomainName[]).map((d) => (
            <option key={d} value={d}>{DOMAIN_LABELS[d]}</option>
          ))}
        </select>
      </div>
      <span className="text-sm text-neutral-500">{topicCount} Topics Found</span>
    </div>
  );
}
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `cd D:/Workbench/github/cognify-dash-002/frontend && npx vitest run src/components/topics/filter-bar.test.tsx`
Expected: All 5 tests pass.

- [ ] **Step 5: Commit**

```bash
cd D:/Workbench/github/cognify-dash-002
git add frontend/src/components/topics/filter-bar.tsx frontend/src/components/topics/filter-bar.test.tsx
git commit -m "feat(dash-002): add FilterBar component with source multi-select"
```

---

## Task 11: `GenerateArticleModal` Component (TDD)

**Files:**
- Create: `frontend/src/components/topics/generate-article-modal.test.tsx`
- Create: `frontend/src/components/topics/generate-article-modal.tsx`

- [ ] **Step 1: Write failing tests**

Create `frontend/src/components/topics/generate-article-modal.test.tsx`:

```typescript
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { GenerateArticleModal } from "./generate-article-modal";
import type { RankedTopic } from "@/types/api";

const mockTopic: RankedTopic = {
  title: "AI-Powered Phishing Detection",
  description: "Test description",
  source: "google_trends",
  external_url: "",
  trend_score: 94,
  discovered_at: new Date().toISOString(),
  velocity: 55,
  domain_keywords: [],
  composite_score: 94,
  rank: 1,
  source_count: 3,
  domain: "cybersecurity",
  trend_status: "trending",
};

describe("GenerateArticleModal", () => {
  it("renders nothing when topic is null", () => {
    const { container } = render(
      <GenerateArticleModal topic={null} onClose={vi.fn()} onConfirm={vi.fn()} />,
    );
    expect(container.querySelector("[role='dialog']")).toBeNull();
  });

  it("shows topic title when topic provided", () => {
    render(<GenerateArticleModal topic={mockTopic} onClose={vi.fn()} onConfirm={vi.fn()} />);
    expect(screen.getByText("AI-Powered Phishing Detection")).toBeInTheDocument();
  });

  it("shows estimated time message", () => {
    render(<GenerateArticleModal topic={mockTopic} onClose={vi.fn()} onConfirm={vi.fn()} />);
    expect(screen.getByText(/2-5 minutes/)).toBeInTheDocument();
  });

  it("calls onClose when Cancel clicked", () => {
    const onClose = vi.fn();
    render(<GenerateArticleModal topic={mockTopic} onClose={onClose} onConfirm={vi.fn()} />);
    fireEvent.click(screen.getByText("Cancel"));
    expect(onClose).toHaveBeenCalled();
  });

  it("calls onConfirm when Generate clicked", () => {
    const onConfirm = vi.fn();
    render(<GenerateArticleModal topic={mockTopic} onClose={vi.fn()} onConfirm={onConfirm} />);
    fireEvent.click(screen.getByText("Generate"));
    expect(onConfirm).toHaveBeenCalledWith(mockTopic);
  });
});
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `cd D:/Workbench/github/cognify-dash-002/frontend && npx vitest run src/components/topics/generate-article-modal.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `generate-article-modal.tsx`**

Create `frontend/src/components/topics/generate-article-modal.tsx`:

```tsx
import { Button } from "@/components/ui/button";
import { TrendBadge } from "@/components/common/trend-badge";
import { DomainBadge } from "@/components/common/domain-badge";
import type { RankedTopic } from "@/types/api";

interface GenerateArticleModalProps {
  topic: RankedTopic | null;
  onClose: () => void;
  onConfirm: (topic: RankedTopic) => void;
}

export function GenerateArticleModal({ topic, onClose, onConfirm }: GenerateArticleModalProps) {
  if (!topic) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div
        role="dialog"
        className="w-full max-w-md rounded-xl bg-white p-6 shadow-lg"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="font-heading text-lg font-semibold text-neutral-900">Generate Article</h2>
        <div className="mt-4 space-y-3">
          <div className="flex items-center gap-2">
            <TrendBadge variant={topic.trend_status} />
            <DomainBadge domain={topic.domain} />
          </div>
          <h3 className="font-heading text-base font-medium text-neutral-900">{topic.title}</h3>
          <p className="text-sm text-neutral-500">{topic.description}</p>
          <p className="text-sm text-neutral-500">
            Score: <span className="font-semibold text-neutral-900">{topic.composite_score}</span>
          </p>
        </div>
        <p className="mt-4 text-sm text-neutral-500">
          This will start the content generation pipeline. Estimated time: 2-5 minutes.
        </p>
        <div className="mt-6 flex justify-end gap-3">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={() => onConfirm(topic)}>Generate</Button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `cd D:/Workbench/github/cognify-dash-002/frontend && npx vitest run src/components/topics/generate-article-modal.test.tsx`
Expected: All 5 tests pass.

- [ ] **Step 5: Commit**

```bash
cd D:/Workbench/github/cognify-dash-002
git add frontend/src/components/topics/generate-article-modal.tsx frontend/src/components/topics/generate-article-modal.test.tsx
git commit -m "feat(dash-002): add GenerateArticleModal component with TDD"
```

---

## Task 12: Topics Page Assembly

**Files:**
- Modify: `frontend/src/app/(dashboard)/topics/page.tsx`

- [ ] **Step 1: Replace the placeholder page**

Replace `frontend/src/app/(dashboard)/topics/page.tsx` with the full implementation:

```tsx
"use client";

import { useState } from "react";
import { Zap, Compass, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Header } from "@/components/layout/header";
import { Skeleton } from "@/components/ui/skeleton";
import { TopicCard } from "@/components/topics/topic-card";
import { FilterBar } from "@/components/topics/filter-bar";
import { ScanProgressBanner } from "@/components/topics/scan-progress-banner";
import { TopicPagination } from "@/components/topics/topic-pagination";
import { GenerateArticleModal } from "@/components/topics/generate-article-modal";
import { useTopicDiscovery } from "@/hooks/use-topic-discovery";

function SkeletonGrid() {
  return (
    <div className="grid grid-cols-2 gap-6">
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="rounded-lg border border-neutral-200 p-5">
          <Skeleton className="h-5 w-20" />
          <Skeleton className="mt-3 h-5 w-3/4" />
          <Skeleton className="mt-2 h-10 w-full" />
          <Skeleton className="mt-4 h-4 w-1/2" />
        </div>
      ))}
    </div>
  );
}

function EmptyNoScan() {
  return (
    <div className="flex flex-1 items-center justify-center py-20">
      <div className="text-center">
        <Compass className="mx-auto h-12 w-12 text-neutral-400" />
        <h2 className="mt-4 font-heading text-xl font-semibold text-neutral-900">No topics discovered yet</h2>
        <p className="mt-2 text-sm text-neutral-500">Select a domain and click &apos;New Scan&apos; to discover trending topics.</p>
      </div>
    </div>
  );
}

function EmptyNoMatch() {
  return (
    <div className="flex flex-1 items-center justify-center py-20">
      <div className="text-center">
        <Search className="mx-auto h-12 w-12 text-neutral-400" />
        <h2 className="mt-4 font-heading text-xl font-semibold text-neutral-900">No topics match your filters</h2>
        <p className="mt-2 text-sm text-neutral-500">Try adjusting your source or time range filters.</p>
      </div>
    </div>
  );
}

export default function TopicsPage() {
  const {
    topics, totalTopics, scanState, startScan,
    filters, setFilters, page, totalPages, setPage,
    modalTopic, openModal, closeModal,
  } = useTopicDiscovery();
  const [toast, setToast] = useState<string | null>(null);

  const canScan = !scanState.isScanning && filters.domain !== "";
  const hasDoneAnyScan = scanState.completedSources > 0 || topics.length > 0;

  const handleGenerate = (t: typeof modalTopic) => {
    closeModal();
    if (t) setToast(`Article generation started for "${t.title}"`);
    setTimeout(() => setToast(null), 4000);
  };

  return (
    <div className="space-y-6">
      <Header title="Topic Discovery" subtitle="Real-time trend signals from multiple data sources">
        <Button
          size="sm"
          className="bg-primary hover:bg-primary/90"
          disabled={!canScan}
          onClick={() => startScan(filters.domain)}
          title={filters.domain === "" ? "Select a domain to scan" : undefined}
        >
          <Zap className="mr-2 h-4 w-4" />
          {scanState.isScanning ? "Scanning..." : "New Scan"}
        </Button>
      </Header>

      <FilterBar filters={filters} onFilterChange={setFilters} topicCount={totalTopics} />

      <ScanProgressBanner
        isScanning={scanState.isScanning}
        completedSources={scanState.completedSources}
        totalSources={scanState.totalSources}
        failedSources={scanState.failedSources}
      />

      {scanState.isScanning && topics.length === 0 && <SkeletonGrid />}

      {!scanState.isScanning && !hasDoneAnyScan && <EmptyNoScan />}

      {!scanState.isScanning && hasDoneAnyScan && totalTopics === 0 && <EmptyNoMatch />}

      {topics.length > 0 && (
        <>
          <div className="grid grid-cols-2 gap-6">
            {topics.map((topic) => (
              <TopicCard key={topic.rank} topic={topic} onRequestGeneration={openModal} />
            ))}
          </div>
          <TopicPagination currentPage={page} totalPages={totalPages} onPageChange={setPage} />
        </>
      )}

      <GenerateArticleModal
        topic={modalTopic}
        onClose={closeModal}
        onConfirm={handleGenerate}
      />

      {toast && (
        <div className="fixed bottom-6 right-6 z-50 rounded-lg border border-success/30 bg-success-light px-4 py-3 text-sm text-success shadow-md">
          {toast}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Run frontend tests**

Run: `cd D:/Workbench/github/cognify-dash-002/frontend && npx vitest run`
Expected: All tests pass (existing DASH-001 tests + all new tests).

- [ ] **Step 3: Commit**

```bash
cd D:/Workbench/github/cognify-dash-002
git add frontend/src/app/\(dashboard\)/topics/page.tsx
git commit -m "feat(dash-002): replace topics placeholder with full Topic Discovery page"
```

---

## Task 13: Full Suite Verification & Lint

- [ ] **Step 1: Run all frontend tests**

Run: `cd D:/Workbench/github/cognify-dash-002/frontend && npx vitest run`
Expected: All tests pass.

- [ ] **Step 2: Run backend tests to verify no regressions**

Run: `cd D:/Workbench/github/cognify-dash-002 && uv run python -m pytest --tb=short -q`
Expected: 683 tests pass (no backend changes in this ticket).

- [ ] **Step 3: Lint check**

Run: `cd D:/Workbench/github/cognify-dash-002/frontend && npx tsc --noEmit`
Expected: No TypeScript errors.

- [ ] **Step 4: Verify file sizes**

Run: `wc -l D:/Workbench/github/cognify-dash-002/frontend/src/components/topics/*.tsx D:/Workbench/github/cognify-dash-002/frontend/src/hooks/use-*.ts`
Expected: All under 200 lines.

- [ ] **Step 5: Fix any issues found, commit fixes**

```bash
cd D:/Workbench/github/cognify-dash-002
git add -A
git commit -m "chore(dash-002): fix lint and verification issues"
```
