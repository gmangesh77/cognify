"use client";

import { useEffect, useState } from "react";
import { useSessionEvents } from "@/hooks/use-session-events";
import type { SessionConnectionState } from "@/hooks/session-events-reducer";
import { useResearchSession } from "@/hooks/use-research-sessions";
import { isTerminalSessionStatus } from "@/lib/research/session-status";
import { SessionStatusBadge } from "./session-status-badge";
import { SessionStepList } from "./session-step-list";
import { SessionProgressFooter } from "./session-progress-footer";

function formatElapsed(startedAt: string | undefined, nowMs: number): string | null {
  if (!startedAt) return null;
  const startMs = new Date(startedAt).getTime();
  if (Number.isNaN(startMs)) return null;
  const totalSeconds = Math.max(0, Math.floor((nowMs - startMs) / 1000));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `Elapsed: ${minutes}m ${seconds}s`;
}

interface ConnectionChipProps {
  connection: SessionConnectionState;
  onRetry: () => void;
}

function ConnectionChip({ connection, onRetry }: ConnectionChipProps) {
  if (connection === "closed") return null;
  if (connection === "live") {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-success-light px-2.5 py-0.5 text-xs font-medium text-success">
        <span className="h-2 w-2 rounded-full bg-success" />
        Live
      </span>
    );
  }
  if (connection === "reconnecting") {
    return (
      <span className="inline-flex items-center rounded-full bg-warning-light px-2.5 py-0.5 text-xs font-medium text-warning">
        Reconnecting…
      </span>
    );
  }
  if (connection === "error") {
    return (
      <span className="inline-flex items-center gap-2 rounded-full bg-error-light px-2.5 py-0.5 text-xs font-medium text-error">
        Offline — showing last known state
        <button type="button" onClick={onRetry} className="font-semibold underline">
          Retry
        </button>
      </span>
    );
  }
  return (
    <span className="inline-flex items-center rounded-full bg-neutral-100 px-2.5 py-0.5 text-xs font-medium text-neutral-600">
      Connecting…
    </span>
  );
}

interface SessionProgressProps {
  sessionId: string;
}

export function SessionProgress({ sessionId }: SessionProgressProps) {
  const events = useSessionEvents(sessionId);
  const sessionQuery = useResearchSession(sessionId);
  const status = events.status ?? sessionQuery.data?.status ?? null;

  const [nowMs, setNowMs] = useState(() => Date.now());

  useEffect(() => {
    if (isTerminalSessionStatus(status)) return undefined;
    const timer = setInterval(() => setNowMs(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [status]);

  const elapsed = formatElapsed(sessionQuery.data?.started_at, nowMs);

  return (
    <section className="space-y-5 rounded-lg border border-neutral-200 bg-white p-6 shadow-sm">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="font-heading text-lg font-semibold text-neutral-900">
            {sessionQuery.data?.topic_title ?? "Research session"}
          </h2>
          <div className="mt-1 flex items-center gap-3">
            <SessionStatusBadge status={status ?? ""} />
            {elapsed && <span className="text-xs text-neutral-500">{elapsed}</span>}
          </div>
        </div>
        <ConnectionChip connection={events.connection} onRetry={events.reconnect} />
      </header>
      <SessionStepList steps={events.steps} />
      <SessionProgressFooter
        sessionId={sessionId}
        status={status}
        steps={events.steps}
        sections={events.sections}
      />
    </section>
  );
}
