"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { getAccessToken } from "@/lib/api/client";
import { humanizeStreamUrl } from "@/lib/api/content";
import { changeIds, resolveSegments } from "@/lib/content/resolve-segments";
import { consumeSse } from "@/lib/sse/consume-sse";
import type { HumanizeDoneEvent, HumanizePassEvent } from "@/types/content";

export type HumanizeStreamStatus = "idle" | "streaming" | "done" | "error";

export interface UseHumanizeStreamArgs {
  sectionId: string;
  currentMarkdown: string;
}

interface StreamState {
  status: HumanizeStreamStatus;
  passes: HumanizePassEvent[];
  done: HumanizeDoneEvent | null;
  error: string | null;
}

const IDLE: StreamState = { status: "idle", passes: [], done: null, error: null };

function applyEvent(state: StreamState, type: string, data: unknown): StreamState {
  if (type === "pass") {
    return { ...state, passes: [...state.passes, data as HumanizePassEvent] };
  }
  if (type === "done") {
    return { ...state, status: "done", done: data as HumanizeDoneEvent };
  }
  if (type === "error") {
    const msg = (data as { message?: string } | null)?.message ?? "Humanize failed";
    return { ...state, status: "error", error: msg };
  }
  return state;
}

/**
 * Drives `POST /content/humanize-preview/stream` (AUTHOR-009).
 *
 * `run()` streams pass events; on `done` every changed sentence starts
 * accepted (design decision) and `rejected` tracks opt-outs.
 * `resolvedMarkdown` is what the parent stages into the editor.
 */
export function useHumanizeStream({ sectionId, currentMarkdown }: UseHumanizeStreamArgs) {
  const [state, setState] = useState<StreamState>(IDLE);
  const [rejected, setRejected] = useState<ReadonlySet<string>>(new Set());
  const controller = useRef<AbortController | null>(null);

  const cancel = useCallback(() => {
    controller.current?.abort();
    controller.current = null;
    setState(IDLE);
    setRejected(new Set());
  }, []);

  useEffect(() => () => controller.current?.abort(), []);

  const onEvent = useCallback((type: string, data: unknown) => {
    if (type === "done") setRejected(new Set());
    setState((s) => applyEvent(s, type, data));
  }, []);

  const run = useCallback(() => {
    controller.current?.abort();
    const ctrl = new AbortController();
    controller.current = ctrl;
    setRejected(new Set());
    setState({ ...IDLE, status: "streaming" });
    consumeSse(humanizeStreamUrl(), {
      method: "POST",
      body: { section_id: sectionId, current_markdown: currentMarkdown },
      token: getAccessToken(),
      signal: ctrl.signal,
      onEvent,
    })
      .then(() => {
        if (ctrl.signal.aborted) return;
        setState((s) =>
          s.status === "streaming" ? { ...s, status: "error", error: "Stream ended early" } : s,
        );
      })
      .catch((err: unknown) => {
        if (ctrl.signal.aborted) return;
        const msg = err instanceof Error ? err.message : "Humanize failed";
        setState((s) => ({ ...s, status: "error", error: msg }));
      });
  }, [sectionId, currentMarkdown, onEvent]);

  const toggle = useCallback((id: string) => {
    setRejected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);
  const acceptAll = useCallback(() => setRejected(new Set()), []);
  const rejectAll = useCallback(
    () => setRejected(new Set(state.done ? changeIds(state.done.segments) : [])),
    [state.done],
  );

  const resolvedMarkdown = useMemo(
    () => (state.done ? resolveSegments(state.done.segments, rejected) : null),
    [state.done, rejected],
  );

  return {
    ...state,
    rejected,
    resolvedMarkdown,
    run,
    cancel,
    reset: cancel,
    toggle,
    acceptAll,
    rejectAll,
  };
}
