# DASH-002: Topic Discovery Screen — Design Specification

> **Date**: 2026-03-20
> **Status**: Approved
> **Ticket**: DASH-002
> **Depends on**: DASH-001 (Dashboard Overview — Done)
> **Design reference**: `pencil_designs/cognify.pen` → "Topic Discovery" frame

---

## 1. Overview

The Topic Discovery screen lets users browse, filter, and act on trending topics discovered from multiple data sources. Users can trigger scans, review ranked topics, and initiate article generation.

**Route**: `/topics` (replaces current `PagePlaceholder`)

---

## 2. Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Scan loading UX | Progressive — results appear per source | User wants to see results as they arrive |
| "Generate Article" UX | Confirmation modal + background task | Pipeline takes minutes; user stays on page |
| Source filter | Multi-select | Users want to combine sources (e.g., Reddit + HN) |
| Time range filter | Single-select: Last Hour, 24h, 7 Days, 30 Days, All Time | Standard time buckets |
| Domain filter | Single-select: All Domains + configured domains | "All Domains" added per user request |
| Pagination | 10 per page, max 100 topics | User preference over infinite scroll or fixed top-N |
| Empty states | Two distinct messages (no scan yet / no filter match) | Context-specific guidance |
| Scan button during scan | Disabled until current scan completes | Avoids race conditions; scan completes within ~60s |
| API approach | 5 parallel HTTP requests (one per source) + rank endpoint | Works with both current and ARCH-002 unified endpoint |

---

## 3. Page Layout

```
┌─────────────────────────────────────────────┐
│ Header: "Topic Discovery" + [New Scan] btn  │
│ Subtitle: "Real-time trend signals from     │
│            multiple data sources"            │
├─────────────────────────────────────────────┤
│ Filter Bar:                                  │
│ [Sources ▼] [Time Range ▼] [Domain ▼]       │
│                            "X Topics Found"  │
├─────────────────────────────────────────────┤
│ (Scan Progress Banner — visible during scan) │
│ "Scanning... 3/5 sources complete"           │
├─────────────────────────────────────────────┤
│  ┌──────────────────┐  ┌──────────────────┐ │
│  │ [Trending]       │  │ [New]            │ │
│  │ Topic Title      │  │ Topic Title      │ │
│  │ Description...   │  │ Description...   │ │
│  │ 🏷 Sources  ⏱ 4h │  │ 🏷 Sources  ⏱ 2h │ │
│  │     [Generate ▸] │  │     [Generate ▸] │ │
│  │          Score:94 │  │          Score:88 │ │
│  └──────────────────┘  └──────────────────┘ │
│  ┌──────────────────┐  ┌──────────────────┐ │
│  │ ...              │  │ ...              │ │
│  └──────────────────┘  └──────────────────┘ │
├─────────────────────────────────────────────┤
│ Pagination: [< 1 2 3 ... 10 >]              │
└─────────────────────────────────────────────┘
```

Matches the Pencil design: 2-column card grid, filter bar with 3 controls, header with scan button.

---

## 4. Components

### 4.1 New Components

#### `TopicCard`
- **File**: `frontend/src/components/topics/topic-card.tsx`
- **Props**: `topic: RankedTopic`, `onRequestGeneration: (topic: RankedTopic) => void`
- **Renders**: Card with trend badge (top-left), composite score (top-right), title, description (2-line clamp), source tags, relative time, "Generate Article" link button (bottom-right)
- **Styling**: White bg, border `border-neutral-200`, rounded-lg, shadow-sm, hover shadow-md transition

#### `FilterBar`
- **File**: `frontend/src/components/topics/filter-bar.tsx`
- **Props**: `filters: TopicFilters`, `onFilterChange: (update: Partial<TopicFilters>) => void`, `topicCount: number`
- **Contains**:
  - **Source multi-select**: Checkboxes for Google Trends, Reddit, Hacker News, NewsAPI, arXiv. Dropdown trigger shows "All Sources" or "N selected"
  - **Time range select**: Single-select dropdown — Last Hour, Last 24 Hours, Last 7 Days (default), Last 30 Days, All Time
  - **Domain select**: Single-select dropdown — All Domains (default), Cybersecurity, AI & ML, Cloud, DevOps. Hardcoded for now; will eventually be populated from a settings/config API.
  - **Topic count**: Right-aligned text "X Topics Found"
