import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { WorkflowSteps } from "./workflow-steps";
import type { WorkflowStep } from "@/types/articles";

const mockSteps: WorkflowStep[] = [
  { name: "Research", durationSeconds: 45 },
  { name: "Outline", durationSeconds: 12 },
  { name: "Drafting", durationSeconds: 90 },
];

describe("WorkflowSteps", () => {
  it("renders all step names", () => {
    render(<WorkflowSteps steps={mockSteps} />);
    expect(screen.getByText("Research")).toBeInTheDocument();
    expect(screen.getByText("Outline")).toBeInTheDocument();
    expect(screen.getByText("Drafting")).toBeInTheDocument();
  });

  it("renders durations", () => {
    render(<WorkflowSteps steps={mockSteps} />);
    expect(screen.getByText("(45s)")).toBeInTheDocument();
    expect(screen.getByText("(12s)")).toBeInTheDocument();
    expect(screen.getByText("(90s)")).toBeInTheDocument();
  });

  it("renders checkmark icons", () => {
    const { container } = render(<WorkflowSteps steps={mockSteps} />);
    const checks = container.querySelectorAll("[data-testid='step-check']");
    expect(checks).toHaveLength(3);
  });
});
