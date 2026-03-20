import { describe, it, expect } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useTopicPagination } from "./use-topic-pagination";

const items = Array.from({ length: 25 }, (_, i) => ({ id: i }));

describe("useTopicPagination", () => {
  it("returns first page of 10 items", () => {
    const { result } = renderHook(() => useTopicPagination(items));
    expect(result.current.paginatedItems).toHaveLength(10);
    expect(result.current.page).toBe(1);
    expect(result.current.totalPages).toBe(3);
  });

  it("navigates to page 2", () => {
    const { result } = renderHook(() => useTopicPagination(items));
    act(() => result.current.setPage(2));
    expect(result.current.page).toBe(2);
    expect(result.current.paginatedItems).toHaveLength(10);
    expect(result.current.paginatedItems[0]).toEqual({ id: 10 });
  });

  it("last page has partial items", () => {
    const { result } = renderHook(() => useTopicPagination(items));
    act(() => result.current.setPage(3));
    expect(result.current.paginatedItems).toHaveLength(5);
  });

  it("clamps to valid page range", () => {
    const { result } = renderHook(() => useTopicPagination(items));
    act(() => result.current.setPage(99));
    expect(result.current.page).toBe(3);
    act(() => result.current.setPage(0));
    expect(result.current.page).toBe(1);
  });

  it("resets to page 1 when items change", () => {
    const { result, rerender } = renderHook(
      ({ items }) => useTopicPagination(items),
      { initialProps: { items } },
    );
    act(() => result.current.setPage(3));
    rerender({ items: items.slice(0, 5) });
    expect(result.current.page).toBe(1);
    expect(result.current.totalPages).toBe(1);
  });

  it("handles empty items", () => {
    const { result } = renderHook(() => useTopicPagination([]));
    expect(result.current.paginatedItems).toHaveLength(0);
    expect(result.current.totalPages).toBe(0);
    expect(result.current.page).toBe(1);
  });
});
