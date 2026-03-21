# DASH-004: Research Sessions Screen — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Research Sessions placeholder page with a full session monitoring screen — filterable list of research sessions with expandable agent step details.

**Architecture:** Single `/research` page with client-side filter/expand state. Two TanStack Query hooks: `useResearchSessions` for the paginated list and `useResearchSession` for expanded detail with steps. Mock data serves all queries with TODOs for real API integration. Components follow existing DASH-002/003 patterns.

**Tech Stack:** Next.js 15, React 19, TypeScript, Tailwind v4, TanStack Query, Vitest, React Testing Library

**Spec:** `docs/superpowers/specs/2026-03-21-dash-004-research-sessions-screen-design.md`

**Baseline:** 191 frontend tests passing across 33 test files.

**Worktree:** `D:/Workbench/github/cognify-dash-004` on branch `feature/DASH-004-research-sessions-screen`

---

## File Structure

### New Files

| File | Responsibility | ~Lines |
|------|---------------|--------|
| `frontend/src/types/research.ts` | Type definitions for sessions, steps, pagination | ~35 |
| `frontend/src/lib/mock/research-sessions.ts` | 8 mock sessions with steps, detail lookup | ~150 |
| `frontend/src/hooks/use-research-sessions.ts` | TanStack Query hooks for list + detail | ~55 |
| `frontend/src/hooks/use-research-sessions.test.ts` | Hook tests | ~70 |
| `frontend/src/components/research/session-status-badge.tsx` | Colored dot + label badge | ~30 |
| `frontend/src/components/research/session-status-badge.test.tsx` | Badge tests | ~30 |
| `frontend/src/components/research/session-steps.tsx` | Vertical timeline of agent steps | ~55 |
| `frontend/src/components/research/session-steps.test.tsx` | Steps tests | ~60 |
| `frontend/src/components/research/session-card.tsx` | Expandable session card | ~80 |
| `frontend/src/components/research/session-card.test.tsx` | Card tests | ~70 |
| `frontend/src/components/research/session-filters.tsx` | Status filter pill tabs | ~45 |
| `frontend/src/components/research/session-filters.test.tsx` | Filter tests | ~50 |
| `frontend/src/components/research/knowledge-base-stub.tsx` | Deferred feature placeholder | ~15 |
| `frontend/src/components/research/knowledge-base-stub.test.tsx` | Stub test | ~15 |
| `frontend/src/app/(dashboard)/research/page.test.tsx` | Page integration tests | ~80 |

### Modified Files

| File | Change |
|------|--------|
| `frontend/src/app/(dashboard)/research/page.tsx` | Replace `PagePlaceholder` with full research sessions page (~85 lines) |

---

## Task 1: Types and Mock Data

**Files:**
- Create: `frontend/src/types/research.ts`
- Create: `frontend/src/lib/mock/research-sessions.ts`

- [ ] **Step 1: Create type definitions**

Create `frontend/src/types/research.ts`:

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
  // Frontend-only fields populated in mock data:
  topic_title?: string; // TODO: backend doesn't return this — extend API or join client-side
  duration_seconds?: number | null; // TODO: backend only returns this in detail response
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

- [ ] **Step 2: Create mock data**

Create `frontend/src/lib/mock/research-sessions.ts` with 8 sessions covering all 4 statuses. Each session has 5 agent steps (`plan_research`, `web_search`, `evaluate`, `index_findings`, `compile_results`). Include a `mockSessionDetails` map for detail lookups, and a `getMockSessions` function that filters by status and paginates.

