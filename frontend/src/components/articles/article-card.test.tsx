import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ArticleCard } from "./article-card";
import type { ArticleListItem } from "@/types/articles";

const mockArticle: ArticleListItem = {
  id: "art-001",
  title: "AI-Powered Phishing Detection Trends",
  summary: "New machine learning approaches to detecting sophisticated phishing attacks",
  domain: "cybersecurity",
  status: "complete",
  wordCount: 3200,
  generatedAt: new Date().toISOString(),
};

describe("ArticleCard", () => {
  it("renders title", () => {
    render(<ArticleCard article={mockArticle} />);
    expect(screen.getByText("AI-Powered Phishing Detection Trends")).toBeInTheDocument();
  });

  it("renders summary", () => {
    render(<ArticleCard article={mockArticle} />);
    expect(screen.getByText(/machine learning approaches/)).toBeInTheDocument();
  });

  it("renders domain badge", () => {
    render(<ArticleCard article={mockArticle} />);
    expect(screen.getByText("Cybersecurity")).toBeInTheDocument();
  });

  it("renders status badge", () => {
    render(<ArticleCard article={mockArticle} />);
    expect(screen.getByText("Complete")).toBeInTheDocument();
  });

  it("renders word count", () => {
    render(<ArticleCard article={mockArticle} />);
    expect(screen.getByText(/3,200 words/)).toBeInTheDocument();
  });

  it("has link to article detail", () => {
    render(<ArticleCard article={mockArticle} />);
    const link = screen.getByText("View →");
    expect(link.closest("a")).toHaveAttribute("href", "/articles/art-001");
  });
});
