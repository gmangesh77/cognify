// Persona voice engine types (AUTHOR-011). Mirrors src/api/schemas/personas.py
// and src/models/persona.py verbatim — snake_case fields match the wire shape.

export interface DimStat {
  mean: number;
  stddev: number;
  confidence: number;
}

export interface VoiceFingerprint {
  dims: Record<string, DimStat>;
  sample_count: number;
}

export interface DimScore {
  value: number;
  z: number;
  confidence: number;
}

export interface VoiceDeviation {
  dim: string;
  observed: number;
  target: number;
  message: string;
}

export type VoiceBand = "match" | "close" | "off_voice";

export interface VoiceScore {
  score: number;
  band: VoiceBand;
  per_dim: Record<string, DimScore>;
  deviations: VoiceDeviation[];
}

export interface PersonaSummary {
  id: string;
  name: string;
  description: string | null;
  sample_count: number;
  ready: boolean;
  updated_at: string;
}

export interface SampleView {
  id: string;
  word_count: number;
  preview: string;
  created_at: string;
}

export interface PersonaDetail extends PersonaSummary {
  fingerprint: VoiceFingerprint | null;
  samples: SampleView[];
}

export interface PersonaCreate {
  name: string;
  description?: string | null;
}

export interface PersonaUpdate {
  name?: string;
  description?: string | null;
}

/**
 * Human-readable dimension labels — mirrors
 * `src/services/persona/lexicon.py::DIM_LABELS` verbatim (13 keys).
 */
export const DIM_LABELS: Record<string, string> = {
  sentence_len_mean: "average sentence length (words)",
  sentence_len_std: "sentence length variation",
  fk_grade: "reading grade level",
  ttr: "vocabulary variety (type-token ratio)",
  contraction_rate: "contractions per 100 words",
  hedge_rate: "hedging words per 100 words",
  booster_rate: "booster words per 100 words",
  punct_comma_per_1k: "commas per 1,000 words",
  punct_semicolon_per_1k: "semicolons per 1,000 words",
  punct_dash_per_1k: "dashes per 1,000 words",
  punct_question_per_1k: "questions per 1,000 words",
  paragraph_len_mean: "average paragraph length (words)",
  first_person_rate: "first-person words per 100 words",
};

/**
 * Minimum samples of >= 150 words the backend requires before a fingerprint
 * exists (`src/services/persona/fingerprint.py::MIN_SAMPLES`). Used to
 * compute the "needs N more" badge text from `sample_count`.
 */
export const MIN_READY_SAMPLES = 5;

/** Minimum word count per sample (`fingerprint.py::MIN_SAMPLE_WORDS`). */
export const MIN_SAMPLE_WORDS = 150;
