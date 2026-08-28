import { describe, expect, it, vi, beforeEach } from "vitest";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";

const consume = vi.fn();
vi.mock("@/lib/sse/consume-sse", () => ({ consumeSse: (...a: unknown[]) => consume(...a) }));
vi.mock("@/lib/api/client", () => ({
  getAccessToken: () => "T",
  apiClient: { defaults: { baseURL: "http://api/api/v1" } },
}));

import { HumanizationDiffPanel } from "./HumanizationDiffPanel";

const PASS0 = {
  index: 0,
  name: "mechanical",
  score_before: 35,
  score_after: 40,
  rating: "SUSPICIOUS",
  changed: true,
  model: null,
};
const PASS1 = {
  index: 1,
  name: "llm",
  score_before: 40,
  score_after: 85,
  rating: "CLEAN",
  changed: true,
  model: "claude",
};
const DONE = {
  original: "Old wordy paragraph. Keep me.",
  rewritten: "Tighter paragraph. Keep me.",
  diff: [],
  passes: 2,
  llm_called: true,
  model: "claude",
  score_before: 35,
  score_after: 85,
  segments: [
    {
      id: "s0",
      kind: "change",
      before: "Old wordy paragraph.",
      after: "Tighter paragraph.",
      ops: [
        { kind: "replace", before: "Old wordy", after: "Tighter" },
        { kind: "equal", before: " paragraph.", after: " paragraph." },
      ],
    },
    { id: "s1", kind: "equal", before: " Keep me.", after: " Keep me.", ops: [] },
  ],
};

let emit!: (t: string, d: unknown) => void;
let finish!: () => void;

beforeEach(() => {
  consume.mockReset();
  consume.mockImplementation(async (_url: string, o: { onEvent: typeof emit }) => {
    emit = o.onEvent;
    await new Promise<void>((resolve) => {
      finish = resolve;
    });
  });
});

function setup() {
  const onAccept = vi.fn();
  const onCancel = vi.fn();
  render(
    <HumanizationDiffPanel
      sectionId="abc:1"
      currentMarkdown="Old wordy paragraph. Keep me."
      onAccept={onAccept}
      onCancel={onCancel}
    />,
  );
  return { onAccept, onCancel };
}

async function runToDone() {
  fireEvent.click(screen.getByTestId("run-humanize"));
  await waitFor(() => expect(consume).toHaveBeenCalled());
  act(() => emit("pass", PASS0));
  act(() => emit("pass", PASS1));
  act(() => emit("done", DONE));
  act(() => finish());
  await waitFor(() => screen.getByTestId("accept-humanize"));
}

describe("HumanizationDiffPanel (streaming)", () => {
  it("streams pass tiles as events arrive, then shows score badges", async () => {
    setup();
    fireEvent.click(screen.getByTestId("run-humanize"));
    await waitFor(() => expect(consume).toHaveBeenCalled());
    expect(screen.getByTestId("humanize-pass-pending")).toBeInTheDocument();
    act(() => emit("pass", PASS0));
    expect(screen.getAllByTestId("humanize-pass-tile")).toHaveLength(1);
    act(() => emit("pass", PASS1));
    expect(screen.getAllByTestId("humanize-pass-tile")).toHaveLength(2);
    act(() => emit("done", DONE));
    act(() => finish());
    await waitFor(() =>
      expect(screen.getByTestId("humanize-score-badges")).toHaveTextContent("35"),
    );
    expect(screen.queryByTestId("humanize-pass-pending")).not.toBeInTheDocument();
  });

  it("Accept emits the resolved markdown; rejecting a sentence restores it", async () => {
    const { onAccept } = setup();
    await runToDone();
    expect(screen.getAllByTestId("humanize-change")).toHaveLength(1);
    fireEvent.click(screen.getByTestId("accept-humanize"));
    expect(onAccept).toHaveBeenLastCalledWith("Tighter paragraph. Keep me.");
    fireEvent.click(screen.getByTestId("toggle-change-s0"));
    expect(screen.getByTestId("humanize-change")).toHaveAttribute("data-rejected", "true");
    fireEvent.click(screen.getByTestId("accept-humanize"));
    expect(onAccept).toHaveBeenLastCalledWith("Old wordy paragraph. Keep me.");
  });

  it("Reject all / Accept all flip every change", async () => {
    setup();
    await runToDone();
    fireEvent.click(screen.getByTestId("reject-all-changes"));
    expect(screen.getByTestId("humanize-change")).toHaveAttribute("data-rejected", "true");
    fireEvent.click(screen.getByTestId("accept-all-changes"));
    expect(screen.getByTestId("humanize-change")).toHaveAttribute("data-rejected", "false");
  });

  it("Reject clears the result and shows Run again", async () => {
    setup();
    await runToDone();
    fireEvent.click(screen.getByTestId("reject-humanize"));
    expect(screen.queryByTestId("humanize-change")).not.toBeInTheDocument();
    expect(screen.getByTestId("run-humanize")).toBeInTheDocument();
  });

  it("Cancel while streaming aborts and Close calls onCancel", async () => {
    const { onCancel } = setup();
    fireEvent.click(screen.getByTestId("run-humanize"));
    await waitFor(() => expect(consume).toHaveBeenCalled());
    const opts = consume.mock.calls[0][1] as { signal: AbortSignal };
    fireEvent.click(screen.getByTestId("cancel-humanize"));
    expect(opts.signal.aborted).toBe(true);
    expect(screen.getByTestId("run-humanize")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Close"));
    expect(onCancel).toHaveBeenCalled();
  });

  it("renders the error event", async () => {
    setup();
    fireEvent.click(screen.getByTestId("run-humanize"));
    await waitFor(() => expect(consume).toHaveBeenCalled());
    act(() => emit("error", { message: "boom" }));
    act(() => finish());
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("boom"));
  });
});