- **Source labels**: Use a `SOURCE_LABELS` constant mapping machine names to display names (e.g., `google_trends` → "Google Trends", `hackernews` → "Hacker News")

#### `GenerateArticleModal`
- **File**: `frontend/src/components/topics/generate-article-modal.tsx`
- **Props**: `topic: RankedTopic | null`, `isOpen: boolean`, `onClose`, `onConfirm`
- **Content**: Topic title, description, domain badge, trend score, estimated time message, Cancel + Generate buttons
- **On confirm**: Calls mock `POST /api/v1/articles/generate`, shows toast, closes modal

#### `TopicPagination`
- **File**: `frontend/src/components/topics/topic-pagination.tsx`
- **Props**: `currentPage`, `totalPages`, `onPageChange`
- **Renders**: Previous/Next buttons (disabled at boundaries), page numbers with ellipsis for large ranges
- **Config**: 10 items per page, max 100 items (10 pages max)

#### `ScanProgressBanner`
- **File**: `frontend/src/components/topics/scan-progress-banner.tsx`
- **Props**: `completedSources: number`, `totalSources: number`, `failedSources: string[]`
- **States**:
  - Scanning: "Scanning... 3/5 sources complete" with progress bar
  - Partial failure: Warning banner — "2 of 5 sources failed to respond. Results may be incomplete."
  - Hidden when not scanning and no failures

### 4.2 Reused Components (from DASH-001 / Design System)

| Component | From | Usage |
|-----------|------|-------|
| `Header` | `components/dashboard/header.tsx` | Page title + "New Scan" action button |
| `TrendBadge` | `components/common/trend-badge.tsx` | Trending/New/Rising/Steady pill on cards |
| `DomainBadge` | `components/common/domain-badge.tsx` | Colored domain label on cards |
| `Skeleton` | `components/ui/skeleton.tsx` | Loading placeholders for cards |
| `Button` | `components/ui/button.tsx` | Scan button, modal actions, pagination |
| `Card` | `components/ui/card.tsx` | Base for TopicCard |
| `PagePlaceholder` / Empty State | `components/common/page-placeholder.tsx` | Empty states |

---

## 5. Data Flow

### 5.1 Types

```typescript
type TimeRange = "1h" | "24h" | "7d" | "30d" | "all"

interface TopicFilters {
  sources: string[]        // empty = all sources
  timeRange: TimeRange     // default: "7d"
  domain: string           // "" = all domains
}

interface ScanState {
  isScanning: boolean
  completedSources: number
  totalSources: number
  failedSources: string[]
}
```

### 5.2 Composable Hooks

The state is split into focused hooks to stay under file/function size limits:

**`useScanTopics()`** — `frontend/src/hooks/use-scan-topics.ts` (~60 lines)
- Owns scan lifecycle: fires 5 parallel API calls, tracks progress per source
- Returns `{ topics: RankedTopic[], scanState: ScanState, startScan: (domain: string) => Promise<void> }`
- Handles 60s timeout via `AbortController`
- Calls `POST /topics/rank` once all sources settle

**`useTopicFilters(topics)`** — `frontend/src/hooks/use-topic-filters.ts` (~40 lines)
- Owns filter state, applies client-side filtering
- Returns `{ filteredTopics: RankedTopic[], filters: TopicFilters, setFilters: (update: Partial<TopicFilters>) => void }`

**`useTopicPagination(items)`** — `frontend/src/hooks/use-topic-pagination.ts` (~30 lines)
- Owns pagination math
- Returns `{ paginatedItems: RankedTopic[], page: number, totalPages: number, setPage: (n: number) => void }`
- Config: pageSize = 10

