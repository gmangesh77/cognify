import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { ArticleContent } from "./article-content";

vi.mock("./mermaid-diagram", () => ({
  MermaidDiagram: () => <div data-testid="mermaid-stub" />,
}));

const mockMarkdown =
  "## Introduction\n\nThis is a test article about security [1].\n\n## Key Findings\n\nImportant findings here [2].";

describe("ArticleContent — per-section editing toolbar (AUTHOR-004)", () => {
  it("mounts the toolbar per section and forwards onRegenerate with the 0-based index", () => {
    const onRegenerate = vi.fn();
    render(
      <ArticleContent
        bodyMarkdown={mockMarkdown}
        citations={[]}
        visuals={[]}
        editing={{
          articleId: "art-1",
          onEditText: vi.fn(),
          onEditVisual: vi.fn(),
          onRefineLayout: vi.fn(),
          onRegenerate,
        }}
      />,
    );
    fireEvent.click(screen.getByTestId("toolbar-regenerate-0"));
    expect(onRegenerate).toHaveBeenCalledWith(0, expect.stringMatching(/^## Introduction/));
    fireEvent.click(screen.getByTestId("toolbar-regenerate-1"));
    expect(onRegenerate).toHaveBeenLastCalledWith(1, expect.stringMatching(/^## Key Findings/));
  });

  it("gives the preamble no toolbar and keeps the first H2 at index 0", () => {
    render(
      <ArticleContent
        bodyMarkdown={`Intro para.\n\n${mockMarkdown}`}
        citations={[]}
        visuals={[]}
        editing={{
          articleId: "art-1",
          onEditText: vi.fn(),
          onEditVisual: vi.fn(),
          onRefineLayout: vi.fn(),
          onRegenerate: vi.fn(),
        }}
      />,
    );
    expect(screen.queryByTestId("toolbar-regenerate--1")).toBeNull();
    expect(screen.getByTestId("toolbar-regenerate-0")).toBeInTheDocument();
  });
});
