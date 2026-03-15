import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RecentArticlesList } from "./recent-articles-list";
import { mockArticles } from "@/lib/mock/articles";

vi.mock("next/link", () => ({
  default: ({ children, href, ...props }: { children: React.ReactNode; href: string; [key: string]: unknown }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

describe("RecentArticlesList", () => {
  it("renders article rows when data is provided", () => {
    render(<RecentArticlesList articles={mockArticles} isLoading={false} />);
    expect(screen.getByText("The Rise of AI in Threat Detection: A 2026 Overview")).toBeInTheDocument();
    expect(screen.getByText("Recent Articles")).toBeInTheDocument();
    expect(screen.getByText("View All")).toBeInTheDocument();
  });

  it("renders skeleton loading state", () => {
    const { container } = render(<RecentArticlesList articles={[]} isLoading={true} />);
    const skeletons = container.querySelectorAll("[data-slot='skeleton']");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("renders error state with retry button", async () => {
    const onRetry = vi.fn();
    render(<RecentArticlesList articles={[]} isLoading={false} isError={true} onRetry={onRetry} />);
    expect(screen.getByText("Unable to load recent articles")).toBeInTheDocument();
    await userEvent.click(screen.getByText("Retry"));
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it("renders empty state when no articles", () => {
    render(<RecentArticlesList articles={[]} isLoading={false} />);
    expect(screen.getByText(/No articles yet/)).toBeInTheDocument();
  });
});