```typescript
import type {
  AgentStep,
  PaginatedResearchSessions,
  ResearchSessionDetail,
  ResearchSessionSummary,
  SessionStatus,
} from "@/types/research";

function makeSteps(statuses: string[], durations: (number | null)[]): AgentStep[] {
  const names = ["plan_research", "web_search", "evaluate", "index_findings", "compile_results"];
  const now = new Date();
  return names.map((name, i) => ({
    step_name: name,
    status: statuses[i] ?? "pending",
    duration_ms: durations[i] ?? null,
    started_at: new Date(now.getTime() - (5 - i) * 60000).toISOString(),
    completed_at: statuses[i] === "complete" ? new Date(now.getTime() - (4 - i) * 60000).toISOString() : null,
  }));
}

export const mockSessions: ResearchSessionSummary[] = [
  {
    session_id: "sess-001",
    topic_id: "topic-001",
    status: "complete",
    round_count: 3,
    findings_count: 12,
    started_at: "2026-03-20T10:00:00Z",
    topic_title: "AI Security Trends 2026",
    duration_seconds: 272,
  },
  {
    session_id: "sess-002",
    topic_id: "topic-002",
    status: "in_progress",
    round_count: 2,
    findings_count: 8,
    started_at: "2026-03-21T09:30:00Z",
    topic_title: "Zero Trust Architecture",
    duration_seconds: 135,
  },
  {
    session_id: "sess-003",
    topic_id: "topic-003",
    status: "failed",
    round_count: 1,
    findings_count: 0,
    started_at: "2026-03-21T08:00:00Z",
    topic_title: "Quantum Computing Risks",
    duration_seconds: 45,
  },
  {
    session_id: "sess-004",
    topic_id: "topic-004",
    status: "planning",
    round_count: 0,
    findings_count: 0,
    started_at: "2026-03-21T11:00:00Z",
    topic_title: "Supply Chain Attacks",
  },
  {
    session_id: "sess-005",
    topic_id: "topic-005",
    status: "complete",
    round_count: 2,
    findings_count: 9,
    started_at: "2026-03-19T14:00:00Z",
    topic_title: "Cloud Security Posture",
    duration_seconds: 198,
  },
  {
    session_id: "sess-006",
    topic_id: "topic-006",
    status: "in_progress",
    round_count: 1,
    findings_count: 4,
    started_at: "2026-03-21T10:15:00Z",
    topic_title: "Ransomware Evolution",
    duration_seconds: 90,
  },
  {
    session_id: "sess-007",
    topic_id: "topic-007",
    status: "complete",
    round_count: 3,
    findings_count: 15,
    started_at: "2026-03-18T16:00:00Z",
    topic_title: "API Security Best Practices",
    duration_seconds: 310,
  },
  {
    session_id: "sess-008",
    topic_id: "topic-008",
    status: "complete",
    round_count: 2,
    findings_count: 7,
    started_at: "2026-03-17T11:30:00Z",
    topic_title: "Insider Threat Detection",
    duration_seconds: 185,
  },
];

export const mockSessionDetails: Record<string, ResearchSessionDetail> = {
  "sess-001": {
    ...mockSessions[0],
    duration_seconds: 272,
    completed_at: "2026-03-20T10:04:32Z",
    steps: makeSteps(
      ["complete", "complete", "complete", "complete", "complete"],
      [1200, 45000, 12000, 8000, 3000],
    ),
  },
  "sess-002": {
    ...mockSessions[1],
    duration_seconds: 135,
    completed_at: null,
    steps: makeSteps(
      ["complete", "complete", "running", "pending", "pending"],
      [1100, 42000, null, null, null],
    ),
  },
  "sess-003": {
    ...mockSessions[2],
    duration_seconds: 45,
    completed_at: "2026-03-21T08:00:45Z",
    steps: makeSteps(
      ["complete", "failed", "pending", "pending", "pending"],
      [1500, null, null, null, null],
    ),
  },
  "sess-004": {
    ...mockSessions[3],
    duration_seconds: null,
    completed_at: null,
    steps: makeSteps(
      ["running", "pending", "pending", "pending", "pending"],
      [null, null, null, null, null],
    ),
  },
  "sess-005": {
    ...mockSessions[4],
    duration_seconds: 198,
    completed_at: "2026-03-19T14:03:18Z",
    steps: makeSteps(
      ["complete", "complete", "complete", "complete", "complete"],
      [900, 38000, 10000, 7500, 2800],
    ),
  },
  "sess-006": {
    ...mockSessions[5],
    duration_seconds: 90,
    completed_at: null,
    steps: makeSteps(
      ["complete", "running", "pending", "pending", "pending"],
      [1300, null, null, null, null],
    ),
  },
  "sess-007": {
    ...mockSessions[6],
    duration_seconds: 310,
    completed_at: "2026-03-18T16:05:10Z",
    steps: makeSteps(
      ["complete", "complete", "complete", "complete", "complete"],
      [1100, 50000, 15000, 9000, 3500],
    ),
  },
  "sess-008": {
    ...mockSessions[7],
    duration_seconds: 185,
    completed_at: "2026-03-17T11:33:05Z",
    steps: makeSteps(
      ["complete", "complete", "complete", "complete", "complete"],
      [1000, 35000, 9000, 6000, 2500],
    ),
  },
};

export function getMockSessions(
  status?: SessionStatus,
  page = 1,
  size = 10,
): PaginatedResearchSessions {
  const filtered = status ? mockSessions.filter((s) => s.status === status) : mockSessions;
  const start = (page - 1) * size;
  return {
    items: filtered.slice(start, start + size),
    total: filtered.length,
    page,
    size,
  };
}
```

- [ ] **Step 3: Verify TypeScript compiles**

Run: `cd D:/Workbench/github/cognify-dash-004/frontend && npx tsc --noEmit 2>&1 | head -20`
Expected: No errors related to research types.

- [ ] **Step 4: Commit**

```bash
cd D:/Workbench/github/cognify-dash-004
git add frontend/src/types/research.ts frontend/src/lib/mock/research-sessions.ts
git commit -m "feat(dash-004): add research session types and mock data"
```

---

## Task 2: TanStack Query Hooks

**Files:**
- Create: `frontend/src/hooks/use-research-sessions.test.ts`
- Create: `frontend/src/hooks/use-research-sessions.ts`

- [ ] **Step 1: Write failing hook tests**

Create `frontend/src/hooks/use-research-sessions.test.ts`:

