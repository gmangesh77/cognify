import type {
  AgentStep,
  PaginatedResearchSessions,
  ResearchSessionDetail,
  ResearchSessionSummary,
  SessionStatus,
} from "@/types/research";

function makeSteps(statuses: string[], durations: (number | null)[]): AgentStep[] {
  const names = ["plan_research", "web_search", "evaluate", "index_findings", "compile_results"];
  const now = new Date();
  return names.map((name, i) => ({
    step_name: name,
    status: statuses[i] ?? "pending",
    duration_ms: durations[i] ?? null,
    started_at: new Date(now.getTime() - (5 - i) * 60000).toISOString(),
    completed_at: statuses[i] === "complete" ? new Date(now.getTime() - (4 - i) * 60000).toISOString() : null,
  }));
}

export const mockSessions: ResearchSessionSummary[] = [
  {
    session_id: "sess-001",
    topic_id: "topic-001",
    status: "complete",
    round_count: 3,
    findings_count: 12,
    started_at: "2026-03-20T10:00:00Z",
    topic_title: "AI Security Trends 2026",
    duration_seconds: 272,
  },
  {
    session_id: "sess-002",
    topic_id: "topic-002",
    status: "in_progress",
    round_count: 2,
    findings_count: 8,
    started_at: "2026-03-21T09:30:00Z",
    topic_title: "Zero Trust Architecture",
    duration_seconds: 135,
  },
  {
    session_id: "sess-003",
    topic_id: "topic-003",
    status: "failed",
    round_count: 1,
    findings_count: 0,
    started_at: "2026-03-21T08:00:00Z",
    topic_title: "Quantum Computing Risks",
    duration_seconds: 45,
  },
  {
    session_id: "sess-004",
    topic_id: "topic-004",
    status: "planning",
    round_count: 0,
    findings_count: 0,
    started_at: "2026-03-21T11:00:00Z",
    topic_title: "Supply Chain Attacks",
  },
  {
    session_id: "sess-005",
    topic_id: "topic-005",
    status: "complete",
    round_count: 2,
    findings_count: 9,
    started_at: "2026-03-19T14:00:00Z",
    topic_title: "Cloud Security Posture",
    duration_seconds: 198,
  },
  {
    session_id: "sess-006",
    topic_id: "topic-006",
    status: "in_progress",
    round_count: 1,
    findings_count: 4,
    started_at: "2026-03-21T10:15:00Z",
    topic_title: "Ransomware Evolution",
    duration_seconds: 90,
  },
  {
    session_id: "sess-007",
    topic_id: "topic-007",
    status: "complete",
    round_count: 3,
    findings_count: 15,
    started_at: "2026-03-18T16:00:00Z",
    topic_title: "API Security Best Practices",
    duration_seconds: 310,
  },
  {
    session_id: "sess-008",
    topic_id: "topic-008",
    status: "complete",
    round_count: 2,
    findings_count: 7,
    started_at: "2026-03-17T11:30:00Z",
    topic_title: "Insider Threat Detection",
    duration_seconds: 185,
  },
];

export const mockSessionDetails: Record<string, ResearchSessionDetail> = {
  "sess-001": {
    ...mockSessions[0],
    duration_seconds: 272,
    completed_at: "2026-03-20T10:04:32Z",
    steps: makeSteps(
      ["complete", "complete", "complete", "complete", "complete"],
      [1200, 45000, 12000, 8000, 3000],
    ),
  },
  "sess-002": {
    ...mockSessions[1],
    duration_seconds: 135,
    completed_at: null,
    steps: makeSteps(
      ["complete", "complete", "running", "pending", "pending"],
      [1100, 42000, null, null, null],
    ),
  },
  "sess-003": {
    ...mockSessions[2],
    duration_seconds: 45,
    completed_at: "2026-03-21T08:00:45Z",
    steps: makeSteps(
      ["complete", "failed", "pending", "pending", "pending"],
      [1500, null, null, null, null],
    ),
  },
  "sess-004": {
    ...mockSessions[3],
    duration_seconds: null,
    completed_at: null,
    steps: makeSteps(
      ["running", "pending", "pending", "pending", "pending"],
      [null, null, null, null, null],
    ),
  },
  "sess-005": {
    ...mockSessions[4],
    duration_seconds: 198,
    completed_at: "2026-03-19T14:03:18Z",
    steps: makeSteps(
      ["complete", "complete", "complete", "complete", "complete"],
      [900, 38000, 10000, 7500, 2800],
    ),
  },
  "sess-006": {
    ...mockSessions[5],
    duration_seconds: 90,
    completed_at: null,
    steps: makeSteps(
      ["complete", "running", "pending", "pending", "pending"],
      [1300, null, null, null, null],
    ),
  },
  "sess-007": {
    ...mockSessions[6],
    duration_seconds: 310,
    completed_at: "2026-03-18T16:05:10Z",
    steps: makeSteps(
      ["complete", "complete", "complete", "complete", "complete"],
      [1100, 50000, 15000, 9000, 3500],
    ),
  },
  "sess-008": {
    ...mockSessions[7],
    duration_seconds: 185,
    completed_at: "2026-03-17T11:33:05Z",
    steps: makeSteps(
      ["complete", "complete", "complete", "complete", "complete"],
      [1000, 35000, 9000, 6000, 2500],
    ),
  },
};

export function getMockSessions(
  status?: SessionStatus,
  page = 1,
  size = 10,
): PaginatedResearchSessions {
  const filtered = status ? mockSessions.filter((s) => s.status === status) : mockSessions;
  const start = (page - 1) * size;
  return {
    items: filtered.slice(start, start + size),
    total: filtered.length,
    page,
    size,
  };
}
