"use client";

import { useState } from "react";
import { PersonaEditor } from "@/components/settings/persona-editor";
import { PersonaSamples } from "@/components/settings/persona-samples";
import { PersonasList } from "@/components/settings/personas-list";
import { useToast } from "@/components/ui/toaster";
import { usePersona, usePersonas } from "@/hooks/use-personas";
import { extractPersonaViolations } from "@/lib/api/personas";
import { currentRole } from "@/lib/auth/role";
import type { PersonaUpdate } from "@/types/persona";

export function PersonasSettings() {
  const { personas, isLoading, error, create, update, remove } = usePersonas();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const { persona, addSample, removeSample, isMutating } = usePersona(selectedId);
  const { showToast } = useToast();
  const [violations, setViolations] = useState<string[]>([]);
  const canEdit = currentRole() !== "viewer";

  const select = (id: string | null) => {
    setSelectedId(id);
    setViolations([]);
  };

  const handleCreate = async (name: string) => {
    try {
      const created = await create({ name });
      select(created.id);
      showToast("Persona created");
    } catch {
      showToast("Failed to create persona");
    }
  };

  const handleSave = async (patch: PersonaUpdate) => {
    if (!selectedId) return;
    try {
      await update(selectedId, patch);
      showToast("Persona saved");
    } catch {
      showToast("Failed to save persona");
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await remove(id);
      select(null);
      showToast("Persona deleted");
    } catch {
      showToast("Failed to delete persona");
    }
  };

  const handleAdd = async (text: string) => {
    try {
      await addSample(text);
      setViolations([]);
      showToast("Sample added");
    } catch (err) {
      const found = extractPersonaViolations(err);
      setViolations(found.length ? found : ["Failed to add sample"]);
    }
  };

  const handleRemoveSample = async (sampleId: string) => {
    try {
      await removeSample(sampleId);
      showToast("Sample removed");
    } catch {
      showToast("Failed to remove sample");
    }
  };

  return (
    <div>
      <h2 className="font-heading text-lg font-semibold text-neutral-900">Personas</h2>
      <p className="mt-1 text-sm text-neutral-500">
        Build an author voice from 5+ writing samples of 150+ words each.
      </p>
      {error && <p className="mt-3 text-sm text-error">{error}</p>}
      {isLoading ? (
        <p className="mt-4 text-sm text-neutral-500">Loading…</p>
      ) : (
        <div className="mt-4 grid grid-cols-1 gap-6 lg:grid-cols-2">
          <PersonasList personas={personas} selectedId={selectedId} onSelect={select} onCreate={handleCreate} />
          {persona ? (
            <div className="space-y-6">
              <div className="flex items-center justify-between">
                <h3 className="font-heading text-sm font-semibold text-neutral-900">{persona.name}</h3>
                {canEdit && (
                  <button
                    type="button"
                    onClick={() => handleDelete(persona.id)}
                    className="rounded-md bg-red-600 px-2.5 py-1 text-xs font-medium text-white hover:bg-red-700"
                  >
                    Delete persona
                  </button>
                )}
              </div>
              <PersonaEditor persona={persona} canEdit={canEdit} onSave={handleSave} />
              <PersonaSamples
                persona={persona}
                canEdit={canEdit}
                violations={violations}
                onAdd={handleAdd}
                onRemove={handleRemoveSample}
                isMutating={isMutating}
              />
            </div>
          ) : (
            <p className="text-sm text-neutral-500">Select a persona to view or edit it.</p>
          )}
        </div>
      )}
    </div>
  );
}
