import { describe, expect, it, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

vi.mock("@/lib/api/content", () => ({
  previewHumanization: vi.fn(),
}));

import { previewHumanization } from "@/lib/api/content";
import { HumanizationDiffPanel } from "./HumanizationDiffPanel";

const RESPONSE = {
  section_id: "abc:1",
  original: "Old wordy paragraph with slop.",
  rewritten: "Tighter paragraph.",
  diff: [
    { kind: "delete" as const, before: "Old wordy ", after: "" },
    { kind: "insert" as const, before: "", after: "Tighter " },
    { kind: "equal" as const, before: "paragraph.", after: "paragraph." },
  ],
  score_before: { score: 35, rating: "SUSPICIOUS", violation_count: 4 },
  score_after: { score: 85, rating: "CLEAN", violation_count: 0 },
  llm_called: true,
  model: "claude",
};

describe("HumanizationDiffPanel", () => {
  beforeEach(() => {
    vi.mocked(previewHumanization).mockReset();
  });

  function setup() {
    const onAccept = vi.fn();
    const onCancel = vi.fn();
    render(
      <HumanizationDiffPanel
        sectionId="abc:1"
        currentMarkdown="Old wordy paragraph with slop."
        onAccept={onAccept}
        onCancel={onCancel}
      />,
    );
    return { onAccept, onCancel };
  }

  it("calls previewHumanization on Run, shows diff + score badges", async () => {
    vi.mocked(previewHumanization).mockResolvedValue(RESPONSE);
    setup();
    fireEvent.click(screen.getByTestId("run-humanize"));
    await waitFor(() => {
      expect(previewHumanization).toHaveBeenCalledWith({
        section_id: "abc:1",
        current_markdown: "Old wordy paragraph with slop.",
      });
    });
    await waitFor(() => {
      expect(screen.getByTestId("word-diff-view")).toBeInTheDocument();
      expect(screen.getByTestId("humanize-score-badges")).toBeInTheDocument();
    });
  });

  it("Accept emits the rewritten markdown to the parent", async () => {
    vi.mocked(previewHumanization).mockResolvedValue(RESPONSE);
    const { onAccept } = setup();
    fireEvent.click(screen.getByTestId("run-humanize"));
    await waitFor(() => screen.getByTestId("word-diff-view"));
    fireEvent.click(screen.getByTestId("accept-humanize"));
    expect(onAccept).toHaveBeenCalledWith("Tighter paragraph.");
  });

  it("Reject clears the diff and shows Run button again", async () => {
    vi.mocked(previewHumanization).mockResolvedValue(RESPONSE);
    setup();
    fireEvent.click(screen.getByTestId("run-humanize"));
    await waitFor(() => screen.getByTestId("word-diff-view"));
    fireEvent.click(screen.getByTestId("reject-humanize"));
    expect(screen.queryByTestId("word-diff-view")).not.toBeInTheDocument();
    expect(screen.getByTestId("run-humanize")).toBeInTheDocument();
  });

  it("renders error when API call fails", async () => {
    vi.mocked(previewHumanization).mockRejectedValue(new Error("boom"));
    setup();
    fireEvent.click(screen.getByTestId("run-humanize"));
    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent("boom");
    });
  });
});
