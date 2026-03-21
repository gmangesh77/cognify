import { describe, it, expect } from "vitest";
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
