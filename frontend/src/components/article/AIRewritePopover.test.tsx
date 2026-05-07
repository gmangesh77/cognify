import { describe, expect, it, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

vi.mock("@/lib/api/content", () => ({
  rewriteSectionProse: vi.fn(),
  applyTonePreset: vi.fn(),
}));

import { applyTonePreset, rewriteSectionProse } from "@/lib/api/content";
import { AIRewritePopover } from "./AIRewritePopover";

const RESPONSE = {
  section_id: "abc:1",
  markdown_fragment: "Tighter rewritten paragraph.",
  diff: [
    { kind: "delete" as const, before: "Old wordy ", after: "" },
    { kind: "insert" as const, before: "", after: "Tighter " },
    { kind: "equal" as const, before: "rewritten paragraph.", after: "rewritten paragraph." },
  ],
  model: "claude",
  prompt_used: "system",
  instruction: "tighten",
  tokens_input: 5,
  tokens_output: 3,
  usd: null,
};

describe("AIRewritePopover", () => {
  beforeEach(() => {
    vi.mocked(rewriteSectionProse).mockReset();
    vi.mocked(applyTonePreset).mockReset();
  });

  function setup(overrides: { paragraphIndex?: number; scope?: "section" | "paragraph" } = {}) {
    const onAccept = vi.fn();
    const onCancel = vi.fn();
    render(
      <AIRewritePopover
        sectionId="abc:1"
        scope={overrides.scope ?? "paragraph"}
        paragraphIndex={overrides.paragraphIndex ?? 0}
        currentMarkdown="Old wordy rewritten paragraph."
        audiencePersona="cto"
        onAccept={onAccept}
        onCancel={onCancel}
      />,
    );
    return { onAccept, onCancel };
  }

  it("renders all four tone preset chips", () => {
    setup();
    expect(screen.getByTestId("tone-preset-shorter")).toBeInTheDocument();
    expect(screen.getByTestId("tone-preset-more_concrete")).toBeInTheDocument();
    expect(screen.getByTestId("tone-preset-more_conversational")).toBeInTheDocument();
    expect(screen.getByTestId("tone-preset-more_authoritative")).toBeInTheDocument();
  });

  it("calls rewriteSectionProse on Run AI and shows the diff with accept/reject", async () => {
    vi.mocked(rewriteSectionProse).mockResolvedValue(RESPONSE);
    const { onAccept } = setup();
    fireEvent.change(screen.getByPlaceholderText(/lead with the metric/), {
      target: { value: "tighten the second sentence" },
    });
    fireEvent.click(screen.getByTestId("run-ai-rewrite"));
    await waitFor(() => {
      expect(rewriteSectionProse).toHaveBeenCalledWith(
        expect.objectContaining({
          section_id: "abc:1",
          instruction: "tighten the second sentence",
          audience_persona: "cto",
        }),
      );
    });
    // Diff is rendered
    await waitFor(() => {
      expect(screen.getByTestId("word-diff-view")).toBeInTheDocument();
    });
    // Accept fires onAccept with the new markdown
    fireEvent.click(screen.getByTestId("accept-rewrite"));
    expect(onAccept).toHaveBeenCalledWith(
      "Tighter rewritten paragraph.",
      "tighten",
    );
  });

  it("reject clears the diff so the editor can rerun", async () => {
    vi.mocked(rewriteSectionProse).mockResolvedValue(RESPONSE);
    setup();
    fireEvent.change(screen.getByPlaceholderText(/lead with the metric/), {
      target: { value: "tighten" },
    });
    fireEvent.click(screen.getByTestId("run-ai-rewrite"));
    await waitFor(() => screen.getByTestId("word-diff-view"));
    fireEvent.click(screen.getByTestId("reject-rewrite"));
    expect(screen.queryByTestId("word-diff-view")).not.toBeInTheDocument();
    // Run AI button is back
    expect(screen.getByTestId("run-ai-rewrite")).toBeInTheDocument();
  });

  it("tone preset clicks ship only the preset name to the backend", async () => {
    vi.mocked(applyTonePreset).mockResolvedValue(RESPONSE);
    setup();
    fireEvent.click(screen.getByTestId("tone-preset-shorter"));
    await waitFor(() => {
      expect(applyTonePreset).toHaveBeenCalledWith(
        expect.objectContaining({
          section_id: "abc:1",
          paragraph_index: 0,
          preset: "shorter",
        }),
      );
    });
    // Crucially, no `instruction` field is sent — that lives server-side.
    const callArg = vi.mocked(applyTonePreset).mock.calls[0][0];
    expect(callArg).not.toHaveProperty("instruction");
  });
});
