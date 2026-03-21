import { cn } from "@/lib/utils";
import type { DomainConfig } from "@/types/settings";

interface DomainCardProps {
  domain: DomainConfig;
  onEdit: (domain: DomainConfig) => void;
}

export function DomainCard({ domain, onEdit }: DomainCardProps) {
  const isActive = domain.status === "active";

  return (
    <div
      className={cn(
        "rounded-lg border p-4 shadow-sm",
        isActive ? "border-primary border-2" : "border-neutral-200"
      )}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h3 className="font-heading text-base font-semibold text-neutral-900">
            {domain.name}
          </h3>
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
        <button
          onClick={() => onEdit(domain)}
          className="text-sm font-medium text-primary hover:underline"
        >
          Edit
        </button>
      </div>
      <div className="mt-3 grid grid-cols-3 gap-4 text-sm">
        <div>
          <span className="text-xs font-medium uppercase text-neutral-400">
            Trend Sources
          </span>
          <p className="mt-0.5 text-neutral-700">
            {domain.trendSources.length} sources
          </p>
        </div>
        <div>
          <span className="text-xs font-medium uppercase text-neutral-400">
            Keywords
          </span>
          <p className="mt-0.5 text-neutral-700">
            {domain.keywords.length} keywords
          </p>
        </div>
        <div>
          <span className="text-xs font-medium uppercase text-neutral-400">
            Articles
          </span>
          <p className="mt-0.5 text-neutral-700">
            {domain.articleCount} articles
          </p>
        </div>
      </div>
    </div>
  );
}
