import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { OutlineReviewStep } from "./outline-review-step";
import type { ArticleOutline, OutlineResponse } from "@/types/research";

vi.mock("@/lib/api/research", () => ({
  fetchOutline: vi.fn(),
  updateOutline: vi.fn(),
  regenerateOutline: vi.fn(),
  approveOutline: vi.fn(),
  cancelSession: vi.fn(),
}));

import {
  fetchOutline,
  updateOutline,
  regenerateOutline,
  approveOutline,
} from "@/lib/api/research";

const mockFetchOutline = vi.mocked(fetchOutline);
const mockUpdateOutline = vi.mocked(updateOutline);
const mockRegenerateOutline = vi.mocked(regenerateOutline);
const mockApproveOutline = vi.mocked(approveOutline);

const baseOutline: ArticleOutline = {
  title: "Zero Trust Architecture",
  subtitle: "A practical guide",
  content_type: "article",
  sections: [
    {
      index: 0,
      title: "Introduction",
      description: "Set the stage",
      key_points: ["point a", "point b"],
      target_word_count: 200,
      relevant_facets: [0],
    },
    {
      index: 1,
      title: "Deep Dive",
      description: "Go deeper",
      key_points: ["point c"],
      target_word_count: 400,
      relevant_facets: [1],
    },
  ],
  total_target_words: 600,
  reasoning: "Because reasons",
};

const baseResponse: OutlineResponse = {
  draft_id: "draft-1",
  session_id: "sess-1",
  status: "outline_complete",
  outline: baseOutline,
};

function renderStep(sessionId = "sess-1") {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <OutlineReviewStep sessionId={sessionId} />
    </QueryClientProvider>,
  );
}

