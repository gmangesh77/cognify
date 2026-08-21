"use client";

import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";
import {
  fetchSectionHistory,
  restoreSectionVersion,
} from "@/lib/api/content";
import type { SectionVersionEntry } from "@/types/content";

/**
 * Section version history drawer (VISUAL-011 / Phase 8).
 *
 * Lists prior versions newest-first, lets the editor restore any of
 * them. The restore POST round-trips through `/section/{id}/restore`,
 * which re-runs the anchor validator and persists a new version row
 * marked `source = "restore"`.
 */

export interface SectionHistoryDrawerProps {
  sectionId: string;
  open: boolean;
  onClose: () => void;
  onRestored?: (newMarkdown: string, versionId: string) => void;
  className?: string;
}

interface DrawerState {
  loading: boolean;
  error: string | null;
  versions: SectionVersionEntry[];
}

const INITIAL_STATE: DrawerState = {
  loading: false,
  error: null,
  versions: [],
};

export function SectionHistoryDrawer({
  sectionId,
  open,
  onClose,
  onRestored,
  className,
}: SectionHistoryDrawerProps) {
  const [state, setState] = useState<DrawerState>(INITIAL_STATE);
  const [restoring, setRestoring] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setState({ ...INITIAL_STATE, loading: true });
    fetchSectionHistory(sectionId)
      .then((res) => {
        if (cancelled) return;
        setState({ loading: false, error: null, versions: res.versions });
      })
      .catch((err) => {
        if (cancelled) return;
        const msg = err instanceof Error ? err.message : "Failed to load history";
        setState({ loading: false, error: msg, versions: [] });
      });
    return () => {
      cancelled = true;
    };
  }, [open, sectionId]);

  async function handleRestore(versionId: string) {
    setRestoring(versionId);
    try {
      const res = await restoreSectionVersion(sectionId, {
        version_id: versionId,
      });
      onRestored?.(res.persisted_markdown, res.version_id);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Restore failed";
      setState((s) => ({ ...s, error: msg }));
    } finally {
      setRestoring(null);
    }
  }

  if (!open) return null;

  return (
    <aside
      role="dialog"
      aria-label="Section history"
      data-testid="section-history-drawer"
      className={cn(
        "z-30 flex w-[360px] flex-col gap-3 rounded-lg border border-neutral-200 bg-white p-4 shadow-lg",
        className,
      )}
    >
      <header className="flex items-center justify-between gap-3">
        <h3 className="font-heading text-sm font-semibold text-neutral-900">
          Section history
        </h3>
        <button
          type="button"
          onClick={onClose}
          className="text-xs font-medium text-neutral-500 hover:text-neutral-700"
        >
          Close
        </button>
      </header>

      {state.loading ? (
        <p className="text-xs text-neutral-500">Loading versions…</p>
      ) : null}

      {state.error ? (
        <p role="alert" className="text-xs text-error">
          {state.error}
        </p>
      ) : null}

      {!state.loading && state.versions.length === 0 ? (
        <p className="text-xs text-neutral-500">No versions yet.</p>
      ) : null}

      <ul className="flex flex-col gap-2">
        {state.versions.map((v) => (
          <li
            key={v.id}
            data-testid={`history-version-${v.id}`}
            className="flex flex-col gap-1 rounded-md border border-neutral-200 bg-neutral-50 p-3"
          >
            <div className="flex items-center justify-between gap-2">
              <span className="text-xs font-medium text-neutral-600">
                {labelForSource(v.source)}
              </span>
              <span className="text-[11px] text-neutral-500">
                {formatTimestamp(v.created_at)}
              </span>
            </div>
            {v.instruction ? (
              <p className="line-clamp-2 text-xs italic text-neutral-500">
                “{v.instruction}”
              </p>
            ) : null}
            <p className="line-clamp-3 text-xs text-neutral-700">
              {v.markdown.slice(0, 220)}
              {v.markdown.length > 220 ? "…" : ""}
            </p>
            <div className="flex items-center justify-end gap-2 pt-1">
              <button
                type="button"
                onClick={() => handleRestore(v.id)}
                disabled={restoring !== null}
                data-testid={`restore-version-${v.id}`}
                className="inline-flex items-center justify-center rounded-md bg-primary px-2.5 py-1 text-xs font-medium text-white hover:bg-primary/90 disabled:opacity-60"
              >
                {restoring === v.id ? "Restoring…" : "Restore"}
              </button>
            </div>
          </li>
        ))}
      </ul>
    </aside>
  );
}

function labelForSource(source: SectionVersionEntry["source"]): string {
  switch (source) {
    case "ai":
      return "AI rewrite";
    case "manual":
      return "Manual edit";
    case "tone_preset":
      return "Tone preset";
    case "restore":
      return "Restored";
    case "regenerate":
      return "Regenerated";
    default:
      return source;
  }
}

function formatTimestamp(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleString();
  } catch {
    return iso;
  }
}