```typescript
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useResearchSessions, useResearchSession } from "./use-research-sessions";

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

describe("useResearchSessions", () => {
  it("returns paginated sessions", async () => {
    const { result } = renderHook(() => useResearchSessions(), {
      wrapper: createWrapper(),
    });
    await waitFor(() => expect(result.current.data).toBeDefined());
    expect(result.current.data!.items.length).toBeGreaterThan(0);
    expect(result.current.data!.total).toBe(8);
    expect(result.current.data!.page).toBe(1);
  });

  it("filters by status", async () => {
    const { result } = renderHook(() => useResearchSessions("complete"), {
      wrapper: createWrapper(),
    });
    await waitFor(() => expect(result.current.data).toBeDefined());
    expect(result.current.data!.items.every((s) => s.status === "complete")).toBe(true);
  });

  it("respects page and size params", async () => {
    const { result } = renderHook(() => useResearchSessions(undefined, 1, 3), {
      wrapper: createWrapper(),
    });
    await waitFor(() => expect(result.current.data).toBeDefined());
    expect(result.current.data!.items.length).toBe(3);
    expect(result.current.data!.size).toBe(3);
  });
});

describe("useResearchSession", () => {
  it("returns null when sessionId is null", () => {
    const { result } = renderHook(() => useResearchSession(null), {
      wrapper: createWrapper(),
    });
    expect(result.current.data).toBeUndefined();
  });

  it("returns session detail with steps", async () => {
    const { result } = renderHook(() => useResearchSession("sess-001"), {
      wrapper: createWrapper(),
    });
    await waitFor(() => expect(result.current.data).toBeDefined());
    expect(result.current.data!.steps.length).toBe(5);
    expect(result.current.data!.session_id).toBe("sess-001");
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd D:/Workbench/github/cognify-dash-004/frontend && npx vitest run src/hooks/use-research-sessions.test.ts 2>&1 | tail -10`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement hooks**

Create `frontend/src/hooks/use-research-sessions.ts`:

```typescript
import { useQuery } from "@tanstack/react-query";
import type {
  PaginatedResearchSessions,
  ResearchSessionDetail,
  SessionStatus,
} from "@/types/research";
import { getMockSessions, mockSessionDetails } from "@/lib/mock/research-sessions";

async function fetchSessions(
  status?: SessionStatus,
  page = 1,
  size = 10,
): Promise<PaginatedResearchSessions> {
  // TODO: Replace with GET /api/v1/research/sessions?status=...&page=...&size=...
  return getMockSessions(status, page, size);
}

async function fetchSessionDetail(
  sessionId: string,
): Promise<ResearchSessionDetail | undefined> {
  // TODO: Replace with GET /api/v1/research/sessions/{sessionId}
  return mockSessionDetails[sessionId];
}

export function useResearchSessions(
  status?: SessionStatus,
  page = 1,
  size = 10,
) {
  return useQuery({
    queryKey: ["research-sessions", status, page, size],
    queryFn: () => fetchSessions(status, page, size),
    staleTime: 15 * 60 * 1000,
  });
}

export function useResearchSession(sessionId: string | null) {
  return useQuery({
    queryKey: ["research-session", sessionId],
    queryFn: () => fetchSessionDetail(sessionId!),
    enabled: sessionId !== null,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === "planning" || status === "in_progress") return 10_000;
      return false;
    },
  });
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd D:/Workbench/github/cognify-dash-004/frontend && npx vitest run src/hooks/use-research-sessions.test.ts 2>&1 | tail -10`
Expected: 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd D:/Workbench/github/cognify-dash-004
git add frontend/src/hooks/use-research-sessions.ts frontend/src/hooks/use-research-sessions.test.ts
git commit -m "feat(dash-004): add useResearchSessions and useResearchSession hooks"
```

---

## Task 3: SessionStatusBadge Component

**Files:**
- Create: `frontend/src/components/research/session-status-badge.test.tsx`
- Create: `frontend/src/components/research/session-status-badge.tsx`

- [ ] **Step 1: Write failing tests**

Create `frontend/src/components/research/session-status-badge.test.tsx`:

```typescript
import { render, screen } from "@testing-library/react";
import { SessionStatusBadge } from "./session-status-badge";
import type { SessionStatus } from "@/types/research";

const cases: { status: SessionStatus; label: string; dotClass: string }[] = [
  { status: "planning", label: "Planning", dotClass: "bg-blue-500" },
  { status: "in_progress", label: "In Progress", dotClass: "bg-amber-500" },
  { status: "complete", label: "Complete", dotClass: "bg-green-500" },
  { status: "failed", label: "Failed", dotClass: "bg-red-500" },
];

describe("SessionStatusBadge", () => {
  it.each(cases)("renders $label for status $status", ({ status, label }) => {
    render(<SessionStatusBadge status={status} />);
    expect(screen.getByText(label)).toBeInTheDocument();
  });

  it.each(cases)("renders colored dot for $status", ({ status, dotClass }) => {
    const { container } = render(<SessionStatusBadge status={status} />);
    const dot = container.querySelector("[data-testid='status-dot']");
    expect(dot?.className).toContain(dotClass);
  });
});
```

- [ ] **Step 2: Run to verify failure**

Run: `cd D:/Workbench/github/cognify-dash-004/frontend && npx vitest run src/components/research/session-status-badge.test.tsx 2>&1 | tail -5`
Expected: FAIL.

- [ ] **Step 3: Implement component**

Create `frontend/src/components/research/session-status-badge.tsx`:

```typescript
import { cn } from "@/lib/utils";
import type { SessionStatus } from "@/types/research";

