import type { SessionEvent, SessionStatus, SessionStepRow } from "@/types/research";

export interface SessionSectionsProgress {
  done: number;
  total: number;
  current?: string;
}

export interface SessionEventsState {
  status: SessionStatus | null;
  steps: SessionStepRow[];
  sections: SessionSectionsProgress | null;
  connection: "connecting" | "live" | "closed" | "error";
  error: string | null;
}

export const initialSessionEventsState: SessionEventsState = {
  status: null,
  steps: [],
  sections: null,
  connection: "connecting",
  error: null,
};

export type SessionEventsAction =
  | { kind: "sse"; event: SessionEvent }
  | { kind: "live" }
  | { kind: "connection_error"; message: string };

function stepIdOf(event: SessionEvent): string {
  const id = event.data.step_id;
  return typeof id === "string" ? id : `${event.step ?? "step"}-${event.ts}`;
}

function upsertStep(
  steps: SessionStepRow[],
  id: string,
  patch: Partial<SessionStepRow>,
  fallback: SessionStepRow,
): SessionStepRow[] {
  const idx = steps.findIndex((s) => s.id === id);
  if (idx === -1) return [...steps, { ...fallback, ...patch }];
  const next = [...steps];
  next[idx] = { ...next[idx], ...patch };
  return next;
}

function applyStepStarted(state: SessionEventsState, event: SessionEvent): SessionEventsState {
  const id = stepIdOf(event);
  const status = event.status ?? "running";
  const fallback: SessionStepRow = {
    id,
    step_name: event.step ?? "",
    status,
    started_at: event.ts,
    completed_at: null,
    duration_ms: null,
    output_data: {},
  };
  return {
    ...state,
    steps: upsertStep(state.steps, id, { status, step_name: event.step ?? "" }, fallback),
  };
}

function applyStepProgress(state: SessionEventsState, event: SessionEvent): SessionEventsState {
  const id = stepIdOf(event);
  const existing = state.steps.find((s) => s.id === id);
  const fallback: SessionStepRow = {
    id,
    step_name: event.step ?? "",
    status: "running",
    started_at: event.ts,
    completed_at: null,
    duration_ms: null,
    output_data: event.data,
  };
  const steps = upsertStep(
    state.steps,
    id,
    { output_data: { ...(existing?.output_data ?? {}), ...event.data } },
    fallback,
  );
  const sections =
    event.step === "content_draft"
      ? {
          done: Number(event.data.sections_done ?? 0),
          total: Number(event.data.sections_total ?? 0),
          current:
            typeof event.data.current_section === "string"
              ? event.data.current_section
              : undefined,
        }
      : state.sections;
  return { ...state, steps, sections };
}

function applyStepFinished(
  state: SessionEventsState,
  event: SessionEvent,
  status: string,
): SessionEventsState {
  const id = stepIdOf(event);
  const patch: Partial<SessionStepRow> = { status };
  if (typeof event.data.duration_ms === "number") patch.duration_ms = event.data.duration_ms;
  if (typeof event.data.completed_at === "string") patch.completed_at = event.data.completed_at;
  const fallback: SessionStepRow = {
    id,
    step_name: event.step ?? "",
    status,
    started_at: event.ts,
    completed_at: patch.completed_at ?? null,
    duration_ms: patch.duration_ms ?? null,
    output_data: {},
  };
  return { ...state, steps: upsertStep(state.steps, id, patch, fallback) };
}

function applySessionEvent(state: SessionEventsState, event: SessionEvent): SessionEventsState {
  switch (event.type) {
    case "snapshot": {
      const steps = Array.isArray(event.data.steps)
        ? (event.data.steps as SessionStepRow[])
        : state.steps;
      return { ...state, steps, status: (event.status as SessionStatus | null) ?? state.status };
    }
    case "step_started":
      return applyStepStarted(state, event);
    case "step_progress":
      return applyStepProgress(state, event);
    case "step_done":
      return applyStepFinished(state, event, event.status ?? "complete");
    case "step_failed":
      return applyStepFinished(state, event, event.status ?? "failed");
    case "status_changed":
      return { ...state, status: (event.status as SessionStatus | null) ?? state.status };
    case "done":
      return {
        ...state,
        status: (event.status as SessionStatus | null) ?? state.status,
        connection: "closed",
      };
    case "error":
      return {
        ...state,
        connection: "error",
        error:
          typeof event.data.message === "string" ? event.data.message : "Session stream error",
      };
    case "keepalive":
    default:
      return state;
  }
}

export function sessionEventsReducer(
  state: SessionEventsState,
  action: SessionEventsAction,
): SessionEventsState {
  switch (action.kind) {
    case "live":
      return state.connection === "closed"
        ? state
        : { ...state, connection: "live", error: null };
    case "connection_error":
      return { ...state, connection: "error", error: action.message };
    case "sse":
      return applySessionEvent(state, action.event);
    default:
      return state;
  }
}
