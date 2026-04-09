"use client";

import type { PipelineDebugResponse } from "@/types/pipeline-debug";
import { SessionStatusBadge } from "@/components/research/session-status-badge";

interface PipelineSummaryProps {
  data: PipelineDebugResponse;
}

function formatDuration(seconds: number | null): string {
  if (seconds === null) return "—";
  if (seconds < 60) return `${Math.round(seconds)}s`;
  return `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`;
}

export function PipelineSummary({ data }: PipelineSummaryProps) {
  return (
    <div className="rounded-lg border border-neutral-200 bg-white p-6 shadow-sm">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="font-heading text-xl font-semibold text-neutral-900">
            {data.topic_title}
          </h2>
          <p className="mt-1 text-sm text-neutral-500">
            {data.topic_domain}
            {data.target_audience && ` · ${data.target_audience}`}
            {data.content_tone && ` · ${data.content_tone}`}
          </p>
        </div>
        <SessionStatusBadge status={data.status} />
      </div>
      <div className="mt-4 grid grid-cols-4 gap-4">
        <Metric label="Duration" value={formatDuration(data.duration_seconds)} />
        <Metric label="Steps" value={String(data.steps.length)} />
        <Metric label="LLM Calls" value={String(data.total_llm_calls)} />
        <Metric
          label="Tokens"
          value={`${data.total_input_tokens.toLocaleString()} in / ${data.total_output_tokens.toLocaleString()} out`}
        />
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs font-medium text-neutral-500">{label}</p>
      <p className="mt-0.5 font-heading text-sm font-semibold text-neutral-900">
        {value}
      </p>
    </div>
  );
}
