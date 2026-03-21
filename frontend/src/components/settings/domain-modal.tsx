import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { SOURCE_NAMES, SOURCE_LABELS } from "@/types/sources";
import type { SourceName } from "@/types/sources";
import type { DomainConfig } from "@/types/settings";

export type DomainModalAction =
  | { type: "save"; data: Omit<DomainConfig, "id" | "articleCount"> }
  | { type: "delete"; id: string };

interface DomainModalProps {
  domain: DomainConfig | null;
  open: boolean;
  onClose: () => void;
  onSubmit: (action: DomainModalAction) => void;
}

export function DomainModal({ domain, open, onClose, onSubmit }: DomainModalProps) {
  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      onClick={onClose}
    >
      <DomainModalForm
        key={`${domain?.id ?? "new"}-${open}`}
        domain={domain}
        onClose={onClose}
        onSubmit={onSubmit}
      />
    </div>
  );
}

function DomainModalForm({
  domain,
  onClose,
  onSubmit,
}: {
  domain: DomainConfig | null;
  onClose: () => void;
  onSubmit: (action: DomainModalAction) => void;
}) {
  const [name, setName] = useState(domain?.name ?? "");
  const [status, setStatus] = useState<"active" | "inactive">(domain?.status ?? "active");
  const [sources, setSources] = useState<SourceName[]>(domain?.trendSources ?? []);
  const [keywords, setKeywords] = useState(domain?.keywords.join(", ") ?? "");
  const [confirmDelete, setConfirmDelete] = useState(false);

  const isEdit = domain !== null;

  function toggleSource(source: SourceName) {
    setSources((prev) =>
      prev.includes(source)
        ? prev.filter((s) => s !== source)
        : [...prev, source],
    );
  }

  function handleSave() {
    const parsed = keywords
      .split(",")
      .map((k) => k.trim())
      .filter(Boolean);
    onSubmit({ type: "save", data: { name, status, trendSources: sources, keywords: parsed } });
  }

  function handleDelete() {
    if (!confirmDelete) {
      setConfirmDelete(true);
      return;
    }
    onSubmit({ type: "delete", id: domain!.id });
  }

  return (
    <div
      role="dialog"
      className="w-full max-w-lg rounded-xl bg-white p-6 shadow-lg"
      onClick={(e) => e.stopPropagation()}
    >
      <h2 className="font-heading text-lg font-semibold text-neutral-900">
        {isEdit ? "Edit Domain" : "Add Domain"}
      </h2>

      <div className="mt-4 space-y-4">
        <div>
          <label htmlFor="domain-name" className="block text-sm font-medium text-neutral-700">
            Domain Name
          </label>
          <Input id="domain-name" value={name} onChange={(e) => setName(e.target.value)} className="mt-1" />
        </div>

        <div>
          <span className="block text-sm font-medium text-neutral-700">Trend Sources</span>
          <div className="mt-1 flex flex-wrap gap-3">
            {SOURCE_NAMES.map((src) => (
              <label key={src} className="flex items-center gap-1.5 text-sm">
                <input
                  type="checkbox"
                  checked={sources.includes(src)}
                  onChange={() => toggleSource(src)}
                  className="rounded"
                  aria-label={SOURCE_LABELS[src]}
                />
                {SOURCE_LABELS[src]}
              </label>
            ))}
          </div>
        </div>

        <div>
          <label htmlFor="domain-keywords" className="block text-sm font-medium text-neutral-700">
            Keywords
          </label>
          <Input
            id="domain-keywords"
            value={keywords}
            onChange={(e) => setKeywords(e.target.value)}
            placeholder="Comma-separated keywords"
            className="mt-1"
          />
        </div>

        <div>
          <label htmlFor="domain-status" className="block text-sm font-medium text-neutral-700">
            Status
          </label>
          <select
            id="domain-status"
            value={status}
            onChange={(e) => setStatus(e.target.value as "active" | "inactive")}
            className="mt-1 h-8 w-full rounded-lg border border-input bg-transparent px-2.5 text-sm"
          >
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
          </select>
        </div>
      </div>

      {confirmDelete && (
        <p className="mt-3 text-sm text-red-600">Are you sure? This cannot be undone.</p>
      )}

      <div className="mt-6 flex items-center justify-between">
        <div>
          {isEdit && (
            <Button variant="ghost" onClick={handleDelete} className="text-red-600 hover:text-red-700">
              {confirmDelete ? "Confirm Delete" : "Delete Domain"}
            </Button>
          )}
        </div>
        <div className="flex gap-3">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={handleSave}>Save Domain</Button>
        </div>
      </div>
    </div>
  );
}
