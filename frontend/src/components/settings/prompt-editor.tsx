import { useState } from "react";
import type { PromptView } from "@/types/prompts";

interface PromptEditorProps {
  prompt: PromptView;
  canEdit: boolean;
  violations: string[];
  saving: boolean;
  onSave: (template: string) => void;
  onReset: () => void;
}

export function PromptEditor({ prompt, canEdit, violations, saving, onSave, onReset }: PromptEditorProps) {
  const [draft, setDraft] = useState(prompt.template);
  // Adjust state during render (React-recommended pattern) instead of a
  // setState-in-effect, so a new selected prompt (or a post-save/reset
  // refetch of the same key) resets the draft without a cascading effect.
  const [synced, setSynced] = useState({ key: prompt.key, template: prompt.template });
  if (synced.key !== prompt.key || synced.template !== prompt.template) {
    setSynced({ key: prompt.key, template: prompt.template });
    setDraft(prompt.template);
  }
  const dirty = draft !== prompt.template;

  return (
    <div className="space-y-3" data-testid="prompt-editor">
      <div>
        <h3 className="font-mono text-sm font-semibold text-neutral-900">{prompt.key}</h3>
        <p className="text-xs text-neutral-500">{prompt.description}</p>
      </div>
      <p className="text-xs text-neutral-500">
        Use {"{variable}"} for the listed variables; write literal braces as {"{{"} and {"}}"}.
      </p>
      <textarea
        value={draft}
        readOnly={!canEdit}
        onChange={(e) => setDraft(e.target.value)}
        rows={14}
        className="w-full rounded-md border border-neutral-200 p-3 font-mono text-sm text-neutral-800 focus:border-primary focus:outline-none"
      />
      {violations.length > 0 && (
        <ul className="rounded-md border border-error/40 bg-error-light p-3 text-xs text-error">
          {violations.map((v) => <li key={v}>{v}</li>)}
        </ul>
      )}
      {!canEdit ? (
        <p className="text-xs text-neutral-500">Only admins can edit prompts.</p>
      ) : (
        <div className="flex gap-2">
          <button
            type="button"
            disabled={!dirty || saving}
            onClick={() => onSave(draft)}
            className="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-white hover:bg-primary/90 disabled:opacity-50"
          >
            Save
          </button>
          {prompt.is_overridden && (
            <button
              type="button"
              disabled={saving}
              onClick={onReset}
              className="rounded-md bg-neutral-100 px-3 py-1.5 text-sm font-medium text-neutral-700 hover:bg-neutral-200 disabled:opacity-50"
            >
              Reset to default
            </button>
          )}
        </div>
      )}
    </div>
  );
}
