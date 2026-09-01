import { useState } from "react";
import { cn } from "@/lib/utils";
import { MIN_READY_SAMPLES } from "@/types/persona";
import type { PersonaSummary } from "@/types/persona";

interface PersonasListProps {
  personas: PersonaSummary[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onCreate: (name: string) => void;
}

function readyBadge(persona: PersonaSummary) {
  if (persona.ready) {
    return (
      <span className="shrink-0 rounded-full bg-success-light px-2.5 py-0.5 text-xs font-medium text-success">
        Ready
      </span>
    );
  }
  const remaining = Math.max(0, MIN_READY_SAMPLES - persona.sample_count);
  return (
    <span className="shrink-0 rounded-full bg-warning-light px-2.5 py-0.5 text-xs font-medium text-warning">
      needs {remaining} more
    </span>
  );
}

export function PersonasList({ personas, selectedId, onSelect, onCreate }: PersonasListProps) {
  const [name, setName] = useState("");

  const handleCreate = () => {
    const trimmed = name.trim();
    if (!trimmed) return;
    onCreate(trimmed);
    setName("");
  };

  return (
    <div className="space-y-3" data-testid="personas-list">
      <ul className="divide-y divide-neutral-100 rounded-lg border border-neutral-200">
        {personas.map((persona) => (
          <li key={persona.id}>
            <button
              type="button"
              onClick={() => onSelect(persona.id)}
              className={cn(
                "flex w-full items-center justify-between gap-3 px-4 py-3 text-left hover:bg-neutral-50",
                selectedId === persona.id && "bg-primary-light",
              )}
            >
              <span>
                <span className="block text-sm font-medium text-neutral-900">{persona.name}</span>
                <span className="block text-xs text-neutral-500">
                  {persona.sample_count} sample{persona.sample_count === 1 ? "" : "s"}
                </span>
              </span>
              {readyBadge(persona)}
            </button>
          </li>
        ))}
        {personas.length === 0 && (
          <li className="px-4 py-3 text-sm text-neutral-500">No personas yet.</li>
        )}
      </ul>
      <div className="flex gap-2">
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="New persona name"
          className="w-full rounded-md border border-neutral-200 px-3 py-1.5 text-sm text-neutral-800 focus:border-primary focus:outline-none"
        />
        <button
          type="button"
          disabled={!name.trim()}
          onClick={handleCreate}
          className="shrink-0 rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-white hover:bg-primary/90 disabled:opacity-50"
        >
          New persona
        </button>
      </div>
    </div>
  );
}
