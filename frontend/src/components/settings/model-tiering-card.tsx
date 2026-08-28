"use client";

/** AUTHOR-010 — read-only view of the env-driven step → model map. */
export function ModelTieringCard({
  defaultModel,
  modelByStep,
}: {
  defaultModel: string;
  modelByStep: Record<string, string>;
}) {
  const rows = Object.entries(modelByStep).sort(([a], [b]) => a.localeCompare(b));
  return (
    <section
      data-testid="model-tiering-card"
      className="rounded-lg border border-neutral-200 bg-white p-5 shadow-sm"
    >
      <h3 className="font-heading text-base font-medium text-neutral-900">Model tiering</h3>
      <p className="mt-1 text-xs text-neutral-500">
        Set per step with <code className="font-mono">COGNIFY_LLM_MODEL_BY_STEP</code> (JSON map
        of tracked step name → model id). Read-only here.
      </p>
      <p data-testid="tiering-default-model" className="mt-3 text-sm text-neutral-700">
        Default model: <span className="font-mono">{defaultModel || "—"}</span>
      </p>
      {rows.length === 0 ? (
        <p data-testid="tiering-empty" className="mt-2 text-sm text-neutral-500">
          All steps use the default model.
        </p>
      ) : (
        <table className="mt-3 w-full text-sm">
          <thead>
            <tr className="bg-neutral-50 text-left text-xs font-medium uppercase text-neutral-500">
              <th className="px-2 py-1">Step</th>
              <th className="px-2 py-1">Model</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(([step, model]) => (
              <tr key={step} data-testid="tiering-row" className="border-b border-neutral-100">
                <td className="px-2 py-1 font-mono text-neutral-700">{step}</td>
                <td className="px-2 py-1 font-mono text-neutral-700">{model}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
