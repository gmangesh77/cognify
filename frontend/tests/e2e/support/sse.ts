/**
 * SSE frame builders for the mocked `GET /research/sessions/{id}/events`
 * stream (AUTHOR-014).
 *
 * Wire format mirrors `src/models/session_events.py::SessionEvent.to_sse`:
 * `event: <type>\ndata: <json>\n\n`. The frontend reducer switches on the
 * JSON `type` field (the `event:` line is parsed and discarded) and keys
 * step rows by `data.step_id`, so every step event carries the same id as
 * its snapshot row.
 *
 * Each phase body is finite. `useSessionEvents` treats a stream that ends
 * without a terminal `done` as a drop and reconnects after 1 s (any event
 * resets its backoff), so the page keeps re-requesting the stream and picks
 * up whichever phase the mock backend is in — no streaming server needed.
 */
import type { ArticleOutline, SessionEvent, SessionStepRow } from "@/types/research";
import { SESSION_ID, STARTED_AT } from "./create-article-fixtures";

export type Phase =
  | "researching"
  | "awaiting_outline_review"
  | "generating_article"
  | "article_complete";

type StepStatus = "complete" | "running";

const RESEARCH_STEPS = ["plan_research", "research_facet_0", "index_findings"];
const CONTENT_STEPS = [
  "content_outline",
  "content_queries",
  "content_draft",
  "content_validate",
  "content_seo",
];

export function sseFrame(event: SessionEvent): string {
  return `event: ${event.type}\ndata: ${JSON.stringify(event)}\n\n`;
}

function makeEvent(type: SessionEvent["type"], patch: Partial<SessionEvent>): SessionEvent {
  return { type, session_id: SESSION_ID, status: null, step: null, data: {}, ts: STARTED_AT, ...patch };
}

export function stepRow(
  stepName: string,
  status: StepStatus,
  outputData: Record<string, unknown> = {},
): SessionStepRow {
  const finished = status === "complete";
  return {
    id: `step-${stepName}`,
    step_name: stepName,
    status,
    started_at: STARTED_AT,
    completed_at: finished ? STARTED_AT : null,
    duration_ms: finished ? 1500 : null,
    output_data: outputData,
  };
}

function completeRows(names: string[]): SessionStepRow[] {
  return names.map((name) => stepRow(name, "complete"));
}

function snapshot(status: string, steps: SessionStepRow[]): string {
  return sseFrame(makeEvent("snapshot", { status, data: { steps } }));
}

/** Research done, outline being generated, then the gate opens. */
function researchStream(): string {
  const steps = [...completeRows(RESEARCH_STEPS), stepRow("content_outline", "running")];
  const outlineDone = makeEvent("step_done", {
    status: "complete",
    step: "content_outline",
    data: { step_id: "step-content_outline", duration_ms: 2100 },
  });
  const gate = makeEvent("status_changed", { status: "awaiting_outline_review" });
  return snapshot("researching", steps) + sseFrame(outlineDone) + sseFrame(gate);
}

function outlineReviewStream(): string {
  const steps = [...completeRows(RESEARCH_STEPS), stepRow("content_outline", "complete")];
  return snapshot("awaiting_outline_review", steps);
}

/** Drafting section 1 of N — `current_section` comes from the (possibly edited) outline. */
function draftingStream(outline: ArticleOutline): string {
  const progress = {
    sections_done: 1,
    sections_total: outline.sections.length,
    current_section: outline.sections[0]?.title ?? "",
  };
  const steps = [
    ...completeRows(RESEARCH_STEPS),
    ...completeRows(["content_outline", "content_queries"]),
    stepRow("content_draft", "running", progress),
  ];
  const tick = makeEvent("step_progress", {
    status: "running",
    step: "content_draft",
    data: { step_id: "step-content_draft", ...progress },
  });
  return snapshot("generating_article", steps) + sseFrame(tick);
}

function completeStream(): string {
  const steps = completeRows([...RESEARCH_STEPS, ...CONTENT_STEPS]);
  return snapshot("article_complete", steps) + sseFrame(makeEvent("done", { status: "article_complete" }));
}

export function streamBodyFor(phase: Phase, outline: ArticleOutline): string {
  switch (phase) {
    case "researching":
      return researchStream();
    case "awaiting_outline_review":
      return outlineReviewStream();
    case "generating_article":
      return draftingStream(outline);
    case "article_complete":
      return completeStream();
  }
}
