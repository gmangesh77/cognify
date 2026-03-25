import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { SessionCard } from "./session-card";
import type { ResearchSessionSummary } from "@/types/research";

const completeSession: ResearchSessionSummary = {
  session_id: "sess-001",
  topic_id: "topic-001",
  status: "complete",
  round_count: 3,
  findings_count: 12,
  sources_count: 8,
  embeddings_count: 24,
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
    expect(screen.getByText("Research Complete")).toBeInTheDocument();
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
    expect((c1.firstChild as HTMLElement)?.className).toContain("border-l-blue-500");

    const { container: c2 } = render(
      <SessionCard session={inProgressSession} isExpanded={false} onToggle={() => {}} />,
    );
    expect((c2.firstChild as HTMLElement)?.className).toContain("border-l-amber-500");
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
