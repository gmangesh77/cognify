import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { ModelTieringCard } from "./model-tiering-card";

describe("ModelTieringCard", () => {
  it("shows the empty state when no steps are mapped", () => {
    render(<ModelTieringCard defaultModel="claude-sonnet-4-6" modelByStep={{}} />);
    expect(screen.getByTestId("tiering-default-model")).toHaveTextContent("claude-sonnet-4-6");
    expect(screen.getByTestId("tiering-empty")).toBeInTheDocument();
    expect(screen.queryAllByTestId("tiering-row")).toHaveLength(0);
  });

  it("lists mapped steps sorted by step name", () => {
    render(
      <ModelTieringCard
        defaultModel="claude-sonnet-4-6"
        modelByStep={{ content_validate: "claude-haiku-4-5", content_queries: "claude-haiku-4-5" }}
      />,
    );
    const rows = screen.getAllByTestId("tiering-row");
    expect(rows).toHaveLength(2);
    expect(rows[0]).toHaveTextContent("content_queries");
    expect(rows[1]).toHaveTextContent("content_validate");
    expect(rows[0]).toHaveTextContent("claude-haiku-4-5");
    expect(screen.getByText(/COGNIFY_LLM_MODEL_BY_STEP/)).toBeInTheDocument();
  });
});