describe("OutlineReviewStep", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFetchOutline.mockResolvedValue(baseResponse);
    mockUpdateOutline.mockResolvedValue(baseResponse);
    mockRegenerateOutline.mockResolvedValue(baseResponse);
    mockApproveOutline.mockResolvedValue({ session_id: "sess-1", status: "generating_article" });
  });

  it("renders the sections from the loaded outline", async () => {
    renderStep();
    expect(await screen.findByDisplayValue("Introduction")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Deep Dive")).toBeInTheDocument();
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
  });

  it("renders key points one per line", async () => {
    renderStep();
    const textarea = (await screen.findByLabelText(
      "Section 1 key points",
    )) as HTMLTextAreaElement;
    expect(textarea.tagName).toBe("TEXTAREA");
    expect(textarea.value).toBe("point a\npoint b");
  });

  it("adds a new section when 'Add section' is clicked", async () => {
    renderStep();
    await screen.findByDisplayValue("Introduction");
    fireEvent.click(screen.getByRole("button", { name: /add section/i }));
    expect(screen.getAllByRole("listitem")).toHaveLength(3);
    expect(screen.getByDisplayValue("New section")).toBeInTheDocument();
  });

  it("defaults a new section's word budget to the outline average", async () => {
    // AUTHOR-008: sections target 200 + 400 -> average 300.
    renderStep();
    await screen.findByDisplayValue("Introduction");
    fireEvent.click(screen.getByRole("button", { name: /add section/i }));
    expect(screen.getByText("~300 words")).toBeInTheDocument();
  });

  it("shows the outline's total word target", async () => {
    renderStep();
    await screen.findByDisplayValue("Introduction");
    expect(screen.getByText("Total target: ~600 words")).toBeInTheDocument();
  });

  it("deletes a section when its delete button is clicked", async () => {
    renderStep();
    await screen.findByDisplayValue("Introduction");
    fireEvent.click(screen.getByRole("button", { name: /delete section 1/i }));
    expect(screen.getAllByRole("listitem")).toHaveLength(1);
    expect(screen.queryByDisplayValue("Introduction")).not.toBeInTheDocument();
  });

  it("reorders sections with the move down / move up buttons", async () => {
    renderStep();
    await screen.findByDisplayValue("Introduction");
    fireEvent.click(screen.getByRole("button", { name: /move section 1 down/i }));
    const titles = screen.getAllByRole("listitem").map((li) =>
      (li.querySelector("input") as HTMLInputElement).value,
    );
    expect(titles).toEqual(["Deep Dive", "Introduction"]);
  });

  it("approves directly (no save) when the outline has not been edited", async () => {
    renderStep();
    await screen.findByDisplayValue("Introduction");
    fireEvent.click(screen.getByRole("button", { name: /approve & write/i }));
    await waitFor(() => expect(mockApproveOutline).toHaveBeenCalledWith("sess-1"));
    expect(mockUpdateOutline).not.toHaveBeenCalled();
  });

  it("saves the local edits before approving when the outline is dirty", async () => {
    renderStep();
    const titleInput = await screen.findByDisplayValue("Introduction");
    fireEvent.change(titleInput, { target: { value: "Intro Renamed" } });
    fireEvent.click(screen.getByRole("button", { name: /approve & write/i }));

    await waitFor(() => expect(mockApproveOutline).toHaveBeenCalledWith("sess-1"));
    expect(mockUpdateOutline).toHaveBeenCalledTimes(1);
    const [sessionIdArg, outlineArg] = mockUpdateOutline.mock.calls[0];
    expect(sessionIdArg).toBe("sess-1");
    expect(outlineArg.sections[0].title).toBe("Intro Renamed");
    // save must resolve before approve is invoked
    const saveOrder = mockUpdateOutline.mock.invocationCallOrder[0];
    const approveOrder = mockApproveOutline.mock.invocationCallOrder[0];
    expect(saveOrder).toBeLessThan(approveOrder);
  });

  it("renders 422 validation errors from a failed save", async () => {
    mockUpdateOutline.mockRejectedValue({
      isAxiosError: true,
      response: { status: 422, data: { detail: ["sections[0].title: too short"] } },
    });
    renderStep();
    const titleInput = await screen.findByDisplayValue("Introduction");
    fireEvent.change(titleInput, { target: { value: "x" } });
    fireEvent.click(screen.getByRole("button", { name: /approve & write/i }));

    expect(await screen.findByText(/too short/)).toBeInTheDocument();
    expect(mockApproveOutline).not.toHaveBeenCalled();
  });

  it("shows a friendly message when approve fails with 409", async () => {
    mockApproveOutline.mockRejectedValue({
      isAxiosError: true,
      response: { status: 409, data: {} },
    });
    renderStep();
    await screen.findByDisplayValue("Introduction");
    fireEvent.click(screen.getByRole("button", { name: /approve & write/i }));

    expect(
      await screen.findByText(/session is no longer awaiting review/i),
    ).toBeInTheDocument();
  });

  it("shows a friendly message when regenerate fails with 429", async () => {
    mockRegenerateOutline.mockRejectedValue({
      isAxiosError: true,
      response: { status: 429, data: {} },
    });
    renderStep();
    await screen.findByDisplayValue("Introduction");
    fireEvent.click(screen.getByRole("button", { name: /regenerate outline/i }));

    expect(
      await screen.findByText(/too many regenerate requests/i),
    ).toBeInTheDocument();
  });

  it("calls regenerateOutline with the typed instruction when the outline is clean", async () => {
    renderStep();
    await screen.findByDisplayValue("Introduction");
    fireEvent.change(screen.getByLabelText(/regenerate instruction/i), {
      target: { value: "focus on enterprise" },
    });
    fireEvent.click(screen.getByRole("button", { name: /regenerate outline/i }));

    await waitFor(() =>
      expect(mockRegenerateOutline).toHaveBeenCalledWith("sess-1", "focus on enterprise"),
    );
  });

  it("asks to discard local edits before regenerating when dirty", async () => {
    renderStep();
    const titleInput = await screen.findByDisplayValue("Introduction");
    fireEvent.change(titleInput, { target: { value: "Edited" } });
    fireEvent.click(screen.getByRole("button", { name: /regenerate outline/i }));

    expect(
      screen.getByText(/discard local edits and regenerate/i),
    ).toBeInTheDocument();
    expect(mockRegenerateOutline).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: /discard & regenerate/i }));
    await waitFor(() => expect(mockRegenerateOutline).toHaveBeenCalledWith("sess-1", undefined));
  });

  it("disables the approve button while a mutation is pending", async () => {
    let resolveApprove!: (value: { session_id: string; status: string }) => void;
    mockApproveOutline.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveApprove = resolve;
        }),
    );
    renderStep();
    await screen.findByDisplayValue("Introduction");
    const approveBtn = screen.getByRole("button", { name: /approve & write/i });
    fireEvent.click(approveBtn);
    await waitFor(() => expect(approveBtn).toBeDisabled());
    resolveApprove({ session_id: "sess-1", status: "generating_article" });
  });
});
