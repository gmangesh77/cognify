import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { GenerateArticleModal } from "./generate-article-modal";
import type { RankedTopic } from "@/types/api";

const mockTopic: RankedTopic = {
  title: "AI-Powered Phishing Detection",
  description: "Test description",
  source: "google_trends",
  external_url: "",
  trend_score: 94,
  discovered_at: new Date().toISOString(),
  velocity: 55,
  domain_keywords: [],
  composite_score: 94,
  rank: 1,
  source_count: 3,
  domain: "cybersecurity",
  trend_status: "trending",
};

describe("GenerateArticleModal", () => {
  it("renders nothing when topic is null", () => {
    const { container } = render(
      <GenerateArticleModal topic={null} onClose={vi.fn()} onConfirm={vi.fn()} />,
    );
    expect(container.querySelector("[role='dialog']")).toBeNull();
  });
  it("shows topic title when topic provided", () => {
    render(<GenerateArticleModal topic={mockTopic} onClose={vi.fn()} onConfirm={vi.fn()} />);
    expect(screen.getByText("AI-Powered Phishing Detection")).toBeInTheDocument();
  });
  it("shows estimated time message", () => {
    render(<GenerateArticleModal topic={mockTopic} onClose={vi.fn()} onConfirm={vi.fn()} />);
    expect(screen.getByText(/2-5 minutes/)).toBeInTheDocument();
  });
  it("calls onClose when Cancel clicked", () => {
    const onClose = vi.fn();
    render(<GenerateArticleModal topic={mockTopic} onClose={onClose} onConfirm={vi.fn()} />);
    fireEvent.click(screen.getByText("Cancel"));
    expect(onClose).toHaveBeenCalled();
  });
  it("calls onConfirm when Generate clicked", () => {
    const onConfirm = vi.fn();
    render(<GenerateArticleModal topic={mockTopic} onClose={vi.fn()} onConfirm={onConfirm} />);
    fireEvent.click(screen.getByText("Generate"));
    expect(onConfirm).toHaveBeenCalledWith(mockTopic);
  });
});
