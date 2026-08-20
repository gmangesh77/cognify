"use client";

import type { StructuralDiagramMode } from "@/types/api";

const DIAGRAM_MODE_OPTIONS: { value: StructuralDiagramMode; label: string }[] = [
  { value: "illustration", label: "AI illustration (gpt-image-1)" },
  { value: "mermaid", label: "Mermaid (crisp labeled diagrams)" },
];

interface DiagramModeSelectProps {
  value: StructuralDiagramMode;
  onChange: (v: StructuralDiagramMode) => void;
}

export function DiagramModeSelect({ value, onChange }: DiagramModeSelectProps) {
  return (
    <div>
      <label
        htmlFor="diagram-mode"
        className="mb-1 block text-sm font-medium text-neutral-700"
      >
        Diagram style
      </label>
      <select
        id="diagram-mode"
        value={value}
        onChange={(e) => onChange(e.target.value as StructuralDiagramMode)}
        className="w-full rounded-md border border-neutral-200 px-3 py-2 text-sm focus:border-primary focus:outline-none"
      >
        {DIAGRAM_MODE_OPTIONS.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
      <p className="mt-1 text-xs text-neutral-500">
        Applies to structural diagrams (concept, process, comparison).
        Hero and editorial visuals always use AI illustration.
      </p>
    </div>
  );
}
