import { describe, it, expect } from "vitest";
import {
  sessionEventsReducer,
  initialSessionEventsState,
  type SessionEventsState,
} from "./session-events-reducer";
import type { SessionEvent } from "@/types/research";

function baseEvent(overrides: Partial<SessionEvent>): SessionEvent {
  return {
    type: "keepalive",
    session_id: "s1",
    status: null,
    step: null,
    data: {},
    ts: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

const runningStep = {
  id: "s-1",
  step_name: "plan_research",
  status: "running",
  started_at: "",
  completed_at: null,
  duration_ms: null,
  output_data: {},
};

describe("sessionEventsReducer", () => {
  it("step_started uses the event status verbatim when already complete (controller ruling)", () => {
    const event = baseEvent({
      type: "step_started",
      step: "plan_research",
      status: "complete",
      data: { step_id: "s-1" },
    });
    const next = sessionEventsReducer(initialSessionEventsState, { kind: "sse", event });
    expect(next.steps).toEqual([
      expect.objectContaining({ id: "s-1", step_name: "plan_research", status: "complete" }),
    ]);
  });

  it("step_started falls back to running only when status is null", () => {
    const event = baseEvent({
      type: "step_started",
      step: "plan_research",
      status: null,
      data: { step_id: "s-2" },
    });
    const next = sessionEventsReducer(initialSessionEventsState, { kind: "sse", event });
    expect(next.steps[0].status).toBe("running");
  });

  it("done with a terminal status closes the connection", () => {
    const event = baseEvent({ type: "done", status: "article_complete" });
    const next = sessionEventsReducer(
      { ...initialSessionEventsState, connection: "live" },
      { kind: "sse", event },
    );
    expect(next.connection).toBe("closed");
  });

  it("done with a non-terminal status leaves connection untouched (hook decides whether to reconnect)", () => {
    const event = baseEvent({ type: "done", status: "researching" });
    const next = sessionEventsReducer(
      { ...initialSessionEventsState, connection: "live" },
      { kind: "sse", event },
    );
    expect(next.connection).toBe("live");
    expect(next.status).toBe("researching");
  });

  it("status_changed updates status without touching connection", () => {
    const event = baseEvent({ type: "status_changed", status: "researching" });
    const next = sessionEventsReducer(initialSessionEventsState, { kind: "sse", event });
    expect(next.status).toBe("researching");
    expect(next.connection).toBe("connecting");
  });

  it("step_done marks the matching step complete and merges duration_ms", () => {
    const state: SessionEventsState = { ...initialSessionEventsState, steps: [runningStep] };
    const event = baseEvent({
      type: "step_done",
      step: "plan_research",
      status: "complete",
      data: { step_id: "s-1", duration_ms: 42 },
    });
    const next = sessionEventsReducer(state, { kind: "sse", event });
    expect(next.steps[0]).toMatchObject({ status: "complete", duration_ms: 42 });
  });

  it("step_failed marks the matching step failed", () => {
    const state: SessionEventsState = { ...initialSessionEventsState, steps: [runningStep] };
    const event = baseEvent({
      type: "step_failed",
      step: "plan_research",
      status: "failed",
      data: { step_id: "s-1" },
    });
    const next = sessionEventsReducer(state, { kind: "sse", event });
    expect(next.steps[0].status).toBe("failed");
  });

  it("error sets connection to error with the provided message (backend key: data.error)", () => {
    const event = baseEvent({ type: "error", data: { error: "session not found" } });
    const next = sessionEventsReducer(initialSessionEventsState, { kind: "sse", event });
    expect(next.connection).toBe("error");
    expect(next.error).toBe("session not found");
  });

  it("error falls back to data.message when data.error is absent", () => {
    const event = baseEvent({ type: "error", data: { message: "legacy message" } });
    const next = sessionEventsReducer(initialSessionEventsState, { kind: "sse", event });
    expect(next.error).toBe("legacy message");
  });

  it("error falls back to a generic message when neither data.error nor data.message is present", () => {
    const event = baseEvent({ type: "error", data: {} });
    const next = sessionEventsReducer(initialSessionEventsState, { kind: "sse", event });
    expect(next.error).toBe("Session stream error");
  });

  it("snapshot derives sections from a running content_draft step row", () => {
    const event = baseEvent({
      type: "snapshot",
      status: "generating_article",
      data: {
        steps: [
          {
            id: "cd-1",
            step_name: "content_draft",
            status: "running",
            started_at: "",
            completed_at: null,
            duration_ms: null,
            output_data: { sections_done: 2, sections_total: 5, current_section: "Intro" },
          },
        ],
      },
    });
    const next = sessionEventsReducer(initialSessionEventsState, { kind: "sse", event });
    expect(next.sections).toEqual({ done: 2, total: 5, current: "Intro" });
  });

  it("snapshot with a completed content_draft step clears sections", () => {
    const seeded: SessionEventsState = { ...initialSessionEventsState, sections: { done: 2, total: 5 } };
    const event = baseEvent({
      type: "snapshot",
      status: "article_complete",
      data: {
        steps: [
          {
            id: "cd-1",
            step_name: "content_draft",
            status: "complete",
            started_at: "",
            completed_at: "",
            duration_ms: 1000,
            output_data: { sections_done: 5, sections_total: 5 },
          },
        ],
      },
    });
    const next = sessionEventsReducer(seeded, { kind: "sse", event });
    expect(next.sections).toBeNull();
  });

  it("snapshot with no content_draft row clears sections", () => {
    const seeded: SessionEventsState = { ...initialSessionEventsState, sections: { done: 2, total: 5 } };
    const event = baseEvent({
      type: "snapshot",
      status: "researching",
      data: { steps: [{ ...runningStep, step_name: "plan_research" }] },
    });
    const next = sessionEventsReducer(seeded, { kind: "sse", event });
    expect(next.sections).toBeNull();
  });

  it("step_done for content_draft clears sections", () => {
    const seeded: SessionEventsState = {
      ...initialSessionEventsState,
      sections: { done: 4, total: 5, current: "Conclusion" },
    };
    const event = baseEvent({
      type: "step_done",
      step: "content_draft",
      status: "complete",
      data: { step_id: "cd-1" },
    });
    const next = sessionEventsReducer(seeded, { kind: "sse", event });
    expect(next.sections).toBeNull();
  });

  it("step_failed for content_draft clears sections", () => {
    const seeded: SessionEventsState = {
      ...initialSessionEventsState,
      sections: { done: 1, total: 5 },
    };
    const event = baseEvent({
      type: "step_failed",
      step: "content_draft",
      status: "failed",
      data: { step_id: "cd-1" },
    });
    const next = sessionEventsReducer(seeded, { kind: "sse", event });
    expect(next.sections).toBeNull();
  });

  it("keepalive is a no-op", () => {
    const event = baseEvent({ type: "keepalive" });
    const next = sessionEventsReducer(initialSessionEventsState, { kind: "sse", event });
    expect(next).toBe(initialSessionEventsState);
  });

  it("never downgrades a closed connection: connection_failed is ignored", () => {
    const closed: SessionEventsState = { ...initialSessionEventsState, connection: "closed" };
    const next = sessionEventsReducer(closed, { kind: "connection_failed", message: "boom" });
    expect(next).toBe(closed);
  });

  it("never downgrades a closed connection: reconnecting is ignored", () => {
    const closed: SessionEventsState = { ...initialSessionEventsState, connection: "closed" };
    const next = sessionEventsReducer(closed, { kind: "reconnecting", message: "boom" });
    expect(next).toBe(closed);
  });

  it("never downgrades a closed connection: live is ignored", () => {
    const closed: SessionEventsState = { ...initialSessionEventsState, connection: "closed" };
    const next = sessionEventsReducer(closed, { kind: "live" });
    expect(next).toBe(closed);
  });
});
