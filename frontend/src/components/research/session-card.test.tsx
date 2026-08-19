import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { SessionCard } from "./session-card";
import type { ResearchSessionSummary } from "@/types/research";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

vi.mock("next/link", () => ({
  default: ({ href, children }: { href: string; children: React.ReactNode }) => (
    <a href={href}>{children}</a>
  ),
}));

vi.mock("@/lib/api/research", () => ({
  fetchSessionArticle: vi.fn(async () => ({ article_id: "art-9" })),
}));

const completeSession: ResearchSessionSummary = {
  session_id: "sess-001",
  topic_id: "topic-001",
  status: "complete",
  round_count: 3,
  findings_count: 12,
  sources_count: 8,
  embeddings_count: 24,
  started_at: "2026-03-20T10:00:00Z",
  topic_title: "AI Security Trends 2026",
  duration_seconds: 272,
};

const inProgressSession: ResearchSessionSummary = {
  ...completeSession,
  session_id: "sess-002",
  status: "in_progress",
  topic_title: "Zero Trust Architecture",
};

const articleCompleteSession: ResearchSessionSummary = {
  ...completeSession,
  session_id: "sess-003",
  status: "article_complete",
  topic_title: "Post-Quantum Crypto",
};

const failedSession: ResearchSessionSummary = {
  ...completeSession,
  session_id: "sess-004",
  status: "article_failed",
  topic_title: "Failed Article",
};

const awaitingReviewSession: ResearchSessionSummary = {
  ...completeSession,
  session_id: "sess-005",
  status: "awaiting_outline_review",
  topic_title: "Outline Pending",
};

const cancelledSession: ResearchSessionSummary = {
  ...completeSession,
  session_id: "sess-006",
  status: "cancelled",
  topic_title: "Cancelled Session",
};

describe("SessionCard", () => {
  beforeEach(() => {
    push.mockClear();
  });

  it("renders topic title and status badge", () => {
    render(<SessionCard session={completeSession} isExpanded={false} onToggle={() => {}} />);
    expect(screen.getByText("AI Security Trends 2026")).toBeInTheDocument();
    expect(screen.getByText("Research Complete")).toBeInTheDocument();
  });

  it("renders round count and findings count", () => {
    render(<SessionCard session={completeSession} isExpanded={false} onToggle={() => {}} />);
    expect(screen.getByText(/3 rounds/)).toBeInTheDocument();
    expect(screen.getByText(/12 findings/)).toBeInTheDocument();
  });

  it("renders progress bar", () => {
    const { container } = render(
      <SessionCard session={completeSession} isExpanded={false} onToggle={() => {}} />,
    );
    const bar = container.querySelector("[data-testid='progress-bar']");
    expect(bar).toBeInTheDocument();
  });

  it("calls onToggle when clicked", () => {
    const onToggle = vi.fn();
    render(<SessionCard session={completeSession} isExpanded={false} onToggle={onToggle} />);
    fireEvent.click(screen.getByText("AI Security Trends 2026"));
    expect(onToggle).toHaveBeenCalledOnce();
  });

  it("shows correct left border color for each status", () => {
    const { container: c1 } = render(
      <SessionCard session={completeSession} isExpanded={false} onToggle={() => {}} />,
    );
    expect((c1.firstChild as HTMLElement)?.className).toContain("border-l-blue-500");

    const { container: c2 } = render(
      <SessionCard session={inProgressSession} isExpanded={false} onToggle={() => {}} />,
    );
    expect((c2.firstChild as HTMLElement)?.className).toContain("border-l-amber-500");
  });

  it("renders children when expanded", () => {
    render(
      <SessionCard session={completeSession} isExpanded={true} onToggle={() => {}}>
        <div>Expanded content</div>
      </SessionCard>,
    );
    expect(screen.getByText("Expanded content")).toBeInTheDocument();
  });

  it("shows an indeterminate progress bar with aria-busy for non-terminal sessions", () => {
    const { container } = render(
      <SessionCard session={inProgressSession} isExpanded={false} onToggle={() => {}} />,
    );
    const bar = container.querySelector("[data-testid='progress-bar']") as HTMLElement;
    expect(bar).toHaveAttribute("aria-busy", "true");
    expect(bar.className).toContain("animate-pulse");
    expect(bar.className).toContain("w-1/3");
    expect(bar.style.width).toBe("");
  });

  it("shows a full, determinate progress bar for terminal sessions without aria-busy", () => {
    const { container } = render(
      <SessionCard session={articleCompleteSession} isExpanded={false} onToggle={() => {}} />,
    );
    const bar = container.querySelector("[data-testid='progress-bar']") as HTMLElement;
    expect(bar).not.toHaveAttribute("aria-busy");
    expect(bar.className).toContain("w-full");
    expect(bar.style.width).toBe("");
  });

  it("shows a View progress link for non-terminal sessions", () => {
    render(<SessionCard session={inProgressSession} isExpanded={false} onToggle={() => {}} />);
    const link = screen.getByRole("link", { name: /view progress/i });
    expect(link).toHaveAttribute("href", "/research/sess-002");
  });

  it("does not show a View progress link for terminal sessions", () => {
    render(<SessionCard session={articleCompleteSession} isExpanded={false} onToggle={() => {}} />);
    expect(screen.queryByRole("link", { name: /view progress/i })).not.toBeInTheDocument();
  });

  it("shows a View article button for article_complete that navigates on click", async () => {
    render(
      <SessionCard session={articleCompleteSession} isExpanded={false} onToggle={() => {}} />,
    );
    fireEvent.click(screen.getByRole("button", { name: /view article/i }));
    await waitFor(() => expect(push).toHaveBeenCalledWith("/articles/art-9"));
  });

  it("does not show a View article button for non-article_complete terminal sessions", () => {
    render(<SessionCard session={failedSession} isExpanded={false} onToggle={() => {}} />);
    expect(screen.queryByRole("button", { name: /view article/i })).not.toBeInTheDocument();
  });

  it("shows a Review outline link (not View progress) for awaiting_outline_review sessions", () => {
    render(<SessionCard session={awaitingReviewSession} isExpanded={false} onToggle={() => {}} />);
    const link = screen.getByRole("link", { name: /review outline/i });
    expect(link).toHaveAttribute("href", "/research/sess-005");
    expect(screen.queryByRole("link", { name: /view progress/i })).not.toBeInTheDocument();
  });

  it("shows the info border color for awaiting_outline_review sessions", () => {
    const { container } = render(
      <SessionCard session={awaitingReviewSession} isExpanded={false} onToggle={() => {}} />,
    );
    expect((container.firstChild as HTMLElement)?.className).toContain("border-l-info");
  });

  it("shows a neutral border and progress bar for cancelled sessions", () => {
    const { container } = render(
      <SessionCard session={cancelledSession} isExpanded={false} onToggle={() => {}} />,
    );
    expect((container.firstChild as HTMLElement)?.className).toContain("border-l-neutral-300");
    const bar = container.querySelector("[data-testid='progress-bar']") as HTMLElement;
    expect(bar.className).toContain("bg-neutral-300");
  });
});