**`useTopicDiscovery()`** — `frontend/src/hooks/use-topic-discovery.ts` (~30 lines)
- Thin orchestrator composing the above three hooks
- Also manages modal state: `{ modalTopic: RankedTopic | null, openModal, closeModal }`

### 5.3 Scan Flow

```
User clicks "New Scan"
  → Button disables, ScanProgressBanner shows "0/5 sources"
  → Grid area shows 4-6 skeleton cards in 2-column layout
  → 5 parallel API calls fire:
      POST /api/v1/trends/hackernews/fetch
      POST /api/v1/trends/reddit/fetch
      POST /api/v1/trends/google/fetch         ← note: "/google/", not "/google-trends/"
      POST /api/v1/trends/newsapi/fetch
      POST /api/v1/trends/arxiv/fetch
  → Each request body: { domain_keywords: DOMAIN_KEYWORDS[selectedDomain], max_results: 30 }
  → As each resolves:
      completedSources++ (or failedSources.push on error)
      Banner updates: "3/5 sources complete"
      Topics from successful source append to staging list
  → Once all settled (or 60s timeout):
      POST /api/v1/topics/rank with { topics: combinedTopics, domain: selectedDomain, top_n: 100 }
  → Frontend enriches ranked results with derived fields (see Section 5.5)
  → Ranked results stored, filters reset, page = 1
  → Button re-enables, banner hides (or shows partial failure warning)
```

**Note on response shapes**: Each source endpoint returns a different response schema (e.g., `HNFetchResponse` has `total_fetched`, `RedditFetchResponse` has `subreddits_scanned`). The frontend destructures only `{ topics }` from each response, ignoring source-specific metadata fields.

**"All Domains" and scan**: When "All Domains" is selected in the filter, the "New Scan" button is disabled with a tooltip: "Select a domain to scan." A scan requires a specific domain to provide `domain_keywords` to the backend.

**Scan result replacement**: Each new scan **replaces** the previous scan's results entirely. There is no cross-domain accumulation. The TanStack Query cache key is simply `["topics"]` — a new scan invalidates and replaces the cached data. The "All Domains" filter option filters within the current scan's results only (useful when the scan returns topics tagged with different domains via source metadata). Multi-domain scanning is out of scope for DASH-002.

### 5.4 Domain-to-Keywords Mapping

Each domain maps to a list of keywords used in the `domain_keywords` field of fetch requests. Defined as a `DOMAIN_KEYWORDS` constant in `frontend/src/types/domain.ts`:

```typescript
const DOMAIN_KEYWORDS: Record<DomainName, string[]> = {
  cybersecurity: ["cybersecurity", "security", "infosec", "threat", "vulnerability"],
  "ai-ml": ["artificial intelligence", "machine learning", "deep learning", "AI", "ML"],
  cloud: ["cloud computing", "AWS", "Azure", "GCP", "kubernetes"],
  devops: ["devops", "CI/CD", "infrastructure", "deployment", "SRE"],
}
```

This is hardcoded for the mock-first approach. Will eventually be fetched from a domain configuration API.

### 5.5 Derived Fields: `domain` and `trend_status`

The backend `RankedTopic` does NOT include `domain` or `trend_status` fields. The frontend derives them:

- **`domain`**: Set from the domain selected when the scan was triggered. Stored alongside the ranked results.
- **`trend_status`**: Computed client-side from `velocity`, `composite_score`, and `discovered_at`:
  ```typescript
  function deriveTrendStatus(topic: RankedTopic): TrendStatus {
    const hoursAgo = (Date.now() - new Date(topic.discovered_at).getTime()) / 3600000
    if (topic.velocity >= 50 && topic.composite_score >= 80) return "trending"
    if (topic.velocity >= 30) return "rising"
    if (hoursAgo <= 24) return "new"   // recently discovered
    return "steady"
  }
  ```

