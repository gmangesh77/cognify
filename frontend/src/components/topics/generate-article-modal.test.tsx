import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { GenerateArticleModal } from "./generate-article-modal";
import type { RankedTopic } from "@/types/api";

// Mock the analyzeTopic API so the modal can auto-fill without network.
vi.mock("@/lib/api/trends", () => ({
  analyzeTopic: vi.fn().mockResolvedValue({
    description: "LLM generated description",
    domain: "cybersecurity",
    keywords: ["phishing", "ML detection", "email security"],
    target_audience: "security engineers",
    content_tone: "technical-authoritative",
    preferred_angle: "practical defender playbook",
  }),
}));

const mockTopic: RankedTopic = {
  title: "AI-Powered Phishing Detection",
  description: "Original topic description",
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
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders nothing when topic is null", () => {
    const { container } = render(
      <GenerateArticleModal
        topic={null}
        onClose={vi.fn()}
        onConfirm={vi.fn()}
      />,
    );
    expect(container.querySelector("[role='dialog']")).toBeNull();
  });

  it("shows topic title when topic provided", async () => {
    render(
      <GenerateArticleModal
        topic={mockTopic}
        onClose={vi.fn()}
        onConfirm={vi.fn()}
      />,
    );
    expect(
      screen.getByText("AI-Powered Phishing Detection"),
    ).toBeInTheDocument();
  });

  it("shows estimated time message", () => {
    render(
      <GenerateArticleModal
        topic={mockTopic}
        onClose={vi.fn()}
        onConfirm={vi.fn()}
      />,
    );
    expect(screen.getByText(/2-5 minutes/)).toBeInTheDocument();
  });

  it("calls onClose when Cancel clicked", () => {
    const onClose = vi.fn();
    render(
      <GenerateArticleModal
        topic={mockTopic}
        onClose={onClose}
        onConfirm={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByText("Cancel"));
    expect(onClose).toHaveBeenCalled();
  });

  it("auto-fills fields from topic analyzer and shows editable inputs", async () => {
    render(
      <GenerateArticleModal
        topic={mockTopic}
        onClose={vi.fn()}
        onConfirm={vi.fn()}
      />,
    );
    // Description field — editable, seeded with topic's original description
    const description = await screen.findByDisplayValue(
      "Original topic description",
    );
    expect(description).toBeInTheDocument();
    expect(description.tagName).toBe("TEXTAREA");
  });

  it("shows keywords field auto-filled from analyzer", async () => {
    render(
      <GenerateArticleModal
        topic={mockTopic}
        onClose={vi.fn()}
        onConfirm={vi.fn()}
      />,
    );
    const keywords = await screen.findByDisplayValue(
      "phishing, ML detection, email security",
    );
    expect(keywords).toBeInTheDocument();
  });

  it("shows target audience from analyzer", async () => {
    render(
      <GenerateArticleModal
        topic={mockTopic}
        onClose={vi.fn()}
        onConfirm={vi.fn()}
      />,
    );
    const audience = await screen.findByDisplayValue("security engineers");
    expect(audience).toBeInTheDocument();
  });

  it("shows preferred angle from analyzer", async () => {
    render(
      <GenerateArticleModal
        topic={mockTopic}
        onClose={vi.fn()}
        onConfirm={vi.fn()}
      />,
    );
    const angle = await screen.findByDisplayValue(
      "practical defender playbook",
    );
    expect(angle).toBeInTheDocument();
  });

  it("passes all fields to onConfirm when Generate is clicked", async () => {
    const onConfirm = vi.fn();
    render(
      <GenerateArticleModal
        topic={mockTopic}
        onClose={vi.fn()}
        onConfirm={onConfirm}
      />,
    );
    // Wait for analyzer to finish
    await screen.findByDisplayValue("security engineers");
    fireEvent.click(screen.getByText("Generate"));
    await waitFor(() => {
      expect(onConfirm).toHaveBeenCalled();
    });
    const [, params] = onConfirm.mock.calls[0];
    expect(params.target_audience).toBe("security engineers");
    expect(params.content_tone).toBe("technical-authoritative");
    expect(params.preferred_angle).toBe("practical defender playbook");
    expect(params.keywords).toEqual([
      "phishing",
      "ML detection",
      "email security",
    ]);
    // Description was NOT edited, so override should be undefined.
    expect(params.topic_description_override).toBeUndefined();
  });

  it("sends topic_description_override only when description is edited", async () => {
    const onConfirm = vi.fn();
    render(
      <GenerateArticleModal
        topic={mockTopic}
        onClose={vi.fn()}
        onConfirm={onConfirm}
      />,
    );
    const description = await screen.findByDisplayValue(
      "Original topic description",
    );
    fireEvent.change(description, { target: { value: "My edited version" } });
    fireEvent.click(screen.getByText("Generate"));
    await waitFor(() => {
      expect(onConfirm).toHaveBeenCalled();
    });
    const [, params] = onConfirm.mock.calls[0];
    expect(params.topic_description_override).toBe("My edited version");
  });

  it("Generate button is disabled while analyzing", () => {
    render(
      <GenerateArticleModal
        topic={mockTopic}
        onClose={vi.fn()}
        onConfirm={vi.fn()}
      />,
    );
    // Immediately (before the mock resolves), Generate should be disabled
    const btn = screen.getByRole("button", { name: "Generate" });
    expect(btn).toBeDisabled();
  });
});
