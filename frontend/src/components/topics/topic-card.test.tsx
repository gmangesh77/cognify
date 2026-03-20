import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { TopicCard } from "./topic-card";
import type { RankedTopic } from "@/types/api";

const mockTopic: RankedTopic = {
  title: "AI-Powered Phishing Detection",
  description: "New machine learning approaches to detecting sophisticated phishing attacks",
  source: "google_trends",
  external_url: "",
  trend_score: 94,
  discovered_at: new Date().toISOString(),
  velocity: 55,
  domain_keywords: ["phishing", "ai"],
  composite_score: 94,
  rank: 1,
  source_count: 3,
  domain: "cybersecurity",
  trend_status: "trending",
};

describe("TopicCard", () => {
  it("renders topic title", () => {
    render(<TopicCard topic={mockTopic} onRequestGeneration={vi.fn()} />);
    expect(screen.getByText("AI-Powered Phishing Detection")).toBeInTheDocument();
  });
  it("renders description", () => {
    render(<TopicCard topic={mockTopic} onRequestGeneration={vi.fn()} />);
    expect(screen.getByText(/machine learning approaches/)).toBeInTheDocument();
  });
  it("renders composite score", () => {
    render(<TopicCard topic={mockTopic} onRequestGeneration={vi.fn()} />);
    expect(screen.getByText("94")).toBeInTheDocument();
  });
  it("renders trend badge", () => {
    render(<TopicCard topic={mockTopic} onRequestGeneration={vi.fn()} />);
    expect(screen.getByText("Trending")).toBeInTheDocument();
  });
  it("renders source label", () => {
    render(<TopicCard topic={mockTopic} onRequestGeneration={vi.fn()} />);
    expect(screen.getByText("Google Trends")).toBeInTheDocument();
  });
  it("calls onRequestGeneration when Generate Article is clicked", () => {
    const handler = vi.fn();
    render(<TopicCard topic={mockTopic} onRequestGeneration={handler} />);
    fireEvent.click(screen.getByText("Generate Article"));
    expect(handler).toHaveBeenCalledWith(mockTopic);
  });
});
