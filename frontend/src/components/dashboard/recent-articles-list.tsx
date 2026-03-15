import Link from "next/link";
import { Skeleton } from "@/components/ui/skeleton";
import { ArticleRow } from "./article-row";
import type { Article } from "@/types/api";

interface RecentArticlesListProps {
  articles: Article[];
  isLoading: boolean;
  isError?: boolean;
  onRetry?: () => void;
}

export function RecentArticlesList({ articles, isLoading, isError, onRetry }: RecentArticlesListProps) {
  return (
    <div className="rounded-md border border-border bg-white shadow-md">
      <div className="flex items-center justify-between border-b border-border px-5 py-4">
        <h2 className="font-heading text-base font-semibold text-neutral-900">Recent Articles</h2>
        <Link href="/articles" className="text-sm font-medium text-primary hover:text-primary/80">
          View All
        </Link>
      </div>
      {isLoading && (
        <div className="space-y-0">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="border-b border-border px-5 py-4 last:border-b-0">
              <Skeleton className="h-4 w-3/4" />
              <Skeleton className="mt-2 h-3 w-1/3" />
            </div>
          ))}
        </div>
      )}
      {isError && (
        <div className="px-5 py-10 text-center">
          <p className="text-sm text-neutral-500">Unable to load recent articles</p>
          {onRetry && (
            <button onClick={onRetry} className="mt-2 text-sm font-medium text-primary hover:text-primary/80">
              Retry
            </button>
          )}
        </div>
      )}
      {!isLoading && !isError && articles.length === 0 && (
        <div className="px-5 py-10 text-center">
          <p className="text-sm text-neutral-500">No articles yet. Generate your first article from a trending topic.</p>
        </div>
      )}
      {!isLoading && !isError && articles.length > 0 && (
        <div>
          {articles.map((article) => (
            <ArticleRow key={article.id} article={article} />
          ))}
        </div>
      )}
    </div>
  );
}
