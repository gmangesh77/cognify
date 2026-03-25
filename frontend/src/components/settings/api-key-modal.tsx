import { useState } from "react";
import { Eye, EyeOff } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { API_KEY_SERVICES } from "@/types/settings";
import type { ApiKeyService } from "@/types/settings";

interface ApiKeyModalProps {
  open: boolean;
  onSave: (service: ApiKeyService, key: string) => void;
  onClose: () => void;
}

export function ApiKeyModal({ open, onSave, onClose }: ApiKeyModalProps) {
  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      onClick={onClose}
    >
      <ApiKeyModalForm key={String(open)} onSave={onSave} onClose={onClose} />
    </div>
  );
}

function ApiKeyModalForm({
  onSave,
  onClose,
}: {
  onSave: (service: ApiKeyService, key: string) => void;
  onClose: () => void;
}) {
  const [service, setService] = useState<ApiKeyService>("anthropic");
  const [key, setKey] = useState("");
  const [showKey, setShowKey] = useState(false);

  function handleSave() {
    onSave(service, key);
    onClose();
  }

  return (
    <div
      role="dialog"
      className="w-full max-w-md rounded-xl bg-white p-6 shadow-lg"
      onClick={(e) => e.stopPropagation()}
    >
      <h2 className="font-heading text-lg font-semibold text-neutral-900">
        Add API Key
      </h2>
      <div className="mt-4 space-y-4">
        <div>
          <label htmlFor="api-service" className="block text-sm font-medium text-neutral-700">
            Service
          </label>
          <select
            id="api-service"
            value={service}
            onChange={(e) => setService(e.target.value as ApiKeyService)}
            className="mt-1 h-8 w-full rounded-lg border border-input bg-transparent px-2.5 text-sm"
          >
            {API_KEY_SERVICES.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="api-key-value" className="block text-sm font-medium text-neutral-700">
            API Key
          </label>
          <div className="relative mt-1">
            <Input
              id="api-key-value"
              type={showKey ? "text" : "password"}
              value={key}
              onChange={(e) => setKey(e.target.value)}
            />
            <button
              type="button"
              aria-label="Toggle key visibility"
              onClick={() => setShowKey((prev) => !prev)}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-neutral-400 hover:text-neutral-600"
            >
              {showKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </button>
          </div>
        </div>
      </div>
      <div className="mt-6 flex justify-end gap-3">
        <Button variant="ghost" onClick={onClose}>Cancel</Button>
        <Button onClick={handleSave}>Save</Button>
      </div>
    </div>
  );
}