These derived fields are added when results are stored from a scan, not on every render.

### 5.6 Client-Side Filtering

All topics are in memory (max 100). Filtering is instant:
- **Sources**: `topic.source` is in selected sources (or show all if empty)
- **Time range**: `topic.discovered_at` is within the selected window
- **Domain**: `topic.domain` matches selected domain (or show all)

Filter changes reset pagination to page 1.

### 5.7 Caching

TanStack Query with 15-minute stale time (same as DASH-001). Navigating away and back shows cached results without refetching.

---

## 6. Empty States

### 6.1 No Topics Yet (First Visit)

- **Condition**: No topics in cache, no scan has been done
- **Icon**: Compass (matches Topics nav icon)
- **Title**: "No topics discovered yet"
- **Description**: "Click 'New Scan' to discover trending topics in your domain."
- **CTA**: "New Scan" button (triggers scan flow)

### 6.2 No Filter Matches

- **Condition**: Topics exist but current filter combination returns zero results
- **Icon**: Search icon
- **Title**: "No topics match your filters"
- **Description**: "Try adjusting your source or time range filters."
- **CTA**: None (user adjusts filters directly)

---

## 7. Generate Article Modal

### 7.1 Modal Content

```
┌──────────────────────────────────┐
│ Generate Article                 │
│                                  │
│ [Trending] [Cybersecurity]       │
│ AI-Powered Phishing Detection    │
│ Machine learning analysis of...  │
│ Score: 94                        │
│                                  │
│ This will start the content      │
│ generation pipeline.             │
│ Estimated time: 2-5 minutes.     │
│                                  │
│        [Cancel]  [Generate]      │
└──────────────────────────────────┘
```

### 7.2 Flow

1. User clicks "Generate Article" on a TopicCard → modal opens
2. Modal shows topic details + estimated time
3. "Generate" → calls `POST /api/v1/articles/generate` (mock, returns 202)
4. Success → toast: "Article generation started for [title]", modal closes
5. Error → toast: "Failed to start generation. Please try again.", modal stays open

---

## 8. Edge Cases

| Scenario | Behavior |
|----------|----------|
| Scan — loading state | Grid shows 4-6 skeleton cards in 2-column layout while awaiting first results |
| Scan — all sources succeed | Normal flow, show all ranked results |
| Scan — partial failure | Show results from successful sources + warning banner |
| Scan — total failure | Error toast, button re-enables, no results change |
| Scan — timeout (60s) | Treat unfinished sources as failed, rank what we have |
| Scan — user navigates away mid-scan | Scan completes in background, results cached |
| Filter — no matches | Empty state #2 |
| Pagination — last page has < 10 items | Show partial grid (1-column if odd) |
| Generate Article — API error | Toast error, modal stays open for retry |

---

## 9. File Structure

### New Files

```
frontend/src/
  app/(dashboard)/topics/page.tsx                   — TopicDiscovery page (replace placeholder)
  components/topics/
    topic-card.tsx                                   — Single topic card
    topic-card.test.tsx
    filter-bar.tsx                                   — Filter controls + topic count
    filter-bar.test.tsx
    generate-article-modal.tsx                       — Confirmation modal
    generate-article-modal.test.tsx
    topic-pagination.tsx                             — Page controls
    topic-pagination.test.tsx
    scan-progress-banner.tsx                         — Scan progress + partial failure
    scan-progress-banner.test.tsx
  hooks/
    use-scan-topics.ts                               — Scan lifecycle + API calls
    use-scan-topics.test.ts
    use-topic-filters.ts                             — Client-side filter state
    use-topic-filters.test.ts
    use-topic-pagination.ts                          — Pagination math
    use-topic-pagination.test.ts
    use-topic-discovery.ts                           — Thin orchestrator composing hooks above
    use-topic-discovery.test.ts
```

### Modified Files

