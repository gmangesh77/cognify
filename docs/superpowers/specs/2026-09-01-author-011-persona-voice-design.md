# AUTHOR-011 — Persona voice engine v1

**Status:** approved design (2026-09-01) · **Epic 11 Phase C** · program plan §5.11 · review §6 #12
**Story points:** 13 · **Branch:** `feature/AUTHOR-011-persona-voice` (local only until the user says otherwise)

## 1. Problem

Cognify's only notion of "persona" is a fixed set of eight *audience* keys
(`cto`, `marketer`, …) that steer the image planner and the AI-rewrite
register. There is no way to make the pipeline write *like* a specific
author or brand, no measurement of how close a draft came, and no feedback
loop. ImpactAI's Persona Engine (voice fingerprint → prompt → score → fix)
is the most differentiating idea in the August review. Acceptance
criterion (program plan §9, Phase C):

> A persona built from ≥5 samples yields a fingerprint with per-dimension
> `{value, stddev, confidence}`; generation with that persona scores ≥
> threshold or triggers exactly one fix pass; the article stores
> `voice_match_score` and `few_shot_sample_ids`.

## 2. Decisions taken with the user

| Decision | Choice | Why |
|---|---|---|
| What a persona is | **Author/brand voice from pasted writing samples** (≥5 samples of ≥150 words) — a new entity, separate from the 8 audience keys | Audience keys are an enum validated everywhere and drive *image* style; a measured voice is a different concept. URL crawl is out of scope. |
| Few-shot store | **In-process cosine over Postgres samples** (embedding stored per sample, `EmbeddingService` + numpy) | `MilvusService` is single-schema; a second collection is a refactor + sync surface for ≤ ~50 samples per persona. |
| Score → fix loop | **Per-section score, ONE targeted LLM rewrite per weak section** (mirrors the humanize node) | Bounded cost, deviations named precisely, structure/citations preserved per section. |
| Dependencies | **stdlib only** (`re`, `statistics`, syllable heuristic) — no textstat/spaCy | Matches `slop_scorer.py`; keeps the image lean (review §10 risk row). |
| Gating | `COGNIFY_ENABLE_VOICE_ENGINE` default **false**; nodes are absent from the graph when off and no-ops when the session has no persona | Default pipeline byte-identical. |

## 3. Data model

```
personas
  id uuid PK · owner_id varchar(100) idx · name varchar(200) · description text null
  fingerprint jsonb (VoiceFingerprint, null until ≥5 valid samples)
  sample_count int · created_at/updated_at

persona_samples
  id uuid PK · persona_id uuid FK personas ON DELETE CASCADE idx
  text text · word_count int · embedding jsonb null (384 floats) · created_at
```

Migration `f3b8d1c6a2e4_add_personas.py` (down_revision `e2a7c4d9b1f3`).
Also adds to `research_sessions`: `voice_persona_id uuid null FK personas
ON DELETE SET NULL`; to `briefs`: `voice_persona_id uuid null` (same FK); to
`canonical_articles`: `voice_persona_id uuid null`, `voice_match_score
float null`, `voice_scores_by_section jsonb null`, `few_shot_sample_ids
jsonb not null default '[]'`, and — fixing a pre-existing gap —
`audience_persona varchar(100) null` so the existing model field finally
round-trips.

Pydantic (`src/models/persona.py`): `Persona`, `PersonaCreate`,
`PersonaUpdate` (name/description), `PersonaSample`, `SampleCreate(text)`,
`VoiceFingerprint(dims: dict[str, DimStat], sample_count)`,
`DimStat(mean, stddev, confidence)`, `VoiceScore(score, band, per_dim,
deviations)`, `VoiceDeviation(dim, observed, target, message)`.

Repositories (`src/db/persona_repository.py`): `PersonaRepository`
Protocol — `create(owner_id, data)`, `get(id)`, `list()`, `update(id,
data)`, `delete(id)`, `add_sample(persona_id, sample)`, `delete_sample(id)`,
`list_samples(persona_id)`, `set_fingerprint(id, fp)`,
`set_sample_embedding(sample_id, vec)`; Pg + in-memory. Owner is recorded
(`TokenPayload.sub`) but personas are global, like prompts.

## 4. Engine — `src/services/persona/`

### 4.1 `fingerprint.py` (pure)
`text_features(text) -> dict[str, float]`, 12 dims: `sentence_len_mean`,
`sentence_len_std`, `fk_grade` (Flesch–Kincaid with a vowel-group syllable
heuristic), `ttr` (type-token ratio over the first 500 tokens),
`contraction_rate`, `hedge_rate`, `booster_rate` (per 100 words, fixed
word lists), `punct_comma_per_1k`, `punct_semicolon_per_1k`,
`punct_dash_per_1k`, `punct_question_per_1k`, `paragraph_len_mean`,
`first_person_rate`. Sentence split = the slop scorer's regex; markdown
structure stripped first (`markdown_structure` prose blocks only).

`build_fingerprint(samples: list[str]) -> VoiceFingerprint`: per dim
`mean`, `stddev` (population), `confidence = min(1, n/8) × (1 − min(1,
cv))` where `cv = stddev/|mean|` (dims that vary wildly across samples get
low confidence). Raises `InsufficientSamples` below 5 samples × 150 words.

### 4.2 `scoring.py` (pure)
`score_text(text, fp) -> VoiceScore`: for each dim with `confidence ≥
0.5`, `z = (observed − mean) / max(stddev, floor)`; `penalty = min(|z|,
3)/3`; `score = 100 × (1 − Σ conf·penalty / Σ conf)`; band `match ≥ 80`,
`close ≥ 60`, else `off_voice`. Deviations = dims with `|z| > 1.5`, message
like `"sentences average 28 words; target 17 ± 4"`. Sections shorter than
60 words are scored but excluded from the article mean.

