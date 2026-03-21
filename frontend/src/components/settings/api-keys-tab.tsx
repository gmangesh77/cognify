import { useState } from "react";
import { Key } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ApiKeyRow } from "./api-key-row";
import { ApiKeyModal } from "./api-key-modal";
import type { ApiKeyConfig, ApiKeyService } from "@/types/settings";

interface KeyActions {
  add: (service: ApiKeyService, key: string) => void;
  rotate: (id: string, newKey: string) => void;
}

interface ApiKeysTabProps {
  apiKeys: ApiKeyConfig[];
  actions: KeyActions;
}

export function ApiKeysTab({ apiKeys, actions }: ApiKeysTabProps) {
  const [modalOpen, setModalOpen] = useState(false);

  return (
    <div>
      <div className="flex items-center justify-between">
        <h2 className="font-heading text-lg font-semibold text-neutral-900">API Keys</h2>
        <Button variant="ghost" size="sm" onClick={() => setModalOpen(true)}>
          + Add API Key
        </Button>
      </div>

      {apiKeys.length === 0 ? (
        <div className="mt-8 flex flex-col items-center justify-center py-12 text-center">
          <Key className="mb-4 h-10 w-10 text-neutral-300" />
          <p className="text-sm text-neutral-500">No API keys configured</p>
        </div>
      ) : (
        <div className="mt-4 rounded-lg border border-neutral-200 px-4">
          {apiKeys.map((key) => (
            <ApiKeyRow key={key.id} apiKey={key} onRotate={actions.rotate} />
          ))}
        </div>
      )}

      <ApiKeyModal
        open={modalOpen}
        onSave={(service, key) => { actions.add(service, key); setModalOpen(false); }}
        onClose={() => setModalOpen(false)}
      />
    </div>
  );
}
