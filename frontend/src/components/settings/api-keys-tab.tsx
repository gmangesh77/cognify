import { useState } from "react";
import { Key, Linkedin } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ApiKeyRow } from "./api-key-row";
import { ApiKeyModal } from "./api-key-modal";
import { getLinkedInAuthUrl, disconnectLinkedIn } from "@/lib/api/settings";
import type { ApiKeyConfig, ApiKeyService } from "@/types/settings";

interface KeyActions {
  add: (service: ApiKeyService, key: string) => void;
  rotate: (id: string, newKey: string) => void;
  delete: (id: string) => void;
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
            <ApiKeyRow key={key.id} apiKey={key} onRotate={actions.rotate} onDelete={actions.delete} />
          ))}
        </div>
      )}

      <ApiKeyModal
        open={modalOpen}
        onSave={(service, key) => { actions.add(service, key); setModalOpen(false); }}
        onClose={() => setModalOpen(false)}
      />

      <LinkedInConnection apiKeys={apiKeys} onDisconnect={actions.delete} />
    </div>
  );
}

function LinkedInConnection({
  apiKeys,
  onDisconnect,
}: {
  apiKeys: ApiKeyConfig[];
  onDisconnect: (id: string) => void;
}) {
  const isConnected = apiKeys.some((k) => k.service === "linkedin_access_token");

  const handleConnect = async () => {
    const url = await getLinkedInAuthUrl();
    window.location.href = url;
  };

  const handleDisconnect = async () => {
    await disconnectLinkedIn(apiKeys);
    const linkedinKeys = apiKeys.filter(
      (k) => k.service === "linkedin_access_token" || k.service === "linkedin_refresh_token",
    );
    linkedinKeys.forEach((k) => onDisconnect(k.id));
  };

  return (
    <div className="mt-8">
      <h3 className="font-heading text-base font-medium text-neutral-900">Platform Connections</h3>
      <div className="mt-3 flex items-center justify-between rounded-lg border border-neutral-200 p-4">
        <div className="flex items-center gap-3">
          <Linkedin className="h-5 w-5 text-neutral-500" />
          <div>
            <p className="text-sm font-medium text-neutral-700">LinkedIn</p>
            <p className="text-xs text-neutral-500">
              {isConnected ? "Connected — posts shared as link cards" : "Share articles on LinkedIn"}
            </p>
          </div>
        </div>
        {isConnected ? (
          <Button variant="ghost" size="sm" onClick={handleDisconnect}>
            Disconnect
          </Button>
        ) : (
          <Button size="sm" onClick={handleConnect}>
            Connect
          </Button>
        )}
      </div>
    </div>
  );
}
