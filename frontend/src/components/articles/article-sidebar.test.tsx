import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ArticleSidebar } from "./article-sidebar";
import type { ArticleDetail } from "@/types/articles";

const mockArticle: Partial<ArticleDetail> = {
  domain: "cybersecurity",
  contentType: "analysis",
  wordCount: 3200,
  authors: ["Cognify"],
  generatedAt: new Date().toISOString(),
  keyClaims: ["AI detection improved by 40%", "Phishing attacks rose 25% in 2026"],
  workflow: [
    { name: "Research", durationSeconds: 45 },
    { name: "Outline", durationSeconds: 12 },
    { name: "Drafting", durationSeconds: 90 },
  ],
};

describe("ArticleSidebar", () => {
  it("renders publish button", () => {
    render(<ArticleSidebar article={mockArticle as ArticleDetail} onPublish={vi.fn()} />);
    expect(screen.getByText("Publish Article")).toBeInTheDocument();
  });

  it("renders domain", () => {
    render(<ArticleSidebar article={mockArticle as ArticleDetail} onPublish={vi.fn()} />);
    expect(screen.getByText("Cybersecurity")).toBeInTheDocument();
  });

  it("renders word count", () => {
    render(<ArticleSidebar article={mockArticle as ArticleDetail} onPublish={vi.fn()} />);
    expect(screen.getByText(/3,200/)).toBeInTheDocument();
  });

  it("renders workflow steps", () => {
    render(<ArticleSidebar article={mockArticle as ArticleDetail} onPublish={vi.fn()} />);
    expect(screen.getByText("Research")).toBeInTheDocument();
    expect(screen.getByText("Drafting")).toBeInTheDocument();
  });

  it("renders key claims", () => {
    render(<ArticleSidebar article={mockArticle as ArticleDetail} onPublish={vi.fn()} />);
    expect(screen.getByText(/AI detection improved/)).toBeInTheDocument();
    expect(screen.getByText(/Phishing attacks rose/)).toBeInTheDocument();
  });

  it("calls onPublish when publish button clicked", () => {
    const handler = vi.fn();
    render(<ArticleSidebar article={mockArticle as ArticleDetail} onPublish={handler} />);
    fireEvent.click(screen.getByText("Publish Article"));
    expect(handler).toHaveBeenCalled();
  });
});
