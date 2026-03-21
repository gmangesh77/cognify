# DASH-004: Research Sessions Screen — Design Specification

> **Date**: 2026-03-21
> **Status**: Draft
> **Ticket**: DASH-004
> **Depends on**: DASH-001 (Dashboard Overview — Done), RESEARCH-001 (Agent Orchestrator — Done)
> **Design reference**: `pencil_designs/cognify.pen` → "Research Sessions" frame (DESIGN-006)

---

## 1. Overview

The Research Sessions screen lets users monitor active and past research sessions. Each session represents an agent orchestration run for a topic — users can see status, progress, duration, and drill into individual agent steps. This page is **view-only** — new research is initiated from Topic Discovery (`/topics`).

**Route**: `/research` (replaces current `PagePlaceholder`)

---

## 2. Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Page layout | Full-width expandable list | Consistent with DASH-002 topic card pattern; simpler state management; mobile-friendly |
| Status values | `planning`, `in_progress`, `complete`, `failed` | Match backend API exactly — no frontend mapping layer |
| "New Research" flow | Not on this page — initiated from Topic Discovery | Avoids duplicate entry points; Topics page already has the action |
| Knowledge base stats | Deferred stub panel with placeholder text | No backend endpoint exists yet; avoids investing in mock-only features |
| Data source connectors | Deferred (same as above) | No backend endpoint; defer to future ticket |
| Polling for active sessions | 10s refetchInterval on detail query | Balances freshness vs. API load; WebSocket deferred to RESEARCH-005 |
| Pagination | 10 per page | Consistent with DASH-002 |
| Expand behavior | Single session expanded at a time | Reduces visual noise; detail fetch only when needed |

---

## 3. Page Layout

```
┌─────────────────────────────────────────────┐
│ Header: "Research Sessions"                 │
│ Subtitle: "Monitor agent research workflows"│
├─────────────────────────────────────────────┤
│ Filter Tabs:                                │
│ [All] [Planning] [In Progress] [Complete]   │
│ [Failed]                "X Sessions"        │
├─────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────┐ │
│ │ ▌ AI Security Trends 2026     ● Complete│ │
│ │   3 rounds · 12 findings · 4m 32s      │ │
│ │   ████████████████████████████ 100%     │ │
│ └─────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────┐ │
│ │ ▌ Zero Trust Architecture  ◌ In Progress│ │
│ │   2 rounds · 8 findings · 2m 15s...    │ │
│ │   ████████████████░░░░░░░░░░░  60%     │ │
│ │  ┌─ Agent Steps ───────────────────┐    │ │
│ │  │ ✓ Plan Research          1.2s   │    │ │
│ │  │ ✓ Web Search             45.0s  │    │ │
│ │  │ ◌ Evaluate Findings      ...    │    │ │
│ │  │ ○ Index Findings                │    │ │
│ │  │ ○ Compile Results               │    │ │
│ │  └────────────────────────────────-┘    │ │
│ └─────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────┐ │
│ │ ▌ Quantum Computing Risks     ✕ Failed  │ │
│ │   1 round · 0 findings · Timeout       │ │
│ │   ████░░░░░░░░░░░░░░░░░░░░░░░  20%    │ │
│ └─────────────────────────────────────────┘ │
├─────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────┐ │
│ │ 📊 Knowledge Base                       │ │
│ │ Stats coming in a future update.        │ │
│ └─────────────────────────────────────────┘ │
├─────────────────────────────────────────────┤
│ Pagination: [< 1 2 3 >]                    │
└─────────────────────────────────────────────┘
```

---

## 4. Types

### 4.1 New Type File

**File**: `frontend/src/types/research.ts`

```typescript
export type SessionStatus = "planning" | "in_progress" | "complete" | "failed";

export interface AgentStep {
  step_name: string;
  status: string;
  duration_ms: number | null;
  started_at: string;
  completed_at: string | null;
}

export interface ResearchSessionSummary {
  session_id: string;
  topic_id: string;
  status: SessionStatus;
  round_count: number;
  findings_count: number;
  started_at: string;
}

export interface ResearchSessionDetail extends ResearchSessionSummary {
  duration_seconds: number | null;
  completed_at: string | null;
  steps: AgentStep[];
}

export interface PaginatedResearchSessions {
  items: ResearchSessionSummary[];
  total: number;
  page: number;
  size: number;
}
```

These types mirror the backend schemas in `src/api/schemas/research.py` exactly.

---

