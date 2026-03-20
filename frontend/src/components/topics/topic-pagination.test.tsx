import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { TopicPagination } from "./topic-pagination";

describe("TopicPagination", () => {
  it("renders page info", () => {
    render(<TopicPagination currentPage={1} totalPages={5} onPageChange={vi.fn()} />);
    expect(screen.getByText("Page 1 of 5")).toBeInTheDocument();
  });
  it("disables Previous on first page", () => {
    render(<TopicPagination currentPage={1} totalPages={5} onPageChange={vi.fn()} />);
    expect(screen.getByText("Previous")).toBeDisabled();
  });
  it("disables Next on last page", () => {
    render(<TopicPagination currentPage={5} totalPages={5} onPageChange={vi.fn()} />);
    expect(screen.getByText("Next")).toBeDisabled();
  });
  it("calls onPageChange with next page", () => {
    const handler = vi.fn();
    render(<TopicPagination currentPage={2} totalPages={5} onPageChange={handler} />);
    fireEvent.click(screen.getByText("Next"));
    expect(handler).toHaveBeenCalledWith(3);
  });
  it("calls onPageChange with previous page", () => {
    const handler = vi.fn();
    render(<TopicPagination currentPage={3} totalPages={5} onPageChange={handler} />);
    fireEvent.click(screen.getByText("Previous"));
    expect(handler).toHaveBeenCalledWith(2);
  });
  it("renders nothing when totalPages is 0", () => {
    const { container } = render(
      <TopicPagination currentPage={1} totalPages={0} onPageChange={vi.fn()} />,
    );
    expect(container.firstChild).toBeNull();
  });
});
