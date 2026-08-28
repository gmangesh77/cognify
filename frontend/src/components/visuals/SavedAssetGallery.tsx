"use client";

import { useEffect, useMemo, useState } from "react";
import { cn } from "@/lib/utils";
import { fetchSavedAssets } from "@/lib/api/visuals";
import type {
  SavedAssetItem,
  SavedAssetsResponse,
} from "@/types/visuals";
import { FacetSidebar, RoleFilterRail } from "./SavedAssetFacets";
import { AssetGrid, EmptyState } from "./SavedAssetGrid";

/**
 * Saved Asset Gallery modal (Pencil Screen 5 `SL2pb`).
 *
 * Shows every previously rendered image so editors can pick one to re-use
 * across articles. Filterable by role / style / provider / source article
 * via the sidebar facets; sortable by recency. Closes on Escape or
 * backdrop click via the host modal wrapper.
 *
 * The component is presentation + data-loading; the host page owns the
 * "open / close" lifecycle and the "select asset" callback. Facet rails and
 * the grid live in `SavedAssetFacets.tsx` / `SavedAssetGrid.tsx`
 * (INFRA-008 split).
 */

export interface SavedAssetGalleryProps {
  open: boolean;
  onClose: () => void;
  onSelect?: (asset: SavedAssetItem) => void;
  className?: string;
}

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
    // Defer the loading/error reset so it doesn't fire synchronously
    // inside the effect body (react-hooks/set-state-in-effect). The
    // fetch then runs and resolves on its own microtask.
    void (async () => {
      if (cancelled) return;
      setLoading(true);
      setError(null);
      try {
        const res = await fetchSavedAssets({
          role_style: roleFilter ?? undefined,
          provider: providerFilter ?? undefined,
        });
        if (!cancelled) setData(res);
      } catch (err) {
        if (!cancelled) {
          const msg = err instanceof Error ? err.message : "Load failed";
          setError(msg);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
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