## 5. Components

### 5.1 New Components

#### `SessionCard`
- **File**: `frontend/src/components/research/session-card.tsx`
- **Props**: `session: ResearchSessionSummary`, `isExpanded: boolean`, `onToggle: () => void`
- **Renders**: Card with left border colored by status, topic title (from session — note: backend `ResearchSessionSummary` doesn't include topic title, so we display session_id prefix or fetch separately; see §5.3), status badge, round count, findings count, duration (relative time for active, absolute for complete), progress bar, chevron toggle
- **Left border colors**: planning=blue-500, in_progress=amber-500, complete=green-500, failed=red-500
- **Styling**: bg-white, border border-neutral-200, rounded-lg, shadow-sm, hover:shadow-md transition. Matches DASH-002 card style.

#### `SessionSteps`
- **File**: `frontend/src/components/research/session-steps.tsx`
- **Props**: `steps: AgentStep[]`, `isLoading: boolean`
- **Renders**: Vertical timeline inside expanded card. Each step has an icon (checkmark=complete, spinner=running, circle=pending, x-circle=failed), humanized name, and duration.
- **Humanize step names**: `plan_research` → "Plan Research", `web_search` → "Web Search", `evaluate` → "Evaluate Findings", `index_findings` → "Index Findings", `compile_results` → "Compile Results"
- **Loading state**: Skeleton lines while detail is fetching

#### `SessionStatusBadge`
- **File**: `frontend/src/components/research/session-status-badge.tsx`
- **Props**: `status: SessionStatus`
- **Renders**: Colored dot + capitalized label. Colors: planning=blue, in_progress=amber, complete=green, failed=red
- **Pattern**: Same as existing `StatusBadge` in `components/common/`

#### `SessionFilters`
- **File**: `frontend/src/components/research/session-filters.tsx`
- **Props**: `activeFilter: SessionStatus | "all"`, `onFilterChange: (filter: SessionStatus | "all") => void`, `totalCount: number`
- **Renders**: Horizontal pill buttons for each status + "All". Active pill has primary bg. Shows "X Sessions" count on the right.

#### `KnowledgeBaseStub`
- **File**: `frontend/src/components/research/knowledge-base-stub.tsx`
- **Props**: none
- **Renders**: Muted card with Database icon, "Knowledge Base" title, and subtitle "Stats and data source connectors coming in a future update." Minimal — just signals the feature is planned.

### 5.2 Reused Components

- `Header` from `components/layout/header.tsx`
- `Skeleton` from `components/ui/skeleton.tsx`
- `Button` from `components/ui/button.tsx`
- `Card` from `components/ui/card.tsx`
- Pagination pattern from DASH-002 (`TopicPagination`)

### 5.3 Topic Title Resolution

The backend `ResearchSessionSummary` includes `topic_id` but not `topic_title`. Two options:

- **Option A (mock phase)**: Include `topic_title` in mock data directly. Add a `// TODO: backend doesn't return topic_title — either extend the API or join client-side` comment.
- **Option B (future)**: Backend adds `topic_title` to `ResearchSessionSummary`.

We go with **Option A** for now — extend the frontend type with an optional `topic_title?: string` field populated in mock data. This avoids a backend change in this ticket.

---

## 6. Hooks

### 6.1 `useResearchSessions`
- **File**: `frontend/src/hooks/use-research-sessions.ts`
- **Signature**: `useResearchSessions(status?: SessionStatus, page?: number, size?: number)`
- **Returns**: TanStack Query result with `PaginatedResearchSessions`
- **Query key**: `["research-sessions", status, page, size]`
- **Stale time**: 15 minutes (consistent with other hooks)
- **Mock**: Returns filtered/paginated mock data. `// TODO: Replace with GET /api/v1/research/sessions`

### 6.2 `useResearchSession`
- **File**: `frontend/src/hooks/use-research-sessions.ts` (same file, named export)
- **Signature**: `useResearchSession(sessionId: string | null)`
- **Returns**: TanStack Query result with `ResearchSessionDetail`
- **Query key**: `["research-session", sessionId]`
- **Enabled**: only when `sessionId` is not null
- **Polling**: `refetchInterval: 10_000` when session status is `planning` or `in_progress`
- **Mock**: Returns detail mock with steps array. `// TODO: Replace with GET /api/v1/research/sessions/{id}`

---

## 7. Mock Data

**File**: `frontend/src/lib/mock/research-sessions.ts`

8 mock sessions covering all statuses:
- 2 `complete` sessions (all steps done, realistic durations)
- 2 `in_progress` sessions (2-3 steps done, rest pending)
- 1 `planning` session (1 step running)
- 1 `failed` session (stops mid-way with a failed step)
- 2 more `complete` for pagination testing

Each session has 4-5 agent steps from this set: `plan_research`, `web_search`, `evaluate`, `index_findings`, `compile_results`.

Topic titles from cybersecurity domain: "AI Security Trends 2026", "Zero Trust Architecture", "Quantum Computing Risks", "Supply Chain Attacks", "Cloud Security Posture", "Ransomware Evolution", "API Security Best Practices", "Insider Threat Detection".

---

## 8. Page State

**File**: `frontend/src/app/(dashboard)/research/page.tsx`

```typescript
// State
const [activeFilter, setActiveFilter] = useState<SessionStatus | "all">("all");
const [expandedSessionId, setExpandedSessionId] = useState<string | null>(null);
const [currentPage, setCurrentPage] = useState(1);

// Queries
const sessionsQuery = useResearchSessions(
  activeFilter === "all" ? undefined : activeFilter,
  currentPage,
  10
);
const detailQuery = useResearchSession(expandedSessionId);
```

**Behavior:**
- Changing filter resets to page 1 and collapses any expanded card
- Clicking an expanded card collapses it (toggle)
- Clicking a different card expands it and collapses the previous
- Loading state: skeleton cards (3 placeholder cards)
- Empty state: "No research sessions found" with contextual message per filter
- Error state: "Failed to load sessions" with retry button

---

## 9. Testing

### 9.1 Component Tests

#### `session-card.test.tsx`
- Renders session title, status badge, round count, findings count
- Shows correct left border color for each status
- Progress bar width matches completed steps / total steps
- Chevron rotates when expanded
- Calls onToggle when clicked

#### `session-steps.test.tsx`
- Renders all steps with correct icons per status
- Humanizes step names correctly
- Shows duration for completed steps
- Shows "..." for running steps
- Shows skeleton when loading

#### `session-status-badge.test.tsx`
- Renders correct color and label for each of 4 statuses

#### `session-filters.test.tsx`
- Renders all 5 filter tabs
- Active filter has distinct styling
- Calls onFilterChange with correct value
- Shows total count

#### `knowledge-base-stub.test.tsx`
- Renders placeholder text

### 9.2 Hook Tests

#### `use-research-sessions.test.ts`
- Returns paginated mock data
- Filters by status when provided
- Passes page/size params
- Detail query enabled only when sessionId provided
- Detail query polls when session is active

### 9.3 Page Test

#### `research/page.test.tsx`
- Renders header and filter tabs
- Renders session cards from mock data
- Filter tabs filter the list
- Clicking card expands to show steps
- Clicking again collapses
- Empty state renders when no sessions match filter
- Pagination renders when total > page size

### 9.4 Coverage Target

≥75% on all new files, consistent with frontend test strategy.

---

## 10. File Summary

| File | Type | ~Lines |
|------|------|--------|
| `frontend/src/types/research.ts` | Types | ~35 |
| `frontend/src/lib/mock/research-sessions.ts` | Mock data | ~120 |
| `frontend/src/hooks/use-research-sessions.ts` | Hooks | ~60 |
| `frontend/src/components/research/session-card.tsx` | Component | ~80 |
| `frontend/src/components/research/session-steps.tsx` | Component | ~60 |
| `frontend/src/components/research/session-status-badge.tsx` | Component | ~30 |
| `frontend/src/components/research/session-filters.tsx` | Component | ~50 |
| `frontend/src/components/research/knowledge-base-stub.tsx` | Component | ~20 |
| `frontend/src/app/(dashboard)/research/page.tsx` | Page | ~90 |
| Tests (7 files) | Tests | ~350 |
| **Total** | | **~895** |

---

## 11. Deferred Items

| Item | Reason | Future Ticket |
|------|--------|---------------|
| Knowledge base stats (doc count, embeddings, storage) | No backend endpoint | Needs new API endpoint |
| Data source connectors with connection status | No backend endpoint | Needs new API endpoint |
| Real-time WebSocket updates for active sessions | RESEARCH-005 scope | RESEARCH-005 |
| "New Research" button / flow | Handled by Topic Discovery | Already exists on DASH-002 |
| Topic title in session summary API | Backend schema doesn't include it | Backend enhancement |
