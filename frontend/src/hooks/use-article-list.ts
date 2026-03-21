import { articleListItems } from "@/lib/mock/article-details";
import type { ArticleListItem } from "@/types/articles";

interface UseArticleListReturn {
  articles: ArticleListItem[];
}

export function useArticleList(): UseArticleListReturn {
  return { articles: articleListItems };
}