const STATUS_CONFIG: Record<SessionStatus, { label: string; dotClass: string }> = {
  planning: { label: "Planning", dotClass: "bg-blue-500" },
  in_progress: { label: "In Progress", dotClass: "bg-amber-500" },
  complete: { label: "Complete", dotClass: "bg-green-500" },
  failed: { label: "Failed", dotClass: "bg-red-500" },
};

interface SessionStatusBadgeProps {
  status: SessionStatus;
}

export function SessionStatusBadge({ status }: SessionStatusBadgeProps) {
  const { label, dotClass } = STATUS_CONFIG[status];
  return (
    <span className="inline-flex items-center gap-1.5 text-xs font-medium text-neutral-600">
      <span data-testid="status-dot" className={cn("h-2 w-2 rounded-full", dotClass)} />
      {label}
    </span>
  );
}
```

- [ ] **Step 4: Run tests to verify pass**

Run: `cd D:/Workbench/github/cognify-dash-004/frontend && npx vitest run src/components/research/session-status-badge.test.tsx 2>&1 | tail -5`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd D:/Workbench/github/cognify-dash-004
git add frontend/src/components/research/session-status-badge.tsx frontend/src/components/research/session-status-badge.test.tsx
git commit -m "feat(dash-004): add SessionStatusBadge component"
```

---

## Task 4: SessionSteps Component

**Files:**
- Create: `frontend/src/components/research/session-steps.test.tsx`
- Create: `frontend/src/components/research/session-steps.tsx`

- [ ] **Step 1: Write failing tests**

Create `frontend/src/components/research/session-steps.test.tsx`:

```typescript
import { render, screen } from "@testing-library/react";
import { SessionSteps } from "./session-steps";
import type { AgentStep } from "@/types/research";

const mockSteps: AgentStep[] = [
  { step_name: "plan_research", status: "complete", duration_ms: 1200, started_at: "2026-03-21T10:00:00Z", completed_at: "2026-03-21T10:00:01Z" },
  { step_name: "web_search", status: "complete", duration_ms: 45000, started_at: "2026-03-21T10:00:01Z", completed_at: "2026-03-21T10:00:46Z" },
  { step_name: "evaluate", status: "running", duration_ms: null, started_at: "2026-03-21T10:00:46Z", completed_at: null },
  { step_name: "index_findings", status: "pending", duration_ms: null, started_at: "2026-03-21T10:00:46Z", completed_at: null },
  { step_name: "compile_results", status: "pending", duration_ms: null, started_at: "2026-03-21T10:00:46Z", completed_at: null },
];

describe("SessionSteps", () => {
  it("renders humanized step names", () => {
    render(<SessionSteps steps={mockSteps} isLoading={false} />);
    expect(screen.getByText("Plan Research")).toBeInTheDocument();
    expect(screen.getByText("Web Search")).toBeInTheDocument();
    expect(screen.getByText("Evaluate Findings")).toBeInTheDocument();
    expect(screen.getByText("Index Findings")).toBeInTheDocument();
    expect(screen.getByText("Compile Results")).toBeInTheDocument();
  });

  it("shows duration for completed steps", () => {
    render(<SessionSteps steps={mockSteps} isLoading={false} />);
    expect(screen.getByText("1.2s")).toBeInTheDocument();
    expect(screen.getByText("45.0s")).toBeInTheDocument();
  });

  it("shows ellipsis for running steps", () => {
    render(<SessionSteps steps={mockSteps} isLoading={false} />);
    expect(screen.getByText("...")).toBeInTheDocument();
  });

  it("renders skeleton when loading", () => {
    const { container } = render(<SessionSteps steps={[]} isLoading={true} />);
    expect(container.querySelectorAll("[data-testid='step-skeleton']").length).toBeGreaterThan(0);
  });
});
```

- [ ] **Step 2: Run to verify failure**

Run: `cd D:/Workbench/github/cognify-dash-004/frontend && npx vitest run src/components/research/session-steps.test.tsx 2>&1 | tail -5`
Expected: FAIL.

- [ ] **Step 3: Implement component**

Create `frontend/src/components/research/session-steps.tsx`:

```typescript
import { CheckCircle2, Circle, Loader2, XCircle } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import type { AgentStep } from "@/types/research";

const STEP_LABELS: Record<string, string> = {
  plan_research: "Plan Research",
  web_search: "Web Search",
  evaluate: "Evaluate Findings",
  index_findings: "Index Findings",
  compile_results: "Compile Results",
};

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function StepIcon({ status }: { status: string }) {
  switch (status) {
    case "complete":
      return <CheckCircle2 className="h-4 w-4 text-green-500" />;
    case "running":
      return <Loader2 className="h-4 w-4 animate-spin text-blue-500" />;
    case "failed":
      return <XCircle className="h-4 w-4 text-red-500" />;
    default:
      return <Circle className="h-4 w-4 text-neutral-300" />;
  }
}

interface SessionStepsProps {
  steps: AgentStep[];
  isLoading: boolean;
}

export function SessionSteps({ steps, isLoading }: SessionStepsProps) {
  if (isLoading) {
    return (
      <div className="mt-3 space-y-2 border-l-2 border-neutral-200 pl-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} data-testid="step-skeleton" className="h-5 w-48" />
        ))}
      </div>
    );
  }

  return (
    <div className="mt-3 space-y-1.5 border-l-2 border-neutral-200 pl-4">
      {steps.map((step) => (
        <div key={step.step_name} className="flex items-center gap-2 text-sm">
          <StepIcon status={step.status} />
          <span className={step.status === "pending" ? "text-neutral-400" : "text-neutral-700"}>
            {STEP_LABELS[step.step_name] ?? step.step_name}
          </span>
          <span className="ml-auto text-xs text-neutral-400">
            {step.status === "complete" && step.duration_ms !== null
              ? formatDuration(step.duration_ms)
              : step.status === "running"
                ? "..."
                : ""}
          </span>
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify pass**

Run: `cd D:/Workbench/github/cognify-dash-004/frontend && npx vitest run src/components/research/session-steps.test.tsx 2>&1 | tail -5`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd D:/Workbench/github/cognify-dash-004
git add frontend/src/components/research/session-steps.tsx frontend/src/components/research/session-steps.test.tsx
git commit -m "feat(dash-004): add SessionSteps timeline component"
```

