/**
 * Static fixtures for the create-article E2E flow (AUTHOR-014).
 *
 * Shapes are lifted from the Vitest fixtures next to the components they
 * feed (`use-article.test.ts`, `outline-review-step.test.tsx`,
 * `generate-article-modal.test.tsx`, `session-progress.test.tsx`) and typed
 * with the app's own contracts so a backend-shape change fails `tsc`
 * before it fails the browser run.
 */
import type { ArticleResponse } from "@/lib/api/articles";
import type { PersistedTopic } from "@/lib/api/trends";
import type { TopicAnalysisResult } from "@/types/api";
import type { Brief } from "@/types/brief";
import type { ArticleOutline, ResearchSessionDetail, SessionStatus } from "@/types/research";
import type { UsageSummary } from "@/types/usage";

export const SESSION_ID = "sess-e2e-1";
export const ARTICLE_ID = "art-e2e-001";
export const STARTED_AT = "2026-08-29T10:00:00Z";

/** `GET /settings/domains` item — mirrors `ApiDomain` in `use-topic-discovery.ts`. */
export interface DomainFixture {
  id: string;
  name: string;
  status: "active" | "inactive";
  trend_sources: string[];
  keywords: string[];
  article_count: number;
}

export const DOMAINS: DomainFixture[] = [
  {
    id: "dom-1",
    name: "cybersecurity",
    status: "active",
    trend_sources: ["hackernews"],
    keywords: ["zero trust"],
    article_count: 3,
  },
];

export const TOPIC: PersistedTopic = {
  id: "topic-e2e-1",
  title: "Zero Trust Architecture",
  description: "Why perimeter security is giving way to identity-centric access.",
  source: "hackernews",
  external_url: "https://example.com/zero-trust",
  trend_score: 87.5,
  velocity: 12.3,
  domain: "cybersecurity",
  discovered_at: STARTED_AT,
  composite_score: 0.91,
  rank: 1,
  source_count: 2,
  created_at: STARTED_AT,
  updated_at: STARTED_AT,
};

export const BRIEFS: Brief[] = [
  {
    id: "b1",
    owner_id: "u",
    name: "Saved brief",
    keywords: ["zt"],
    target_audience: "CISOs",
    content_tone: "analytical",
    preferred_angle: "risk",
    content_type: "analysis",
    length_target: "long",
    structural_diagram_mode: "mermaid",
    require_outline_approval: true,
    created_at: STARTED_AT,
    updated_at: STARTED_AT,
  },
];

export const ANALYSIS: TopicAnalysisResult = {
  description: "LLM generated description",
  domain: "cybersecurity",
  keywords: ["zero trust", "identity", "access control"],
  target_audience: "security engineers",
  content_tone: "technical-authoritative",
  preferred_angle: "practical defender playbook",
  suggested_brief: {
    name: "Suggested name",
    content_type: "analysis",
    length_target: "long",
    keywords: [],
    structural_diagram_mode: "illustration",
    require_outline_approval: false,
  },
};

export const OUTLINE: ArticleOutline = {
  title: "Zero Trust Architecture",
  subtitle: "A practical guide",
  content_type: "analysis",
  sections: [
    {
      index: 0,
      title: "Introduction",
      description: "Set the stage",
      key_points: ["point a", "point b"],
      target_word_count: 200,
      relevant_facets: [0],
    },
    {
      index: 1,
      title: "Deep Dive",
      description: "Go deeper",
      key_points: ["point c"],
      target_word_count: 400,
      relevant_facets: [1],
    },
  ],
  total_target_words: 600,
  reasoning: "Because reasons",
};

export function sessionDetail(status: SessionStatus): ResearchSessionDetail {
  return {
    session_id: SESSION_ID,
    topic_id: TOPIC.id,
    status,
    round_count: 1,
    findings_count: 4,
    sources_count: 2,
    embeddings_count: 12,
    topic_title: TOPIC.title,
    duration_seconds: null,
    started_at: STARTED_AT,
    completed_at: null,
    steps: [],
    require_outline_approval: true,
  };
}

export const USAGE: UsageSummary = {
  session_id: SESSION_ID,
  llm_calls: 3,
  input_tokens: 2400,
  output_tokens: 800,
  images: 0,
  cost_usd: 0.019,
  by_operation: [],
};

export const ARTICLE: ArticleResponse = {
  id: ARTICLE_ID,
  title: "Zero Trust Architecture in Practice",
  subtitle: "A practical guide",
  body_markdown:
    "## Getting Started\n\nIdentity is the new perimeter.\n\n## Deep Dive\n\nPolicy engines evaluate every request.",
  summary: "Zero trust replaces perimeter security with per-request verification.",
  key_claims: ["Claim one", "Claim two"],
  content_type: "analysis",
  domain: "cybersecurity",
  ai_generated: true,
  generated_at: STARTED_AT,
  seo: {
    title: "Zero Trust Architecture in Practice",
    description: "A practical guide to zero trust.",
    keywords: ["zero trust"],
    canonical_url: null,
    structured_data: null,
  },
  citations: [
    {
      index: 1,
      title: "Source 1",
      url: "https://example.com/1",
      authors: ["Author"],
      published_at: STARTED_AT,
    },
    { index: 2, title: "Source 2", url: "https://example.com/2", authors: [], published_at: null },
  ],
  visuals: [],
  provenance: {
    research_session_id: TOPIC.id,
    primary_model: "claude-sonnet-4",
    drafting_model: "claude-sonnet-4",
    embedding_model: "all-MiniLM-L6-v2",
    embedding_version: "v2.0",
  },
  authors: ["Cognify AI"],
  status: "draft",
};
