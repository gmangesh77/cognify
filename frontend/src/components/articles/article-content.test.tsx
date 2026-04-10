import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { ArticleContent } from "./article-content";
import type { Citation, ImageAsset } from "@/types/articles";

vi.mock("./mermaid-diagram", () => ({
  MermaidDiagram: ({
    syntax,
    caption,
  }: {
    syntax: string;
    caption?: string | null;
  }) => (
    <div data-testid="mermaid-stub" data-syntax={syntax}>
      {caption}
    </div>
  ),
}));

const mockMarkdown =
  "## Introduction\n\nThis is a test article about security [1].\n\n## Key Findings\n\nImportant findings here [2].";

const mockCitations: Citation[] = [
  {
    index: 1,
    title: "Security Report 2026",
    url: "https://example.com/report",
    authors: ["John Doe"],
    publishedAt: "2026-01-15T00:00:00Z",
  },
  {
    index: 2,
    title: "Threat Analysis",
    url: "https://example.com/threats",
    authors: ["Jane Smith"],
    publishedAt: null,
  },
];

describe("ArticleContent", () => {
  it("renders markdown headings", () => {
    render(<ArticleContent bodyMarkdown={mockMarkdown} citations={mockCitations} visuals={[]} />);
    expect(screen.getByText("Introduction")).toBeInTheDocument();
    expect(screen.getByText("Key Findings")).toBeInTheDocument();
  });

  it("renders markdown paragraphs", () => {
    render(<ArticleContent bodyMarkdown={mockMarkdown} citations={mockCitations} visuals={[]} />);
    expect(screen.getByText(/test article about security/)).toBeInTheDocument();
  });

  it("renders references section header", () => {
    render(<ArticleContent bodyMarkdown={mockMarkdown} citations={mockCitations} visuals={[]} />);
    expect(screen.getByText(/References \(2\)/)).toBeInTheDocument();
  });

  it("renders citation titles as links", () => {
    render(<ArticleContent bodyMarkdown={mockMarkdown} citations={mockCitations} visuals={[]} />);
    const link = screen.getByText("Security Report 2026");
    expect(link.closest("a")).toHaveAttribute("href", "https://example.com/report");
  });

  it("renders citation authors", () => {
    render(<ArticleContent bodyMarkdown={mockMarkdown} citations={mockCitations} visuals={[]} />);
    expect(screen.getByText(/John Doe/)).toBeInTheDocument();
  });

  it("hides references section when citations empty", () => {
    render(<ArticleContent bodyMarkdown={mockMarkdown} citations={[]} visuals={[]} />);
    expect(screen.queryByText(/References/)).not.toBeInTheDocument();
  });

  describe("with diagram visuals", () => {
    const diagramVisual: ImageAsset = {
      id: "d1",
      url: "/assets/d1.png",
      caption: "Auth flow diagram",
      altText: "Auth Flow",
      metadata: {
        diagram_type: "flowchart",
        source_section: 0,
        mermaid_syntax: "graph TD\n  A --> B",
      },
    };

    const overviewVisual: ImageAsset = {
      id: "d0",
      url: "/assets/overview.png",
      caption: "System overview",
      altText: "Overview",
      metadata: {
        diagram_type: "flowchart",
        source_section: -1,
        mermaid_syntax: "graph LR\n  UI --> API",
      },
    };

    it("renders a MermaidDiagram for a section diagram", async () => {
      render(
        <ArticleContent
          bodyMarkdown={mockMarkdown}
          citations={mockCitations}
          visuals={[diagramVisual]}
        />,
      );
      await waitFor(() => {
        const stubs = screen.getAllByTestId("mermaid-stub");
        expect(stubs).toHaveLength(1);
        expect(stubs[0].getAttribute("data-syntax")).toBe(
          "graph TD\n  A --> B",
        );
      });
    });

    it("renders overview diagrams above per-section diagrams", async () => {
      render(
        <ArticleContent
          bodyMarkdown={mockMarkdown}
          citations={mockCitations}
          visuals={[diagramVisual, overviewVisual]}
        />,
      );
      await waitFor(() => {
        const stubs = screen.getAllByTestId("mermaid-stub");
        expect(stubs).toHaveLength(2);
        expect(stubs[0].getAttribute("data-syntax")).toContain("UI --> API");
      });
    });

    it("ignores non-diagram visuals (charts, illustrations)", () => {
      const chart: ImageAsset = {
        id: "c1",
        url: "/assets/chart.png",
        caption: "Chart",
        altText: "Chart",
        metadata: null,
      };
      render(
        <ArticleContent
          bodyMarkdown={mockMarkdown}
          citations={mockCitations}
          visuals={[chart]}
        />,
      );
      expect(screen.queryByTestId("mermaid-stub")).not.toBeInTheDocument();
    });
  });
});
