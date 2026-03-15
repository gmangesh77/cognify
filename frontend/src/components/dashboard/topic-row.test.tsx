import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { TopicRow } from "./topic-row";
import type { RankedTopic } from "@/types/api";

const mockTopic: RankedTopic = {
  title: "AI-Powered Phishing Detection",
  description: "Test",
  source: "google_trends",
  external_url: "",
  trend_score: 94,
  discovered_at: "2026-03-15T08:00:00Z",
  velocity: 12.5,
  domain_keywords: ["phishing"],
  composite_score: 94,
  rank: 1,
  source_count: 3,
  domain: "cybersecurity",
  trend_status: "trending",
};

describe("TopicRow", () => {
  it("renders topic title", () => {
    render(<TopicRow topic={mockTopic} />);
    expect(screen.getByText("AI-Powered Phishing Detection")).toBeInTheDocument();
  });
  it("renders domain badge", () => {
    render(<TopicRow topic={mockTopic} />);
    expect(screen.getByText("Cybersecurity")).toBeInTheDocument();
  });
  it("renders composite score", () => {
    render(<TopicRow topic={mockTopic} />);
    expect(screen.getByText("94")).toBeInTheDocument();
  });
  it("renders trend badge", () => {
    render(<TopicRow topic={mockTopic} />);
    expect(screen.getByText("Trending")).toBeInTheDocument();
  });
  it("renders source label", () => {
    render(<TopicRow topic={mockTopic} />);
    expect(screen.getByText("google_trends")).toBeInTheDocument();
  });
});
