import { describe, expect, it, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { LinkedInRepurposeModal } from "./linkedin-repurpose-modal";
import { useLinkedInRepurpose } from "@/hooks/use-linkedin-repurpose";

vi.mock("@/hooks/use-linkedin-repurpose", () => ({
  useLinkedInRepurpose: vi.fn(),
}));

const DRAFT = {
  article_id: "a1",
  hook: "hook line",
  beats: ["b1", "b2", "b3"],
  cta: "read more",
  hashtags: ["#ai"],
  text: "hook line\n\nb1\n\nb2\n\nb3\n\nread more\n\n#ai",
  char_count: 40,
  slop_score: 92,
  slop_rating: "HUMAN",
  model: "claude-sonnet-4-6",
  truncated: false,
};

const writeText = vi.fn();
Object.assign(navigator, { clipboard: { writeText } });

function baseState(overrides: Partial<ReturnType<typeof useLinkedInRepurpose>> = {}) {
  return {
    draft: null,
    text: "",
    setText: vi.fn(),
    generate: vi.fn(),
    publish: vi.fn(),
    busy: false,
    error: null,
    publishedUrl: null,
    ...overrides,
  };
}

describe("LinkedInRepurposeModal", () => {
  beforeEach(() => {
    vi.mocked(useLinkedInRepurpose).mockReset();
    writeText.mockReset();
  });

  it("renders nothing when closed", () => {
    vi.mocked(useLinkedInRepurpose).mockReturnValue(baseState());
    const { container } = render(
      <LinkedInRepurposeModal
        open={false}
        articleId="a1"
        onClose={vi.fn()}
        onToast={vi.fn()}
      />,
    );
    expect(container.innerHTML).toBe("");
  });

  it("shows a Generate button before a draft exists", () => {
    vi.mocked(useLinkedInRepurpose).mockReturnValue(baseState());
    render(
      <LinkedInRepurposeModal
        open
        articleId="a1"
        onClose={vi.fn()}
        onToast={vi.fn()}
      />,
    );
    expect(screen.getByText("Generate")).toBeInTheDocument();
  });

  it("calls generate() with the instruction", () => {
    const state = baseState();
    vi.mocked(useLinkedInRepurpose).mockReturnValue(state);
    render(
      <LinkedInRepurposeModal
        open
        articleId="a1"
        onClose={vi.fn()}
        onToast={vi.fn()}
      />,
    );
    fireEvent.change(screen.getByPlaceholderText(/security angle/i), {
      target: { value: "punchier" },
    });
    fireEvent.click(screen.getByText("Generate"));
    expect(state.generate).toHaveBeenCalledWith("punchier");
  });

  it("fills the textarea and counter once a draft exists", () => {
    vi.mocked(useLinkedInRepurpose).mockReturnValue(
      baseState({ draft: DRAFT, text: DRAFT.text }),
    );
    render(
      <LinkedInRepurposeModal
        open
        articleId="a1"
        onClose={vi.fn()}
        onToast={vi.fn()}
      />,
    );
    const textarea = screen.getByTestId("linkedin-post-text") as HTMLTextAreaElement;
    expect(textarea.value).toBe(DRAFT.text);
    expect(screen.getByText(`${DRAFT.text.length} / 3000`)).toBeInTheDocument();
    expect(screen.getByText("Human")).toBeInTheDocument();
  });

  it("counter turns error and Publish disables over 3000 chars", () => {
    const longText = "x".repeat(3001);
    vi.mocked(useLinkedInRepurpose).mockReturnValue(
      baseState({ draft: DRAFT, text: longText }),
    );
    render(
      <LinkedInRepurposeModal
        open
        articleId="a1"
        onClose={vi.fn()}
        onToast={vi.fn()}
      />,
    );
    expect(screen.getByText("3001 / 3000")).toHaveClass("text-error");
    expect(screen.getByText("Publish to LinkedIn")).toBeDisabled();
  });

  it("Copy text copies the current textarea value and toasts", async () => {
    const onToast = vi.fn();
    vi.mocked(useLinkedInRepurpose).mockReturnValue(
      baseState({ draft: DRAFT, text: "edited text" }),
    );
    render(
      <LinkedInRepurposeModal
        open
        articleId="a1"
        onClose={vi.fn()}
        onToast={onToast}
      />,
    );
    fireEvent.click(screen.getByText("Copy text"));
    await waitFor(() => expect(writeText).toHaveBeenCalledWith("edited text"));
    await waitFor(() =>
      expect(onToast).toHaveBeenCalledWith(expect.stringMatching(/copied/i)),
    );
  });

  it("Publish to LinkedIn calls publish()", () => {
    const state = baseState({ draft: DRAFT, text: "edited text" });
    vi.mocked(useLinkedInRepurpose).mockReturnValue(state);
    render(
      <LinkedInRepurposeModal
        open
        articleId="a1"
        onClose={vi.fn()}
        onToast={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByText("Publish to LinkedIn"));
    expect(state.publish).toHaveBeenCalled();
  });

  it("shows the truncated note when draft.truncated", () => {
    vi.mocked(useLinkedInRepurpose).mockReturnValue(
      baseState({ draft: { ...DRAFT, truncated: true }, text: DRAFT.text }),
    );
    render(
      <LinkedInRepurposeModal
        open
        articleId="a1"
        onClose={vi.fn()}
        onToast={vi.fn()}
      />,
    );
    expect(screen.getByText(/truncated to fit/i)).toBeInTheDocument();
  });

  it("disables Publish and shows the not-connected title on a 503 error", () => {
    vi.mocked(useLinkedInRepurpose).mockReturnValue(
      baseState({
        draft: DRAFT,
        text: DRAFT.text,
        error: "LinkedIn is not connected.",
      }),
    );
    render(
      <LinkedInRepurposeModal
        open
        articleId="a1"
        onClose={vi.fn()}
        onToast={vi.fn()}
      />,
    );
    const button = screen.getByText("Publish to LinkedIn");
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("title", "LinkedIn is not connected");
    expect(screen.getByRole("alert")).toHaveTextContent("LinkedIn is not connected.");
  });

  it("calls onClose when Close is clicked", () => {
    const onClose = vi.fn();
    vi.mocked(useLinkedInRepurpose).mockReturnValue(baseState());
    render(
      <LinkedInRepurposeModal
        open
        articleId="a1"
        onClose={onClose}
        onToast={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByLabelText("Close"));
    expect(onClose).toHaveBeenCalled();
  });
});
