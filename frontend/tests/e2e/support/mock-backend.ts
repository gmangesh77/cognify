/**
 * In-browser mock of the Cognify API for the create-article E2E flow
 * (AUTHOR-014). One `page.route("**\/api\/v1\/**")` dispatcher backed by a
 * tiny phase machine; every call is recorded so specs can assert request
 * contracts (session body, edited outline) and not just rendered text.
 *
 * Never fulfils a 401 — `apiClient`'s interceptor would redirect the whole
 * page to `/login`. Unmatched calls get a JSON 404 so a missing mock shows
 * up as a visible failure rather than a hang against a real server.
 */
import type { Page, Request, Route } from "@playwright/test";
import type { ArticleOutline } from "@/types/research";
import {
  ANALYSIS,
  ARTICLE,
  ARTICLE_ID,
  BRIEFS,
  DOMAINS,
  OUTLINE,
  SESSION_ID,
  STARTED_AT,
  TOPIC,
  USAGE,
  sessionDetail,
} from "./create-article-fixtures";
import { streamBodyFor } from "./sse";
import type { Phase } from "./sse";

export type { Phase } from "./sse";

export interface RecordedCall {
  method: string;
  path: string;
  body: unknown;
}

interface Reply {
  status?: number;
  body?: unknown;
  contentType?: string;
}

export class MockBackend {
  phase: Phase = "researching";
  outline: ArticleOutline = structuredClone(OUTLINE);
  readonly calls: RecordedCall[] = [];

  /** Test-controlled transition: drafting finished, article persisted. */
  completeArticle(): void {
    this.phase = "article_complete";
  }

  callsTo(method: string, path: string): RecordedCall[] {
    return this.calls.filter((c) => c.method === method && c.path === path);
  }
}

type Handler = (backend: MockBackend, call: RecordedCall) => Reply;

const SESSION = `/research/sessions/${SESSION_ID}`;

function outlineReply(backend: MockBackend): Reply {
  return {
    body: {
      draft_id: "draft-e2e-1",
      session_id: SESSION_ID,
      status: "outline_complete",
      outline: backend.outline,
    },
  };
}

/** Serve the current phase; the research phase advances itself like the real pipeline. */
function eventsReply(backend: MockBackend): Reply {
  const body = streamBodyFor(backend.phase, backend.outline);
  if (backend.phase === "researching") backend.phase = "awaiting_outline_review";
  return { contentType: "text/event-stream", body };
}

function saveOutline(backend: MockBackend, call: RecordedCall): Reply {
  backend.outline = call.body as ArticleOutline;
  return outlineReply(backend);
}

function approveOutline(backend: MockBackend): Reply {
  backend.phase = "generating_article";
  return { status: 202, body: { session_id: SESSION_ID, status: backend.phase } };
}

const ROUTES: Array<[string, string, Handler]> = [
  ["GET", "/settings/domains", () => ({ body: { items: DOMAINS } })],
  ["GET", "/topics", () => ({ body: { items: [TOPIC], total: 1, page: 1, size: 50 } })],
  ["GET", "/briefs", () => ({ body: BRIEFS })],
  ["POST", "/topics/analyze", () => ({ body: ANALYSIS })],
  [
    "POST",
    "/research/sessions",
    () => ({ status: 201, body: { session_id: SESSION_ID, status: "planning", started_at: STARTED_AT } }),
  ],
  ["GET", SESSION, (b) => ({ body: sessionDetail(b.phase) })],
  ["GET", `${SESSION}/usage`, () => ({ body: USAGE })],
  ["GET", `${SESSION}/events`, eventsReply],
  ["GET", `${SESSION}/outline`, outlineReply],
  ["PUT", `${SESSION}/outline`, saveOutline],
  ["POST", `${SESSION}/outline/approve`, approveOutline],
  ["GET", `${SESSION}/article`, () => ({ body: { article_id: ARTICLE_ID } })],
  ["GET", `/articles/${ARTICLE_ID}`, () => ({ body: ARTICLE })],
  ["GET", `/articles/${ARTICLE_ID}/usage`, () => ({ body: USAGE })],
  ["GET", "/settings/general", () => ({ body: {} })],
];

function apiPath(request: Request): string {
  return new URL(request.url()).pathname.replace(/^.*\/api\/v1/, "");
}

/** Only needed when a reused dev server still points at http://localhost:8000. */
function corsHeaders(request: Request): Record<string, string> {
  return {
    "access-control-allow-origin": request.headers()["origin"] ?? "*",
    "access-control-allow-credentials": "true",
    "access-control-allow-headers": "accept, authorization, content-type, x-request-id",
    "access-control-allow-methods": "GET,POST,PUT,PATCH,DELETE,OPTIONS",
  };
}

function parseBody(request: Request): unknown {
  try {
    return request.postDataJSON();
  } catch {
    return null;
  }
}

function resolve(backend: MockBackend, call: RecordedCall): Reply {
  const route = ROUTES.find(([method, path]) => method === call.method && path === call.path);
  if (!route) return { status: 404, body: { detail: `e2e: unmocked ${call.method} ${call.path}` } };
  return route[2](backend, call);
}

async function dispatch(backend: MockBackend, route: Route): Promise<void> {
  const request = route.request();
  const headers = corsHeaders(request);
  if (request.method() === "OPTIONS") return route.fulfill({ status: 204, headers });
  const call = { method: request.method(), path: apiPath(request), body: parseBody(request) };
  backend.calls.push(call);
  const reply = resolve(backend, call);
  const body = typeof reply.body === "string" ? reply.body : JSON.stringify(reply.body ?? null);
  return route.fulfill({
    status: reply.status ?? 200,
    headers,
    contentType: reply.contentType ?? "application/json",
    body,
  });
}

export async function installMockBackend(page: Page): Promise<MockBackend> {
  const backend = new MockBackend();
  await page.route("**/api/v1/**", (route) => dispatch(backend, route));
  return backend;
}
