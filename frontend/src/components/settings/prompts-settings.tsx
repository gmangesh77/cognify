"use client";

import { useState } from "react";
import { PromptEditor } from "@/components/settings/prompt-editor";
import { PromptsTab } from "@/components/settings/prompts-tab";
import { useToast } from "@/components/ui/toaster";
import { usePrompts } from "@/hooks/use-prompts";
import { extractPromptViolations } from "@/lib/api/prompts";
import { currentRole } from "@/lib/auth/role";

export function PromptsSettings() {
  const { prompts, isLoading, error, save, reset, isSaving } = usePrompts();
  const { showToast } = useToast();
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [violations, setViolations] = useState<string[]>([]);
  const canEdit = currentRole() === "admin";
  const selected = prompts.find((p) => p.key === selectedKey) ?? null;

  const handleSave = async (template: string) => {
    if (!selected) return;
    try {
      await save(selected.key, template);
      setViolations([]);
      showToast("Prompt saved");
    } catch (err) {
      const found = extractPromptViolations(err);
      setViolations(found.length ? found : ["Save failed"]);
    }
  };

  const handleReset = async () => {
    if (!selected) return;
    await reset(selected.key);
    setViolations([]);
    showToast("Prompt reset to default");
  };

  return (
    <div>
      <h2 className="font-heading text-lg font-semibold text-neutral-900">Prompts</h2>
      <p className="mt-1 text-sm text-neutral-500">
        Edits apply to the next run. Every template must use exactly its listed variables.
      </p>
      {error && <p className="mt-3 text-sm text-error">{error}</p>}
      {isLoading ? (
        <p className="mt-4 text-sm text-neutral-500">Loading…</p>
      ) : (
        <div className="mt-4 grid grid-cols-1 gap-6 lg:grid-cols-2">
          <PromptsTab prompts={prompts} selectedKey={selectedKey} onSelect={(k) => { setSelectedKey(k); setViolations([]); }} />
          {selected ? (
            <PromptEditor prompt={selected} canEdit={canEdit} violations={violations} saving={isSaving} onSave={handleSave} onReset={handleReset} />
          ) : (
            <p className="text-sm text-neutral-500">Select a prompt to view or edit it.</p>
          )}
        </div>
      )}
    </div>
  );
}
