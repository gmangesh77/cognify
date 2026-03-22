import { useQuery } from "@tanstack/react-query";
import type { Article } from "@/types/api";
import { fetchArticles as fetchArticlesApi } from "@/lib/api/articles";

export function useArticles() {
  return useQuery({
    queryKey: ["articles"],
    queryFn: async (): Promise<Article[]> => {
      try {
        const result = await fetchArticlesApi(1, 10);
        return result.items.map((a) => ({
          id: a.id,
          title: a.title,
          status: "complete" as const,
          published_at: a.generated_at,
          views: 0,
          domain: a.domain,
        }));
      } catch {
        return [];
      }
    },
    staleTime: 60 * 1000,
  });
}
