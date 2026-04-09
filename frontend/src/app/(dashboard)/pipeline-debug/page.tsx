"use client";

import { useState } from "react";
import { Header } from "@/components/layout/header";
import { Skeleton } from "@/components/ui/skeleton";
import { PipelineSummary } from "@/components/pipeline-debug/pipeline-summary";
import { StepTimeline } from "@/components/pipeline-debug/step-timeline";
import { useDebugSessions, usePipelineDebug } from "@/hooks/use-pipeline-debug";

const PAGE_SIZE = 20;

export default function PipelineDebugPage() {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [page, setPage] = useState(1);

  const sessionsQuery = useDebugSessions(page, PAGE_SIZE);
  const debugQuery = usePipelineDebug(selectedId);

  const sessions = sessionsQuery.data?.items ?? [];
  const total = sessionsQuery.data?.total ?? 0;
  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <div className="space-y-6">
      <Header
        title="Pipeline Debug"
        subtitle="Inspect inputs, outputs, and LLM prompts at every pipeline stage"
      />

      {/* Session selector */}
      <div className="rounded-lg border border-neutral-200 bg-white p-4 shadow-sm">
        <label className="mb-2 block text-xs font-medium text-neutral-500">
          Select Session
        </label>
        <select
          className="w-full rounded-md border border-neutral-200 bg-neutral-50 px-3 py-2 text-sm text-neutral-900 focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
          value={selectedId ?? ""}
          onChange={(e) => setSelectedId(e.target.value || null)}
        >
          <option value="">— Choose a session —</option>
          {sessions.map((s) => (
            <option key={s.session_id} value={s.session_id}>
              {s.topic_title} — {s.status}
              {s.duration_seconds != null && ` (${Math.round(s.duration_seconds)}s)`}
              {s.llm_call_count > 0 && ` · ${s.llm_call_count} LLM calls`}
            </option>
          ))}
        </select>
        {totalPages > 1 && (
          <div className="mt-2 flex items-center gap-2 text-xs text-neutral-500">
            <button
              className="hover:text-primary disabled:text-neutral-300"
              disabled={page <= 1}
              onClick={() => setPage((p) => p - 1)}
            >
              ← Prev
            </button>
            <span>
              Page {page} of {totalPages}
            </span>
            <button
              className="hover:text-primary disabled:text-neutral-300"
              disabled={page >= totalPages}
              onClick={() => setPage((p) => p + 1)}
            >
              Next →
            </button>
          </div>
        )}
      </div>

      {/* Loading state */}
      {selectedId && debugQuery.isLoading && (
        <div className="space-y-4">
          <Skeleton className="h-32 w-full rounded-lg" />
          <Skeleton className="h-20 w-full rounded-lg" />
          <Skeleton className="h-20 w-full rounded-lg" />
        </div>
      )}

      {/* Pipeline debug view */}
      {debugQuery.data && (
        <div className="space-y-6">
          <PipelineSummary data={debugQuery.data} />

          <div>
            <h3 className="mb-3 font-heading text-lg font-semibold text-neutral-900">
              Pipeline Steps ({debugQuery.data.steps.length})
            </h3>
            <StepTimeline steps={debugQuery.data.steps} />
          </div>
        </div>
      )}

      {/* Empty state */}
      {!selectedId && (
        <div className="flex h-48 items-center justify-center rounded-lg border border-dashed border-neutral-300 bg-neutral-50">
          <p className="text-sm text-neutral-500">
            Select a session above to inspect its pipeline execution
          </p>
        </div>
      )}
    </div>
  );
}
