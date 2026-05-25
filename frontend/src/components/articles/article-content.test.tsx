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

  describe("section indexing for non-diagram visuals", () => {
    const makeChart = (
      sourceSection: number | undefined,
      id = "chart-1",
    ): ImageAsset => ({
      id,
      url: `/assets/${id}.png`,
      caption: `Caption ${id}`,
      altText: `Alt ${id}`,
      metadata:
        sourceSection === undefined ? null : { source_section: sourceSection },
    });

    // Visuals (charts/images) render as Fragment siblings AFTER the section
    // div, so to find the section the visual is anchored to, walk backward
    // through siblings until we find a node with `data-section-index`.
    function findAnchoringSection(node: Element): string | null {
      let el: Element | null =
        node.closest("figure")?.previousElementSibling ?? null;
      while (el && !el.hasAttribute("data-section-index")) {
        el = el.previousElementSibling;
      }
      return el?.getAttribute("data-section-index") ?? null;
    }

    it("renders a chart anchored to the last section when markdown starts with ##", () => {
      // mockMarkdown has 2 sections (indices 0,1); chart anchored to last section.
      render(
        <ArticleContent
          bodyMarkdown={mockMarkdown}
          citations={[]}
          visuals={[makeChart(1)]}
        />,
      );
      const img = screen.getByRole("img", { name: "Alt chart-1" });
      expect(findAnchoringSection(img)).toBe("1");
    });

    it("renders a chart anchored to section 0 when markdown starts with ##", () => {
      render(
        <ArticleContent
          bodyMarkdown={mockMarkdown}
          citations={[]}
          visuals={[makeChart(0)]}
        />,
      );
      const img = screen.getByRole("img", { name: "Alt chart-1" });
      expect(findAnchoringSection(img)).toBe("0");
    });

    it("renders a chart anchored to section 0 when markdown starts with a preamble", () => {
      const preambleMarkdown =
        "Preamble paragraph.\n\n## First Section\n\nBody.\n\n## Second Section\n\nMore body.";
      render(
        <ArticleContent
          bodyMarkdown={preambleMarkdown}
          citations={[]}
          visuals={[makeChart(0)]}
        />,
      );
      const img = screen.getByRole("img", { name: "Alt chart-1" });
      expect(findAnchoringSection(img)).toBe("0");
    });

    it("renders a cover image when source_section is missing", () => {
      render(
        <ArticleContent
          bodyMarkdown={mockMarkdown}
          citations={[]}
          visuals={[makeChart(undefined)]}
        />,
      );
      expect(
        screen.getByRole("img", { name: "Alt chart-1" }),
      ).toBeInTheDocument();
    });
  });

  describe("section indexing for diagram visuals", () => {
    it("renders a section diagram under the correct section when markdown starts with ##", async () => {
      const diagram: ImageAsset = {
        id: "d-last",
        url: "/assets/d-last.png",
        caption: "Last section diagram",
        altText: "Last",
        metadata: {
          diagram_type: "flowchart",
          source_section: 1,
          mermaid_syntax: "graph TD\n  X --> Y",
        },
      };
      render(
        <ArticleContent
          bodyMarkdown={mockMarkdown}
          citations={[]}
          visuals={[diagram]}
        />,
      );
      await waitFor(() => {
        const stub = screen.getByTestId("mermaid-stub");
        // Diagrams render as Fragment siblings AFTER the section div, so the
        // previous sibling should be the section div with the matching index.
        let el: Element | null = stub.previousElementSibling;
        while (el && !el.hasAttribute("data-section-index")) {
          el = el.previousElementSibling;
        }
        expect(el?.getAttribute("data-section-index")).toBe("1");
      });
    });
  });
});
