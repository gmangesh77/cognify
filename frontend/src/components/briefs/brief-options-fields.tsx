"use client";

import type { BriefContentType, LengthTarget } from "@/types/brief";

export interface BriefOptions {
  content_type: BriefContentType;
  length_target: LengthTarget;
  save_as_brief: boolean;
  brief_name: string;
}

interface BriefOptionsFieldsProps {
  value: BriefOptions;
  onChange: (next: BriefOptions) => void;
  showSave: boolean;
}

const CONTENT_TYPES: { value: BriefContentType; label: string }[] = [
  { value: "article", label: "Article" },
  { value: "how-to", label: "How-to" },
  { value: "analysis", label: "Analysis" },
  { value: "report", label: "Report" },
];

const LENGTHS: { value: LengthTarget; label: string }[] = [
  { value: "short", label: "Short" },
  { value: "medium", label: "Medium" },
  { value: "long", label: "Long" },
  { value: "pillar", label: "Pillar" },
];

const FIELD_CLASS =
  "w-full rounded-md border border-neutral-200 px-3 py-2 text-sm focus:border-primary focus:outline-none";
const LABEL_CLASS = "mb-1 block text-sm font-medium text-neutral-700";

export function BriefOptionsFields({ value, onChange, showSave }: BriefOptionsFieldsProps) {
  const set = <K extends keyof BriefOptions>(key: K, v: BriefOptions[K]) =>
    onChange({ ...value, [key]: v });
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label htmlFor="content-type" className={LABEL_CLASS}>Content type</label>
          <select id="content-type" value={value.content_type} className={FIELD_CLASS}
            onChange={(e) => set("content_type", e.target.value as BriefContentType)}>
            {CONTENT_TYPES.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>
        <div>
          <label htmlFor="length-target" className={LABEL_CLASS}>Length</label>
          <select id="length-target" value={value.length_target} className={FIELD_CLASS}
            onChange={(e) => set("length_target", e.target.value as LengthTarget)}>
            {LENGTHS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>
      </div>
      {showSave && (
        <div className="space-y-2">
          <label className="flex items-center gap-2 text-sm text-neutral-700">
            <input id="save-as-brief" type="checkbox" checked={value.save_as_brief}
              onChange={(e) => set("save_as_brief", e.target.checked)}
              className="h-4 w-4 rounded border-neutral-300 text-primary focus:ring-primary" />
            Save as brief
          </label>
          {value.save_as_brief && (
            <div>
              <label htmlFor="brief-name" className={LABEL_CLASS}>Brief name</label>
              <input id="brief-name" value={value.brief_name} placeholder="Brief name"
                onChange={(e) => set("brief_name", e.target.value)} className={FIELD_CLASS} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
