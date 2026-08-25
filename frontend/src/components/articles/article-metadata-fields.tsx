"use client";

import type { ReactNode } from "react";
import { RefreshCw } from "lucide-react";

/** Presentational pieces of the header metadata editor (AUTHOR-006/007
 * split — keeps article-header-editor.tsx under the 200-line budget). */

export function Counter({
  id,
  length,
  lo,
  hi,
}: {
  id: string;
  length: number;
  lo: number;
  hi: number;
}) {
  const inRange = length >= lo && length <= hi;
  return (
    <span
      data-testid={id}
      className={`text-xs ${inRange ? "text-neutral-500" : "text-warning"}`}
    >
      {length}/{lo}–{hi}
    </span>
  );
}

export function MetadataField({
  label,
  id,
  value,
  onChange,
  extra,
}: {
  label: string;
  id: string;
  value: string;
  onChange: (value: string) => void;
  extra?: ReactNode;
}) {
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between">
        <label
          htmlFor={id}
          className="text-xs font-medium uppercase tracking-wide text-neutral-500"
        >
          {label}
        </label>
        {extra}
      </div>
      <input
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-md border border-neutral-200 px-3 py-2 text-sm text-neutral-900"
      />
    </div>
  );
}

export function RegenButton({
  label,
  disabled,
  onClick,
}: {
  label: string;
  disabled: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      disabled={disabled}
      onClick={onClick}
      className="rounded-md p-1 text-neutral-500 hover:bg-neutral-100 disabled:opacity-50"
    >
      <RefreshCw className="h-3.5 w-3.5" />
    </button>
  );
}
