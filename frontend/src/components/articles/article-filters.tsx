"use client";

import { cn } from "@/lib/utils";
import type { ArticleStatus } from "@/types/articles";

export type ArticleFilterValue = ArticleStatus | "all";

const FILTERS: { value: ArticleFilterValue; label: string }[] = [
  { value: "all", label: "All" },
  { value: "draft", label: "Draft" },
  { value: "in_review", label: "In Review" },
  { value: "approved", label: "Approved" },
  { value: "published", label: "Published" },
];

interface ArticleFiltersProps {
  activeFilter: ArticleFilterValue;
  onFilterChange: (filter: ArticleFilterValue) => void;
  totalCount: number;
}

export function ArticleFilters({
  activeFilter,
  onFilterChange,
  totalCount,
}: ArticleFiltersProps) {
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
      <span className="text-sm text-neutral-500">{totalCount} Articles</span>
    </div>
  );
}
