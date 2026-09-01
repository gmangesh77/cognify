import { beforeEach, describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

const articleUsage = vi.fn();
vi.mock("@/hooks/use-session-usage", () => ({
  useArticleUsage: (id: string | null) => articleUsage(id),
}));

import { ArticleSidebar } from "./article-sidebar";
import type { ArticleDetail } from "@/types/articles";

const mockArticle: Partial<ArticleDetail> = {
  id: "a1",
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
  beforeEach(() => {
    articleUsage.mockClear();
    articleUsage.mockReturnValue({ usage: null });
  });

  it("renders the usage card with the badge when usage is available", () => {
    articleUsage.mockReturnValue({
      usage: {
        session_id: "s1",
        llm_calls: 3,
        input_tokens: 2100,
        output_tokens: 1100,
        images: 2,
        cost_usd: 0.052,
        by_operation: [
          { op: "images", llm_calls: 0, input_tokens: 0, output_tokens: 0, cost_usd: 0.041 },
        ],
      },
    });
    render(<ArticleSidebar article={mockArticle as ArticleDetail} onPublish={vi.fn()} />);
    expect(screen.getByText("Usage")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /\$0\.052 this article · 3\.2k tok · 2 img/ }),
    ).toBeInTheDocument();
    expect(articleUsage).toHaveBeenCalledWith("a1");
  });

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

  it("does not render the voice match card when voiceMatchScore is absent", () => {
    render(<ArticleSidebar article={mockArticle as ArticleDetail} onPublish={vi.fn()} />);
    expect(screen.queryByText("Voice match")).not.toBeInTheDocument();
  });

  it("renders the voice match card when voiceMatchScore is present", () => {
    render(
      <ArticleSidebar
        article={{
          ...mockArticle,
          voiceMatchScore: 82,
          voiceScoresBySection: { "0": 90 },
        } as ArticleDetail}
        onPublish={vi.fn()}
      />,
    );
    expect(screen.getByText("Voice match")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Voice match: 82/ })).toBeInTheDocument();
  });
});