```
frontend/src/
  lib/mock/topics.ts                                — Extend with more mock topics (20+)
  types/domain.ts                                   — Add DOMAIN_KEYWORDS constant
  types/sources.ts                                  — Add SOURCE_LABELS constant (new file)
  types/api.ts                                      — Add TopicFilters, TimeRange, ScanState types
```

### Estimated Sizes

| File | Estimated Lines |
|------|----------------|
| `topics/page.tsx` | ~80 |
| `topic-card.tsx` | ~60 |
| `filter-bar.tsx` | ~90 |
| `generate-article-modal.tsx` | ~70 |
| `topic-pagination.tsx` | ~50 |
| `scan-progress-banner.tsx` | ~40 |
| `use-scan-topics.ts` | ~60 |
| `use-topic-filters.ts` | ~40 |
| `use-topic-pagination.ts` | ~30 |
| `use-topic-discovery.ts` | ~30 |
| Each test file | ~50-80 |

All well under 200-line limit.

---

## 10. Testing Strategy

### Unit Tests (Vitest + React Testing Library)

| Component | Key Tests |
|-----------|-----------|
| `TopicCard` | Renders title, score, badges, source tags; calls onGenerateArticle on click |
| `FilterBar` | Source multi-select toggles; time range/domain single-select; shows topic count |
| `GenerateArticleModal` | Opens with topic data; calls onConfirm; shows loading state |
| `TopicPagination` | Page navigation; disabled at boundaries; correct page range display |
| `ScanProgressBanner` | Shows progress during scan; warning on partial failure; hidden when idle |
| `useScanTopics` | Fires 5 parallel fetches; tracks progress; handles timeout; calls rank endpoint |
| `useTopicFilters` | Applies source/time/domain filters; resets on change |
| `useTopicPagination` | Correct page slicing; boundary handling; page count math |
| `useTopicDiscovery` | Composes hooks; manages modal state |

### Coverage Targets

- Components: 80%+
- Hook logic: 90%+ (core business logic)
- Page integration: renders without errors, shows empty state by default

---

## 11. API Compatibility

### Current Endpoints (pre-ARCH-002)

```
POST /api/v1/trends/hackernews/fetch     → HNFetchResponse { topics, total_fetched, total_after_filter }
POST /api/v1/trends/reddit/fetch         → RedditFetchResponse { topics, total_fetched, total_after_dedup, ... }
POST /api/v1/trends/google/fetch         → GTFetchResponse { topics, total_trending, total_related, ... }
POST /api/v1/trends/newsapi/fetch        → NewsAPIFetchResponse { topics, total_fetched, total_after_filter }
POST /api/v1/trends/arxiv/fetch          → ArxivFetchResponse { topics, total_fetched, total_after_filter }
POST /api/v1/topics/rank                 → RankTopicsResponse { ranked_topics, duplicates_removed, ... }
```

**Important**: Response shapes differ per source. Frontend destructures only `{ topics }` from each, ignoring source-specific metadata. The `ranked_topics` from the rank endpoint lack `domain` and `trend_status` — these are derived client-side (see Section 5.5).

### Request Bodies

Each source endpoint expects at minimum: `{ domain_keywords: string[], max_results?: number }`. Some sources accept additional optional fields (e.g., Reddit: `subreddits`, `sort`, `time_filter`). The frontend sends only the common fields; source-specific defaults are applied server-side.

The rank endpoint requires: `{ topics: RawTopic[], domain: string, top_n?: number }`.

### Post-ARCH-002 Endpoint

```
POST /api/v1/trends/fetch  → TrendFetchResponse { topics, source_results: {...} }
POST /api/v1/topics/rank   → RankTopicsResponse { ranked_topics, ... }
```

The frontend pattern is identical (5 parallel requests for progressive loading). Only the URL and request shape change — a one-line adaptation in the API client layer.

### Stub Endpoint

```
POST /api/v1/articles/generate  → 202 Accepted
  Response: { task_id: string, status: "queued", estimated_time_seconds: number }
  (Mock — not yet implemented. Frontend uses mock data.)
```
