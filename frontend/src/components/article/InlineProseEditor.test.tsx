import { describe, expect, it, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

vi.mock("@/lib/api/content", () => ({
  persistSectionUpdate: vi.fn(),
}));

import { persistSectionUpdate } from "@/lib/api/content";
import { InlineProseEditor } from "./InlineProseEditor";

describe("InlineProseEditor", () => {
  beforeEach(() => {
    vi.mocked(persistSectionUpdate).mockReset();
  });

  it("disables save until the draft differs from the initial markdown", () => {
    render(
      <InlineProseEditor
        sectionId="abc:1"
        initialMarkdown="## Section\nOriginal body."
      />,
    );
    expect(screen.getByTestId("save-prose-edit")).toBeDisabled();
    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "## Section\nNew body." },
    });
    expect(screen.getByTestId("save-prose-edit")).toBeEnabled();
  });

  it("posts the draft and emits onPersisted with the version id", async () => {
    vi.mocked(persistSectionUpdate).mockResolvedValue({
      section_id: "abc:1",
      version_id: "version-uuid-123",
      persisted_markdown: "## Section\nNew body.",
    });
    const onPersisted = vi.fn();
    render(
      <InlineProseEditor
        sectionId="abc:1"
        initialMarkdown="## Section\nOriginal body."
        onPersisted={onPersisted}
      />,
    );
    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "## Section\nNew body." },
    });
    fireEvent.click(screen.getByTestId("save-prose-edit"));
    await waitFor(() => {
      expect(persistSectionUpdate).toHaveBeenCalledWith(
        expect.objectContaining({
          section_id: "abc:1",
          markdown: "## Section\nNew body.",
          source: "manual",
        }),
      );
    });
    await waitFor(() => {
      expect(onPersisted).toHaveBeenCalledWith(
        "## Section\nNew body.",
        "version-uuid-123",
      );
    });
  });

  it("surfaces anchor-violation details when the backend returns 422", async () => {
    const violation = {
      kind: "heading_text" as const,
      value: "First Section",
      spec_id: "img-01",
      message: "Edit dropped or renamed heading 'First Section'.",
    };
    vi.mocked(persistSectionUpdate).mockRejectedValue({
      response: {
        status: 422,
        data: { detail: { violations: [violation] } },
      },
    });
    render(
      <InlineProseEditor
        sectionId="abc:1"
        initialMarkdown="## First Section\nOriginal body."
      />,
    );
    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "## Renamed Heading\nReplacement." },
    });
    fireEvent.click(screen.getByTestId("save-prose-edit"));
    await waitFor(() => {
      expect(screen.getByTestId("anchor-violations")).toHaveTextContent(
        "First Section",
      );
    });
  });
});
