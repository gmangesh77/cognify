import { cn } from "@/lib/utils";
import type { SessionStatus } from "@/types/research";

type FilterValue = SessionStatus | "all";

const FILTERS: { value: FilterValue; label: string }[] = [
  { value: "all", label: "All" },
  { value: "planning", label: "Planning" },
  { value: "in_progress", label: "In Progress" },
  { value: "complete", label: "Complete" },
  { value: "failed", label: "Failed" },
];

interface SessionFiltersProps {
  activeFilter: FilterValue;
  onFilterChange: (filter: FilterValue) => void;
  totalCount: number;
}

export function SessionFilters({ activeFilter, onFilterChange, totalCount }: SessionFiltersProps) {
  return (
    <div className="flex items-center justify-between">
      <div className="flex gap-2">
        {FILTERS.map(({ value, label }) => (
          <button
            key={value}
            type="button"
            onClick={() => onFilterChange(value)}
            className={cn(
              "rounded-full px-3 py-1 text-xs font-medium transition-colors",
              activeFilter === value
                ? "bg-primary text-white"
                : "bg-neutral-100 text-neutral-600 hover:bg-neutral-200",
            )}
          >
            {label}
          </button>
        ))}
      </div>
      <span className="text-sm text-neutral-500">{totalCount} Sessions</span>
    </div>
  );
}
