import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useResearchSessions, useResearchSession } from "./use-research-sessions";
import type {
  PaginatedResearchSessions,
  ResearchSessionDetail,
  ResearchSessionSummary,
} from "@/types/research";

vi.mock("@/lib/api/research", () => ({
  fetchSessions: vi.fn(),
  fetchSessionDetail: vi.fn(),
}));

import { fetchSessions, fetchSessionDetail } from "@/lib/api/research";

const mockFetchSessions = vi.mocked(fetchSessions);
const mockFetchSessionDetail = vi.mocked(fetchSessionDetail);

const baseSummary: ResearchSessionSummary = {
  session_id: "sess-001",
  topic_id: "topic-001",
  status: "complete",
  round_count: 3,
  findings_count: 12,
  sources_count: 8,
  embeddings_count: 24,
  topic_title: "AI Security Trends 2026",
  duration_seconds: 272,
  started_at: "2026-03-20T10:00:00Z",
};

const allSessions: ResearchSessionSummary[] = [
  baseSummary,
  { ...baseSummary, session_id: "sess-002", status: "in_progress", topic_title: "Zero Trust Architecture" },
  { ...baseSummary, session_id: "sess-003", status: "failed", topic_title: "Quantum Computing Risks" },
  { ...baseSummary, session_id: "sess-004", status: "planning", topic_title: "Supply Chain Attacks" },
  { ...baseSummary, session_id: "sess-005", status: "complete", topic_title: "Cloud Security Posture" },
  { ...baseSummary, session_id: "sess-006", status: "in_progress", topic_title: "Ransomware Evolution" },
  { ...baseSummary, session_id: "sess-007", status: "complete", topic_title: "API Security Best Practices" },
  { ...baseSummary, session_id: "sess-008", status: "complete", topic_title: "Insider Threat Detection" },
];

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("useResearchSessions", () => {
  it("returns paginated sessions", async () => {
    mockFetchSessions.mockResolvedValue({
      items: allSessions,
      total: 8,
      page: 1,
      size: 10,
    });

    const { result } = renderHook(() => useResearchSessions(), {
      wrapper: createWrapper(),
    });
    await waitFor(() => expect(result.current.data).toBeDefined());
    expect(result.current.data!.items.length).toBeGreaterThan(0);
    expect(result.current.data!.total).toBe(8);
    expect(result.current.data!.page).toBe(1);
  });

  it("filters by status", async () => {
    const completeSessions = allSessions.filter((s) => s.status === "complete");
    mockFetchSessions.mockResolvedValue({
      items: completeSessions,
      total: completeSessions.length,
      page: 1,
      size: 10,
    });

    const { result } = renderHook(() => useResearchSessions("complete"), {
      wrapper: createWrapper(),
    });
    await waitFor(() => expect(result.current.data).toBeDefined());
    expect(result.current.data!.items.every((s) => s.status === "complete")).toBe(true);
  });

  it("respects page and size params", async () => {
    mockFetchSessions.mockResolvedValue({
      items: allSessions.slice(0, 3),
      total: 8,
      page: 1,
      size: 3,
    });

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
    const detail: ResearchSessionDetail = {
      ...baseSummary,
      completed_at: "2026-03-20T10:04:32Z",
      steps: [
        { step_name: "plan_research", status: "complete", duration_ms: 1200, started_at: "2026-03-21T10:00:00Z", completed_at: "2026-03-21T10:00:01Z", output_summary: null },
        { step_name: "research_facet_0", status: "complete", duration_ms: 45000, started_at: "2026-03-21T10:00:01Z", completed_at: "2026-03-21T10:00:46Z", output_summary: "Found 5 sources" },
        { step_name: "evaluate_completeness", status: "complete", duration_ms: 2000, started_at: "2026-03-21T10:00:46Z", completed_at: "2026-03-21T10:00:48Z", output_summary: null },
        { step_name: "index_findings", status: "complete", duration_ms: 8000, started_at: "2026-03-21T10:00:48Z", completed_at: "2026-03-21T10:00:56Z", output_summary: null },
        { step_name: "finalize", status: "complete", duration_ms: 3000, started_at: "2026-03-21T10:00:56Z", completed_at: "2026-03-21T10:00:59Z", output_summary: null },
      ],
    };
    mockFetchSessionDetail.mockResolvedValue(detail);

    const { result } = renderHook(() => useResearchSession("sess-001"), {
      wrapper: createWrapper(),
    });
    await waitFor(() => expect(result.current.data).toBeDefined());
    expect(result.current.data!.steps.length).toBe(5);
    expect(result.current.data!.session_id).toBe("sess-001");
  });
});
