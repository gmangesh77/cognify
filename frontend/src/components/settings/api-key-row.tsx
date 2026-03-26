import { useState } from "react";
import { Trash2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { API_KEY_SERVICES } from "@/types/settings";
import type { ApiKeyConfig } from "@/types/settings";

type ActionStep = "idle" | "rotate-confirm" | "rotate-input" | "delete-confirm";

interface ApiKeyRowProps {
  apiKey: ApiKeyConfig;
  onRotate: (id: string, newKey: string) => void;
  onDelete: (id: string) => void;
}

export function ApiKeyRow({ apiKey, onRotate, onDelete }: ApiKeyRowProps) {
  const [step, setStep] = useState<ActionStep>("idle");
  const [newKey, setNewKey] = useState("");

  const label =
    API_KEY_SERVICES.find((s) => s.value === apiKey.service)?.label ?? apiKey.service;
  const isActive = apiKey.status === "active";

  function handleSave() {
    onRotate(apiKey.id, newKey);
    setStep("idle");
    setNewKey("");
  }

  function handleCancel() {
    setStep("idle");
    setNewKey("");
  }

  return (
    <div className="border-b border-neutral-100 py-3 last:border-b-0">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-sm font-semibold text-neutral-900">{label}</span>
          <code className="rounded bg-neutral-100 px-2 py-0.5 text-xs text-neutral-600">
            {apiKey.maskedKey}
          </code>
          <span
            className={cn(
              "rounded-full px-2 py-0.5 text-xs font-medium",
              isActive
                ? "bg-success/10 text-success"
                : "bg-neutral-100 text-neutral-500"
            )}
          >
            {isActive ? "Active" : "Inactive"}
          </span>
        </div>
        {step === "idle" && (
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setStep("rotate-confirm")}
              className="text-primary"
            >
              Rotate
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setStep("delete-confirm")}
              className="text-neutral-400 hover:text-red-600"
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          </div>
        )}
      </div>
      {step === "rotate-confirm" && (
        <div className="mt-2 flex items-center gap-2">
          <p className="text-xs text-neutral-500">
            Are you sure you want to rotate this key?
          </p>
          <Button size="sm" onClick={() => setStep("rotate-input")}>
            Confirm
          </Button>
          <Button variant="ghost" size="sm" onClick={handleCancel}>
            Cancel
          </Button>
        </div>
      )}
      {step === "rotate-input" && (
        <div className="mt-2 flex items-center gap-2">
          <Input
            value={newKey}
            onChange={(e) => setNewKey(e.target.value)}
            placeholder="New API key"
            className="max-w-xs"
          />
          <Button size="sm" onClick={handleSave}>
            Save
          </Button>
          <Button variant="ghost" size="sm" onClick={handleCancel}>
            Cancel
          </Button>
        </div>
      )}
      {step === "delete-confirm" && (
        <div className="mt-2 flex items-center gap-2">
          <p className="text-xs text-red-600">
            Delete this API key? This cannot be undone.
          </p>
          <Button
            size="sm"
            variant="destructive"
            onClick={() => onDelete(apiKey.id)}
          >
            Delete
          </Button>
          <Button variant="ghost" size="sm" onClick={handleCancel}>
            Cancel
          </Button>
        </div>
      )}
    </div>
  );
}
