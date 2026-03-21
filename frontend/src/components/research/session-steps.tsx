import { CheckCircle2, Circle, Loader2, XCircle } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import type { AgentStep } from "@/types/research";

const STEP_LABELS: Record<string, string> = {
  plan_research: "Plan Research",
  index_findings: "Index Findings",
  evaluate_completeness: "Evaluate Completeness",
  finalize: "Finalize",
};

function getStepLabel(stepName: string): string {
  if (STEP_LABELS[stepName]) return STEP_LABELS[stepName];
  if (stepName.startsWith("research_facet_")) {
    const rest = stepName.replace("research_facet_", "");
    if (rest.includes("_round_")) {
      const [idx, round] = rest.split("_round_");
      return `Research Facet ${idx} (Round ${round})`;
    }
    return `Research Facet ${rest}`;
  }
  return stepName;
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function StepIcon({ status }: { status: string }) {
  switch (status) {
    case "complete":
      return <CheckCircle2 className="h-4 w-4 text-green-500" />;
    case "running":
      return <Loader2 className="h-4 w-4 animate-spin text-blue-500" />;
    case "failed":
      return <XCircle className="h-4 w-4 text-red-500" />;
    default:
      return <Circle className="h-4 w-4 text-neutral-300" />;
  }
}

interface SessionStepsProps {
  steps: AgentStep[];
  isLoading: boolean;
}

export function SessionSteps({ steps, isLoading }: SessionStepsProps) {
  if (isLoading) {
    return (
      <div className="mt-3 space-y-2 border-l-2 border-neutral-200 pl-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} data-testid="step-skeleton" className="h-5 w-48" />
        ))}
      </div>
    );
  }

  return (
    <div className="mt-3 space-y-1.5 border-l-2 border-neutral-200 pl-4">
      {steps.map((step) => (
        <div key={step.step_name}>
          <div className="flex items-center gap-2 text-sm">
            <StepIcon status={step.status} />
            <span className={step.status === "pending" ? "text-neutral-400" : "text-neutral-700"}>
              {getStepLabel(step.step_name)}
            </span>
            <span className="ml-auto text-xs text-neutral-400">
              {step.status === "complete" && step.duration_ms !== null
                ? formatDuration(step.duration_ms)
                : step.status === "running"
                  ? "..."
                  : ""}
            </span>
          </div>
          {step.output_summary && (
            <p className="ml-6 text-xs text-neutral-400">{step.output_summary}</p>
          )}
        </div>
      ))}
    </div>
  );
}
