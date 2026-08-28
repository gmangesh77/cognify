"use client";

import { aspectStyle, humanize } from "@/lib/visuals/savedAssetFormat";
import type { SavedAssetItem } from "@/types/visuals";

/** Asset grid + empty state of the Saved Asset Gallery (INFRA-008 split). */

export function AssetGrid({
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

export function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center gap-2 rounded-md border border-dashed border-neutral-300 bg-neutral-50 p-12 text-sm text-neutral-500">
      <span className="font-medium">No saved visuals yet</span>
      <span className="text-xs">
        Render images via the Visual Studio and they&apos;ll show up here.
      </span>
    </div>
  );
}
