import { useState } from "react";
import { Globe } from "lucide-react";
import { Button } from "@/components/ui/button";
import { DomainCard } from "./domain-card";
import { DomainModal } from "./domain-modal";
import type { DomainModalAction } from "./domain-modal";
import type { DomainConfig } from "@/types/settings";

interface DomainActions {
  add: (data: Omit<DomainConfig, "id" | "articleCount">) => void;
  update: (id: string, updates: Partial<DomainConfig>) => void;
  delete: (id: string) => void;
}

interface DomainsTabProps {
  domains: DomainConfig[];
  actions: DomainActions;
}

export function DomainsTab({ domains, actions }: DomainsTabProps) {
  const [editDomain, setEditDomain] = useState<DomainConfig | null>(null);
  const [modalOpen, setModalOpen] = useState(false);

  function openAdd() {
    setEditDomain(null);
    setModalOpen(true);
  }

  function openEdit(domain: DomainConfig) {
    setEditDomain(domain);
    setModalOpen(true);
  }

  function handleSubmit(action: DomainModalAction) {
    if (action.type === "save") {
      if (editDomain) {
        actions.update(editDomain.id, action.data);
      } else {
        actions.add(action.data);
      }
    } else {
      actions.delete(action.id);
    }
    setModalOpen(false);
  }

  return (
    <div>
      <div className="flex items-center justify-between">
        <h2 className="font-heading text-lg font-semibold text-neutral-900">Domains</h2>
        <Button variant="ghost" size="sm" onClick={openAdd}>
          + Add Domain
        </Button>
      </div>

      {domains.length === 0 ? (
        <div className="mt-8 flex flex-col items-center justify-center py-12 text-center">
          <Globe className="mb-4 h-10 w-10 text-neutral-300" />
          <p className="text-sm text-neutral-500">No domains configured</p>
          <p className="mt-1 text-xs text-neutral-400">Click &ldquo;+ Add Domain&rdquo; to get started.</p>
        </div>
      ) : (
        <div className="mt-4 space-y-3">
          {domains.map((domain) => (
            <DomainCard key={domain.id} domain={domain} onEdit={openEdit} />
          ))}
        </div>
      )}

      <DomainModal
        domain={editDomain}
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onSubmit={handleSubmit}
      />
    </div>
  );
}
