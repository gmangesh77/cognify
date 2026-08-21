/**
 * TypeScript mirrors of the per-section content editing API
 * (VISUAL-011 / Phase 8). The Python source of truth lives in
 * `src/api/routers/content.py` and `src/services/content/section_rewriter.py`.
 *
 * Tone preset names are server-side instruction templates — the
 * frontend only ever ships the preset name. Banned-pattern guards
 * and persona register expansion happen on the backend.
 */

export type RewriteScope = "paragraph" | "section";

export type TonePreset =
  | "shorter"
  | "more_concrete"
  | "more_conversational"
  | "more_authoritative";

export type WordDiffKind = "equal" | "insert" | "delete" | "replace";

export interface WordDiffEntry {
  kind: WordDiffKind;
  before: string;
  after: string;
}

export interface SectionRewriteRequest {
  section_id: string;
  instruction: string;
  scope?: RewriteScope;
  paragraph_index?: number;
  current_markdown?: string;
  audience_persona?: string;
}

export interface SectionRewriteResponse {
  section_id: string;
  markdown_fragment: string;
  diff: WordDiffEntry[];
  model: string;
  prompt_used: string;
  instruction: string;
  tokens_input: number | null;
  tokens_output: number | null;
  usd: number | null;
}

export type SectionUpdateSource =
  | "manual"
  | "ai"
  | "tone_preset"
  | "restore"
  | "regenerate";

export interface SectionUpdateRequest {
  section_id: string;
  markdown: string;
  source?: SectionUpdateSource;
  instruction?: string;
}

export interface SectionUpdateResponse {
  section_id: string;
  version_id: string;
  persisted_markdown: string;
}

/** AUTHOR-004 — `section_index` is the 0-based H2 (outline) index (L-013). */
export interface SectionRegenerateRequest {
  article_id: string;
  section_index: number;
  instruction?: string | null;
}

/**
 * Mirrors `SectionRegenerateResponse` in `src/api/routers/content_regenerate.py`.
 * `section_id` is `{article_id}:{section_index}` — pass it to
 * `persistSectionUpdate` unchanged.
 */
export interface SectionRegenerateResponse {
  section_id: string;
  section_index: number;
  markdown: string;
  diff: WordDiffEntry[];
  version_id: string;
  model: string;
  word_count: number;
  tokens_input: number | null;
  tokens_output: number | null;
  instruction: string | null;
}

export interface ParagraphToneRequest {
  section_id: string;
  paragraph_index: number;
  preset: TonePreset;
  current_markdown?: string;
  audience_persona?: string;
}

export interface SectionVersionEntry {
  id: string;
  section_id: string;
  section_index: number;
  source: SectionUpdateSource;
  instruction: string | null;
  markdown: string;
  model: string | null;
  tokens_input: number | null;
  tokens_output: number | null;
  usd: number | null;
  created_at: string;
  created_by: string | null;
}

export interface SectionHistoryResponse {
  section_id: string;
  versions: SectionVersionEntry[];
}

export interface SectionRestoreRequest {
  version_id: string;
}

export interface AnchorViolationEntry {
  kind: "spec_id" | "heading_text";
  value: string;
  spec_id: string | null;
  message: string;
}

export interface SlopScoreEntry {
  score: number;
  rating: string;
  violation_count: number;
}

export interface HumanizePreviewRequest {
  section_id: string;
  title?: string;
  current_markdown?: string;
}

export interface HumanizePreviewResponse {
  section_id: string;
  original: string;
  rewritten: string;
  diff: WordDiffEntry[];
  score_before: SlopScoreEntry;
  score_after: SlopScoreEntry;
  llm_called: boolean;
  model: string | null;
}
