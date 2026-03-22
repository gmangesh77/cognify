import { useQuery } from "@tanstack/react-query";
import { fetchArticles } from "@/lib/api/articles";
import type { ArticleListItem } from "@/types/articles";
import type { ArticleResponse } from "@/lib/api/articles";

function toListItem(a: ArticleResponse): ArticleListItem {
  return {
    id: a.id,
    title: a.title,
    summary: a.summary,
    status: "complete",
    domain: a.domain,
    wordCount: a.body_markdown.split(/\s+/).length,
    generatedAt: a.generated_at,
  };
}

export function useArticleList() {
  const query = useQuery({
    queryKey: ["article-list"],
    queryFn: async () => {
      try {
        const result = await fetchArticles(1, 20);
        return { articles: result.items.map(toListItem) };
      } catch {
        return { articles: [] as ArticleListItem[] };
      }
    },
    staleTime: 60 * 1000,
  });
  return { articles: query.data?.articles ?? [] };
}
