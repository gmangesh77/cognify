import { useState } from "react";
import { DIM_LABELS, MIN_READY_SAMPLES } from "@/types/persona";
import type { PersonaDetail, PersonaUpdate, VoiceFingerprint } from "@/types/persona";

interface PersonaEditorProps {
  persona: PersonaDetail;
  canEdit: boolean;
  onSave: (patch: PersonaUpdate) => void;
}

/** Buckets a 0..1 confidence into one of five Tailwind width classes — no
 * inline styles allowed (DESIGN.md). */
export function confidenceWidthClass(confidence: number): string {
  const c = Math.max(0, Math.min(1, confidence));
  if (c <= 0.2) return "w-1/5";
  if (c <= 0.4) return "w-2/5";
  if (c <= 0.6) return "w-3/5";
  if (c <= 0.8) return "w-4/5";
  return "w-full";
}

function FingerprintRow({ dimKey, stat }: { dimKey: string; stat: { mean: number; stddev: number; confidence: number } }) {
  return (
    <li className="flex items-center justify-between gap-3 px-4 py-2">
      <span className="text-sm text-neutral-700">{DIM_LABELS[dimKey] ?? dimKey}</span>
      <span className="flex items-center gap-2">
        <span className="text-xs text-neutral-500">
          {stat.mean.toFixed(2)} ± {stat.stddev.toFixed(2)}
        </span>
        <span className="h-1.5 w-16 overflow-hidden rounded-full bg-neutral-100" aria-label={`${dimKey} confidence`}>
          <span className={`block h-full rounded-full bg-primary ${confidenceWidthClass(stat.confidence)}`} />
        </span>
      </span>
    </li>
  );
}

function FingerprintCard({ fingerprint, sampleCount }: { fingerprint: VoiceFingerprint | null; sampleCount: number }) {
  if (!fingerprint) {
    const remaining = Math.max(0, MIN_READY_SAMPLES - sampleCount);
    return (
      <p className="rounded-lg border border-neutral-200 bg-neutral-50 p-4 text-sm text-neutral-500">
        No fingerprint yet — needs {remaining} more sample{remaining === 1 ? "" : "s"}.
      </p>
    );
  }
  return (
    <ul className="divide-y divide-neutral-100 rounded-lg border border-neutral-200" data-testid="fingerprint-card">
      {Object.entries(fingerprint.dims).map(([dimKey, stat]) => (
        <FingerprintRow key={dimKey} dimKey={dimKey} stat={stat} />
      ))}
    </ul>
  );
}

export function PersonaEditor({ persona, canEdit, onSave }: PersonaEditorProps) {
  const [name, setName] = useState(persona.name);
  const [description, setDescription] = useState(persona.description ?? "");
  const [synced, setSynced] = useState({ id: persona.id, name: persona.name, description: persona.description });
  if (synced.id !== persona.id || synced.name !== persona.name || synced.description !== persona.description) {
    setSynced({ id: persona.id, name: persona.name, description: persona.description });
    setName(persona.name);
    setDescription(persona.description ?? "");
  }
  const dirty = name !== persona.name || description !== (persona.description ?? "");

  return (
    <div className="space-y-4" data-testid="persona-editor">
      <div className="space-y-2">
        <label className="block text-xs font-medium uppercase tracking-wide text-neutral-500" htmlFor="persona-name">
          Name
        </label>
        <input
          id="persona-name"
          type="text"
          value={name}
          readOnly={!canEdit}
          onChange={(e) => setName(e.target.value)}
          className="w-full rounded-md border border-neutral-200 px-3 py-1.5 text-sm text-neutral-800 focus:border-primary focus:outline-none"
        />
        <label className="block text-xs font-medium uppercase tracking-wide text-neutral-500" htmlFor="persona-description">
          Description
        </label>
        <textarea
          id="persona-description"
          value={description}
          readOnly={!canEdit}
          onChange={(e) => setDescription(e.target.value)}
          rows={3}
          className="w-full rounded-md border border-neutral-200 p-3 text-sm text-neutral-800 focus:border-primary focus:outline-none"
        />
        {canEdit ? (
          <button
            type="button"
            disabled={!dirty || !name.trim()}
            onClick={() => onSave({ name: name.trim(), description: description.trim() || null })}
            className="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-white hover:bg-primary/90 disabled:opacity-50"
          >
            Save
          </button>
        ) : (
          <p className="text-xs text-neutral-500">Only editors and admins can edit personas.</p>
        )}
      </div>

      <div>
        <h3 className="text-xs font-medium uppercase tracking-wide text-neutral-500">Voice fingerprint</h3>
        <div className="mt-2">
          <FingerprintCard fingerprint={persona.fingerprint} sampleCount={persona.sample_count} />
        </div>
      </div>
    </div>
  );
}
