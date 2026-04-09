"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import {
  CheckCircle2,
  Circle,
  Loader2,
  XCircle,
  ChevronDown,
  ChevronRight,
  Cpu,
} from "lucide-react";
import type { DebugStepResponse } from "@/types/pipeline-debug";
import { LlmCallCard } from "./llm-call-card";

const STEP_LABELS: Record<string, string> = {
  plan_research: "Plan Research",
  dispatch_agents: "Dispatch Agents",
  index_findings: "Index Findings",
  evaluate_completeness: "Evaluate Completeness",
  finalize: "Finalize Research",
  content_outline: "Generate Outline",
  content_queries: "Generate Queries",
  content_draft: "Draft Sections",
  content_validate: "Validate Article",
  content_citations: "Manage Citations",
  content_humanize: "Humanize Content",
  content_seo: "SEO Optimize",
  content_charts: "Generate Charts",
  content_illustrations: "Generate Illustrations",
  content_diagrams: "Generate Diagrams",
};

function stepLabel(name: string): string {
  if (STEP_LABELS[name]) return STEP_LABELS[name];
  if (name.startsWith("research_facet_")) {
    const parts = name.replace("research_facet_", "").split("_round_");
    const idx = parts[0];
    const round = parts[1];
    return round ? `Research Facet ${idx} (Round ${round})` : `Research Facet ${idx}`;
  }
  return name.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function StatusIcon({ status }: { status: string }) {
  switch (status) {
    case "complete":
      return <CheckCircle2 className="h-4 w-4 text-green-500" />;
    case "running":
      return <Loader2 className="h-4 w-4 animate-spin text-amber-500" />;
    case "failed":
      return <XCircle className="h-4 w-4 text-red-500" />;
    default:
      return <Circle className="h-4 w-4 text-neutral-300" />;
  }
}

interface StepTimelineProps {
  steps: DebugStepResponse[];
}

export function StepTimeline({ steps }: StepTimelineProps) {
  return (
    <div className="space-y-2">
      {steps.map((step, i) => (
        <StepCard key={step.id} step={step} isLast={i === steps.length - 1} />
      ))}
    </div>
  );
}

function StepCard({ step, isLast }: { step: DebugStepResponse; isLast: boolean }) {
  const [expanded, setExpanded] = useState(false);
  const Icon = expanded ? ChevronDown : ChevronRight;
  const isContent = step.step_name.startsWith("content_");

  return (
    <div className={cn("relative", !isLast && "pb-2")}>
      <div
        className={cn(
          "rounded-lg border bg-white p-4 shadow-sm transition-shadow hover:shadow-md cursor-pointer",
          isContent ? "border-l-4 border-l-primary border-neutral-200" : "border-neutral-200",
        )}
        onClick={() => setExpanded((v) => !v)}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <StatusIcon status={step.status} />
            <span className="font-heading text-sm font-medium text-neutral-900">
              {stepLabel(step.step_name)}
            </span>
            {step.llm_calls.length > 0 && (
              <span className="inline-flex items-center gap-1 rounded-full bg-neutral-100 px-2 py-0.5 text-xs font-medium text-neutral-600">
                <Cpu className="h-3 w-3" />
                {step.llm_calls.length}
              </span>
            )}
          </div>
          <div className="flex items-center gap-3">
            {step.duration_ms != null && (
              <span className="text-xs text-neutral-500">
                {step.duration_ms < 1000
                  ? `${step.duration_ms}ms`
                  : `${(step.duration_ms / 1000).toFixed(1)}s`}
              </span>
            )}
            <Icon className="h-4 w-4 text-neutral-400" />
          </div>
        </div>

        <OutputSummary data={step.output_data} />
      </div>

      {expanded && (
        <div className="ml-4 mt-2 space-y-3 border-l-2 border-neutral-100 pl-4">
          {Object.keys(step.input_data).length > 0 && (
            <JsonBlock title="Input" data={step.input_data} />
          )}
          {Object.keys(step.output_data).length > 0 && (
            <JsonBlock title="Output" data={step.output_data} />
          )}
          {step.llm_calls.length > 0 && (
            <div>
              <p className="mb-2 text-xs font-medium uppercase text-neutral-400">
                LLM Calls ({step.llm_calls.length})
              </p>
              <div className="space-y-2">
                {step.llm_calls.map((call) => (
                  <LlmCallCard key={call.id} call={call} />
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function OutputSummary({ data }: { data: Record<string, unknown> }) {
  if (!data || Object.keys(data).length === 0) return null;
  const parts: string[] = [];
  if (data.facet_count) parts.push(`${data.facet_count} facets`);
  if (data.sources_found) parts.push(`${data.sources_found} sources`);
  if (data.claims_extracted) parts.push(`${data.claims_extracted} claims`);
  if (data.sections) parts.push(`${data.sections} sections`);
  if (data.sections_drafted) parts.push(`${data.sections_drafted} drafted`);
  if (data.word_count) parts.push(`${data.word_count} words`);
  if (data.citation_count) parts.push(`${data.citation_count} citations`);
  if (data.seo_generated) parts.push("SEO done");
  if (data.visuals_count) parts.push(`${data.visuals_count} visuals`);
  if (data.error) parts.push(`Error: ${String(data.error).slice(0, 60)}`);
  if (parts.length === 0) return null;
  return (
    <p className="mt-1.5 text-xs text-neutral-500">{parts.join(" · ")}</p>
  );
}

function JsonBlock({ title, data }: { title: string; data: Record<string, unknown> }) {
  return (
    <div>
      <p className="mb-1 text-xs font-medium uppercase text-neutral-400">{title}</p>
      <pre className="max-h-48 overflow-auto rounded border border-neutral-200 bg-neutral-50 p-2 text-xs text-neutral-700">
        {JSON.stringify(data, null, 2)}
      </pre>
    </div>
  );
}
