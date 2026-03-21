import { useState } from "react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { API_KEY_SERVICES } from "@/lib/mock/settings";
import type { ApiKeyConfig } from "@/types/settings";

type RotateStep = "idle" | "confirm" | "input";

interface ApiKeyRowProps {
  apiKey: ApiKeyConfig;
  onRotate: (id: string, newKey: string) => void;
}

export function ApiKeyRow({ apiKey, onRotate }: ApiKeyRowProps) {
  const [step, setStep] = useState<RotateStep>("idle");
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
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setStep("confirm")}
            className="text-primary"
          >
            Rotate
          </Button>
        )}
      </div>
      {step === "confirm" && (
        <div className="mt-2 flex items-center gap-2">
          <p className="text-xs text-neutral-500">
            Are you sure you want to rotate this key?
          </p>
          <Button size="sm" onClick={() => setStep("input")}>
            Confirm
          </Button>
          <Button variant="ghost" size="sm" onClick={handleCancel}>
            Cancel
          </Button>
        </div>
      )}
      {step === "input" && (
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
    </div>
  );
}
