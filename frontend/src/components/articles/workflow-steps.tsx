import { Check } from "lucide-react";
import type { WorkflowStep } from "@/types/articles";

interface WorkflowStepsProps {
  steps: WorkflowStep[];
}

export function WorkflowSteps({ steps }: WorkflowStepsProps) {
  return (
    <div className="space-y-2">
      {steps.map((step) => (
        <div key={step.name} className="flex items-center gap-2 text-sm">
          <Check data-testid="step-check" className="h-4 w-4 text-success" />
          <span className="text-neutral-700">{step.name}</span>
          <span className="text-neutral-400">({step.durationSeconds}s)</span>
        </div>
      ))}
    </div>
  );
}
