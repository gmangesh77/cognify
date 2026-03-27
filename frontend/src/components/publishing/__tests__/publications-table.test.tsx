import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { PublicationsTable } from "../publications-table";
import type { Publication } from "@/types/publishing";

const mockPub: Publication = {
  id: "pub-1",
  article_id: "art-1",
  article_title: "AI Security Trends",
  platform: "ghost",
  status: "success",
  external_id: "g-1",
  external_url: "https://blog.example.com/ai-security",
  published_at: "2026-03-27T10:00:00Z",
  view_count: 42,
  seo_score: 80,
  error_message: null,
  event_history: [],
  created_at: "2026-03-27T10:00:00Z",
  updated_at: "2026-03-27T10:00:00Z",
};

const failedPub: Publication = {
  ...mockPub,
  id: "pub-2",
  status: "failed",
  external_url: null,
  view_count: 0,
  error_message: "Connection refused",
};

describe("PublicationsTable", () => {
  it("renders publication rows", () => {
    render(<PublicationsTable publications={[mockPub]} onRetry={vi.fn()} retryingId={null} />);
    expect(screen.getByText("AI Security Trends")).toBeInTheDocument();
    expect(screen.getByText("Ghost")).toBeInTheDocument();
    expect(screen.getByText("Live")).toBeInTheDocument();
    expect(screen.getByText("42")).toBeInTheDocument();
    expect(screen.getByText("80")).toBeInTheDocument();
  });

  it("shows retry button only for failed publications", () => {
    render(<PublicationsTable publications={[mockPub, failedPub]} onRetry={vi.fn()} retryingId={null} />);
    const retryButtons = screen.getAllByText("Retry");
    expect(retryButtons).toHaveLength(1);
  });

  it("calls onRetry when retry button clicked", () => {
    const onRetry = vi.fn();
    render(<PublicationsTable publications={[failedPub]} onRetry={onRetry} retryingId={null} />);
    fireEvent.click(screen.getByText("Retry"));
    expect(onRetry).toHaveBeenCalledWith("pub-2");
  });

  it("shows N/A for non-ghost view counts", () => {
    const mediumPub = { ...mockPub, platform: "medium", view_count: 0 };
    render(<PublicationsTable publications={[mediumPub]} onRetry={vi.fn()} retryingId={null} />);
    expect(screen.getByText("N/A")).toBeInTheDocument();
  });

  it("shows empty state when no publications", () => {
    render(<PublicationsTable publications={[]} onRetry={vi.fn()} retryingId={null} />);
    expect(screen.getByText("No publications yet")).toBeInTheDocument();
  });

  it("shows loading state on retry button when retrying", () => {
    render(<PublicationsTable publications={[failedPub]} onRetry={vi.fn()} retryingId="pub-2" />);
    expect(screen.getByText("Retrying...")).toBeInTheDocument();
  });
});
