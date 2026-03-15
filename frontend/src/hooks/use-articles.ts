import { useQuery } from "@tanstack/react-query";
import type { Article } from "@/types/api";
import { mockArticles } from "@/lib/mock/articles";

async function fetchArticles(): Promise<Article[]> {
  // TODO: Replace with real API call when endpoint exists
  return mockArticles;
}

export function useArticles() {
  return useQuery({
    queryKey: ["articles"],
    queryFn: fetchArticles,
    staleTime: 15 * 60 * 1000,
  });
}
