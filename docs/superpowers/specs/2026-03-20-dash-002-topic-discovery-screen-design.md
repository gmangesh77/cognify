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
- **Props**: `topic: RankedTopic`, `onGenerateArticle: (topic) => void`
- **Renders**: Card with trend badge (top-left), composite score (top-right), title, description (2-line clamp), source tags, relative time, "Generate Article" link button (bottom-right)
- **Styling**: White bg, border `border-neutral-200`, rounded-lg, shadow-sm, hover shadow-md transition

#### `FilterBar`
- **File**: `frontend/src/components/topics/filter-bar.tsx`
- **Props**: `filters`, `onFilterChange`, `topicCount: number`
- **Contains**:
  - **Source multi-select**: Checkboxes for Google Trends, Reddit, Hacker News, NewsAPI, arXiv. Dropdown trigger shows "All Sources" or "N selected"
  - **Time range select**: Single-select dropdown — Last Hour, Last 24 Hours, Last 7 Days (default), Last 30 Days, All Time
  - **Domain select**: Single-select dropdown — All Domains (default), Cybersecurity, AI & ML, Cloud, DevOps
  - **Topic count**: Right-aligned text "X Topics Found"

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

### 5.1 Hook: `useTopicDiscovery`

**File**: `frontend/src/hooks/use-topic-discovery.ts`

```typescript
interface TopicDiscoveryState {
  // Data
  topics: RankedTopic[]
  filteredTopics: RankedTopic[]     // after client-side filtering
  paginatedTopics: RankedTopic[]    // current page slice

  // Filters
  filters: {
    sources: string[]               // empty = all sources
    timeRange: TimeRange            // "1h" | "24h" | "7d" | "30d" | "all"
    domain: string                  // "" = all domains
  }

  // Pagination
  page: number
  pageSize: 10
  totalCount: number
  totalPages: number

  // Scan
  scanState: {
    isScanning: boolean
    completedSources: number
    totalSources: number
    failedSources: string[]
  }

  // Actions
  startScan: (domain: string) => Promise<void>
  setFilter: (key: string, value: any) => void
  setPage: (page: number) => void
  openGenerateModal: (topic: RankedTopic) => void
}
```

### 5.2 Scan Flow

```
User clicks "New Scan"
  → Button disables, ScanProgressBanner shows "0/5 sources"
  → 5 parallel API calls fire:
      POST /trends/hackernews/fetch    (or unified endpoint per ARCH-002)
      POST /trends/reddit/fetch
      POST /trends/google-trends/fetch
      POST /trends/newsapi/fetch
      POST /trends/arxiv/fetch
  → As each resolves:
      completedSources++ (or failedSources.push on error)
      Banner updates: "3/5 sources complete"
  → Once all settled (or 60s timeout):
      POST /topics/rank with combined topics
  → Ranked results stored, filters reset, page = 1
  → Button re-enables, banner hides (or shows partial failure warning)
```

### 5.3 Client-Side Filtering

All topics are in memory (max 100). Filtering is instant:
- **Sources**: `topic.source` is in selected sources (or show all if empty)
- **Time range**: `topic.discovered_at` is within the selected window
- **Domain**: `topic.domain` matches selected domain (or show all)

Filter changes reset pagination to page 1.

### 5.4 Caching

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
    use-topic-discovery.ts                           — All page state management
    use-topic-discovery.test.ts
```

### Modified Files

```
frontend/src/
  lib/mock/topics.ts                                — Extend with more mock topics (20+)
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
| `use-topic-discovery.ts` | ~120 |
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
| `useTopicDiscovery` | Scan flow with mock fetch; client-side filtering; pagination math |

### Coverage Targets

- Components: 80%+
- Hook logic: 90%+ (core business logic)
- Page integration: renders without errors, shows empty state by default

---

## 11. API Compatibility

### Current Endpoints (pre-ARCH-002)

```
POST /api/v1/trends/hackernews/fetch     → { topics: RawTopic[] }
POST /api/v1/trends/reddit/fetch         → { topics: RawTopic[] }
POST /api/v1/trends/google-trends/fetch  → { topics: RawTopic[] }
POST /api/v1/trends/newsapi/fetch        → { topics: RawTopic[] }
POST /api/v1/trends/arxiv/fetch          → { topics: RawTopic[] }
POST /api/v1/topics/rank                 → { ranked_topics: RankedTopic[] }
```

### Post-ARCH-002 Endpoint

```
POST /api/v1/trends/fetch  → { topics: RawTopic[], source_results: {...} }
POST /api/v1/topics/rank   → { ranked_topics: RankedTopic[] }
```

The frontend calls are identical in pattern (5 parallel requests, each for one source). Only the URL and request shape change — a one-line adaptation in the API client layer. Mock data abstracts this difference during development.

### Stub Endpoint

```
POST /api/v1/articles/generate  → 202 Accepted (mock — not yet implemented)
```
