"use client";

import type { Brief } from "@/types/brief";

export const NEW_BRIEF = "__new__";

interface BriefPickerProps {
  briefs: Brief[];
  value: string;
  onChange: (id: string) => void;
  isLoading?: boolean;
}

const SELECT_CLASS =
  "w-full rounded-md border border-neutral-200 px-3 py-2 text-sm focus:border-primary focus:outline-none";

export function BriefPicker({ briefs, value, onChange, isLoading = false }: BriefPickerProps) {
  return (
    <div>
      <label htmlFor="brief-picker" className="mb-1 block text-sm font-medium text-neutral-700">
        Brief
      </label>
      <select
        id="brief-picker"
        value={value}
        disabled={isLoading}
        onChange={(e) => onChange(e.target.value)}
        className={SELECT_CLASS}
      >
        <option value={NEW_BRIEF}>New brief (from topic analysis)</option>
        {briefs.map((b) => (
          <option key={b.id} value={b.id}>
            {b.name}
          </option>
        ))}
      </select>
      <p className="mt-1 text-xs text-neutral-500">
        Pick a saved brief to reuse its audience, tone, angle, keywords and settings.
      </p>
    </div>
  );
}
