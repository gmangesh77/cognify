"use client";

import { useCallback, useEffect, useReducer, useRef, useState } from "react";
import { getAccessToken } from "@/lib/api/client";
import { sessionEventsUrl } from "@/lib/api/research";
import { consumeSse } from "@/lib/sse/consume-sse";
import type { SessionEvent } from "@/types/research";
import { initialSessionEventsState, sessionEventsReducer } from "./session-events-reducer";
import type { SessionEventsAction, SessionEventsState } from "./session-events-reducer";

export type { SessionEventsState } from "./session-events-reducer";

const DEFAULT_MAX_ATTEMPTS = 5;
const DEFAULT_BASE_DELAY_MS = 1000;
const MAX_DELAY_MS = 30000;

export interface UseSessionEventsOptions {
  maxAttempts?: number;
  baseDelayMs?: number;
}

export interface UseSessionEventsResult extends SessionEventsState {
  reconnect: () => void;
}

interface StreamContext {
  sessionId: string;
  controller: AbortController;
  attemptRef: { current: number };
  maxAttempts: number;
  baseDelayMs: number;
  dispatch: (action: SessionEventsAction) => void;
  setTimer: (timer: ReturnType<typeof setTimeout> | undefined) => void;
}

function backoffDelay(attemptIndex: number, baseDelayMs: number): number {
  return Math.min(baseDelayMs * 2 ** attemptIndex, MAX_DELAY_MS);
}

function handleEvent(dispatch: StreamContext["dispatch"], raw: unknown) {
  dispatch({ kind: "live" });
  dispatch({ kind: "sse", event: raw as SessionEvent });
}

function handleFailure(ctx: StreamContext, message: string) {
  ctx.attemptRef.current += 1;
  if (ctx.attemptRef.current >= ctx.maxAttempts) {
    ctx.dispatch({ kind: "connection_failed", message });
    return;
  }
  ctx.dispatch({ kind: "reconnecting", message });
  const delay = backoffDelay(ctx.attemptRef.current - 1, ctx.baseDelayMs);
  ctx.setTimer(setTimeout(() => startStream(ctx), delay));
}

function startStream(ctx: StreamContext) {
  consumeSse(sessionEventsUrl(ctx.sessionId), {
    token: getAccessToken(),
    signal: ctx.controller.signal,
    onEvent: (_type, raw) => handleEvent(ctx.dispatch, raw),
  }).catch((err: unknown) => {
    if (ctx.controller.signal.aborted) return;
    handleFailure(ctx, err instanceof Error ? err.message : "Connection failed");
  });
}

interface BuildStreamContextOptions {
  sessionId: string;
  dispatch: StreamContext["dispatch"];
  limits: Required<UseSessionEventsOptions>;
  attemptRef: { current: number };
  setTimer: StreamContext["setTimer"];
}

function buildStreamContext(o: BuildStreamContextOptions): StreamContext {
  return {
    sessionId: o.sessionId,
    controller: new AbortController(),
    attemptRef: o.attemptRef,
    maxAttempts: o.limits.maxAttempts,
    baseDelayMs: o.limits.baseDelayMs,
    dispatch: o.dispatch,
    setTimer: o.setTimer,
  };
}

export function useSessionEvents(
  sessionId: string | null,
  opts?: UseSessionEventsOptions,
): UseSessionEventsResult {
  const [state, dispatch] = useReducer(sessionEventsReducer, initialSessionEventsState);
  const [generation, setGeneration] = useState(0);
  const attemptRef = useRef(0);
  const maxAttempts = opts?.maxAttempts ?? DEFAULT_MAX_ATTEMPTS;
  const baseDelayMs = opts?.baseDelayMs ?? DEFAULT_BASE_DELAY_MS;

  const reconnect = useCallback(() => setGeneration((g) => g + 1), []);

  useEffect(() => {
    if (!sessionId) return undefined;
    let timer: ReturnType<typeof setTimeout> | undefined;
    attemptRef.current = 0;
    const ctx = buildStreamContext({
      sessionId,
      dispatch,
      limits: { maxAttempts, baseDelayMs },
      attemptRef,
      setTimer: (t) => {
        timer = t;
      },
    });
    startStream(ctx);
    return () => {
      ctx.controller.abort();
      if (timer) clearTimeout(timer);
    };
  }, [sessionId, generation, maxAttempts, baseDelayMs]);

  return { ...state, reconnect };
}
