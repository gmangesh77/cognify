import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ArticleRow } from "./article-row";
import type { Article } from "@/types/api";

const mockArticle: Article = {
  id: "art-001",
  title: "The Rise of AI in Threat Detection",
  status: "live",
  published_at: "2026-03-12T10:00:00Z",
  views: 2847,
};

describe("ArticleRow", () => {
  it("renders article title", () => {
    render(<ArticleRow article={mockArticle} />);
    expect(screen.getByText("The Rise of AI in Threat Detection")).toBeInTheDocument();
  });
  it("renders status badge", () => {
    render(<ArticleRow article={mockArticle} />);
    expect(screen.getByText("Live")).toBeInTheDocument();
  });
  it("renders view count", () => {
    render(<ArticleRow article={mockArticle} />);
    expect(screen.getByText("2,847")).toBeInTheDocument();
  });
});
