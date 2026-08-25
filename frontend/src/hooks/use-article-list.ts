import { useQuery } from "@tanstack/react-query";
import { fetchArticles } from "@/lib/api/articles";
import type { ArticleListItem, ArticleStatus } from "@/types/articles";
import type { ArticleResponse } from "@/lib/api/articles";

function toListItem(a: ArticleResponse): ArticleListItem {
  return {
    id: a.id,
    title: a.title,
    summary: a.summary,
    status: (a.status as ArticleStatus) ?? "draft",
    domain: a.domain,
    wordCount: a.body_markdown.split(/\s+/).length,
    generatedAt: a.generated_at,
  };
}

export function useArticleList(status?: ArticleStatus) {
  const query = useQuery({
    queryKey: ["article-list", status ?? "all"],
    queryFn: async () => {
      try {
        const result = await fetchArticles(1, 20, status);
        return { articles: result.items.map(toListItem), total: result.total };
      } catch {
        return { articles: [] as ArticleListItem[], total: 0 };
      }
    },
    staleTime: 60 * 1000,
  });
  return {
    articles: query.data?.articles ?? [],
    total: query.data?.total ?? 0,
  };
}
