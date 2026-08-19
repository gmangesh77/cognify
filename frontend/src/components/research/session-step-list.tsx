import { CheckCircle2, Circle, Loader2, XCircle } from "lucide-react";
import type { SessionStepRow } from "@/types/research";
import { getStepLabel } from "./session-steps";

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function StepIcon({ status }: { status: string }) {
  switch (status) {
    case "complete":
      return <CheckCircle2 className="h-4 w-4 text-success" />;
    case "running":
      return <Loader2 className="h-4 w-4 animate-spin text-info" />;
    case "failed":
      return <XCircle className="h-4 w-4 text-error" />;
    default:
      return <Circle className="h-4 w-4 text-neutral-300" />;
  }
}

interface SessionStepListProps {
  steps: SessionStepRow[];
}

export function SessionStepList({ steps }: SessionStepListProps) {
  return (
    <ol role="list" className="space-y-1.5 border-l-2 border-neutral-200 pl-4">
      {steps.map((step) => (
        <li
          key={step.id}
          role="listitem"
          data-status={step.status}
          className="flex items-center gap-2 text-sm"
        >
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
        </li>
      ))}
    </ol>
  );
}
