"use client";

import { useEffect, useMemo, useState } from "react";
import { cn } from "@/lib/utils";
import { fetchSavedAssets } from "@/lib/api/visuals";
import type {
  SavedAssetItem,
  SavedAssetsResponse,
} from "@/types/visuals";

/**
 * Saved Asset Gallery modal (Pencil Screen 5 `SL2pb`).
 *
 * Shows every previously rendered image so editors can pick one to re-use
 * across articles. Filterable by role / style / provider / source article
 * via the sidebar facets; sortable by recency. Closes on Escape or
 * backdrop click via the host modal wrapper.
 *
 * The component is presentation + data-loading; the host page owns the
 * "open / close" lifecycle and the "select asset" callback.
 */

export interface SavedAssetGalleryProps {
  open: boolean;
  onClose: () => void;
  onSelect?: (asset: SavedAssetItem) => void;
  className?: string;
}

const ROLE_FILTERS = ["hero", "feature_card", "concept", "quote_card"];

export function SavedAssetGallery({
  open,
  onClose,
  onSelect,
  className,
}: SavedAssetGalleryProps) {
  const [data, setData] = useState<SavedAssetsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [roleFilter, setRoleFilter] = useState<string | null>(null);
  const [providerFilter, setProviderFilter] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchSavedAssets({
      role_style: roleFilter ?? undefined,
      provider: providerFilter ?? undefined,
    })
      .then((res) => {
        if (!cancelled) setData(res);
      })
      .catch((err) => {
        if (!cancelled) {
          const msg = err instanceof Error ? err.message : "Load failed";
          setError(msg);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [open, roleFilter, providerFilter]);

  const facetEntries = useMemo(() => {
    if (!data) return { articles: [], providers: [] };
    const articles = Object.entries(data.facets.by_article).sort(
      (a, b) => b[1] - a[1],
    );
    const providers = Object.entries(data.facets.by_provider).sort(
      (a, b) => b[1] - a[1],
    );
    return { articles, providers };
  }, [data]);

  if (!open) return null;

  return (
    <div
      data-testid="saved-asset-gallery-modal"
      role="dialog"
      aria-modal="true"
      aria-label="Saved Asset Gallery"
      className="fixed inset-0 z-50 flex items-center justify-center bg-neutral-900/40 p-6"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        className={cn(
          "flex h-full max-h-[820px] w-full max-w-6xl flex-col gap-4 overflow-hidden rounded-lg border border-neutral-200 bg-white shadow-lg",
          className,
        )}
      >
        <header className="flex items-start justify-between border-b border-neutral-100 px-6 pb-4 pt-5">
          <div>
            <h2 className="text-xl font-heading font-semibold text-neutral-900">
              Your saved visuals
            </h2>
            <p className="text-xs text-neutral-500">
              {data
                ? `${data.total_count} images · $${data.total_spend_usd.toFixed(2)} spent`
                : "Loading saved visuals…"}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <RoleFilterRail
              selected={roleFilter}
              onSelect={setRoleFilter}
            />
            <button
              type="button"
              onClick={onClose}
              aria-label="Close gallery"
              className="rounded-md p-1 text-neutral-500 hover:bg-neutral-100"
            >
              <span aria-hidden="true">×</span>
            </button>
          </div>
        </header>

        <div className="flex flex-1 gap-6 overflow-hidden px-6 pb-5">
          <FacetSidebar
            articles={facetEntries.articles}
            providers={facetEntries.providers}
            providerFilter={providerFilter}
            onProviderSelect={setProviderFilter}
          />
          <main className="flex-1 overflow-y-auto" aria-busy={loading}>
            {error ? (
              <p role="alert" className="text-xs text-error">
                {error}
              </p>
            ) : null}
            {loading ? (
              <p className="text-sm text-neutral-500">Loading…</p>
            ) : null}
            {!loading && data && data.items.length === 0 ? (
              <EmptyState />
            ) : null}
            {!loading && data && data.items.length > 0 ? (
              <AssetGrid items={data.items} onSelect={onSelect} />
            ) : null}
          </main>
        </div>
      </div>
    </div>
  );
}

function RoleFilterRail({
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

function FacetSidebar({
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

function AssetGrid({
  items,
  onSelect,
}: {
  items: SavedAssetItem[];
  onSelect?: (asset: SavedAssetItem) => void;
}) {
  return (
    <ul
      role="list"
      className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-4"
    >
      {items.map((item) => (
        <li key={`${item.article_id}-${item.spec_id}`}>
          <button
            type="button"
            onClick={() => onSelect?.(item)}
            className="group flex w-full flex-col gap-2 rounded-md border border-neutral-200 bg-white p-2 text-left transition-shadow hover:shadow-md"
          >
            <div
              className="relative w-full overflow-hidden rounded-sm bg-neutral-100"
              style={{ aspectRatio: aspectStyle(item.aspect_ratio) }}
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={item.image_url}
                alt={item.alt_text || item.article_title}
                className="absolute inset-0 h-full w-full object-cover"
                loading="lazy"
              />
            </div>
            <div className="flex flex-col gap-0.5">
              <span className="truncate text-sm font-medium text-neutral-900">
                {humanize(item.role_style)}
                {item.visual_style ? ` · ${humanize(item.visual_style)}` : ""}
              </span>
              <span className="truncate text-xs text-neutral-500">
                {item.article_title}
              </span>
              <span className="flex items-center justify-between text-xs text-neutral-400">
                <span>{item.provider}</span>
                <span>
                  {item.cost_usd !== null
                    ? `$${item.cost_usd.toFixed(3)}`
                    : "—"}
                </span>
              </span>
            </div>
          </button>
        </li>
      ))}
    </ul>
  );
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center gap-2 rounded-md border border-dashed border-neutral-300 bg-neutral-50 p-12 text-sm text-neutral-500">
      <span className="font-medium">No saved visuals yet</span>
      <span className="text-xs">
        Render images via the Visual Studio and they&apos;ll show up here.
      </span>
    </div>
  );
}

function aspectStyle(aspect: string): string {
  const map: Record<string, string> = {
    "16:9": "16 / 9",
    "1:1": "1 / 1",
    "4:3": "4 / 3",
    "3:4": "3 / 4",
    "4:5": "4 / 5",
  };
  return map[aspect] ?? "16 / 9";
}

function humanize(key: string): string {
  return key
    .split("_")
    .map((p) => p[0]!.toUpperCase() + p.slice(1))
    .join(" ");
}
