import { useState } from "react";
import { MIN_SAMPLE_WORDS } from "@/types/persona";
import type { PersonaDetail } from "@/types/persona";

interface PersonaSamplesProps {
  persona: PersonaDetail;
  canEdit: boolean;
  violations: string[];
  onAdd: (text: string) => void;
  onRemove: (sampleId: string) => void;
  isMutating?: boolean;
}

/** Same letter-only word regex as `src/services/persona/fingerprint.py::count_words`
 * — keeps the live counter and the backend's 150-word gate in agreement. */
const WORD_RE = /[A-Za-z][A-Za-z']*/g;

export function countWords(text: string): number {
  return text.match(WORD_RE)?.length ?? 0;
}

export function PersonaSamples({ persona, canEdit, violations, onAdd, onRemove, isMutating = false }: PersonaSamplesProps) {
  const [text, setText] = useState("");
  const wordCount = countWords(text);
  const belowMinimum = wordCount < MIN_SAMPLE_WORDS;

  const handleAdd = () => {
    if (belowMinimum || !text.trim()) return;
    onAdd(text);
    setText("");
  };

  return (
    <div className="space-y-4" data-testid="persona-samples">
      {canEdit && (
        <div className="space-y-2">
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Paste a writing sample (150+ words)…"
            rows={6}
            className="w-full rounded-md border border-neutral-200 p-3 text-sm text-neutral-800 focus:border-primary focus:outline-none"
          />
          <div className="flex items-center justify-between">
            <span className={`text-xs ${belowMinimum ? "text-neutral-500" : "text-success"}`}>
              {wordCount} / {MIN_SAMPLE_WORDS} words
            </span>
            <button
              type="button"
              disabled={belowMinimum || isMutating}
              onClick={handleAdd}
              className="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-white hover:bg-primary/90 disabled:opacity-50"
            >
              Add sample
            </button>
          </div>
          {violations.length > 0 && (
            <ul className="rounded-md border border-error/40 bg-error-light p-3 text-xs text-error">
              {violations.map((v) => (
                <li key={v}>{v}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      <ul className="divide-y divide-neutral-100 rounded-lg border border-neutral-200">
        {persona.samples.map((sample) => (
          <li key={sample.id} className="flex items-start justify-between gap-3 px-4 py-3">
            <span>
              <span className="block text-xs text-neutral-500">{sample.word_count} words</span>
              <span className="block text-sm text-neutral-700">{sample.preview}</span>
            </span>
            {canEdit && (
              <button
                type="button"
                disabled={isMutating}
                onClick={() => onRemove(sample.id)}
                className="shrink-0 rounded-md bg-neutral-100 px-2.5 py-1 text-xs font-medium text-neutral-700 hover:bg-neutral-200 disabled:opacity-50"
              >
                Remove
              </button>
            )}
          </li>
        ))}
        {persona.samples.length === 0 && (
          <li className="px-4 py-3 text-sm text-neutral-500">No samples yet.</li>
        )}
      </ul>
    </div>
  );
}
