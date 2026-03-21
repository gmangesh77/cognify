import Link from "next/link";
import { DomainBadge } from "@/components/common/domain-badge";
import { StatusBadge } from "@/components/common/status-badge";
import type { ArticleListItem } from "@/types/articles";

interface ArticleCardProps {
  article: ArticleListItem;
}

function formatTimeAgo(dateStr: string): string {
  const hours = Math.floor((Date.now() - new Date(dateStr).getTime()) / 3600000);
  if (hours < 1) return "Just now";
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

export function ArticleCard({ article }: ArticleCardProps) {
  return (
    <div className="flex flex-col justify-between rounded-lg border border-neutral-200 bg-white p-5 shadow-sm transition-shadow hover:shadow-md">
      <div>
        <div className="flex items-center gap-2">
          <DomainBadge domain={article.domain} />
          <StatusBadge status={article.status} />
        </div>
        <h3 className="mt-3 font-heading text-base font-semibold text-neutral-900 line-clamp-2">
          {article.title}
        </h3>
        <p className="mt-1.5 line-clamp-2 text-sm text-neutral-500">{article.summary}</p>
      </div>
      <div className="mt-4 flex items-center justify-between text-xs text-neutral-400">
        <span>{article.wordCount.toLocaleString()} words &middot; {formatTimeAgo(article.generatedAt)}</span>
        <Link href={`/articles/${article.id}`} className="font-medium text-primary hover:underline">
          View →
        </Link>
      </div>
    </div>
  );
}
