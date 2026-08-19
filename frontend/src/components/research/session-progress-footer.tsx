"use client";

import Link from "next/link";
import { ViewArticleButton } from "./view-article-button";
import type { SessionSectionsProgress } from "@/hooks/session-events-reducer";
import type { SessionStepRow } from "@/types/research";

interface SessionProgressFooterProps {
  sessionId: string;
  status: string | null;
  steps: SessionStepRow[];
  sections: SessionSectionsProgress | null;
}

function findFailedStepError(steps: SessionStepRow[]): string | null {
  const failed = [...steps].reverse().find((s) => s.status === "failed");
  const error = failed?.output_data?.error;
  return typeof error === "string" ? error : null;
}

function SectionsBar({ sections }: { sections: SessionSectionsProgress }) {
  const pct = sections.total > 0 ? Math.round((sections.done / sections.total) * 100) : 0;
  return (
    <div className="space-y-1.5">
      <div className="h-2 w-full overflow-hidden rounded-full bg-neutral-100">
        <div className="h-full rounded-full bg-primary" style={{ width: `${pct}%` }} />
      </div>
      <p className="text-xs text-neutral-500">
        Drafting {sections.done} / {sections.total}
        {sections.current ? ` — ${sections.current}` : ""}
      </p>
    </div>
  );
}

function ErrorPanel({ error }: { error: string | null }) {
  return (
    <div className="space-y-3 rounded-md border border-error/40 bg-error-light p-4">
      <p className="text-sm text-error">{error ?? "Article generation failed."}</p>
      <Link href="/research" className="text-sm font-medium text-primary hover:underline">
        Back to research
      </Link>
    </div>
  );
}

export function SessionProgressFooter({
  sessionId,
  status,
  steps,
  sections,
}: SessionProgressFooterProps) {
  const isFailed = status === "article_failed" || status === "failed";
  return (
    <div className="space-y-4">
      {sections && <SectionsBar sections={sections} />}
      {status === "article_complete" && <ViewArticleButton sessionId={sessionId} />}
      {isFailed && <ErrorPanel error={findFailedStepError(steps)} />}
    </div>
  );
}
