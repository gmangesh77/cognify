import { cn } from "@/lib/utils";

const STATUS_FILTERS = [
  { value: "all", label: "All" },
  { value: "success", label: "Live" },
  { value: "failed", label: "Failed" },
  { value: "scheduled", label: "Scheduled" },
] as const;

interface PublicationFiltersProps {
  activePlatform: string;
  activeStatus: string;
  onPlatformChange: (platform: string) => void;
  onStatusChange: (status: string) => void;
  totalCount: number;
  platforms?: string[];
}

export function PublicationFilters({
  activePlatform,
  activeStatus,
  onPlatformChange,
  onStatusChange,
  totalCount,
  platforms = [],
}: PublicationFiltersProps) {
  const platformFilters = [
    { value: "all", label: "All" },
    ...platforms.map((p) => ({
      value: p,
      label: p.charAt(0).toUpperCase() + p.slice(1),
    })),
  ];

  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex flex-wrap gap-2">
        {platformFilters.map(({ value, label }) => (
          <button
            key={`platform-${value}`}
            type="button"
            onClick={() => onPlatformChange(value === "all" ? "all" : value)}
            className={cn(
              "rounded-full px-3 py-1 text-xs font-medium transition-colors",
              activePlatform === value
                ? "bg-primary text-white"
                : "bg-neutral-100 text-neutral-600 hover:bg-neutral-200",
            )}
          >
            {label}
          </button>
        ))}
        <span className="mx-1 text-neutral-300">|</span>
        {STATUS_FILTERS.map(({ value, label }) => (
          <button
            key={`status-${value}`}
            type="button"
            onClick={() => onStatusChange(value === "all" ? "all" : value)}
            className={cn(
              "rounded-full px-3 py-1 text-xs font-medium transition-colors",
              activeStatus === value
                ? "bg-primary text-white"
                : "bg-neutral-100 text-neutral-600 hover:bg-neutral-200",
            )}
          >
            {label}
          </button>
        ))}
      </div>
      <span className="text-sm text-neutral-500">{totalCount} Publications</span>
    </div>
  );
}
