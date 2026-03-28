import { useState, useMemo } from "react";

const PAGE_SIZE = 10;

export function useTopicPagination<T>(items: T[]) {
  const [page, setPageRaw] = useState(1);
  const totalPages = Math.ceil(items.length / PAGE_SIZE);

  const clampedPage = Math.min(page, totalPages || 1);

  const setPage = (n: number) => {
    setPageRaw(Math.max(1, Math.min(n, totalPages || 1)));
  };

  const paginatedItems = useMemo(() => {
    const start = (clampedPage - 1) * PAGE_SIZE;
    return items.slice(start, start + PAGE_SIZE);
  }, [items, clampedPage]);

  return { paginatedItems, page: clampedPage, totalPages, setPage };
}
