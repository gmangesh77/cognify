import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ArticleContent } from "./article-content";
import type { Citation } from "@/types/articles";

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
    render(<ArticleContent bodyMarkdown={mockMarkdown} citations={mockCitations} />);
    expect(screen.getByText("Introduction")).toBeInTheDocument();
    expect(screen.getByText("Key Findings")).toBeInTheDocument();
  });

  it("renders markdown paragraphs", () => {
    render(<ArticleContent bodyMarkdown={mockMarkdown} citations={mockCitations} />);
    expect(screen.getByText(/test article about security/)).toBeInTheDocument();
  });

  it("renders sources section header", () => {
    render(<ArticleContent bodyMarkdown={mockMarkdown} citations={mockCitations} />);
    expect(screen.getByText("Sources")).toBeInTheDocument();
  });

  it("renders citation titles as links", () => {
    render(<ArticleContent bodyMarkdown={mockMarkdown} citations={mockCitations} />);
    const link = screen.getByText("Security Report 2026");
    expect(link.closest("a")).toHaveAttribute("href", "https://example.com/report");
  });

  it("renders citation authors", () => {
    render(<ArticleContent bodyMarkdown={mockMarkdown} citations={mockCitations} />);
    expect(screen.getByText(/John Doe/)).toBeInTheDocument();
  });

  it("shows no sources message when citations empty", () => {
    render(<ArticleContent bodyMarkdown={mockMarkdown} citations={[]} />);
    expect(screen.getByText("Sources")).toBeInTheDocument();
    expect(screen.getByText("No sources")).toBeInTheDocument();
  });
});
