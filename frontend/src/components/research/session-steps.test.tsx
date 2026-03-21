import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { SessionSteps } from "./session-steps";
import type { AgentStep } from "@/types/research";

const mockSteps: AgentStep[] = [
  { step_name: "plan_research", status: "complete", duration_ms: 1200, started_at: "2026-03-21T10:00:00Z", completed_at: "2026-03-21T10:00:01Z", output_summary: null },
  { step_name: "research_facet_0", status: "complete", duration_ms: 45000, started_at: "2026-03-21T10:00:01Z", completed_at: "2026-03-21T10:00:46Z", output_summary: "Found 5 relevant sources" },
  { step_name: "evaluate_completeness", status: "running", duration_ms: null, started_at: "2026-03-21T10:00:46Z", completed_at: null, output_summary: null },
  { step_name: "index_findings", status: "pending", duration_ms: null, started_at: "2026-03-21T10:00:46Z", completed_at: null, output_summary: null },
  { step_name: "finalize", status: "pending", duration_ms: null, started_at: "2026-03-21T10:00:46Z", completed_at: null, output_summary: null },
];

describe("SessionSteps", () => {
  it("renders humanized step names", () => {
    render(<SessionSteps steps={mockSteps} isLoading={false} />);
    expect(screen.getByText("Plan Research")).toBeInTheDocument();
    expect(screen.getByText("Research Facet 0")).toBeInTheDocument();
    expect(screen.getByText("Evaluate Completeness")).toBeInTheDocument();
    expect(screen.getByText("Index Findings")).toBeInTheDocument();
    expect(screen.getByText("Finalize")).toBeInTheDocument();
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

  it("renders output_summary when present", () => {
    render(<SessionSteps steps={mockSteps} isLoading={false} />);
    expect(screen.getByText("Found 5 relevant sources")).toBeInTheDocument();
  });

  it("renders research_facet with round label", () => {
    const stepsWithRound: AgentStep[] = [
      { step_name: "research_facet_1_round_2", status: "complete", duration_ms: 3000, started_at: "2026-03-21T10:00:00Z", completed_at: "2026-03-21T10:00:03Z", output_summary: null },
    ];
    render(<SessionSteps steps={stepsWithRound} isLoading={false} />);
    expect(screen.getByText("Research Facet 1 (Round 2)")).toBeInTheDocument();
  });
});
