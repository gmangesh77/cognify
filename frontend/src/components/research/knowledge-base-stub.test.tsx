import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { KnowledgeBaseStub } from "./knowledge-base-stub";
import type { ResearchSessionSummary } from "@/types/research";

const mockSessions: ResearchSessionSummary[] = [
  {
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
  },
  {
    session_id: "sess-002",
    topic_id: "topic-002",
    status: "in_progress",
    round_count: 2,
    findings_count: 8,
    sources_count: 5,
    embeddings_count: 15,
    topic_title: "Zero Trust Architecture",
    duration_seconds: 135,
    started_at: "2026-03-21T09:30:00Z",
  },
  {
    session_id: "sess-003",
    topic_id: "topic-003",
    status: "complete",
    round_count: 2,
    findings_count: 9,
    sources_count: 6,
    embeddings_count: 18,
    topic_title: "Cloud Security Posture",
    duration_seconds: 198,
    started_at: "2026-03-19T14:00:00Z",
  },
];

describe("KnowledgeBaseStub", () => {
  it("renders completed session count", () => {
    render(<KnowledgeBaseStub sessions={mockSessions} />);
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("Sessions")).toBeInTheDocument();
  });

  it("renders total sources count", () => {
    render(<KnowledgeBaseStub sessions={mockSessions} />);
    // 8 + 5 + 6 = 19
    expect(screen.getByText("19")).toBeInTheDocument();
    expect(screen.getByText("Sources")).toBeInTheDocument();
  });

  it("renders total embeddings count", () => {
    render(<KnowledgeBaseStub sessions={mockSessions} />);
    // 24 + 15 + 18 = 57
    expect(screen.getByText("57")).toBeInTheDocument();
    expect(screen.getByText("Embeddings")).toBeInTheDocument();
  });

  it("renders zeroes for empty sessions", () => {
    render(<KnowledgeBaseStub sessions={[]} />);
    const zeros = screen.getAllByText("0");
    expect(zeros.length).toBe(3);
  });
});
