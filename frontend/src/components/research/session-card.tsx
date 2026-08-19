import type { ReactNode } from "react";
import Link from "next/link";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";
import { isTerminalSessionStatus } from "@/lib/research/session-status";
import { SessionStatusBadge } from "./session-status-badge";
import { ViewArticleButton } from "./view-article-button";
import type { ResearchSessionSummary } from "@/types/research";

const BORDER_COLORS: Record<string, string> = {
  planning: "border-l-blue-500",
  in_progress: "border-l-amber-500",
  researching: "border-l-amber-500",
  evaluating: "border-l-amber-500",
  running: "border-l-amber-500",
  complete: "border-l-blue-500",
  completed: "border-l-blue-500",
  awaiting_outline_review: "border-l-info",
  generating_article: "border-l-purple-500",
  article_complete: "border-l-green-500",
  article_failed: "border-l-red-500",
  failed: "border-l-red-500",
  cancelled: "border-l-neutral-300",
};

const ACTIVE_BAR_COLORS: Record<string, string> = {
  planning: "bg-blue-500",
  in_progress: "bg-amber-500",
  researching: "bg-amber-500",
  evaluating: "bg-amber-500",
  running: "bg-amber-500",
  complete: "bg-blue-500",
  awaiting_outline_review: "bg-info",
  generating_article: "bg-purple-500",
};

const ERROR_TERMINAL_STATUSES = new Set(["article_failed", "failed"]);

function progressBarColor(status: string, isError: boolean): string {
  if (status === "cancelled") return "bg-neutral-300";
  return isError ? "bg-error" : "bg-success";
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
  const isTerminal = isTerminalSessionStatus(session.status);
  const isError = ERROR_TERMINAL_STATUSES.has(session.status);

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
            {isTerminal ? (
              <div
                data-testid="progress-bar"
                className={cn(
                  "h-full w-full rounded-full transition-all",
                  progressBarColor(session.status, isError),
                )}
              />
            ) : (
              <div
                data-testid="progress-bar"
                aria-busy="true"
                className={cn(
                  "h-full w-1/3 animate-pulse rounded-full transition-all",
                  ACTIVE_BAR_COLORS[session.status] ?? "bg-neutral-400",
                )}
              />
            )}
          </div>
        </div>
        <ChevronDown
          className={cn(
            "ml-3 h-4 w-4 shrink-0 text-neutral-400 transition-transform",
            isExpanded && "rotate-180",
          )}
        />
      </button>
      {!isTerminal && (
        <div className="flex justify-end px-4 pb-3">
          <Link
            href={`/research/${session.session_id}`}
            className="text-xs font-medium text-primary hover:underline"
          >
            {session.status === "awaiting_outline_review"
              ? "Review outline →"
              : "View progress →"}
          </Link>
        </div>
      )}
      {session.status === "article_complete" && (
        <div className="flex justify-end px-4 pb-3">
          <ViewArticleButton sessionId={session.session_id} />
        </div>
      )}
      {isExpanded && <div className="border-t border-neutral-100 px-4 pb-4">{children}</div>}
    </div>
  );
}
