import { Button } from "@/components/ui/button";
import { DomainBadge } from "@/components/common/domain-badge";
import { WorkflowSteps } from "./workflow-steps";
import type { ArticleDetail } from "@/types/articles";

interface ArticleSidebarProps {
  article: ArticleDetail;
  onPublish: () => void;
}

function formatTimeAgo(dateStr: string): string {
  const hours = Math.floor((Date.now() - new Date(dateStr).getTime()) / 3600000);
  if (hours < 1) return "Just now";
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

export function ArticleSidebar({ article, onPublish }: ArticleSidebarProps) {
  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-primary/20 bg-primary/5 p-4">
        <Button className="w-full" onClick={onPublish}>Publish Article</Button>
      </div>

      <div className="rounded-lg border border-neutral-200 p-4">
        <h4 className="text-xs font-medium uppercase text-neutral-400">Metadata</h4>
        <div className="mt-2 space-y-1.5 text-sm text-neutral-700">
          <div className="flex items-center gap-2">
            <span className="text-neutral-500">Domain:</span>
            <DomainBadge domain={article.domain} />
          </div>
          <div><span className="text-neutral-500">Type:</span> {article.contentType}</div>
          <div><span className="text-neutral-500">Words:</span> {article.wordCount.toLocaleString()}</div>
          <div><span className="text-neutral-500">Author:</span> {article.authors.join(", ")}</div>
          <div><span className="text-neutral-500">Generated:</span> {formatTimeAgo(article.generatedAt)}</div>
        </div>
      </div>

      <div className="rounded-lg border border-neutral-200 p-4">
        <h4 className="text-xs font-medium uppercase text-neutral-400">Agent Workflow</h4>
        <div className="mt-2">
          <WorkflowSteps steps={article.workflow} />
        </div>
      </div>

      {article.keyClaims.length > 0 && (
        <div className="rounded-lg border border-neutral-200 p-4">
          <h4 className="text-xs font-medium uppercase text-neutral-400">Key Claims</h4>
          <ul className="mt-2 space-y-1">
            {article.keyClaims.map((claim, i) => (
              <li key={i} className="text-sm text-neutral-700">
                <span className="text-neutral-400">&bull;</span> {claim}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
