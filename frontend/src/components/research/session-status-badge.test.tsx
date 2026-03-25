import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { SessionStatusBadge } from "./session-status-badge";
import type { SessionStatus } from "@/types/research";

const cases: { status: SessionStatus; label: string; dotClass: string }[] = [
  { status: "planning", label: "Planning", dotClass: "bg-blue-500" },
  { status: "in_progress", label: "In Progress", dotClass: "bg-amber-500" },
  { status: "complete", label: "Research Complete", dotClass: "bg-blue-500" },
  { status: "article_complete", label: "Article Ready", dotClass: "bg-green-500" },
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
