import { mockArticleDetails } from "@/lib/mock/article-details";
import type { ArticleDetail } from "@/types/articles";

interface UseArticleReturn {
  article: ArticleDetail | null;
}

export function useArticle(id: string): UseArticleReturn {
  const article = mockArticleDetails.find((a) => a.id === id) ?? null;
  return { article };
}
