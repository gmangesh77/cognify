import type { ComponentProps } from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
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

vi.mock("@/lib/api/briefs", () => ({
  fetchBriefs: vi.fn().mockResolvedValue([
    {
      id: "b1",
      owner_id: "u",
      name: "Saved brief",
      keywords: ["zt"],
      target_audience: "CISOs",
      content_tone: "analytical",
      preferred_angle: "risk",
      content_type: "analysis",
      length_target: "long",
      structural_diagram_mode: "mermaid",
      require_outline_approval: true,
      created_at: "",
      updated_at: "",
    },
  ]),
  createBrief: vi.fn(),
  updateBrief: vi.fn(),
  deleteBrief: vi.fn(),
  duplicateBrief: vi.fn(),
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

function renderModal(
  props: Partial<ComponentProps<typeof GenerateArticleModal>> = {},
) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <GenerateArticleModal
        topic={mockTopic}
        onClose={vi.fn()}
        onConfirm={vi.fn()}
        {...props}
      />
    </QueryClientProvider>,
  );
}

describe("GenerateArticleModal", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders nothing when topic is null", () => {
    const { container } = renderModal({ topic: null });
    expect(container.querySelector("[role='dialog']")).toBeNull();
  });

  it("shows topic title when topic provided", async () => {
    renderModal();
    expect(
      screen.getByText("AI-Powered Phishing Detection"),
    ).toBeInTheDocument();
  });

  it("shows estimated time message", () => {
    renderModal();
    expect(screen.getByText(/2-5 minutes/)).toBeInTheDocument();
  });

  it("calls onClose when Cancel clicked", () => {
    const onClose = vi.fn();
    renderModal({ onClose });
    fireEvent.click(screen.getByText("Cancel"));
    expect(onClose).toHaveBeenCalled();
  });

  it("auto-fills fields from topic analyzer and shows editable inputs", async () => {
    renderModal();
    // Description field — editable, seeded with topic's original description
    const description = await screen.findByDisplayValue(
      "Original topic description",
    );
    expect(description).toBeInTheDocument();
    expect(description.tagName).toBe("TEXTAREA");
  });

  it("shows keywords field auto-filled from analyzer", async () => {
    renderModal();
    const keywords = await screen.findByDisplayValue(
      "phishing, ML detection, email security",
    );
    expect(keywords).toBeInTheDocument();
  });

  it("shows target audience from analyzer", async () => {
    renderModal();
    const audience = await screen.findByDisplayValue("security engineers");
    expect(audience).toBeInTheDocument();
  });

  it("shows preferred angle from analyzer", async () => {
    renderModal();
    const angle = await screen.findByDisplayValue(
      "practical defender playbook",
    );
    expect(angle).toBeInTheDocument();
  });

  it("passes all fields to onConfirm when Generate is clicked", async () => {
    const onConfirm = vi.fn();
    renderModal({ onConfirm });
    // Wait for analyzer to finish
    await screen.findByDisplayValue("security engineers");
    fireEvent.click(screen.getByRole("button", { name: "Generate" }));
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
    renderModal({ onConfirm });
    const description = await screen.findByDisplayValue(
      "Original topic description",
    );
    fireEvent.change(description, { target: { value: "My edited version" } });
    fireEvent.click(screen.getByRole("button", { name: "Generate" }));
    await waitFor(() => {
      expect(onConfirm).toHaveBeenCalled();
    });
    const [, params] = onConfirm.mock.calls[0];
    expect(params.topic_description_override).toBe("My edited version");
  });

  it("omits require_outline_approval when the checkbox is left unchecked", async () => {
    const onConfirm = vi.fn();
    renderModal({ onConfirm });
    await screen.findByDisplayValue("security engineers");
    fireEvent.click(screen.getByRole("button", { name: "Generate" }));
    await waitFor(() => expect(onConfirm).toHaveBeenCalled());
    const [, params] = onConfirm.mock.calls[0];
    expect(params.require_outline_approval).toBeUndefined();
  });

  it("sets require_outline_approval when 'Review outline before drafting' is checked", async () => {
    const onConfirm = vi.fn();
    renderModal({ onConfirm });
    await screen.findByDisplayValue("security engineers");
    fireEvent.click(screen.getByLabelText(/review outline before drafting/i));
    fireEvent.click(screen.getByRole("button", { name: "Generate" }));
    await waitFor(() => expect(onConfirm).toHaveBeenCalled());
    const [, params] = onConfirm.mock.calls[0];
    expect(params.require_outline_approval).toBe(true);
  });

  it("Generate button is disabled while analyzing", () => {
    renderModal();
    // Immediately (before the mock resolves), Generate should be disabled
    const btn = screen.getByRole("button", { name: "Generate" });
    expect(btn).toBeDisabled();
  });

  it("sends content_type and length_target defaults with inline params", async () => {
    const onConfirm = vi.fn();
    renderModal({ onConfirm });
    await waitFor(() =>
      expect(screen.getByLabelText("Content type")).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByRole("button", { name: "Generate" }));
    expect(onConfirm).toHaveBeenCalledWith(
      mockTopic,
      expect.objectContaining({
        content_type: "article",
        length_target: "medium",
        structural_diagram_mode: "illustration",
      }),
    );
    expect(onConfirm.mock.calls[0][1].brief_id).toBeUndefined();
  });

  it("picking a saved brief prefills fields and sends brief_id", async () => {
    const onConfirm = vi.fn();
    renderModal({ onConfirm });
    await waitFor(() =>
      expect(
        screen.getByRole("option", { name: "Saved brief" }),
      ).toBeInTheDocument(),
    );
    fireEvent.change(screen.getByLabelText("Brief"), {
      target: { value: "b1" },
    });
    await waitFor(() =>
      expect(screen.getByDisplayValue("CISOs")).toBeInTheDocument(),
    );
    expect((screen.getByLabelText("Length") as HTMLSelectElement).value).toBe(
      "long",
    );
    expect(
      (screen.getByLabelText("Diagram style") as HTMLSelectElement).value,
    ).toBe("mermaid");
    fireEvent.click(screen.getByRole("button", { name: "Generate" }));
    expect(onConfirm).toHaveBeenCalledWith(
      mockTopic,
      expect.objectContaining({
        brief_id: "b1",
        target_audience: "CISOs",
        length_target: "long",
        structural_diagram_mode: "mermaid",
        require_outline_approval: true,
      }),
    );
  });

  it("save-as-brief sends the flag and a name", async () => {
    const onConfirm = vi.fn();
    renderModal({ onConfirm });
    await waitFor(() =>
      expect(screen.getByLabelText("Save as brief")).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByLabelText("Save as brief"));
    fireEvent.change(screen.getByLabelText("Brief name"), {
      target: { value: "Phishing brief" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Generate" }));
    expect(onConfirm).toHaveBeenCalledWith(
      mockTopic,
      expect.objectContaining({
        save_as_brief: true,
        brief_name: "Phishing brief",
      }),
    );
  });
});
