---

## status: "accepted"
date: 2026-08-19
decision-makers: ["Engineering Team"]
informed-by: "docs/architecture/COGNIFY_VS_IMPACTAI_REVIEW_2026-08.md"
depends-on: "ADR-003 (CanonicalArticle boundary), ADR-006 (Supervised pipeline)"

# ADR-007: Brief as the Authoring Input Contract

## Context and Problem Statement

Per-article generation parameters (description override, audience, tone, angle, keywords, diagram mode) are typed into a modal on every run and copied as loose columns onto `research_sessions`. They cannot be saved, reused, duplicated or referenced; the "Create & Generate" path even drops some of them. As more inputs arrive (length target, content type, persona/voice, outline-approval preference, image art direction) the loose-column approach stops scaling and the UI cannot offer "pick a brief".

`CanonicalArticle` (ADR-003) is the **output** contract of content generation. There is no equivalent **input** contract.

## Decision Drivers

- One place that defines "everything a human tells the pipeline before it runs".
- Reusable across topics and across content types (article today; LinkedIn repurpose, newsletter later).
- Backwards compatible with the existing inline request fields and the autonomous trend-driven path (which has no human brief).
- Past sessions must not change when a brief is edited later.

## Considered Options

### Option A: Keep adding columns to `research_sessions`
**Rejected**: no reuse, no listing, grows the session row with authoring concerns.

### Option B: Store a free-form JSONB "params" blob on the session
**Rejected**: unvalidated, unqueryable, and still not reusable.

### Option C: First-class `Brief` entity (Selected)
`briefs` table + `Brief` Pydantic model (`src/models/brief.py`): name, title, description, target_audience, content_tone, preferred_angle, keywords, content_type, length_target, structural_diagram_mode, audience_persona, require_outline_approval. `research_sessions.brief_id` (nullable FK). `CreateResearchSessionRequest` accepts `brief_id` **or** the existing inline fields; the inline path auto-creates a brief when the user ticks "save as brief". At session start the service **denormalises** brief fields onto the session (existing columns) so later brief edits never alter a past session.

**Implementation note (AUTHOR-003, 2026-08-21):** the shipped implementation matches Option C with four clarifications:
- `briefs.owner_id` is a `String(100)`, not a UUID — it stores the JWT `sub` claim verbatim (e.g. `"user-1"`), which is what every other owner-scoped lookup in the API uses. All `/briefs` reads and writes are scoped by that value in `BriefService`.
- The session carries `content_type`, `length_target` and `audience_persona` alongside the pre-existing inline columns; word budgets derived from `length_target` are consumed later by AUTHOR-008, not here.
- Precedence is resolved once, per field, in `resolve_session_params()` (`src/api/routers/research_params.py`): inline request value > brief value > default. A request that supplies `brief_id` *and* some inline fields keeps `brief_id` on the session for provenance while the inline fields win for those columns. Downstream code (`graph_state.py`, the content graph) reads only session columns — see L-012.
- `Provenance.brief_id` (`src/models/content.py`) was added as a reference-only pointer; the brief body is never embedded in `CanonicalArticle`. The guard test `tests/unit/test_brief_boundary.py` fails if anything under `src/services/publishing/` imports `models.brief`.

## Decision Outcome

Chosen option: **C**.

### Consequences

- Good: briefs can be listed, reused, duplicated, prefilled from topic analysis, and later attached to other content types (ADR-004 transformers read the session/article, not the brief — boundary preserved).
- Good: the autonomous trend path is unchanged (`brief_id = NULL`).
- Bad: one more table and CRUD surface; mitigated by a thin repository + service + router following the existing Route → Service → Repository pattern.
- Neutral: the brief is an *input* artefact; it is never embedded in `CanonicalArticle` (provenance may reference `brief_id` only).

### Invariants

- `Brief` validation lives in Pydantic; routes never accept raw dicts.
- Sessions copy brief values at start; they never read the brief row afterwards.
- Publishing transformers MUST NOT import `src/models/brief.py` (ADR-003/004 boundary).

## References

- `docs/superpowers/plans/2026-08-19-epic-11-supervised-authoring-plan.md` §4.1, §5.4
- `src/api/routers/research.py` (`CreateResearchSessionRequest`), `frontend/src/components/topics/generate-article-modal.tsx`
