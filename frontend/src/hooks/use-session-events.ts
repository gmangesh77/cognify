"use client";

import { useCallback, useEffect, useReducer, useRef, useState } from "react";
import { getAccessToken } from "@/lib/api/client";
import { sessionEventsUrl } from "@/lib/api/research";
import { consumeSse } from "@/lib/sse/consume-sse";
import type { SessionEvent } from "@/types/research";
import {
  initialSessionEventsState,
  sessionEventsReducer,
} from "./session-events-reducer";
import type { SessionEventsState } from "./session-events-reducer";

export type { SessionEventsState } from "./session-events-reducer";

const BASE_DELAY_MS = 1000;
const MAX_DELAY_MS = 30000;
const MAX_ATTEMPTS = 5;

function backoffDelay(attempt: number): number {
  return Math.min(BASE_DELAY_MS * 2 ** attempt, MAX_DELAY_MS);
}

export interface UseSessionEventsResult extends SessionEventsState {
  reconnect: () => void;
}

export function useSessionEvents(sessionId: string | null): UseSessionEventsResult {
  const [state, dispatch] = useReducer(sessionEventsReducer, initialSessionEventsState);
  const [generation, setGeneration] = useState(0);
  const attemptRef = useRef(0);

  const reconnect = useCallback(() => setGeneration((g) => g + 1), []);

  useEffect(() => {
    if (!sessionId) return undefined;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    attemptRef.current = 0;

    const onEvent = (_type: string, raw: unknown) => {
      dispatch({ kind: "live" });
      dispatch({ kind: "sse", event: raw as SessionEvent });
    };

    function scheduleRetry(message: string) {
      dispatch({ kind: "connection_error", message });
      if (attemptRef.current >= MAX_ATTEMPTS) return;
      const delay = backoffDelay(attemptRef.current);
      attemptRef.current += 1;
      timer = setTimeout(run, delay);
    }

    function run() {
      consumeSse(sessionEventsUrl(sessionId as string), {
        token: getAccessToken(),
        signal: controller.signal,
        onEvent,
      }).catch((err: unknown) => {
        if (controller.signal.aborted) return;
        scheduleRetry(err instanceof Error ? err.message : "Connection failed");
      });
    }

    run();

    return () => {
      controller.abort();
      if (timer) clearTimeout(timer);
    };
  }, [sessionId, generation]);

  return { ...state, reconnect };
}
