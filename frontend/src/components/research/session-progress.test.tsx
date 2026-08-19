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

  it("stops ticking once the session reaches a terminal status", () => {
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
    expect(screen.getByText("Elapsed: 0m 0s")).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(5000);
    });
    expect(screen.getByText("Elapsed: 0m 0s")).toBeInTheDocument();
  });
});
