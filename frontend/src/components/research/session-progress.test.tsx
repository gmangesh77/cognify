import { act, render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

vi.mock("next/link", () => ({
  default: ({ href, children }: { href: string; children: React.ReactNode }) => (
    <a href={href}>{children}</a>
  ),
}));

const events = vi.fn();
vi.mock("@/hooks/use-session-events", () => ({ useSessionEvents: (id: string) => events(id) }));

const researchSession = vi.fn();
vi.mock("@/hooks/use-research-sessions", () => ({
  useResearchSession: () => researchSession(),
}));

vi.mock("@/lib/api/research", () => ({ fetchSessionArticle: vi.fn(async () => ({ article_id: "art-1" })) }));

vi.mock("./outline-review-step", () => ({
  OutlineReviewStep: ({ sessionId }: { sessionId: string }) => (
    <div data-testid="outline-review-step">Outline review for {sessionId}</div>
  ),
}));

const cancelMutate = vi.fn();
const cancelSessionHook = vi.fn((_id: string) => ({ mutate: cancelMutate, isPending: false }));
vi.mock("@/hooks/use-outline-review", () => ({
  useCancelSession: (id: string) => cancelSessionHook(id),
}));

import { SessionProgress } from "./session-progress";

const base = {
  status: "generating_article",
  connection: "live",
  error: null,
  sections: null,
  steps: [
    {
      id: "1",
      step_name: "plan_research",
      status: "complete",
      started_at: "",
      completed_at: null,
      duration_ms: 10,
      output_data: {},
    },
    {
      id: "2",
      step_name: "content_draft",
      status: "running",
      started_at: "",
      completed_at: null,
      duration_ms: null,
      output_data: {},
    },
  ],
};

describe("SessionProgress", () => {
  beforeEach(() => {
    researchSession.mockReturnValue({
      data: {
        topic_title: "OAuth 2.1",
        status: "generating_article",
        started_at: new Date().toISOString(),
      },
    });
    cancelMutate.mockClear();
    cancelSessionHook.mockClear();
    cancelSessionHook.mockReturnValue({ mutate: cancelMutate, isPending: false });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders labelled steps with status", () => {
    events.mockReturnValue(base);
    render(<SessionProgress sessionId="s1" />);
    expect(screen.getByText("Plan Research").closest("[role=listitem]")).toHaveAttribute(
      "data-status",
      "complete",
    );
    expect(screen.getByText("Draft Sections").closest("[role=listitem]")).toHaveAttribute(
      "data-status",
      "running",
    );
  });

  it("shows section progress", () => {
    events.mockReturnValue({ ...base, sections: { done: 2, total: 5, current: "Intro" } });
    render(<SessionProgress sessionId="s1" />);
    expect(screen.getByText(/Drafting 2 \/ 5/)).toBeInTheDocument();
  });

  it("offers View article when complete", async () => {
    events.mockReturnValue({ ...base, status: "article_complete", connection: "closed" });
    render(<SessionProgress sessionId="s1" />);
    fireEvent.click(screen.getByRole("button", { name: /view article/i }));
    await waitFor(() => expect(push).toHaveBeenCalledWith("/articles/art-1"));
  });

  it("shows the failed step error", () => {
    events.mockReturnValue({
      ...base,
      status: "article_failed",
      steps: [{ ...base.steps[1], status: "failed", output_data: { error: "LLM timeout" } }],
    });
    render(<SessionProgress sessionId="s1" />);
    expect(screen.getByText(/LLM timeout/)).toBeInTheDocument();
  });

  it("prefers the query status over a frozen events.status when connection is 'error'", () => {
    researchSession.mockReturnValue({
      data: {
        topic_title: "OAuth 2.1",
        status: "article_complete",
        started_at: new Date().toISOString(),
      },
    });
    events.mockReturnValue({
      ...base,
      status: "generating_article",
      connection: "error",
      error: "boom",
    });
    render(<SessionProgress sessionId="s1" />);
    expect(screen.getByRole("button", { name: /view article/i })).toBeInTheDocument();
  });

  it("shows a connecting chip while the stream is establishing", () => {
    events.mockReturnValue({ ...base, connection: "connecting" });
    render(<SessionProgress sessionId="s1" />);
    expect(screen.getByText(/Connecting/i)).toBeInTheDocument();
  });

  it("shows a reconnecting chip on transient drops", () => {
    events.mockReturnValue({ ...base, connection: "reconnecting" });
    render(<SessionProgress sessionId="s1" />);
    expect(screen.getByText(/Reconnecting/i)).toBeInTheDocument();
  });

  it("shows an offline chip with retry on error and calls reconnect", () => {
    const reconnect = vi.fn();
    events.mockReturnValue({ ...base, connection: "error", error: "boom", reconnect });
    render(<SessionProgress sessionId="s1" />);
    expect(screen.getByText(/Offline — showing last known state/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /retry/i }));
    expect(reconnect).toHaveBeenCalledTimes(1);
  });

  it("shows no connection chip once the stream has closed", () => {
    events.mockReturnValue({ ...base, status: "article_complete", connection: "closed" });
    render(<SessionProgress sessionId="s1" />);
    expect(screen.queryByText(/Live|Connecting|Reconnecting|Offline/i)).not.toBeInTheDocument();
  });

  it("ticks the elapsed time every second while the session is active", () => {
    vi.useFakeTimers();
    const start = new Date("2026-01-01T00:00:00.000Z");
    vi.setSystemTime(start);
    researchSession.mockReturnValue({
      data: {
        topic_title: "OAuth 2.1",
        status: "generating_article",
        started_at: start.toISOString(),
      },
    });
    events.mockReturnValue(base);
    render(<SessionProgress sessionId="s1" />);
    expect(screen.getByText("Elapsed: 0m 0s")).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(3000);
    });
    expect(screen.getByText("Elapsed: 0m 3s")).toBeInTheDocument();
  });

  it("stops ticking once the session reaches a terminal status (no completed_at yet)", () => {
    vi.useFakeTimers();
    const start = new Date("2026-01-01T00:00:00.000Z");
    vi.setSystemTime(start);
    researchSession.mockReturnValue({
      data: {
        topic_title: "OAuth 2.1",
        status: "article_complete",
        started_at: start.toISOString(),
      },
    });
    events.mockReturnValue({ ...base, status: "article_complete", connection: "closed" });
    render(<SessionProgress sessionId="s1" />);
    expect(screen.getByText("Duration: 0m 0s")).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(5000);
    });
    expect(screen.getByText("Duration: 0m 0s")).toBeInTheDocument();
  });

  it("computes Duration from started_at to completed_at when terminal, ignoring the current clock", () => {
    vi.useFakeTimers();
    const start = new Date("2026-01-01T00:00:00.000Z");
    const completed = new Date("2026-01-01T00:05:03.000Z");
    // The wall clock is days ahead of completion — this is the regression the
    // fix targets: a page loaded long after the session finished must not
    // show "Elapsed" computed against "now".
    vi.setSystemTime(new Date("2026-01-05T00:00:00.000Z"));
    researchSession.mockReturnValue({
      data: {
        topic_title: "OAuth 2.1",
        status: "article_complete",
        started_at: start.toISOString(),
        completed_at: completed.toISOString(),
      },
    });
    events.mockReturnValue({ ...base, status: "article_complete", connection: "closed" });
    render(<SessionProgress sessionId="s1" />);
    expect(screen.getByText("Duration: 5m 3s")).toBeInTheDocument();
    expect(screen.queryByText(/Elapsed:/)).not.toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(10_000);
    });
    expect(screen.getByText("Duration: 5m 3s")).toBeInTheDocument();
  });

  it("formats durations of an hour or more with hours", () => {
    vi.useFakeTimers();
    const start = new Date("2026-01-01T00:00:00.000Z");
    const completed = new Date("2026-01-01T01:05:09.000Z");
    vi.setSystemTime(start);
    researchSession.mockReturnValue({
      data: {
        topic_title: "OAuth 2.1",
        status: "article_complete",
        started_at: start.toISOString(),
        completed_at: completed.toISOString(),
      },
    });
    events.mockReturnValue({ ...base, status: "article_complete", connection: "closed" });
    render(<SessionProgress sessionId="s1" />);
    expect(screen.getByText("Duration: 1h 5m 9s")).toBeInTheDocument();
  });

  it("renders the OutlineReviewStep when the session is awaiting outline review", () => {
    researchSession.mockReturnValue({
      data: {
        topic_title: "OAuth 2.1",
        status: "awaiting_outline_review",
        started_at: new Date().toISOString(),
      },
    });
    events.mockReturnValue({ ...base, status: "awaiting_outline_review" });
    render(<SessionProgress sessionId="s1" />);
    expect(screen.getByTestId("outline-review-step")).toHaveTextContent("s1");
  });

  it("does not render the OutlineReviewStep for other statuses", () => {
    events.mockReturnValue(base);
    render(<SessionProgress sessionId="s1" />);
    expect(screen.queryByTestId("outline-review-step")).not.toBeInTheDocument();
  });

  it("shows a Cancel button while the session is active and calls cancelSession on click", () => {
    events.mockReturnValue(base);
    render(<SessionProgress sessionId="s1" />);
    const cancelBtn = screen.getByRole("button", { name: /cancel generation/i });
    fireEvent.click(cancelBtn);
    expect(cancelMutate).toHaveBeenCalledTimes(1);
  });

  it("hides the Cancel button once the session is terminal", () => {
    researchSession.mockReturnValue({
      data: {
        topic_title: "OAuth 2.1",
        status: "article_complete",
        started_at: new Date().toISOString(),
      },
    });
    events.mockReturnValue({ ...base, status: "article_complete", connection: "closed" });
    render(<SessionProgress sessionId="s1" />);
    expect(screen.queryByRole("button", { name: /cancel generation/i })).not.toBeInTheDocument();
  });

  it("disables the Cancel button while the cancel mutation is pending", () => {
    cancelSessionHook.mockReturnValue({ mutate: cancelMutate, isPending: true });
    events.mockReturnValue(base);
    render(<SessionProgress sessionId="s1" />);
    expect(screen.getByRole("button", { name: /cancel generation/i })).toBeDisabled();
  });

  it("shows a cancelled panel with a Back to research link when the session was cancelled", () => {
    researchSession.mockReturnValue({
      data: {
        topic_title: "OAuth 2.1",
        status: "cancelled",
        started_at: new Date().toISOString(),
      },
    });
    events.mockReturnValue({ ...base, status: "cancelled", connection: "closed" });
    render(<SessionProgress sessionId="s1" />);
    expect(screen.getByText(/generation cancelled/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /back to research/i })).toHaveAttribute(
      "href",
      "/research",
    );
  });
});
