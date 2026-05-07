import { describe, expect, it, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

vi.mock("@/lib/api/content", () => ({
  fetchSectionHistory: vi.fn(),
  restoreSectionVersion: vi.fn(),
}));

import {
  fetchSectionHistory,
  restoreSectionVersion,
} from "@/lib/api/content";
import { SectionHistoryDrawer } from "./SectionHistoryDrawer";

const VERSION = {
  id: "ver-1",
  section_id: "abc:1",
  section_index: 1,
  source: "ai" as const,
  instruction: "tighten",
  markdown: "## Section\nVersion one body.",
  model: "claude",
  tokens_input: 5,
  tokens_output: 3,
  usd: null,
  created_at: "2026-05-07T10:00:00Z",
  created_by: "user-1",
};

describe("SectionHistoryDrawer", () => {
  beforeEach(() => {
    vi.mocked(fetchSectionHistory).mockReset();
    vi.mocked(restoreSectionVersion).mockReset();
  });

  it("renders nothing when closed", () => {
    render(
      <SectionHistoryDrawer
        sectionId="abc:1"
        open={false}
        onClose={() => {}}
      />,
    );
    expect(
      screen.queryByTestId("section-history-drawer"),
    ).not.toBeInTheDocument();
    expect(fetchSectionHistory).not.toHaveBeenCalled();
  });

  it("loads and renders versions newest-first when opened", async () => {
    vi.mocked(fetchSectionHistory).mockResolvedValue({
      section_id: "abc:1",
      versions: [VERSION],
    });
    render(
      <SectionHistoryDrawer
        sectionId="abc:1"
        open
        onClose={() => {}}
      />,
    );
    await waitFor(() => {
      expect(fetchSectionHistory).toHaveBeenCalledWith("abc:1");
    });
    await waitFor(() => {
      expect(screen.getByTestId("history-version-ver-1")).toBeInTheDocument();
    });
  });

  it("restores a version and emits onRestored", async () => {
    vi.mocked(fetchSectionHistory).mockResolvedValue({
      section_id: "abc:1",
      versions: [VERSION],
    });
    vi.mocked(restoreSectionVersion).mockResolvedValue({
      section_id: "abc:1",
      version_id: "ver-2",
      persisted_markdown: "## Section\nVersion one body.",
    });
    const onRestored = vi.fn();
    render(
      <SectionHistoryDrawer
        sectionId="abc:1"
        open
        onClose={() => {}}
        onRestored={onRestored}
      />,
    );
    await waitFor(() =>
      screen.getByTestId("restore-version-ver-1"),
    );
    fireEvent.click(screen.getByTestId("restore-version-ver-1"));
    await waitFor(() => {
      expect(restoreSectionVersion).toHaveBeenCalledWith("abc:1", {
        version_id: "ver-1",
      });
    });
    await waitFor(() => {
      expect(onRestored).toHaveBeenCalledWith(
        "## Section\nVersion one body.",
        "ver-2",
      );
    });
  });
});
