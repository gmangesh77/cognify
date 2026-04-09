import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { LlmCallCard } from "../llm-call-card";
import type { LlmCallResponse } from "@/types/pipeline-debug";

const makeCall = (overrides: Partial<LlmCallResponse> = {}): LlmCallResponse => ({
  id: "call-1",
  step_id: "step-1",
  call_name: "plan_research",
  model_name: "claude-sonnet-4-20250514",
  prompt_messages: [
    { role: "system", content: "You are a research planner." },
    { role: "human", content: "Plan research for topic X." },
  ],
  response_content: '{"facets": ["A", "B"]}',
  input_tokens: 150,
  output_tokens: 80,
  duration_ms: 1200,
  error: null,
  started_at: "2026-04-02T10:00:00Z",
  completed_at: "2026-04-02T10:00:01.2Z",
  ...overrides,
});

describe("LlmCallCard", () => {
  it("renders model name and duration", () => {
    render(<LlmCallCard call={makeCall()} />);
    expect(screen.getByText("claude-sonnet-4-20250514")).toBeInTheDocument();
    expect(screen.getByText("1200ms")).toBeInTheDocument();
  });

  it("renders token counts", () => {
    render(<LlmCallCard call={makeCall()} />);
    expect(screen.getByText(/150 → 80 tokens/)).toBeInTheDocument();
  });

  it("shows error when present", () => {
    render(<LlmCallCard call={makeCall({ error: "LLM rate limited" })} />);
    expect(screen.getByText("LLM rate limited")).toBeInTheDocument();
  });

  it("expands prompt on click", async () => {
    const user = userEvent.setup();
    render(<LlmCallCard call={makeCall()} />);
    await user.click(screen.getByText("Prompt"));
    expect(screen.getByText("system")).toBeInTheDocument();
    expect(screen.getByText("You are a research planner.")).toBeInTheDocument();
  });

  it("expands response on click", async () => {
    const user = userEvent.setup();
    render(<LlmCallCard call={makeCall()} />);
    await user.click(screen.getByText("Response"));
    expect(screen.getByText(/facets/)).toBeInTheDocument();
  });

  it("shows prompt message count", () => {
    render(<LlmCallCard call={makeCall()} />);
    expect(screen.getByText("(2)")).toBeInTheDocument();
  });

  it("handles missing tokens gracefully", () => {
    render(
      <LlmCallCard
        call={makeCall({ input_tokens: null, output_tokens: null })}
      />,
    );
    expect(screen.getByText("claude-sonnet-4-20250514")).toBeInTheDocument();
  });
});
