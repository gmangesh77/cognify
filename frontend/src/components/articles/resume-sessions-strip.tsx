"use client";

import Link from "next/link";
import { SessionStatusBadge } from "@/components/research/session-status-badge";
import { useResumableSessions } from "@/hooks/use-resumable-sessions";

/** In-flight / failed research sessions with no article yet (AUTHOR-007).
 * Renders nothing when there is nothing to resume. */
export function ResumeSessionsStrip() {
  const { sessions } = useResumableSessions();
  if (sessions.length === 0) return null;
  return (
    <div className="rounded-lg border border-warning/30 bg-warning-light/40 p-4">
      <h3 className="text-xs font-medium uppercase tracking-wide text-neutral-500">
        Sessions needing attention
      </h3>
      <ul className="mt-2 space-y-2">
        {sessions.map((s) => (
          <li key={s.session_id} className="flex items-center justify-between gap-3">
            <span className="flex min-w-0 items-center gap-2">
              <span className="truncate text-sm text-neutral-800">
                {s.topic_title || "Untitled session"}
              </span>
              <SessionStatusBadge status={s.status} />
            </span>
            <Link
              href={`/research/${s.session_id}`}
              className="shrink-0 text-sm font-medium text-primary hover:underline"
            >
              Resume →
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
