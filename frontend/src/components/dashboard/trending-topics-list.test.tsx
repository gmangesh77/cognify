import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TrendingTopicsList } from "./trending-topics-list";
import { mockTopics } from "@/lib/mock/topics";

vi.mock("next/link", () => ({
  default: ({ children, href, ...props }: { children: React.ReactNode; href: string; [key: string]: unknown }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

describe("TrendingTopicsList", () => {
  it("renders topic rows when data is provided", () => {
    render(<TrendingTopicsList topics={mockTopics} isLoading={false} />);
    expect(screen.getByText("AI-Powered Phishing Detection")).toBeInTheDocument();
    expect(screen.getByText("Trending Topics")).toBeInTheDocument();
    expect(screen.getByText("View All")).toBeInTheDocument();
  });

  it("renders skeleton loading state", () => {
    const { container } = render(<TrendingTopicsList topics={[]} isLoading={true} />);
    const skeletons = container.querySelectorAll("[data-slot='skeleton']");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("renders error state with retry button", async () => {
    const onRetry = vi.fn();
    render(<TrendingTopicsList topics={[]} isLoading={false} isError={true} onRetry={onRetry} />);
    expect(screen.getByText("Unable to load trending topics")).toBeInTheDocument();
    await userEvent.click(screen.getByText("Retry"));
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it("renders empty state when no topics", () => {
    render(<TrendingTopicsList topics={[]} isLoading={false} />);
    expect(screen.getByText(/No trending topics found/)).toBeInTheDocument();
  });
});