---

## Task 5: SessionCard Component

**Files:**
- Create: `frontend/src/components/research/session-card.test.tsx`
- Create: `frontend/src/components/research/session-card.tsx`

- [ ] **Step 1: Write failing tests**

Create `frontend/src/components/research/session-card.test.tsx`:

```typescript
import { render, screen, fireEvent } from "@testing-library/react";
import { SessionCard } from "./session-card";
import type { ResearchSessionSummary } from "@/types/research";

const completeSession: ResearchSessionSummary = {
  session_id: "sess-001",
  topic_id: "topic-001",
  status: "complete",
  round_count: 3,
  findings_count: 12,
  started_at: "2026-03-20T10:00:00Z",
  topic_title: "AI Security Trends 2026",
  duration_seconds: 272,
};

const inProgressSession: ResearchSessionSummary = {
  ...completeSession,
  session_id: "sess-002",
  status: "in_progress",
  topic_title: "Zero Trust Architecture",
};

describe("SessionCard", () => {
  it("renders topic title and status badge", () => {
    render(<SessionCard session={completeSession} isExpanded={false} onToggle={() => {}} />);
    expect(screen.getByText("AI Security Trends 2026")).toBeInTheDocument();
    expect(screen.getByText("Complete")).toBeInTheDocument();
  });

  it("renders round count and findings count", () => {
    render(<SessionCard session={completeSession} isExpanded={false} onToggle={() => {}} />);
    expect(screen.getByText(/3 rounds/)).toBeInTheDocument();
    expect(screen.getByText(/12 findings/)).toBeInTheDocument();
  });

  it("renders progress bar", () => {
    const { container } = render(
      <SessionCard session={completeSession} isExpanded={false} onToggle={() => {}} />,
    );
    const bar = container.querySelector("[data-testid='progress-bar']");
    expect(bar).toBeInTheDocument();
  });

  it("calls onToggle when clicked", () => {
    const onToggle = vi.fn();
    render(<SessionCard session={completeSession} isExpanded={false} onToggle={onToggle} />);
    fireEvent.click(screen.getByText("AI Security Trends 2026"));
    expect(onToggle).toHaveBeenCalledOnce();
  });

  it("shows correct left border color for each status", () => {
    const { container: c1 } = render(
      <SessionCard session={completeSession} isExpanded={false} onToggle={() => {}} />,
    );
    expect(c1.firstChild?.className).toContain("border-l-green-500");

    const { container: c2 } = render(
      <SessionCard session={inProgressSession} isExpanded={false} onToggle={() => {}} />,
    );
    expect(c2.firstChild?.className).toContain("border-l-amber-500");
  });

  it("renders children when expanded", () => {
    render(
      <SessionCard session={completeSession} isExpanded={true} onToggle={() => {}}>
        <div>Expanded content</div>
      </SessionCard>,
    );
    expect(screen.getByText("Expanded content")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run to verify failure**

Run: `cd D:/Workbench/github/cognify-dash-004/frontend && npx vitest run src/components/research/session-card.test.tsx 2>&1 | tail -5`
Expected: FAIL.

- [ ] **Step 3: Implement component**

Create `frontend/src/components/research/session-card.tsx`:

```typescript
import type { ReactNode } from "react";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";
import { SessionStatusBadge } from "./session-status-badge";
import type { ResearchSessionSummary, SessionStatus } from "@/types/research";

const BORDER_COLORS: Record<SessionStatus, string> = {
  planning: "border-l-blue-500",
  in_progress: "border-l-amber-500",
  complete: "border-l-green-500",
  failed: "border-l-red-500",
};

const PROGRESS_COLORS: Record<SessionStatus, string> = {
  planning: "bg-blue-500",
  in_progress: "bg-amber-500",
  complete: "bg-green-500",
  failed: "bg-red-500",
};

function getProgressPercent(session: ResearchSessionSummary): number {
  switch (session.status) {
    case "complete":
      return 100;
    case "planning":
      return 15;
    case "in_progress":
      return 50;
    case "failed":
      return Math.min(Math.round((session.round_count / 3) * 100), 90);
  }
}

