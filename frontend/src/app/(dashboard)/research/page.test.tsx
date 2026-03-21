import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import type {
  PaginatedResearchSessions,
  ResearchSessionDetail,
  ResearchSessionSummary,
} from "@/types/research";
import ResearchPage from "./page";

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
  {
    ...baseSummary,
    session_id: "sess-002",
    status: "in_progress",
    topic_title: "Zero Trust Architecture",
    sources_count: 5,
    embeddings_count: 15,
  },
  {
    ...baseSummary,
    session_id: "sess-003",
    status: "failed",
    round_count: 1,
    findings_count: 0,
    topic_title: "Quantum Computing Risks",
    duration_seconds: 45,
    sources_count: 0,
    embeddings_count: 0,
  },
];

const sessionsResponse: PaginatedResearchSessions = {
  items: allSessions,
  total: 3,
  page: 1,
  size: 10,
};

const detailResponse: ResearchSessionDetail = {
  ...baseSummary,
  completed_at: "2026-03-20T10:04:32Z",
  steps: [
    { step_name: "plan_research", status: "complete", duration_ms: 1200, started_at: "2026-03-21T10:00:00Z", completed_at: "2026-03-21T10:00:01Z", output_summary: null },
    { step_name: "research_facet_0", status: "complete", duration_ms: 45000, started_at: "2026-03-21T10:00:01Z", completed_at: "2026-03-21T10:00:46Z", output_summary: null },
    { step_name: "evaluate_completeness", status: "complete", duration_ms: 2000, started_at: "2026-03-21T10:00:46Z", completed_at: "2026-03-21T10:00:48Z", output_summary: null },
    { step_name: "index_findings", status: "complete", duration_ms: 8000, started_at: "2026-03-21T10:00:48Z", completed_at: "2026-03-21T10:00:56Z", output_summary: null },
    { step_name: "finalize", status: "complete", duration_ms: 3000, started_at: "2026-03-21T10:00:56Z", completed_at: "2026-03-21T10:00:59Z", output_summary: null },
  ],
};

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
  mockFetchSessions.mockResolvedValue(sessionsResponse);
  mockFetchSessionDetail.mockResolvedValue(detailResponse);
});

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

  it("renders session cards from API data", async () => {
    render(<ResearchPage />, { wrapper: createWrapper() });
    await waitFor(() => expect(screen.getByText("AI Security Trends 2026")).toBeInTheDocument());
    expect(screen.getByText("Zero Trust Architecture")).toBeInTheDocument();
  });

  it("filters sessions by status tab", async () => {
    render(<ResearchPage />, { wrapper: createWrapper() });
    await waitFor(() => expect(screen.getByText("AI Security Trends 2026")).toBeInTheDocument());

    const failedOnly: PaginatedResearchSessions = {
      items: [allSessions[2]],
      total: 1,
      page: 1,
      size: 10,
    };
    mockFetchSessions.mockResolvedValue(failedOnly);

    fireEvent.click(screen.getByRole("button", { name: "Failed" }));
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

  it("renders knowledge base stats", async () => {
    render(<ResearchPage />, { wrapper: createWrapper() });
    await waitFor(() => expect(screen.getByText("Sessions")).toBeInTheDocument());
    expect(screen.getByText("Sources")).toBeInTheDocument();
    expect(screen.getByText("Embeddings")).toBeInTheDocument();
  });
});
