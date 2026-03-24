import type { ReactNode } from "react";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";
import { SessionStatusBadge } from "./session-status-badge";
import type { ResearchSessionSummary, SessionStatus } from "@/types/research";

const BORDER_COLORS: Record<string, string> = {
  planning: "border-l-blue-500",
  in_progress: "border-l-amber-500",
  complete: "border-l-blue-500",
  generating_article: "border-l-purple-500",
  article_complete: "border-l-green-500",
  article_failed: "border-l-red-500",
  failed: "border-l-red-500",
};

const PROGRESS_COLORS: Record<string, string> = {
  planning: "bg-blue-500",
  in_progress: "bg-amber-500",
  complete: "bg-blue-500",
  generating_article: "bg-purple-500",
  article_complete: "bg-green-500",
  article_failed: "bg-red-500",
  failed: "bg-red-500",
};

function getProgressPercent(session: ResearchSessionSummary): number {
  switch (session.status) {
    case "article_complete":
      return 100;
    case "generating_article":
      return 70;
    case "complete":
      return 50;
    case "planning":
      return 15;
    case "in_progress":
      return 35;
    case "failed":
    case "article_failed":
      return Math.min(Math.round((session.round_count / 3) * 100), 90);
    default:
      return 50;
  }
}

function formatDuration(seconds: number | null | undefined): string {
  if (seconds == null) return "";
  const mins = Math.floor(seconds / 60);
  const secs = Math.round(seconds % 60);
  if (mins === 0) return `${secs}s`;
  return `${mins}m ${secs}s`;
}

interface SessionCardProps {
  session: ResearchSessionSummary;
  isExpanded: boolean;
  onToggle: () => void;
  children?: ReactNode;
}

export function SessionCard({ session, isExpanded, onToggle, children }: SessionCardProps) {
  const progress = getProgressPercent(session);

  return (
    <div
      className={cn(
        "rounded-lg border border-neutral-200 border-l-4 bg-white shadow-sm transition-shadow hover:shadow-md",
        BORDER_COLORS[session.status] ?? "border-l-neutral-300",
      )}
    >
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-start justify-between p-4 text-left"
      >
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-3">
            <h3 className="truncate font-heading text-sm font-semibold text-neutral-900">
              {session.topic_title ?? session.session_id}
            </h3>
            <SessionStatusBadge status={session.status} />
          </div>
          <p className="mt-1 text-xs text-neutral-500">
            {session.round_count} rounds · {session.findings_count} findings
            {session.duration_seconds ? ` · ${formatDuration(session.duration_seconds)}` : ""}
          </p>
          <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-neutral-100">
            <div
              data-testid="progress-bar"
              className={cn("h-full rounded-full transition-all", PROGRESS_COLORS[session.status] ?? "bg-neutral-400")}
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
        <ChevronDown
          className={cn(
            "ml-3 h-4 w-4 shrink-0 text-neutral-400 transition-transform",
            isExpanded && "rotate-180",
          )}
        />
      </button>
      {isExpanded && <div className="border-t border-neutral-100 px-4 pb-4">{children}</div>}
    </div>
  );
}
