import { cn } from "@/lib/utils";
import type { PromptView } from "@/types/prompts";

interface PromptsTabProps {
  prompts: PromptView[];
  selectedKey: string | null;
  onSelect: (key: string) => void;
}

function groupByStep(prompts: PromptView[]): [string, PromptView[]][] {
  const groups = new Map<string, PromptView[]>();
  for (const p of prompts) groups.set(p.step, [...(groups.get(p.step) ?? []), p]);
  return [...groups.entries()];
}

export function PromptsTab({ prompts, selectedKey, onSelect }: PromptsTabProps) {
  return (
    <div className="space-y-5" data-testid="prompts-tab">
      {groupByStep(prompts).map(([step, items]) => (
        <section key={step}>
          <h3 className="text-xs font-medium uppercase tracking-wide text-neutral-500">{step}</h3>
          <ul className="mt-2 divide-y divide-neutral-100 rounded-lg border border-neutral-200">
            {items.map((p) => (
              <li key={p.key}>
                <button
                  type="button"
                  onClick={() => onSelect(p.key)}
                  className={cn(
                    "flex w-full items-start justify-between gap-3 px-4 py-3 text-left hover:bg-neutral-50",
                    selectedKey === p.key && "bg-primary-light",
                  )}
                >
                  <span>
                    <span className="block font-mono text-sm text-neutral-900">{p.key}</span>
                    <span className="block text-xs text-neutral-500">{p.description}</span>
                    <span className="mt-1 flex flex-wrap gap-1">
                      {p.variables.map((v) => (
                        <span key={v} className="rounded-full bg-neutral-100 px-2 py-0.5 font-mono text-xs text-neutral-600">
                          {`{${v}}`}
                        </span>
                      ))}
                    </span>
                  </span>
                  {p.is_overridden && (
                    <span className="shrink-0 rounded-full bg-warning-light px-2.5 py-0.5 text-xs font-medium text-warning">
                      Overridden
                    </span>
                  )}
                </button>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