### 4.3 `few_shot.py`
`pick_samples(query: str, samples, embed: Callable, k=3) ->
list[PersonaSample]`: embed the query (section title + description) with
`EmbeddingService.try_embed`; cosine against stored embeddings
(`cosine_similarity_matrix`); samples lacking an embedding are embedded
lazily and persisted; if the model is cold → the 3 longest samples.
Excerpts are trimmed to ≤ 120 words at a sentence boundary.

### 4.4 `prompt_block.py`
`build_voice_block(fp, samples) -> str`: a "Voice" section listing target
sentences per confident dim (`hedge_rate` → "hedge sparingly / freely"
phrasing, punctuation → "use semicolons rarely", …) followed by the
few-shot excerpts under "Write in the voice of these samples:". Wording
lives in registry keys `voice.block_intro`, `voice.dim.<name>`
(templates with `{target}`/`{low}`/`{high}`), so admins can tune it.

### 4.5 Graph nodes (`src/agents/content/voice_nodes.py`)
- Draft-time: `section_prompt.build_system_prompt` appends
  `state["voice_block"]` (built once per run by `build_initial_state`'s
  caller → `ContentService` resolves the persona, computes the block with
  the article-level few-shot pick, and seeds `voice_block`,
  `voice_fingerprint`, `few_shot_sample_ids`).
- `score_voice` (pure, after `humanize`): scores every section, writes
  `voice_scores_by_section`, `voice_match_score`; no LLM.
- `fix_voice_deviations` (conditional, LLM): for sections with `score <
  COGNIFY_VOICE_FIX_THRESHOLD` (default 70) run ONE rewrite with
  `voice.fix.system` / `voice.fix.user` (block + named deviations +
  section prose via the sentinel payload like the humanizer), verify
  citations preserved, re-score, keep whichever scores higher. Never
  raises; one pass only. Step names `content_score_voice`,
  `content_fix_voice` (added to `KNOWN_LLM_STEPS`).
- Router: `score_voice → fix_voice_deviations` if any section below
  threshold else `seo_optimize`; `fix_voice_deviations → seo_optimize`.
  Both nodes added only when `settings.enable_voice_engine`; both return
  `{}` when `voice_fingerprint` is absent from the state.

## 5. Selection plumbing

`voice_persona_id: UUID | None` on `BriefFields`/`BriefUpdate`,
`CreateResearchSessionRequest`, `SessionParams` (`_INLINE_FIELDS`),
`ResearchSession`, `ContentState`, `CanonicalArticle`. Precedence inline >
brief > none (L-012 — copied at `start_session`). `audience_persona` is
untouched.

## 6. API — `src/api/routers/personas.py`

| Route | Role | Notes |
|---|---|---|
| `GET /personas` | viewer+ | list with `sample_count`, `ready` (fingerprint present) |
| `POST /personas` | editor+ | `PersonaCreate` |
| `GET /personas/{id}` | viewer+ | persona + fingerprint + samples (text truncated to 300 chars, `word_count`) |
| `PATCH /personas/{id}` | editor+ | name/description |
| `DELETE /personas/{id}` | editor+ | cascades samples; sessions keep `NULL` |
| `POST /personas/{id}/samples` | editor+ | `{text}` ≥150 words → 422 otherwise; recompute fingerprint; embed if warm |
| `DELETE /personas/{id}/samples/{sid}` | editor+ | recompute fingerprint (may drop to null) |
| `POST /personas/{id}/score` | viewer+ | `{text}` → `VoiceScore` (preview) ; 409 if no fingerprint |

30/min, route decorator outermost. `app.state.persona_repo` in both
lifespan branches; `PipelineServices.persona_repo` for the worker.

## 7. Frontend

- Types `types/persona.ts`, api `lib/api/personas.ts`, hook
  `hooks/use-personas.ts` (list + mutations, `["personas"]`).
- Settings → **Personas** (`personas-settings.tsx` container,
  `personas-list.tsx`, `persona-editor.tsx` (name/description + fingerprint
  card: dim rows with confidence bars, "needs N more samples"),
  `persona-samples.tsx` (paste box with live word count, list with delete)),
  nav entry + `SettingsTab` union.
- Generate modal + brief form: "Voice" select (None + ready personas).
- Article sidebar: `VoiceMatchChip` (`UsageBadge` anatomy; band colours:
  match `success`, close `warning`, off-voice `error`; popover with
  per-section scores and top deviations) — rendered only when
  `voice_match_score` is present. `ArticleDetail` type gains the fields.
- All new files ≤ 200 lines.

## 8. Tests

Fingerprint dims on fixed texts (exact values pinned), confidence rises
with n and falls with spread, `InsufficientSamples`; scoring z/penalty math
and bands, short-section exclusion; block gating by confidence and
registry-key rendering; few-shot cosine pick + cold fallback + lazy embed
persistence; nodes with FakeLLM: fix fires once per weak section only,
skips above threshold, no-op without persona, absent from the graph with
the flag off (node-set assertion), citations-lost → original kept; repo
unit + PG round trip (cascade); router RBAC/422/409/404/429; frontend
tab/editor/samples/chip/hook. Live smoke: 5 pasted samples → fingerprint
ready → generate with the flag on → `llm_calls` shows `content_fix_voice`
only for weak sections → chip renders with the popover.

## 9. Non-goals

URL/LinkedIn crawl · per-user personas · textstat/spaCy · Milvus sample
store · using the voice persona for images · re-scoring existing articles ·
persona sharing/export · learning from accepted edits.
