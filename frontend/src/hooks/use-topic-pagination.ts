import { useState, useMemo, useEffect, useRef } from "react";

const PAGE_SIZE = 10;

export function useTopicPagination<T>(items: T[]) {
  const [page, setPageRaw] = useState(1);
  const totalPages = Math.ceil(items.length / PAGE_SIZE);
  const prevItemsRef = useRef(items);

  useEffect(() => {
    if (prevItemsRef.current !== items) {
      setPageRaw(1);
      prevItemsRef.current = items;
    }
  }, [items]);

  const setPage = (n: number) => {
    setPageRaw(Math.max(1, Math.min(n, totalPages || 1)));
  };

  const paginatedItems = useMemo(() => {
    const start = (page - 1) * PAGE_SIZE;
    return items.slice(start, start + PAGE_SIZE);
  }, [items, page]);

  return { paginatedItems, page, totalPages, setPage };
}
