import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { RegeneratePopover } from "./RegeneratePopover";
import * as api from "@/lib/api/content";

vi.mock("@/lib/api/content", () => ({
  regenerateSection: vi.fn(),
  persistSectionUpdate: vi.fn(),
}));

const RESPONSE = {
  section_id: "art-1:1",
  section_index: 1,
  markdown: "## Second\n\nbrand new prose",
  diff: [
    { kind: "equal" as const, before: "## Second ", after: "## Second " },
    { kind: "replace" as const, before: "old prose", after: "brand new prose" },
  ],
  version_id: "cand-1",
  model: "claude",
  word_count: 3,
  tokens_input: 100,
  tokens_output: 40,
  instruction: "tighter",
};

function setup() {
  const onAccepted = vi.fn();
  const onCancel = vi.fn();
  render(
    <RegeneratePopover articleId="art-1" sectionIndex={1} onAccepted={onAccepted} onCancel={onCancel} />,
  );
  return { onAccepted, onCancel };
}

describe("RegeneratePopover", () => {
  beforeEach(() => {
    vi.mocked(api.regenerateSection).mockReset();
    vi.mocked(api.persistSectionUpdate).mockReset();
  });

  it("runs with an optional instruction and shows the diff + word count", async () => {
    vi.mocked(api.regenerateSection).mockResolvedValue(RESPONSE);
    setup();
    fireEvent.change(screen.getByTestId("regenerate-instruction"), {
      target: { value: "tighter" },
    });
    fireEvent.click(screen.getByTestId("run-regenerate"));
    await waitFor(() => screen.getByTestId("word-diff-view"));
    expect(api.regenerateSection).toHaveBeenCalledWith({
      article_id: "art-1",
      section_index: 1,
      instruction: "tighter",
    });
    expect(screen.getByTestId("regenerate-meta")).toHaveTextContent("3 words");
    expect(screen.getByTestId("accept-regenerate")).toBeInTheDocument();
    expect(screen.getByTestId("reject-regenerate")).toBeInTheDocument();
  });

  it("run button is enabled with an empty instruction", () => {
    setup();
    expect(screen.getByTestId("run-regenerate")).not.toBeDisabled();
  });

  it("accept persists via section-update with source=regenerate and the returned section_id", async () => {
    vi.mocked(api.regenerateSection).mockResolvedValue(RESPONSE);
    vi.mocked(api.persistSectionUpdate).mockResolvedValue({
      section_id: "art-1:1",
      version_id: "applied-1",
      persisted_markdown: RESPONSE.markdown,
    });
    const { onAccepted } = setup();
    fireEvent.click(screen.getByTestId("run-regenerate"));
    await waitFor(() => screen.getByTestId("accept-regenerate"));
    fireEvent.click(screen.getByTestId("accept-regenerate"));
    await waitFor(() => expect(onAccepted).toHaveBeenCalledWith(RESPONSE.markdown, "applied-1"));
    expect(api.persistSectionUpdate).toHaveBeenCalledWith({
      section_id: "art-1:1",
      markdown: RESPONSE.markdown,
      source: "regenerate",
      instruction: "tighter",
    });
  });

  it("reject clears the diff and keeps the popover open", async () => {
    vi.mocked(api.regenerateSection).mockResolvedValue(RESPONSE);
    const { onCancel } = setup();
    fireEvent.click(screen.getByTestId("run-regenerate"));
    await waitFor(() => screen.getByTestId("reject-regenerate"));
    fireEvent.click(screen.getByTestId("reject-regenerate"));
    expect(screen.queryByTestId("word-diff-view")).toBeNull();
    expect(screen.getByTestId("run-regenerate")).toBeInTheDocument();
    expect(onCancel).not.toHaveBeenCalled();
  });

  it("renders anchor violations from a 422", async () => {
    vi.mocked(api.regenerateSection).mockRejectedValue({
      response: {
        status: 422,
        data: {
          detail: {
            violations: [
              { kind: "spec_id", value: "spec-a", spec_id: "spec-a", message: "dropped spec-a" },
            ],
          },
        },
      },
    });
    setup();
    fireEvent.click(screen.getByTestId("run-regenerate"));
    await waitFor(() => screen.getByRole("alert"));
    expect(screen.getByTestId("regenerate-violations")).toHaveTextContent("dropped spec-a");
  });
});
