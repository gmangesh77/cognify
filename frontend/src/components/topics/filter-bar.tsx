import { useState, useRef, useEffect } from "react";
import type { TopicFilters } from "@/types/api";
import { SOURCE_NAMES, SOURCE_LABELS } from "@/types/sources";
import { DOMAIN_LABELS, type DomainName } from "@/types/domain";

interface FilterBarProps {
  filters: TopicFilters;
  onFilterChange: (update: Partial<TopicFilters>) => void;
  topicCount: number;
}

const TIME_OPTIONS = [
  { value: "1h", label: "Last Hour" },
  { value: "24h", label: "Last 24 Hours" },
  { value: "7d", label: "Last 7 Days" },
  { value: "30d", label: "Last 30 Days" },
  { value: "all", label: "All Time" },
] as const;

function SourceMultiSelect({
  selected,
  onChange,
}: {
  selected: string[];
  onChange: (s: string[]) => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const label = selected.length === 0 ? "All Sources" : `${selected.length} selected`;

  const toggle = (source: string) => {
    const next = selected.includes(source)
      ? selected.filter((s) => s !== source)
      : [...selected, source];
    onChange(next);
  };

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex h-9 items-center gap-2 rounded-lg border border-neutral-200 bg-white px-3 text-sm text-neutral-700"
      >
        {label}
      </button>
      {open && (
        <div className="absolute left-0 top-full z-10 mt-1 w-48 rounded-lg border border-neutral-200 bg-white py-1 shadow-md">
          {SOURCE_NAMES.map((name) => (
            <label
              key={name}
              className="flex cursor-pointer items-center gap-2 px-3 py-1.5 text-sm hover:bg-neutral-50"
            >
              <input
                type="checkbox"
                checked={selected.includes(name)}
                onChange={() => toggle(name)}
                className="rounded"
              />
              {SOURCE_LABELS[name]}
            </label>
          ))}
        </div>
      )}
    </div>
  );
}

export function FilterBar({ filters, onFilterChange, topicCount }: FilterBarProps) {
  return (
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-3">
        <SourceMultiSelect
          selected={filters.sources}
          onChange={(sources) => onFilterChange({ sources })}
        />
        <select
          value={filters.timeRange}
          onChange={(e) => onFilterChange({ timeRange: e.target.value as TopicFilters["timeRange"] })}
          className="h-9 rounded-lg border border-neutral-200 bg-white px-3 text-sm text-neutral-700"
        >
          {TIME_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
        <select
          value={filters.domain}
          onChange={(e) => onFilterChange({ domain: e.target.value })}
          className="h-9 rounded-lg border border-neutral-200 bg-white px-3 text-sm text-neutral-700"
        >
          <option value="">All Domains</option>
          {(Object.keys(DOMAIN_LABELS) as DomainName[]).map((d) => (
            <option key={d} value={d}>
              {DOMAIN_LABELS[d]}
            </option>
          ))}
        </select>
      </div>
      <span className="text-sm text-neutral-500">{topicCount} Topics Found</span>
    </div>
  );
}
