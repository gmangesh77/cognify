import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { StepTimeline } from "../step-timeline";
import type { DebugStepResponse } from "@/types/pipeline-debug";

const makeStep = (overrides: Partial<DebugStepResponse> = {}): DebugStepResponse => ({
  id: "step-1",
  step_name: "plan_research",
  status: "complete",
  input_data: {},
  output_data: { facet_count: 3 },
  duration_ms: 1200,
  started_at: "2026-04-02T10:00:00Z",
  completed_at: "2026-04-02T10:00:01.2Z",
  llm_calls: [],
  ...overrides,
});

describe("StepTimeline", () => {
  it("renders step name with human-readable label", () => {
    render(<StepTimeline steps={[makeStep()]} />);
    expect(screen.getByText("Plan Research")).toBeInTheDocument();
  });

  it("renders content step label", () => {
    render(<StepTimeline steps={[makeStep({ step_name: "content_outline" })]} />);
    expect(screen.getByText("Generate Outline")).toBeInTheDocument();
  });

  it("renders research facet step label", () => {
    render(<StepTimeline steps={[makeStep({ step_name: "research_facet_0" })]} />);
    expect(screen.getByText("Research Facet 0")).toBeInTheDocument();
  });

  it("renders facet with round number", () => {
    render(
      <StepTimeline steps={[makeStep({ step_name: "research_facet_1_round_2" })]} />,
    );
    expect(screen.getByText("Research Facet 1 (Round 2)")).toBeInTheDocument();
  });

  it("shows output summary with facet count", () => {
    render(<StepTimeline steps={[makeStep({ output_data: { facet_count: 5 } })]} />);
    expect(screen.getByText(/5 facets/)).toBeInTheDocument();
  });

  it("shows duration in seconds", () => {
    render(<StepTimeline steps={[makeStep({ duration_ms: 3500 })]} />);
    expect(screen.getByText("3.5s")).toBeInTheDocument();
  });

  it("shows duration in ms for fast steps", () => {
    render(<StepTimeline steps={[makeStep({ duration_ms: 450 })]} />);
    expect(screen.getByText("450ms")).toBeInTheDocument();
  });

  it("shows LLM call count badge", () => {
    render(
      <StepTimeline
        steps={[
          makeStep({
            llm_calls: [
              {
                id: "c1",
                step_id: "step-1",
                call_name: "plan",
                model_name: "claude",
                prompt_messages: [],
                response_content: "ok",
                input_tokens: null,
                output_tokens: null,
                duration_ms: 100,
                error: null,
                started_at: "2026-04-02T10:00:00Z",
                completed_at: "2026-04-02T10:00:00.1Z",
              },
            ],
          }),
        ]}
      />,
    );
    expect(screen.getByText("1")).toBeInTheDocument();
  });

  it("expands step on click to show output JSON", async () => {
    const user = userEvent.setup();
    render(
      <StepTimeline
        steps={[makeStep({ output_data: { facet_count: 3, facet_titles: ["A", "B"] } })]}
      />,
    );
    await user.click(screen.getByText("Plan Research"));
    expect(screen.getByText("Output")).toBeInTheDocument();
  });

  it("renders multiple steps", () => {
    const steps = [
      makeStep({ id: "s1", step_name: "plan_research" }),
      makeStep({ id: "s2", step_name: "content_draft" }),
    ];
    render(<StepTimeline steps={steps} />);
    expect(screen.getByText("Plan Research")).toBeInTheDocument();
    expect(screen.getByText("Draft Sections")).toBeInTheDocument();
  });
});
