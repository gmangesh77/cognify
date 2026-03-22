import { Eye } from "lucide-react";
import { StatusBadge } from "@/components/common/status-badge";
import type { Article } from "@/types/api";

interface ArticleRowProps {
  article: Article;
}

function formatDate(dateString: string): string {
  return new Date(dateString).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function formatViews(views: number): string {
  return views.toLocaleString("en-US");
}

export function ArticleRow({ article }: ArticleRowProps) {
  return (
    <div className="flex items-center justify-between border-b border-border px-5 py-4 last:border-b-0">
      <div className="min-w-0 flex-1">
        <p className="font-heading text-sm font-medium text-neutral-900">
          {article.title}
        </p>
        <div className="mt-1.5 flex items-center gap-2">
          <StatusBadge status={article.status} />
          <span className="text-[13px] text-neutral-400">{formatDate(article.published_at)}</span>
        </div>
      </div>
      <div className="ml-4 flex items-center gap-1 text-[13px] text-neutral-500">
        <Eye className="h-3.5 w-3.5" />
        <span>{formatViews(article.views)}</span>
      </div>
    </div>
  );
}
