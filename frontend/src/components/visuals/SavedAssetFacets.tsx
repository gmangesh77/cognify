"use client";

import { cn } from "@/lib/utils";
import { humanize } from "@/lib/visuals/savedAssetFormat";

/** Filter rails of the Saved Asset Gallery (INFRA-008 split). */

const ROLE_FILTERS = ["hero", "feature_card", "concept", "quote_card"];

export function RoleFilterRail({
  selected,
  onSelect,
}: {
  selected: string | null;
  onSelect: (role: string | null) => void;
}) {
  return (
    <div className="flex items-center gap-1" role="group" aria-label="Filter by role">
      {ROLE_FILTERS.map((role) => {
        const isSelected = role === selected;
        return (
          <button
            key={role}
            type="button"
            onClick={() => onSelect(isSelected ? null : role)}
            aria-pressed={isSelected}
            className={cn(
              "rounded-full px-3 py-1 text-xs font-medium transition-colors",
              isSelected
                ? "bg-primary text-white"
                : "bg-neutral-100 text-neutral-700 hover:bg-neutral-200",
            )}
          >
            {humanize(role)}
          </button>
        );
      })}
    </div>
  );
}

export function FacetSidebar({
  articles,
  providers,
  providerFilter,
  onProviderSelect,
}: {
  articles: [string, number][];
  providers: [string, number][];
  providerFilter: string | null;
  onProviderSelect: (provider: string | null) => void;
}) {
  return (
    <aside
      aria-label="Saved-asset filters"
      className="hidden w-56 flex-shrink-0 flex-col gap-5 overflow-y-auto md:flex"
    >
      <FacetSection title="By article" items={articles} />
      <FacetSection
        title="Providers"
        items={providers}
        selected={providerFilter}
        onSelect={onProviderSelect}
      />
    </aside>
  );
}

function FacetSection({
  title,
  items,
  selected,
  onSelect,
}: {
  title: string;
  items: [string, number][];
  selected?: string | null;
  onSelect?: (key: string | null) => void;
}) {
  return (
    <section className="flex flex-col gap-2">
      <h3 className="text-xs font-medium uppercase tracking-wide text-neutral-500">
        {title}
      </h3>
      {items.length === 0 ? (
        <p className="text-xs text-neutral-400">None yet.</p>
      ) : (
        <ul className="flex flex-col gap-1">
          {items.map(([key, count]) => {
            const isSelected = selected === key;
            const Tag = onSelect ? "button" : "div";
            return (
              <li key={key}>
                <Tag
                  {...(onSelect
                    ? {
                        type: "button",
                        onClick: () => onSelect(isSelected ? null : key),
                        "aria-pressed": isSelected,
                      }
                    : {})}
                  className={cn(
                    "flex w-full items-center justify-between rounded-sm px-2 py-1 text-left text-xs",
                    isSelected
                      ? "bg-primary-light text-primary"
                      : "text-neutral-700 hover:bg-neutral-50",
                  )}
                >
                  <span className="truncate" title={key}>
                    {key}
                  </span>
                  <span className="text-neutral-500">{count}</span>
                </Tag>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
