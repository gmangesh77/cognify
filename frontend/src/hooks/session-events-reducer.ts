import type { SessionEvent, SessionStatus, SessionStepRow } from "@/types/research";

export interface SessionSectionsProgress {
  done: number;
  total: number;
  current?: string;
}

export type SessionConnectionState = "connecting" | "live" | "reconnecting" | "closed" | "error";

export interface SessionEventsState {
  status: SessionStatus | null;
  steps: SessionStepRow[];
  sections: SessionSectionsProgress | null;
  connection: SessionConnectionState;
  error: string | null;
}

// Mirrors src/models/session_events.py TERMINAL_STATUSES.
export const TERMINAL_SESSION_STATUSES: ReadonlySet<string> = new Set([
  "article_complete",
  "article_failed",
  "failed",
  "cancelled",
  "completed",
]);

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
  | { kind: "reconnecting"; message: string }
  | { kind: "connection_failed"; message: string };

function stepIdOf(event: SessionEvent): string {
  const id = event.data.step_id;
  return typeof id === "string" ? id : `${event.step ?? "step"}-${event.ts}`;
}

function makeFallbackStep(
  id: string,
  event: SessionEvent,
  status: string,
  outputData: Record<string, unknown> = {},
): SessionStepRow {
  return {
    id,
    step_name: event.step ?? "",
    status,
    started_at: event.ts,
    completed_at: null,
    duration_ms: null,
    output_data: outputData,
  };
}

interface UpsertStepOptions {
  steps: SessionStepRow[];
  id: string;
  patch: Partial<SessionStepRow>;
  fallback: SessionStepRow;
}

function upsertStep({ steps, id, patch, fallback }: UpsertStepOptions): SessionStepRow[] {
  const idx = steps.findIndex((s) => s.id === id);
  if (idx === -1) return [...steps, { ...fallback, ...patch }];
  const next = [...steps];
  next[idx] = { ...next[idx], ...patch };
  return next;
}

function applyStepStarted(state: SessionEventsState, event: SessionEvent): SessionEventsState {
  const id = stepIdOf(event);
  const status = event.status ?? "running";
  const fallback = makeFallbackStep(id, event, status);
  const patch = { status, step_name: event.step ?? "" };
  return { ...state, steps: upsertStep({ steps: state.steps, id, patch, fallback }) };
}

function computeSectionsProgress(
  state: SessionEventsState,
  event: SessionEvent,
): SessionSectionsProgress | null {
  if (event.step !== "content_draft") return state.sections;
  return {
    done: Number(event.data.sections_done ?? 0),
    total: Number(event.data.sections_total ?? 0),
    current:
      typeof event.data.current_section === "string" ? event.data.current_section : undefined,
  };
}

function applyStepProgress(state: SessionEventsState, event: SessionEvent): SessionEventsState {
  const id = stepIdOf(event);
  const existing = state.steps.find((s) => s.id === id);
  const outputData = { ...(existing?.output_data ?? {}), ...event.data };
  const fallback = makeFallbackStep(id, event, "running", outputData);
  const patch = { output_data: outputData };
  const steps = upsertStep({ steps: state.steps, id, patch, fallback });
  return { ...state, steps, sections: computeSectionsProgress(state, event) };
}

function buildFinishedPatch(event: SessionEvent, status: string): Partial<SessionStepRow> {
  const patch: Partial<SessionStepRow> = { status };
  if (typeof event.data.duration_ms === "number") patch.duration_ms = event.data.duration_ms;
  if (typeof event.data.completed_at === "string") patch.completed_at = event.data.completed_at;
  return patch;
}

function applyStepFinished(
  state: SessionEventsState,
  event: SessionEvent,
  status: string,
): SessionEventsState {
  const id = stepIdOf(event);
  const patch = buildFinishedPatch(event, status);
  const fallback = { ...makeFallbackStep(id, event, status), ...patch };
  const steps = upsertStep({ steps: state.steps, id, patch, fallback });
  const sections = event.step === "content_draft" ? null : state.sections;
  return { ...state, steps, sections };
}

function sectionsFromSteps(steps: SessionStepRow[]): SessionSectionsProgress | null {
  const row = steps.find((s) => s.step_name === "content_draft");
  if (!row || row.status !== "running") return null;
  const output = row.output_data ?? {};
  if (output.sections_done === undefined && output.sections_total === undefined) return null;
  return {
    done: Number(output.sections_done ?? 0),
    total: Number(output.sections_total ?? 0),
    current: typeof output.current_section === "string" ? output.current_section : undefined,
  };
}

function handleSnapshot(state: SessionEventsState, event: SessionEvent): SessionEventsState {
  const steps = Array.isArray(event.data.steps)
    ? (event.data.steps as SessionStepRow[])
    : state.steps;
  return {
    ...state,
    steps,
    status: (event.status as SessionStatus | null) ?? state.status,
    sections: sectionsFromSteps(steps),
  };
}

function handleStatusChanged(state: SessionEventsState, event: SessionEvent): SessionEventsState {
  return { ...state, status: (event.status as SessionStatus | null) ?? state.status };
}

function handleDone(state: SessionEventsState, event: SessionEvent): SessionEventsState {
  const status = (event.status as SessionStatus | null) ?? state.status;
  // A `done` with a non-terminal status (e.g. the server's `max_seconds`
  // safety valve) is not a real end-of-session — leave `connection` alone so
  // the hook's reconnect-on-stream-end logic isn't blocked by the "closed"
  // sticky guard below.
  const terminal = !!status && TERMINAL_SESSION_STATUSES.has(status);
  return { ...state, status, connection: terminal ? "closed" : state.connection };
}

function handleError(state: SessionEventsState, event: SessionEvent): SessionEventsState {
  const message = event.data.error ?? event.data.message;
  return {
    ...state,
    connection: "error",
    error: typeof message === "string" ? message : "Session stream error",
  };
}

function handleStepDone(state: SessionEventsState, event: SessionEvent): SessionEventsState {
  return applyStepFinished(state, event, event.status ?? "complete");
}

function handleStepFailed(state: SessionEventsState, event: SessionEvent): SessionEventsState {
  return applyStepFinished(state, event, event.status ?? "failed");
}

type EventHandler = (state: SessionEventsState, event: SessionEvent) => SessionEventsState;

const eventHandlers: Partial<Record<SessionEvent["type"], EventHandler>> = {
  snapshot: handleSnapshot,
  step_started: applyStepStarted,
  step_progress: applyStepProgress,
  step_done: handleStepDone,
  step_failed: handleStepFailed,
  status_changed: handleStatusChanged,
  done: handleDone,
  error: handleError,
};

function applySessionEvent(state: SessionEventsState, event: SessionEvent): SessionEventsState {
  const handler = eventHandlers[event.type];
  return handler ? handler(state, event) : state;
}

export function sessionEventsReducer(
  state: SessionEventsState,
  action: SessionEventsAction,
): SessionEventsState {
  if (state.connection === "closed" && action.kind !== "sse") return state;
  switch (action.kind) {
    case "live":
      return { ...state, connection: "live", error: null };
    case "reconnecting":
      return { ...state, connection: "reconnecting", error: action.message };
    case "connection_failed":
      return { ...state, connection: "error", error: action.message };
    case "sse":
      return applySessionEvent(state, action.event);
    default:
      return state;
  }
}
