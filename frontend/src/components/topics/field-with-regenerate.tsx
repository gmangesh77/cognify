"use client";

import { RefreshCw } from "lucide-react";

interface FieldWithRegenerateProps {
  label: string;
  field: string;
  isRegenerating: string | null;
  onRegenerate: () => void;
  children: React.ReactNode;
}

export function FieldWithRegenerate({
  label,
  field,
  isRegenerating,
  onRegenerate,
  children,
}: FieldWithRegenerateProps) {
  return (
    <div>
      <div className="flex items-center justify-between">
        <label className="text-sm font-medium text-neutral-700">{label}</label>
        <button
          type="button"
          onClick={onRegenerate}
          disabled={isRegenerating === field}
          className="text-neutral-400 hover:text-neutral-600 disabled:animate-spin"
          title={`Regenerate ${label.toLowerCase()}`}
        >
          <RefreshCw className="h-3.5 w-3.5" />
        </button>
      </div>
      <div className="mt-1">{children}</div>
    </div>
  );
}
