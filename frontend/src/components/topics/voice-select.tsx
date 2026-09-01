"use client";

import { usePersonas } from "@/hooks/use-personas";

interface VoiceSelectProps {
  value: string | null;
  onChange: (v: string | null) => void;
}

export function VoiceSelect({ value, onChange }: VoiceSelectProps) {
  const { personas } = usePersonas();
  const readyPersonas = personas.filter((p) => p.ready);

  return (
    <div>
      <label
        htmlFor="voice-select"
        className="mb-1 block text-sm font-medium text-neutral-700"
      >
        Voice
      </label>
      <select
        id="voice-select"
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value || null)}
        className="w-full rounded-md border border-neutral-200 px-3 py-2 text-sm focus:border-primary focus:outline-none"
      >
        <option value="">None</option>
        {readyPersonas.map((p) => (
          <option key={p.id} value={p.id}>
            {p.name}
          </option>
        ))}
      </select>
      <p className="mt-1 text-xs text-neutral-500">
        Draft in a saved author voice. Only personas with enough samples
        appear here.
      </p>
    </div>
  );
}
