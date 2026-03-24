import { cn } from "@/lib/utils";
import type { SessionStatus } from "@/types/research";

const STATUS_CONFIG: Record<string, { label: string; dotClass: string }> = {
  planning: { label: "Planning", dotClass: "bg-blue-500" },
  in_progress: { label: "In Progress", dotClass: "bg-amber-500" },
  researching: { label: "Researching", dotClass: "bg-amber-500" },
  evaluating: { label: "Evaluating", dotClass: "bg-amber-500" },
  running: { label: "Running", dotClass: "bg-amber-500" },
  complete: { label: "Research Complete", dotClass: "bg-blue-500" },
  completed: { label: "Research Complete", dotClass: "bg-blue-500" },
  generating_article: { label: "Generating Article", dotClass: "bg-purple-500 animate-pulse" },
  article_complete: { label: "Article Ready", dotClass: "bg-green-500" },
  article_failed: { label: "Article Failed", dotClass: "bg-red-500" },
  failed: { label: "Failed", dotClass: "bg-red-500" },
};

const DEFAULT_STATUS = { label: "Unknown", dotClass: "bg-neutral-400" };

interface SessionStatusBadgeProps {
  status: string;
}

export function SessionStatusBadge({ status }: SessionStatusBadgeProps) {
  const { label, dotClass } = STATUS_CONFIG[status] ?? DEFAULT_STATUS;
  return (
    <span className="inline-flex items-center gap-1.5 text-xs font-medium text-neutral-600">
      <span data-testid="status-dot" className={cn("h-2 w-2 rounded-full", dotClass)} />
      {label}
    </span>
  );
}
