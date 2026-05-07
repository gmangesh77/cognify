"use client";

import { useRef, useState } from "react";
import { cn } from "@/lib/utils";
import { persistSectionUpdate } from "@/lib/api/content";
import type {
  AnchorViolationEntry,
  SectionUpdateSource,
} from "@/types/content";

/**
 * Inline section markdown editor (VISUAL-011 / Phase 8).
 *
 * Wraps a textarea (intentionally NOT contenteditable for v1 — markdown
 * round-trip on contenteditable is a deep rabbit hole and the handoff
 * brief explicitly scopes Playwright + collaborative editing OUT of
 * Phase 8). The editor exposes:
 *
 * - paragraph-level selection (used by the AI popover to scope rewrites)
 * - manual save → POST `/content/section-update`
 * - 422 anchor-violation surfacing so the editor can fix and re-save
 */

export interface InlineProseEditorProps {
  sectionId: string;
  initialMarkdown: string;
  onPersisted?: (newMarkdown: string, versionId: string) => void;
  onCancel?: () => void;
  onParagraphFocus?: (
    paragraphIndex: number,
    paragraphMarkdown: string,
  ) => void;
  className?: string;
}

interface EditorState {
  busy: boolean;
  error: string | null;
  violations: AnchorViolationEntry[];
}

const INITIAL_STATE: EditorState = {
  busy: false,
  error: null,
  violations: [],
};

const SOURCE: SectionUpdateSource = "manual";

export function InlineProseEditor({
  sectionId,
  initialMarkdown,
  onPersisted,
  onCancel,
  onParagraphFocus,
  className,
}: InlineProseEditorProps) {
  // `key={sectionId}` on the parent remounts the editor when the
  // section switches — that's the canonical React way to reset
  // local state without a setState-in-effect.
  const [draft, setDraft] = useState(initialMarkdown);
  const [state, setState] = useState<EditorState>(INITIAL_STATE);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  function handleSelect() {
    const ta = textareaRef.current;
    if (!ta || !onParagraphFocus) return;
    const cursor = ta.selectionStart ?? 0;
    const { paragraphIndex, paragraphMarkdown } = locateParagraph(draft, cursor);
    onParagraphFocus(paragraphIndex, paragraphMarkdown);
  }

  async function handleSave() {
    setState({ busy: true, error: null, violations: [] });
    try {
      const res = await persistSectionUpdate({
        section_id: sectionId,
        markdown: draft,
        source: SOURCE,
      });
      setState(INITIAL_STATE);
      onPersisted?.(res.persisted_markdown, res.version_id);
    } catch (err) {
      handleSaveError(err);
    }
  }

  function handleSaveError(err: unknown) {
    const violations = extractViolations(err);
    if (violations.length > 0) {
      setState({
        busy: false,
        error: "Edit dropped one or more required image anchors.",
        violations,
      });
      return;
    }
    const msg = err instanceof Error ? err.message : "Save failed";
    setState({ busy: false, error: msg, violations: [] });
  }

  return (
    <section
      role="group"
      aria-label="Inline prose editor"
      data-testid="inline-prose-editor"
      className={cn(
        "flex flex-col gap-3 rounded-lg border border-neutral-200 bg-white p-4 shadow-sm",
        className,
      )}
    >
      <textarea
        ref={textareaRef}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onSelect={handleSelect}
        rows={Math.min(20, Math.max(6, draft.split("\n").length + 1))}
        className="w-full rounded-md border border-neutral-200 bg-neutral-50 px-3 py-2 font-body text-sm leading-7 text-neutral-900 focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/30"
      />

      {state.violations.length > 0 ? (
        <ul
          role="alert"
          data-testid="anchor-violations"
          className="flex flex-col gap-1 rounded-md border border-error/40 bg-error-light/40 p-3 text-xs text-error"
        >
          {state.violations.map((v) => (
            <li key={`${v.kind}:${v.value}`}>{v.message}</li>
          ))}
        </ul>
      ) : null}

      {state.error && state.violations.length === 0 ? (
        <p role="alert" className="text-xs text-error">
          {state.error}
        </p>
      ) : null}

      <footer className="flex items-center justify-end gap-2 border-t border-neutral-100 pt-3">
        {onCancel ? (
          <button
            type="button"
            onClick={onCancel}
            className="inline-flex items-center justify-center rounded-md bg-neutral-100 px-3 py-2 text-xs font-medium text-neutral-700 hover:bg-neutral-200"
          >
            Cancel
          </button>
        ) : null}
        <button
          type="button"
          onClick={handleSave}
          disabled={state.busy || draft === initialMarkdown}
          data-testid="save-prose-edit"
          className="inline-flex items-center justify-center rounded-md bg-primary px-3 py-2 text-xs font-medium text-white hover:bg-primary/90 disabled:opacity-60"
        >
          {state.busy ? "Saving…" : "Save"}
        </button>
      </footer>
    </section>
  );
}

function locateParagraph(
  markdown: string,
  cursor: number,
): { paragraphIndex: number; paragraphMarkdown: string } {
  const paragraphs = markdown.split(/\n{2,}/);
  let traversed = 0;
  for (let i = 0; i < paragraphs.length; i++) {
    const len = paragraphs[i].length + 2; // 2 for the "\n\n" separator
    if (cursor <= traversed + len) {
      return { paragraphIndex: i, paragraphMarkdown: paragraphs[i] };
    }
    traversed += len;
  }
  const last = paragraphs.length - 1;
  return {
    paragraphIndex: Math.max(0, last),
    paragraphMarkdown: paragraphs[Math.max(0, last)] ?? "",
  };
}

function extractViolations(err: unknown): AnchorViolationEntry[] {
  // Axios error shape: err.response.data.detail.violations OR
  //                    err.response.data.error.details (CognifyError)
  type _AxiosLike = {
    response?: {
      status?: number;
      data?: {
        detail?: {
          violations?: AnchorViolationEntry[];
        };
      };
    };
  };
  const e = err as _AxiosLike;
  if (e?.response?.status !== 422) return [];
  return e.response.data?.detail?.violations ?? [];
}