function formatDuration(seconds: number | null | undefined): string {
  if (seconds == null) return "";
  const mins = Math.floor(seconds / 60);
  const secs = Math.round(seconds % 60);
  if (mins === 0) return `${secs}s`;
  return `${mins}m ${secs}s`;
}

interface SessionCardProps {
  session: ResearchSessionSummary;
  isExpanded: boolean;
  onToggle: () => void;
  children?: ReactNode;
}

export function SessionCard({ session, isExpanded, onToggle, children }: SessionCardProps) {
  const progress = getProgressPercent(session);

  return (
    <div
      className={cn(
        "rounded-lg border border-neutral-200 border-l-4 bg-white shadow-sm transition-shadow hover:shadow-md",
        BORDER_COLORS[session.status],
      )}
    >
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-start justify-between p-4 text-left"
      >
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-3">
            <h3 className="truncate font-heading text-sm font-semibold text-neutral-900">
              {session.topic_title ?? session.session_id}
            </h3>
            <SessionStatusBadge status={session.status} />
          </div>
          <p className="mt-1 text-xs text-neutral-500">
            {session.round_count} rounds · {session.findings_count} findings
            {session.duration_seconds ? ` · ${formatDuration(session.duration_seconds)}` : ""}
          </p>
          <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-neutral-100">
            <div
              data-testid="progress-bar"
              className={cn("h-full rounded-full transition-all", PROGRESS_COLORS[session.status])}
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
        <ChevronDown
          className={cn(
            "ml-3 h-4 w-4 shrink-0 text-neutral-400 transition-transform",
            isExpanded && "rotate-180",
          )}
        />
      </button>
      {isExpanded && <div className="border-t border-neutral-100 px-4 pb-4">{children}</div>}
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify pass**

Run: `cd D:/Workbench/github/cognify-dash-004/frontend && npx vitest run src/components/research/session-card.test.tsx 2>&1 | tail -5`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd D:/Workbench/github/cognify-dash-004
git add frontend/src/components/research/session-card.tsx frontend/src/components/research/session-card.test.tsx
git commit -m "feat(dash-004): add SessionCard expandable component"
```

---

## Task 6: SessionFilters and KnowledgeBaseStub

**Files:**
- Create: `frontend/src/components/research/session-filters.test.tsx`
- Create: `frontend/src/components/research/session-filters.tsx`
- Create: `frontend/src/components/research/knowledge-base-stub.test.tsx`
- Create: `frontend/src/components/research/knowledge-base-stub.tsx`

- [ ] **Step 1: Write failing tests for SessionFilters**

Create `frontend/src/components/research/session-filters.test.tsx`:

```typescript
import { render, screen, fireEvent } from "@testing-library/react";
import { SessionFilters } from "./session-filters";

describe("SessionFilters", () => {
  it("renders all 5 filter tabs", () => {
    render(<SessionFilters activeFilter="all" onFilterChange={() => {}} totalCount={8} />);
    expect(screen.getByText("All")).toBeInTheDocument();
    expect(screen.getByText("Planning")).toBeInTheDocument();
    expect(screen.getByText("In Progress")).toBeInTheDocument();
    expect(screen.getByText("Complete")).toBeInTheDocument();
    expect(screen.getByText("Failed")).toBeInTheDocument();
  });

  it("shows total count", () => {
    render(<SessionFilters activeFilter="all" onFilterChange={() => {}} totalCount={8} />);
    expect(screen.getByText("8 Sessions")).toBeInTheDocument();
  });

  it("calls onFilterChange with correct value", () => {
    const onChange = vi.fn();
    render(<SessionFilters activeFilter="all" onFilterChange={onChange} totalCount={8} />);
    fireEvent.click(screen.getByText("Complete"));
    expect(onChange).toHaveBeenCalledWith("complete");
  });

  it("highlights active filter", () => {
    render(<SessionFilters activeFilter="complete" onFilterChange={() => {}} totalCount={4} />);
    const completeBtn = screen.getByText("Complete");
    expect(completeBtn.className).toContain("bg-primary");
  });
});
```

- [ ] **Step 2: Write failing test for KnowledgeBaseStub**

Create `frontend/src/components/research/knowledge-base-stub.test.tsx`:

```typescript
import { render, screen } from "@testing-library/react";
import { KnowledgeBaseStub } from "./knowledge-base-stub";

describe("KnowledgeBaseStub", () => {
  it("renders placeholder text", () => {
    render(<KnowledgeBaseStub />);
    expect(screen.getByText("Knowledge Base")).toBeInTheDocument();
    expect(screen.getByText(/coming in a future update/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 3: Run to verify both fail**

Run: `cd D:/Workbench/github/cognify-dash-004/frontend && npx vitest run src/components/research/session-filters.test.tsx src/components/research/knowledge-base-stub.test.tsx 2>&1 | tail -5`
Expected: FAIL.

- [ ] **Step 4: Implement SessionFilters**

Create `frontend/src/components/research/session-filters.tsx`:

```typescript
import { cn } from "@/lib/utils";
import type { SessionStatus } from "@/types/research";

type FilterValue = SessionStatus | "all";

const FILTERS: { value: FilterValue; label: string }[] = [
  { value: "all", label: "All" },
  { value: "planning", label: "Planning" },
  { value: "in_progress", label: "In Progress" },
  { value: "complete", label: "Complete" },
  { value: "failed", label: "Failed" },
];

interface SessionFiltersProps {
  activeFilter: FilterValue;
  onFilterChange: (filter: FilterValue) => void;
  totalCount: number;
}

export function SessionFilters({ activeFilter, onFilterChange, totalCount }: SessionFiltersProps) {
  return (
    <div className="flex items-center justify-between">
      <div className="flex gap-2">
        {FILTERS.map(({ value, label }) => (
          <button
            key={value}
            type="button"
            onClick={() => onFilterChange(value)}
            className={cn(
              "rounded-full px-3 py-1 text-xs font-medium transition-colors",
              activeFilter === value
                ? "bg-primary text-white"
                : "bg-neutral-100 text-neutral-600 hover:bg-neutral-200",
            )}
          >
            {label}
          </button>
        ))}
      </div>
      <span className="text-sm text-neutral-500">{totalCount} Sessions</span>
    </div>
  );
}
```

- [ ] **Step 5: Implement KnowledgeBaseStub**

Create `frontend/src/components/research/knowledge-base-stub.tsx`:

```typescript
import { Database } from "lucide-react";

export function KnowledgeBaseStub() {
  return (
    <div className="flex items-center gap-3 rounded-lg border border-dashed border-neutral-300 bg-neutral-50 p-4">
      <Database className="h-5 w-5 text-neutral-400" />
      <div>
        <p className="text-sm font-medium text-neutral-600">Knowledge Base</p>
        <p className="text-xs text-neutral-400">Stats and data source connectors coming in a future update.</p>
      </div>
    </div>
  );
}
```

- [ ] **Step 6: Run tests to verify pass**

Run: `cd D:/Workbench/github/cognify-dash-004/frontend && npx vitest run src/components/research/session-filters.test.tsx src/components/research/knowledge-base-stub.test.tsx 2>&1 | tail -10`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
cd D:/Workbench/github/cognify-dash-004
git add frontend/src/components/research/session-filters.tsx frontend/src/components/research/session-filters.test.tsx frontend/src/components/research/knowledge-base-stub.tsx frontend/src/components/research/knowledge-base-stub.test.tsx
git commit -m "feat(dash-004): add SessionFilters and KnowledgeBaseStub"
```

---

## Task 7: Research Sessions Page Assembly

**Files:**
- Modify: `frontend/src/app/(dashboard)/research/page.tsx`
- Create: `frontend/src/app/(dashboard)/research/page.test.tsx`

- [ ] **Step 1: Write failing page tests**

Create `frontend/src/app/(dashboard)/research/page.test.tsx`:

```typescript
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import ResearchPage from "./page";

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

describe("ResearchPage", () => {
  it("renders header", async () => {
    render(<ResearchPage />, { wrapper: createWrapper() });
    expect(screen.getByText("Research Sessions")).toBeInTheDocument();
  });

  it("renders filter tabs", async () => {
    render(<ResearchPage />, { wrapper: createWrapper() });
    await waitFor(() => expect(screen.getByText("All")).toBeInTheDocument());
    expect(screen.getByText("Complete")).toBeInTheDocument();
    expect(screen.getByText("Failed")).toBeInTheDocument();
  });

  it("renders session cards from mock data", async () => {
    render(<ResearchPage />, { wrapper: createWrapper() });
    await waitFor(() => expect(screen.getByText("AI Security Trends 2026")).toBeInTheDocument());
    expect(screen.getByText("Zero Trust Architecture")).toBeInTheDocument();
  });

  it("filters sessions by status tab", async () => {
    render(<ResearchPage />, { wrapper: createWrapper() });
    await waitFor(() => expect(screen.getByText("AI Security Trends 2026")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Failed"));
    await waitFor(() => {
      expect(screen.getByText("Quantum Computing Risks")).toBeInTheDocument();
      expect(screen.queryByText("AI Security Trends 2026")).not.toBeInTheDocument();
    });
  });

  it("expands card to show agent steps", async () => {
    render(<ResearchPage />, { wrapper: createWrapper() });
    await waitFor(() => expect(screen.getByText("AI Security Trends 2026")).toBeInTheDocument());
    fireEvent.click(screen.getByText("AI Security Trends 2026"));
    await waitFor(() => expect(screen.getByText("Plan Research")).toBeInTheDocument());
  });

  it("collapses expanded card on second click", async () => {
    render(<ResearchPage />, { wrapper: createWrapper() });
    await waitFor(() => expect(screen.getByText("AI Security Trends 2026")).toBeInTheDocument());
    fireEvent.click(screen.getByText("AI Security Trends 2026"));
    await waitFor(() => expect(screen.getByText("Plan Research")).toBeInTheDocument());
    fireEvent.click(screen.getByText("AI Security Trends 2026"));
    await waitFor(() => expect(screen.queryByText("Plan Research")).not.toBeInTheDocument());
  });

  it("renders knowledge base stub", async () => {
    render(<ResearchPage />, { wrapper: createWrapper() });
    await waitFor(() => expect(screen.getByText("Knowledge Base")).toBeInTheDocument());
  });
});
```

- [ ] **Step 2: Run to verify failure**

Run: `cd D:/Workbench/github/cognify-dash-004/frontend && npx vitest run src/app/\\(dashboard\\)/research/page.test.tsx 2>&1 | tail -10`
Expected: FAIL (page still renders placeholder).

- [ ] **Step 3: Implement the page**

Replace `frontend/src/app/(dashboard)/research/page.tsx`:

```typescript
"use client";

import { useState } from "react";
import { Header } from "@/components/layout/header";
import { Skeleton } from "@/components/ui/skeleton";
import { SessionCard } from "@/components/research/session-card";
import { SessionSteps } from "@/components/research/session-steps";
import { SessionFilters } from "@/components/research/session-filters";
import { KnowledgeBaseStub } from "@/components/research/knowledge-base-stub";
import { TopicPagination } from "@/components/topics/topic-pagination";
import { useResearchSessions, useResearchSession } from "@/hooks/use-research-sessions";
import type { SessionStatus } from "@/types/research";

const PAGE_SIZE = 10;

export default function ResearchPage() {
  const [activeFilter, setActiveFilter] = useState<SessionStatus | "all">("all");
  const [expandedSessionId, setExpandedSessionId] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState(1);

  const sessionsQuery = useResearchSessions(
    activeFilter === "all" ? undefined : activeFilter,
    currentPage,
    PAGE_SIZE,
  );
  const detailQuery = useResearchSession(expandedSessionId);

  function handleFilterChange(filter: SessionStatus | "all") {
    setActiveFilter(filter);
    setCurrentPage(1);
    setExpandedSessionId(null);
  }

  function handleToggle(sessionId: string) {
    setExpandedSessionId((prev) => (prev === sessionId ? null : sessionId));
  }

  const sessions = sessionsQuery.data?.items ?? [];
  const totalCount = sessionsQuery.data?.total ?? 0;
  const totalPages = Math.ceil(totalCount / PAGE_SIZE);

  return (
    <div className="space-y-6">
      <Header title="Research Sessions" subtitle="Monitor agent research workflows" />

      <SessionFilters
        activeFilter={activeFilter}
        onFilterChange={handleFilterChange}
        totalCount={totalCount}
      />

      {sessionsQuery.isLoading ? (
        <div className="space-y-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-24 w-full rounded-lg" />
          ))}
        </div>
      ) : sessions.length === 0 ? (
        <div className="rounded-lg border border-dashed border-neutral-300 bg-neutral-50 py-12 text-center">
          <p className="text-sm text-neutral-500">No research sessions found.</p>
          <p className="mt-1 text-xs text-neutral-400">
            {activeFilter !== "all"
              ? `No sessions with status "${activeFilter}". Try a different filter.`
              : "Start a research session from Topic Discovery."}
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {sessions.map((session) => (
            <SessionCard
              key={session.session_id}
              session={session}
              isExpanded={expandedSessionId === session.session_id}
              onToggle={() => handleToggle(session.session_id)}
            >
              <SessionSteps
                steps={detailQuery.data?.steps ?? []}
                isLoading={detailQuery.isLoading}
              />
            </SessionCard>
          ))}
        </div>
      )}

      <KnowledgeBaseStub />

      {totalPages > 1 && (
        <TopicPagination
          currentPage={currentPage}
          totalPages={totalPages}
          onPageChange={setCurrentPage}
        />
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run page tests to verify pass**

Run: `cd D:/Workbench/github/cognify-dash-004/frontend && npx vitest run src/app/\\(dashboard\\)/research/page.test.tsx 2>&1 | tail -10`
Expected: PASS.

- [ ] **Step 5: Run full test suite**

Run: `cd D:/Workbench/github/cognify-dash-004/frontend && npx vitest run 2>&1 | tail -10`
Expected: All tests pass (191 existing + ~30 new ≈ 221+).

- [ ] **Step 6: Commit**

```bash
cd D:/Workbench/github/cognify-dash-004
git add frontend/src/app/\(dashboard\)/research/page.tsx frontend/src/app/\(dashboard\)/research/page.test.tsx
git commit -m "feat(dash-004): assemble Research Sessions page with all components"
```

---

## Task 8: Final Verification and Cleanup

**Files:** None new — verification only.

- [ ] **Step 1: Run full frontend test suite**

Run: `cd D:/Workbench/github/cognify-dash-004/frontend && npx vitest run 2>&1 | tail -15`
Expected: All tests pass, 0 failures.

- [ ] **Step 2: Run TypeScript check**

Run: `cd D:/Workbench/github/cognify-dash-004/frontend && npx tsc --noEmit 2>&1 | tail -10`
Expected: No errors.

- [ ] **Step 3: Run ESLint**

Run: `cd D:/Workbench/github/cognify-dash-004/frontend && npx eslint src/ 2>&1 | tail -10`
Expected: No errors.

- [ ] **Step 4: Verify no lint warnings that could be fixed**

If ESLint shows warnings, fix them and commit:

```bash
cd D:/Workbench/github/cognify-dash-004
git add -A && git commit -m "fix(dash-004): resolve lint warnings"
```

- [ ] **Step 5: Verify test count increased**

The baseline was 191 tests. New tests should bring total to ~220+. If significantly less, investigate missing test files.
