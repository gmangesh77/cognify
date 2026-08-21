# AUTHOR-004 — Per-Section Regenerate-with-Feedback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Each task is self-contained — a fresh agent can pick it up with only this file and the repo.

**Goal:** Let an editor regenerate **one** article section from the article-detail toolbar, optionally with a free-text instruction, see a word-level diff against the current section, and accept (persist) or reject it — without re-running the pipeline and without losing any `data-spec-id` image anchors. Because every existing per-section flow (edit / AI rewrite / history / restore) addressed the **wrong section** (off-by-one between the frontend's 0-based H2 index and `split_sections`' prelude-is-0 index), this ticket first fixes the section-id contract at the root (**L-013**) — that is why it grew from 3 SP to **5 SP**.

**Architecture:** Task 1 fixes the section-id contract: the public `section_id` is `{article_id}:{outline_index}` (0-based over H2 sections — the space used by the frontend, the planner's `ImagePlacement.section_index` and `section_drafts`), and ONE pair of helpers (`md_index_for` / `outline_index_for` in `section_history_contracts.py`) converts to `split_sections` indices inside `SectionHistoryService`; `validate_anchors` is always called with the outline index. Task 2 extracts prompt assembly into `section_prompt.py`, adds `DraftingContext.instruction`, and exposes the graph-free `draft_one_section(section, queries, ctx) -> OneSectionDraft` (body + word count + token usage). Task 3 promotes helpers that the regenerate path reuses instead of copying (`strip_fences`, `model_label`, `extract_usage`, `strip_leading_heading`, `find_spec_ids`, `VersionRepoProtocol`), lifts the shared route helpers into `content_shared.py`, exposes `ContentService.deps`, and makes `content.py`'s `_get_content_llm` prefer the pipeline's tracked LLM. Task 4 adds `ArticleDraftRepository.find_by_article_id` (in-memory + Pg) and `SectionRegenerateService` (value objects in `section_regenerate_models.py`): loads the article + outline section via `drafts.find_by_article_id(article.id)` — **never** via `article.provenance.research_session_id`, which the graph fills with the TOPIC id (`graph_state.py:36` `"session_id": topic.id` → `seo_node.py:69`), so `find_latest_by_session(provenance)` is None for every real article — builds a `DraftingContext` from the live previous sections + session params (`research.get(draft.session_id)`), drafts the section with ONE tracked LLM call (contextvars `current_session_id = draft.session_id` — the real FK target of `llm_calls.session_id` — / `current_step_name="section_regenerate"` bound in `try/finally`), re-prefixes the original H2, re-inserts every `data-spec-id` block at its relative block position (via `markdown_structure`), runs `validate_anchors` with the outline index, appends a candidate `section_versions` row (`source="regenerate"`, body untouched) and returns markdown + diff + word count + tokens. Task 5 mounts `POST /content/section-regenerate` in a new router module (editor/admin, `10/minute`) that reads `request.app.state.content_service.deps`. Tasks 6–7 add the frontend client/hook/popover/toolbar action and split `page.tsx` + `article-content.tsx` + `InlineProseEditor.tsx` under 200 lines. **Accept** POSTs the existing `/content/section-update` with `source="regenerate"` using the same outline-space `section_id`.

**Tech Stack:** FastAPI, Pydantic v2, LangChain `BaseChatModel` (FakeListChatModel / AsyncMock in tests), pytest + httpx; Next.js 15 / React 19 / Vitest + Testing Library.

**Spec:** `docs/superpowers/plans/2026-08-19-epic-11-supervised-authoring-plan.md` §5.5, §6, §7 (`test_section_regenerate.py`), §9 Phase A AC "Regenerate on a section returns a diff, preserves all `data-spec-id` anchors, appends a `section_versions` row with `source=regenerate`"; ADR-006 (supervised pipeline — this is a per-section re-entry that bypasses the graph).

## Spec ambiguities resolved (read before coding)

1. **Section index spaces — fixed at the root (L-013, in scope).** Verified: `section_markdown.split_sections` ALWAYS puts the prelude at index 0 (empty string when the body starts with `## `), so the first H2 is markdown index **1**; `ArticleOutline.sections[].index`, `SectionDraft.section_index`, `ImagePlacement.section_index` and the frontend `sectionIdx` are all **0-based over H2 sections**. The pre-existing flows sent `{id}:{sectionIdx}` straight into `parse_section_id`, so "section 0" addressed the prelude and every edit / rewrite / history / restore landed one section early; worse, `persist_section_update` fed the markdown index to `validate_anchors._check_headings`, which compares it with `ImagePlacement.section_index` (outline space). **Design:** the public `section_id` contract becomes `{article_id}:{outline_index}` everywhere; `section_history_contracts.md_index_for(outline_index) = outline_index + 1` (+ inverse `outline_index_for`) is the ONLY conversion, used by `SectionHistoryService.get_section_markdown` / `persist_section_update`; `validate_anchors` is always called with the outline index (history service, regenerate service and the accept path all agree). The frontend `makeSectionId` is already 0-based — only its doc comment changes. The prelude is no longer addressable (it never was editable from the UI). **Visual Studio's `studioSections`** (`page.tsx`) built its own indices with `segments.slice(1)` — i.e. it assumed a prelude and dropped the first section for the common no-prelude article, shifting `ImagePlacement.section_index` by one; the `makeSectionId` grep cannot catch it. Task 7 replaces it with `studioSectionsFrom(bodyMarkdown)` (`lib/articles/studio-sections.ts`), which reuses the same `splitBySections` / `hasPreamble` pair as `article-content.tsx` (moved to `lib/articles/split-sections.ts`), so every frontend index is outline space.
   **Data already in the DB (no migration):** the frontend always sent `{id}:{sectionIdx}` in outline space, so `section_versions.section_id` / `section_index` are already in the NEW space and stay addressable — restore now lands on the intended H2. But (a) rows with `source IN ('ai','tone_preset','humanize')` created through section-rewrite with `current_markdown=None` were generated from `get_section_markdown(md k)` = the PREVIOUS section, so restoring such a row writes section k-1's prose under section k's heading (the anchor validator only catches it when a `before_heading` spec is bound); (b) any body saved pre-fix had `replace_section(md k)` overwrite section k-1 with section k's edited text, so duplicated-section bodies may exist. Ops checks (also recorded in L-013 and the PROGRESS resume note): `SELECT id, section_id, source, created_at FROM section_versions WHERE source <> 'manual' AND created_at < '<deploy-date>';` and `SELECT id FROM canonical_articles WHERE body_markdown ~ '(## [^\n]+)\n[\s\S]*\1\n';`. `labelForSource` is deliberately NOT changed to flag pre-L-013 rows — the drawer has no deploy date and a wrong label is worse than none; the SQL list is the audit.
2. **`draft_one_section` signature.** The program plan says `draft_one_section(llm, retriever, ctx) -> str`, but `DraftingContext` already carries `llm` + `retriever` and the 3-param rule applies; the extracted function is `draft_one_section(section: OutlineSection, queries: SectionQueries, ctx: DraftingContext) -> OneSectionDraft` (`body_markdown`, `word_count`, `tokens_input`, `tokens_output`). Importable without LangGraph (`section_drafter.py` has no graph imports).
3. **Persist vs preview.** §5.5 says the endpoint writes a `section_versions` row; §6/AC says accept calls section-update. Both happen: the regenerate call appends a **candidate** row (`source="regenerate"`, article body untouched — Reject costs nothing and the history drawer keeps an audit of every paid regeneration), and Accept POSTs `/content/section-update` with `source="regenerate"` + the instruction, which replaces the body and appends the **applied** row. Two rows per accepted regenerate, documented.
4. **Anchors — carried by position, never by naive `"\n\n"` split.** Regenerated prose never contains `data-spec-id` markers. `carry_anchor_blocks` parses the OLD section with `src/utils/markdown_structure.parse_markdown_blocks` (as the humanizer does), takes the `data-spec-id` **lines** of every block that has one (a figure sharing a paragraph with prose carries only the figure line — the prose is not duplicated), and re-inserts them into the NEW block list at their relative block position: first block stays first, last stays last, anything else lands at `round(pos / (old_total - 1) * new_total)`. Then `validate_anchors(original=old section text, section_index=outline index)` runs; any residual violation → `AnchorViolationError` → HTTP 422 with the same `{"error":"anchor_violation","violations":[…]}` shape as section-update (built by the shared `anchor_violation_http`).
5. **Citations.** Fresh retrieval renumbers `[N]` relative to this call's chunks while the article's References list is not regenerated, so `[N]` markers are stripped (`citation_manager.strip_citation_markers`). Retrieval queries are derived without an LLM call: `SectionQueries(section_index, queries=[title, *key_points])`.
6. **LLM + retriever + cost — and which session id.** The new router reads `request.app.state.content_service.deps` (new public `ContentService.deps` property — no new `app.state` attribute), so the regenerate call goes through the pipeline's `TrackedChatModel`. **Context is resolved by article id, not by provenance:** `CanonicalArticle.provenance.research_session_id` is filled from `state["session_id"]`, which `graph_state.build_initial_state` sets to `topic.id` (verified: `src/services/content/graph_state.py:36`, `src/agents/content/seo_node.py:69`; `ResearchSession.id` is a separate `uuid4()`), so keying anything on it breaks in production — `find_latest_by_session(topic_id)` → None → HTTP 409 for every real article, `research.get(topic_id)` → None (no audience/tone), and the `llm_calls` insert fails its `ForeignKey("research_sessions.id")` (`src/db/tables.py:146`) and is swallowed by `_save_call`. `store_article` (`src/services/content_finalize.py:39-45`) stamps `draft.article_id`, so the service calls the new `drafts.find_by_article_id(article.id)` and then uses `draft.session_id` (the real research-session id) for `research.get(...)` **and** for `current_session_id`. `SectionRegenerateService` binds `current_session_id = draft.session_id` and `current_step_name = "section_regenerate"` (`src/utils/tracked_llm.py` contextvars) around the call so one `llm_calls` row with `call_name="section_regenerate"` lands in Pipeline Debug / AUTHOR-005. The provenance bug itself is pre-existing and out of scope (AUTHOR-001's `articles.find_by_session` in `src/api/routers/session_events.py:72` depends on the current value) — it gets a PROGRESS follow-up line, not a fix here. Token usage is read off the response (`src/utils/llm_usage.extract_usage`, promoted from `section_rewriter`) and stored on the version row + returned. `content.py`'s `_get_content_llm` now prefers the same deps (fallback: the current `ChatAnthropic` construction), so rewrite and regenerate share the tracked model.
7. **`source` validation site.** `section_versions.source` is `String(20)` with no CHECK; repo alias `VersionSource = str`. The ONLY enforcement is the request Literal `SectionUpdateRequest.source` (`src/api/routers/content.py`) and the TS union `SectionUpdateSource` (`frontend/src/types/content.ts`) — both gain `"regenerate"`. No migration. L-003 is not triggered (no session status touched).
8. **Humanize — v1 returns un-humanized prose.** A regenerate is deliberately **exactly one** LLM call (L-007, predictable cost, < 10 s round-trip); running the humanizer would add 1–2 calls per regenerate and duplicate the Humanize panel the editor already has on the same section. `RegenerateResult.word_count` is surfaced (response + TS type) and `section_word_count_outside_range` is logged by the existing `_log_word_count` inside `section_drafter._draft` (no new code). Per-pass humanize streaming is AUTHOR-009 — follow-up line in Task 8 docs.

## Global Constraints

- Functions < 20 lines, files < 200 lines, ≤ 3 params (bundle in frozen dataclasses / Pydantic models). Files over the cap that this ticket touches and leaves over (pre-existing, edits kept minimal; INFRA-008 owns the splits): `src/api/routers/content.py` (546 → ≈ 495 after the shared-helper lift), `src/services/content/section_rewriter.py` (248 → ≈ 232), `src/api/main.py` (791 → +6), `src/services/content/__init__.py` (314 → +5), `src/db/repositories.py` (904 → +14, `PgArticleDraftRepository.find_by_article_id`). Everything else touched ends < 200 lines — the counts given per task are **measured** (`uv run ruff format` with the repo config, then `wc -l`), not estimates. Function length is measured AST-style (`def` line through last line, signature included) — every new or rewritten function in this plan is < 20 on that measure; Task 4 Step 4 and Task 1 Step 4 include the one-liner that checks it.
- TDD every task: failing test → run → minimal code → run → commit. Backend: `COGNIFY_ANTHROPIC_API_KEY= uv run pytest <path> -q -p no:cacheprovider` (blank key avoids the Milvus import hang). Frontend: `cd frontend && npx vitest run <path>`. Lint before each commit: `uv run ruff check --fix src/ tests/ && uv run ruff format src/ tests/ && uv run mypy src/ --ignore-missing-imports`; `cd frontend && npx tsc --noEmit && npx eslint src`.
- **L-007 (FakeLLM counts):** a regenerate is **exactly one** `llm.ainvoke` (`draft_one_section → _draft`); retrieval is `[]` when `retriever is None`, and query derivation never calls the LLM. `FakeListChatModel(responses=[one string])` per regenerate — no pipeline padding.
- **L-001/L-002:** no JSONB writes, no JSON parsing (plain prose). **L-003:** no status values touched. **L-013 (this ticket):** outline index everywhere; the only `+1` lives in `md_index_for`.
- Design system: no new colours; toolbar button = existing `ToolbarButton`; popover = same classes as `AIRewritePopover` (`w-[460px] rounded-lg border border-neutral-200 bg-white p-4 shadow-lg`, accept `bg-primary`, reject `bg-neutral-100`, diff via `WordDiffView`). Icon: `RefreshCw` from lucide-react.
- Named exports only (Next page default export is the route exception). No inline styles. structlog events: `section_regenerate_started`, `section_regenerated`, `section_regenerate_anchor_violation`.
- Branch `feature/AUTHOR-004-section-regenerate` (worktree `.claude/worktrees/AUTHOR-004`), conventional commits, one PR off `develop`, never stacked. Commit trailers:
  ```
  Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01EAUaG8xvdTFWnnvhuQEVDx
  ```

## File map

| File | Responsibility | Expected lines |
|---|---|---|
| `src/services/content/section_history_contracts.py` (new) | `md_index_for`, `outline_index_for`, `make_section_id`, `parse_section_id`, error classes, `ArticleRepoProtocol`, `VersionRepoProtocol`, `VersionMeta`, `VersionRow`, `PersistResult`, `append_version_row` | 168 (measured) |
| `src/services/content/section_history.py` | `SectionHistoryService` only; `__all__` = service + 3 errors (contracts are imported from `section_history_contracts`); outline-index contract | 187 (measured) |
| `src/services/content/section_anchors.py` | + public `find_spec_ids` | ≈ 122 |
| `src/agents/content/article_assembler.py` | `_strip_leading_heading` → public `strip_leading_heading` | ≈ 125 |
| `src/services/content/section_rewriter.py` | `_strip_fences` → public `strip_fences`; new `model_label`; imports `extract_usage` | ≈ 232 (pre-existing over cap) |
| `src/utils/llm_usage.py` (new) | `extract_usage(response)` promoted from `section_rewriter` | ≈ 35 |
| `src/agents/content/section_prompt.py` (new) | `SYSTEM_PROMPT`, `build_system_prompt`, `build_user_prompt`, `build_messages` | ≈ 90 |
| `src/agents/content/section_drafter.py` | `DraftingContext.instruction`, `OneSectionDraft`, `draft_one_section`, `_draft` | ≈ 170 |
| `src/api/routers/content_shared.py` (new) | `WordDiffEntry`, `AnchorViolationEntry`, `anchor_violation_http`, `get_history_service` | ≈ 75 |
| `src/api/routers/content.py` | imports shared helpers; Literal += `"regenerate"`; `_get_content_llm(request)` prefers `content_service.deps.llm` | ≈ 495 (pre-existing over cap) |
| `src/services/content/__init__.py` | `ContentService.deps` property | 314 → ≈ 319 |
| `src/services/content_repositories.py` | `ArticleDraftRepository.find_by_article_id` (Protocol + in-memory) | 121 → ≈ 132 |
| `src/db/repositories.py` | `PgArticleDraftRepository.find_by_article_id` | 904 → ≈ 918 (pre-existing over cap) |
| `src/services/content/section_regenerate_models.py` (new) | `STEP_NAME`, `DraftContextMissingError`, `RegenerateCommand`, `RegenerateDeps`, `RegenerateInputs`, `RegenerateResult` | 91 (measured) |
| `src/services/content/section_regenerate_text.py` (new) | `build_drafting_context(prep, deps)`, `reject_non_prose`, `carry_anchor_blocks`, `assemble_section`, `prior_drafts_from_body`, `queries_for` | 161 (measured) |
| `src/services/content/section_regenerate.py` (new) | `SectionRegenerateService` (`regenerate` → `_prepare` / `_outline_section` / `_draft` / `_validate` / `_record`, each < 20 lines) | 177 (measured) |
| `src/api/routers/content_regenerate.py` (new) | `content_regenerate_router` — `POST /content/section-regenerate`; `_map_regenerate_error`, `_resolve_regenerate_state` | 171 (measured) |
| `src/api/main.py` | import + `include_router` | +6 |
| `frontend/src/types/content.ts` | `SectionRegenerateRequest/Response`; `SectionUpdateSource` += `"regenerate"` | ≈ 150 |
| `frontend/src/lib/api/content.ts` | `regenerateSection(body)`; `makeSectionId` doc comment | ≈ 100 |
| `frontend/src/lib/api/anchorViolations.ts` (new) | `extractAnchorViolations(err)` | ≈ 25 |
| `frontend/src/lib/articles/locate-paragraph.ts` (new) | `locateParagraph` moved out of `InlineProseEditor` | ≈ 25 |
| `frontend/src/components/article/InlineProseEditor.tsx` | imports the two helpers above (local copies deleted) | ≈ 189 |
| `frontend/src/hooks/use-section-regenerate.ts` (new) | `useSectionRegenerate()` | ≈ 60 |
| `frontend/src/components/article/RegeneratePopover.tsx` (new) | instruction → diff → Reject / Accept | ≈ 165 |
| `frontend/src/components/article/SectionContextToolbar.tsx` | 4th action `onRegenerate` | ≈ 105 |
| `frontend/src/components/article/SectionHistoryDrawer.tsx` | `labelForSource("regenerate")` | ≈ 189 |
| `frontend/src/lib/articles/bucket-visuals.ts` (new) | `bucketVisuals`, `isDiagramVisual`, `sectionIndexOf` | ≈ 70 |
| `frontend/src/components/articles/article-content-parts.tsx` (new) | `ArticleImage`, `DiagramList`, `ReferencesList` | ≈ 75 |
| `frontend/src/lib/articles/split-sections.ts` (new) | `splitBySections`, `hasPreamble` (moved out of `article-content.tsx`; shared with Visual Studio) | ≈ 20 |
| `frontend/src/lib/articles/studio-sections.ts` (new) | `studioSectionsFrom(bodyMarkdown)` — outline-space sections for `VisualStudio` (replaces the `segments.slice(1)` prelude assumption in `page.tsx`) | ≈ 25 |
| `frontend/src/components/articles/article-content.tsx` | render loop only; `SectionEditingProps.onRegenerate` | ≈ 120 |
| `frontend/src/components/articles/article-detail-toolbar.tsx` (new) | Saved visuals / Import image / Open Visual Studio button row | ≈ 35 |
| `frontend/src/components/articles/article-not-found.tsx` (new) | `ArticleNotFound` empty state | ≈ 15 |
| `frontend/src/components/article/SectionEditingWorkbench.tsx` (new) | action row + editor + Humanize / Rewrite / Regenerate / Refine panels | ≈ 165 |
| `frontend/src/hooks/use-article-actions.ts` (new) | `useArticleActions({id, refetch, showToast})` → `{insertVisuals, publish}` | ≈ 75 |
| `frontend/src/app/(dashboard)/articles/[id]/page.tsx` | layout + state only | 182 (counted from the Task 7 block) |
| docs: `project-management/PROGRESS.md`, `project-management/BACKLOG.md`, `CLAUDE.md`, `docs/LEARNINGS.md` (**L-013**), program plan §9 AC, ADR-006 impl-note, `frontend/DESIGN.md` toolbar section | — | — |

---

### Task 1: Section-id contract — outline index everywhere (L-013)

**Files:**
- Create: `src/services/content/section_history_contracts.py`
- Modify: `src/services/content/section_history.py` (service only; `__all__` = service + errors), `src/api/routers/content.py` (import re-point only — 2 names), `frontend/src/lib/api/content.ts` (`makeSectionId` doc comment only)
- Test (new cases + fix the off-by-one the old tests encoded): `tests/unit/services/content/test_section_history.py`, `tests/unit/api/test_content_endpoints.py` (+ import re-point)

**All callers of the contract (grep done 2026-08-21 — re-run before editing):**
```bash
grep -rn "parse_section_id\|make_section_id\|get_section_markdown\|persist_section_update\|validate_anchors" src/ tests/ --include=*.py
grep -rn "makeSectionId\|articleId}:\${" frontend/src
```
- Backend: `src/services/content/section_history.py` (definitions + internal use), `src/api/routers/content.py:126` (`get_section_markdown` in section-rewrite), `:191` (`persist_section_update` in section-update), `:311`/`:363` (`parse_section_id` validation in history/restore), `:506` (`_parse_or_400`), `:544` (`make_section_id` re-export), `src/services/content/section_anchors.py:47` (`validate_anchors` def), `src/services/content/section_rewriter.py:17` (docstring only). None of the router sites do arithmetic on the index — they pass it straight through, so fixing the service fixes every route. `content.py:43-44` and `tests/unit/api/test_content_endpoints.py:38-40` import `make_section_id` / `parse_section_id` from `section_history` — both move to `section_history_contracts` in this task (the service module stops re-exporting contracts to stay < 200 lines).
- Tests: `tests/unit/services/content/test_section_history.py` (uses `section_index=1` for "First Section" — old space), `tests/unit/api/test_content_endpoints.py` (`section_id` fixture = `make_section_id(article_id, 1)` and a spec with `section_index=1` for "First Section" — old space), `tests/unit/services/content/test_section_anchors.py` (calls `validate_anchors` directly with matching spec indices — semantics unchanged, untouched).
- Frontend: `frontend/src/lib/api/content.ts:87` (`makeSectionId` def — already 0-based), `frontend/src/app/(dashboard)/articles/[id]/page.tsx:191,206` (callers), `frontend/src/components/articles/article-content.tsx:163` (inline `${editing.articleId}:${sectionIdx}` — already 0-based). No frontend arithmetic changes.

**Interfaces:**
```python
# src/services/content/section_history_contracts.py
def md_index_for(outline_index: int) -> int          # outline_index + 1  (split_sections: prelude is 0)
def outline_index_for(md_index: int) -> int          # md_index - 1
def make_section_id(article_id: UUID, outline_index: int) -> str
def parse_section_id(section_id: str) -> tuple[UUID, int]   # (article_id, outline_index)
class AnchorViolationError(Exception); class SectionNotFoundError(Exception); class ArticleNotFoundError(Exception)
class ArticleRepoProtocol(Protocol); class VersionRepoProtocol(Protocol)   # public (were _-prefixed)
class VersionMeta(TypedDict, total=False): instruction, model, tokens_input, tokens_output, usd, created_by   # PEP 692 kwargs bundle
@dataclass(frozen=True) class VersionRow: article_id, section_index, markdown, source, instruction=None, model=None, tokens_input=None, tokens_output=None, usd=None, created_by=None
@dataclass(frozen=True) class PersistResult: article, new_section_markdown, version_id
async def append_version_row(repo: VersionRepoProtocol, row: VersionRow) -> UUID   # the ONE VersionRow → repo.append(11 kwargs) fan-out (history service + regenerate service)

# src/services/content/section_history.py — same keyword API, outline-index semantics; __all__ = service + 3 errors
class SectionHistoryService:
    async def get_section_markdown(self, article_id: UUID, section_index: int) -> tuple[CanonicalArticle, MarkdownSection]   # section_index = OUTLINE index
    async def persist_section_update(self, *, article_id, section_index, new_section_markdown, source, **meta: Unpack[VersionMeta]) -> PersistResult  # OUTLINE index; validate_anchors(section_index=outline); every existing keyword call site still type-checks
    async def list_history(...); async def restore(...)   # unchanged behaviour
```

- [ ] **Step 1: Write the failing tests**

Replace `tests/unit/services/content/test_section_history.py` with:
```python
"""Tests for the section-history service (outline-index contract, L-013)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from src.models.content import (
    CanonicalArticle,
    ContentType,
    Provenance,
    SEOMetadata,
)
from src.models.visual import ImagePlacement, ImageSpec
from src.services.content.section_history import (
    AnchorViolationError,
    ArticleNotFoundError,
    SectionHistoryService,
    SectionNotFoundError,
)
from src.services.content.section_history_contracts import (
    VersionRow,
    append_version_row,
    make_section_id,
    md_index_for,
    outline_index_for,
    parse_section_id,
)

ARTICLE_BODY = (
    "Intro prelude paragraph.\n\n"
    "## First Section\n"
    "First section body.\n\n"
    "## Second Section\n"
    "Second section body.\n"
)
BODY_NO_PRELUDE = (
    "## First Section\nFirst section body.\n\n## Second Section\nSecond section body.\n"
)


def _build_article(
    article_id: UUID,
    *,
    image_specs: list[ImageSpec] | None = None,
    body: str = ARTICLE_BODY,
) -> CanonicalArticle:
    return CanonicalArticle(
        id=article_id,
        title="Quiet refactor",
        body_markdown=body,
        summary="Small steps compound.",
        content_type=ContentType.ARTICLE,
        seo=SEOMetadata(title="Quiet refactor", description="Summary."),
        authors=["Cognify"],
        domain="engineering",
        generated_at=datetime.now(UTC),
        provenance=Provenance(
            research_session_id=uuid4(),
            primary_model="m",
            drafting_model="m",
            embedding_model="e",
            embedding_version="v1",
        ),
        image_specs=image_specs or [],
    )


def _heading_spec(section_index: int, heading: str = "First Section") -> ImageSpec:
    return ImageSpec(
        id=f"img-{section_index}",
        role_style="hero",
        prompt="placeholder",
        placement=ImagePlacement(
            anchor="before_heading",
            heading_text=heading,
            section_index=section_index,
        ),
    )


@dataclass
class _StoredVersion:
    id: UUID
    markdown: str


class _FakeArticleRepo:
    def __init__(self, article: CanonicalArticle | None) -> None:
        self.article = article
        self.persisted_body: str | None = None

    async def get(self, article_id: UUID) -> CanonicalArticle | None:
        if self.article is None or self.article.id != article_id:
            return None
        return self.article

    async def update_body_markdown(
        self, article_id: UUID, body_markdown: str
    ) -> CanonicalArticle | None:
        if self.article is None or self.article.id != article_id:
            return None
        self.persisted_body = body_markdown
        self.article = self.article.model_copy(update={"body_markdown": body_markdown})
        return self.article


class _FakeVersionRepo:
    def __init__(self) -> None:
        self.appended: list[dict[str, object]] = []
        self._stored: dict[UUID, _StoredVersion] = {}

    async def append(self, **kwargs: object) -> _StoredVersion:
        version_id = uuid4()
        markdown = kwargs.get("markdown", "")
        assert isinstance(markdown, str)
        self.appended.append(kwargs)
        stored = _StoredVersion(id=version_id, markdown=markdown)
        self._stored[version_id] = stored
        return stored

    async def list_for_section(
        self, *, article_id: UUID, section_id: str, limit: int = 50
    ) -> list[_StoredVersion]:
        return list(self._stored.values())

    async def get(self, version_id: UUID) -> _StoredVersion | None:
        return self._stored.get(version_id)


def _service(
    article: CanonicalArticle | None,
) -> tuple[SectionHistoryService, _FakeArticleRepo, _FakeVersionRepo]:
    articles = _FakeArticleRepo(article)
    versions = _FakeVersionRepo()
    return SectionHistoryService(articles, versions), articles, versions


class TestSectionIdHelpers:
    def test_make_and_parse_round_trip(self) -> None:
        article_id = uuid4()
        sid = make_section_id(article_id, 3)
        parsed_article, parsed_index = parse_section_id(sid)
        assert parsed_article == article_id
        assert parsed_index == 3

    def test_parse_rejects_malformed(self) -> None:
        with pytest.raises(ValueError):
            parse_section_id("not-a-section-id")

    def test_md_index_is_outline_plus_one_and_inverts(self) -> None:
        assert md_index_for(0) == 1
        assert outline_index_for(1) == 0
        assert outline_index_for(md_index_for(4)) == 4

    @pytest.mark.asyncio
    async def test_append_version_row_fans_out_every_column(self) -> None:
        article_id = uuid4()
        versions = _FakeVersionRepo()
        row = VersionRow(
            article_id=article_id,
            section_index=2,
            markdown="## H\n\nbody",
            source="regenerate",
            instruction="tighter",
            model="claude-x",
            tokens_input=10,
            tokens_output=4,
            usd=0.01,
            created_by="user-1",
        )
        version_id = await append_version_row(versions, row)
        assert versions.appended == [
            {
                "article_id": article_id,
                "section_id": make_section_id(article_id, 2),
                "section_index": 2,
                "markdown": "## H\n\nbody",
                "source": "regenerate",
                "instruction": "tighter",
                "model": "claude-x",
                "tokens_input": 10,
                "tokens_output": 4,
                "usd": 0.01,
                "created_by": "user-1",
            }
        ]
        assert version_id == next(iter(versions._stored))


class TestOutlineIndexContract:
    """section_index is the 0-based H2 index — never the split_sections index."""

    @pytest.mark.asyncio
    async def test_index_zero_is_first_h2_when_body_starts_with_heading(self) -> None:
        article_id = uuid4()
        svc, _, _ = _service(_build_article(article_id, body=BODY_NO_PRELUDE))
        _, section = await svc.get_section_markdown(article_id, 0)
        assert section.heading == "## First Section"
        _, second = await svc.get_section_markdown(article_id, 1)
        assert second.heading == "## Second Section"

    @pytest.mark.asyncio
    async def test_index_zero_skips_the_prelude(self) -> None:
        article_id = uuid4()
        svc, _, _ = _service(_build_article(article_id))
        _, section = await svc.get_section_markdown(article_id, 0)
        assert section.heading == "## First Section"
        assert "Intro prelude" not in section.text

    @pytest.mark.asyncio
    async def test_negative_index_is_not_found(self) -> None:
        article_id = uuid4()
        svc, _, _ = _service(_build_article(article_id))
        with pytest.raises(SectionNotFoundError):
            await svc.get_section_markdown(article_id, -1)

    @pytest.mark.asyncio
    async def test_persist_replaces_outline_section_and_records_outline_index(
        self,
    ) -> None:
        article_id = uuid4()
        svc, articles, versions = _service(_build_article(article_id))
        await svc.persist_section_update(
            article_id=article_id,
            section_index=0,
            new_section_markdown="## First Section\nNew first body.",
            source="manual",
        )
        body = articles.persisted_body or ""
        assert body.startswith("Intro prelude paragraph.")
        assert "New first body." in body
        assert "## Second Section\nSecond section body." in body
        assert versions.appended[0]["section_index"] == 0
        assert versions.appended[0]["section_id"] == make_section_id(article_id, 0)

    @pytest.mark.asyncio
    async def test_heading_check_receives_the_outline_index(self) -> None:
        # Spec bound to OUTLINE section 0 ("First Section").
        article_id = uuid4()
        svc, articles, _ = _service(
            _build_article(article_id, image_specs=[_heading_spec(0)])
        )
        # Renaming section 0's heading must violate.
        with pytest.raises(AnchorViolationError) as ei:
            await svc.persist_section_update(
                article_id=article_id,
                section_index=0,
                new_section_markdown="## Renamed Heading\nNew body.",
                source="manual",
            )
        assert ei.value.violations[0].kind == "heading_text"
        assert articles.persisted_body is None
        # Renaming section 1's heading is fine — the spec is not bound to it.
        await svc.persist_section_update(
            article_id=article_id,
            section_index=1,
            new_section_markdown="## Other\nNew body.",
            source="manual",
        )
        assert "## Other" in (articles.persisted_body or "")


class TestPersistSectionUpdate:
    @pytest.mark.asyncio
    async def test_happy_path_updates_body_and_appends_version(self) -> None:
        article_id = uuid4()
        svc, articles, versions = _service(_build_article(article_id))
        result = await svc.persist_section_update(
            article_id=article_id,
            section_index=0,
            new_section_markdown="## First Section\nA tighter rewrite.",
            source="manual",
            created_by="user-1",
        )
        assert articles.persisted_body is not None
        assert "tighter rewrite" in articles.persisted_body
        assert "## Second Section" in articles.persisted_body
        assert len(versions.appended) == 1
        assert versions.appended[0]["source"] == "manual"
        assert result.version_id is not None

    @pytest.mark.asyncio
    async def test_anchor_violation_raises(self) -> None:
        article_id = uuid4()
        svc, articles, versions = _service(
            _build_article(article_id, image_specs=[_heading_spec(0)])
        )
        with pytest.raises(AnchorViolationError) as ei:
            await svc.persist_section_update(
                article_id=article_id,
                section_index=0,
                new_section_markdown="## Renamed Heading\nNew body.",
                source="manual",
            )
        assert ei.value.violations
        assert ei.value.violations[0].kind == "heading_text"
        assert articles.persisted_body is None
        assert versions.appended == []

    @pytest.mark.asyncio
    async def test_unknown_article_raises_not_found(self) -> None:
        svc, _, _ = _service(None)
        with pytest.raises(ArticleNotFoundError):
            await svc.persist_section_update(
                article_id=uuid4(),
                section_index=0,
                new_section_markdown="x",
                source="manual",
            )

    @pytest.mark.asyncio
    async def test_out_of_range_section_raises(self) -> None:
        article_id = uuid4()
        svc, _, _ = _service(_build_article(article_id))
        with pytest.raises(SectionNotFoundError):
            await svc.persist_section_update(
                article_id=article_id,
                section_index=99,
                new_section_markdown="x",
                source="manual",
            )

    @pytest.mark.asyncio
    async def test_restore_round_trip_uses_outline_index(self) -> None:
        article_id = uuid4()
        svc, articles, versions = _service(_build_article(article_id))
        v1 = await svc.persist_section_update(
            article_id=article_id,
            section_index=0,
            new_section_markdown="## First Section\nVersion one.",
            source="ai",
            instruction="tighten",
        )
        await svc.persist_section_update(
            article_id=article_id,
            section_index=0,
            new_section_markdown="## First Section\nVersion two.",
            source="manual",
        )
        assert "Version two" in (articles.persisted_body or "")
        restored = await svc.restore(
            section_id=make_section_id(article_id, 0),
            version_id=v1.version_id,
            created_by="user-1",
        )
        body = articles.persisted_body or ""
        assert "Version one" in body
        assert body.startswith("Intro prelude paragraph.")  # prelude untouched
        assert "## Second Section" in body
        assert restored.version_id is not None
        assert len(versions.appended) == 3
        assert versions.appended[-1]["source"] == "restore"
```

Edit `tests/unit/api/test_content_endpoints.py` (fix the old index space — four edits + one new class):
0. Import: `make_section_id` moves out of the `section_history` import block into `from src.services.content.section_history_contracts import make_section_id` (the service module no longer re-exports it).
1. `section_id` fixture: `return make_section_id(article_id, 1)` → `return make_section_id(article_id, 0)`.
2. In `test_anchor_violation_returns_422_with_diff`: `section_index=1,` (inside `ImagePlacement`) → `section_index=0,` and `"section_id": make_section_id(article_id, 1),` → `"section_id": make_section_id(article_id, 0),`.
3. Append at end of file:
```python
class TestOutlineIndexContractEndpoint:
    """L-013 — `{article_id}:0` is the first H2, not the prelude."""

    async def test_section_update_on_index_zero_replaces_first_h2(
        self,
        content_client: httpx.AsyncClient,
        content_settings: Settings,
        article_id: UUID,
        article_repo: _FakeArticleRepo,
    ) -> None:
        resp = await content_client.post(
            "/api/v1/content/section-update",
            json={
                "section_id": make_section_id(article_id, 0),
                "markdown": "## First Section\nReplaced first body.",
                "source": "manual",
            },
            headers=_editor_headers(content_settings),
        )
        assert resp.status_code == 200, resp.text
        body = article_repo.persisted_body or ""
        assert body.startswith("Intro prelude paragraph.")
        assert "Replaced first body." in body
        assert "## Second Section\nSecond section body." in body
```

- [ ] **Step 2: Run — expect failure**

`COGNIFY_ANTHROPIC_API_KEY= uv run pytest tests/unit/services/content/test_section_history.py tests/unit/api/test_content_endpoints.py -q -p no:cacheprovider` → `ModuleNotFoundError: src.services.content.section_history_contracts`; after stubbing the module, `test_index_zero_skips_the_prelude` fails (prelude returned), `test_heading_check_receives_the_outline_index` fails (no violation raised for section 0) and `test_append_version_row_fans_out_every_column` fails (`ImportError: append_version_row`).

- [ ] **Step 3: Implement**

Create `src/services/content/section_history_contracts.py` (168 lines after `ruff format`):
```python
"""Section-id contract, index conversion, errors and repo protocols (L-013).

PUBLIC CONTRACT: ``section_id = f"{article_id}:{outline_index}"`` where
``outline_index`` is the 0-based index over H2 sections — the same space as
`ArticleOutline.sections[].index`, `SectionDraft.section_index`,
`ImagePlacement.section_index` and the frontend's `sectionIdx`.

`section_markdown.split_sections` uses a different space: index 0 is ALWAYS
the prelude (possibly empty), so the first H2 is markdown index 1. The two
helpers below are the ONLY place that conversion happens.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, TypedDict
from uuid import UUID

from src.models.content import CanonicalArticle
from src.services.content.section_anchors import AnchorViolation


def md_index_for(outline_index: int) -> int:
    """Outline (0-based H2) index → `split_sections` index (prelude is 0)."""
    return outline_index + 1


def outline_index_for(md_index: int) -> int:
    """Inverse of `md_index_for`."""
    return md_index - 1


def make_section_id(article_id: UUID, outline_index: int) -> str:
    """Stable, schema-free identifier — outline space (L-013)."""
    return f"{article_id}:{outline_index}"


def parse_section_id(section_id: str) -> tuple[UUID, int]:
    """Inverse of `make_section_id`. Raises ValueError on malformed input."""
    if ":" not in section_id:
        raise ValueError(f"section_id missing ':' separator: {section_id!r}")
    raw_article, raw_index = section_id.rsplit(":", 1)
    return UUID(raw_article), int(raw_index)


class AnchorViolationError(Exception):
    """Raised when an edit would drop one or more required anchors."""

    def __init__(self, violations: list[AnchorViolation]) -> None:
        self.violations = violations
        super().__init__(f"edit would drop {len(violations)} required anchor(s)")


class SectionNotFoundError(Exception):
    """Raised when the article exists but the section index is out of range."""


class ArticleNotFoundError(Exception):
    """Raised when the article id does not resolve to a CanonicalArticle."""


class ArticleRepoProtocol(Protocol):
    async def get(self, article_id: UUID) -> CanonicalArticle | None: ...
    async def update_body_markdown(
        self, article_id: UUID, body_markdown: str
    ) -> CanonicalArticle | None: ...


class VersionRepoProtocol(Protocol):
    """Append-only `section_versions` repo (mirrors PgSectionVersionRepository)."""

    async def append(  # noqa: PLR0913 — repo signature, mirrored for typing
        self,
        *,
        article_id: UUID,
        section_id: str,
        section_index: int,
        markdown: str,
        source: str,
        instruction: str | None = None,
        model: str | None = None,
        tokens_input: int | None = None,
        tokens_output: int | None = None,
        usd: float | None = None,
        created_by: str | None = None,
    ) -> object: ...

    async def list_for_section(
        self,
        *,
        article_id: UUID,
        section_id: str,
        limit: int = 50,
    ) -> list[object]: ...

    async def get(self, version_id: UUID) -> object | None: ...


class VersionMeta(TypedDict, total=False):
    """Optional audit columns of a `section_versions` row (PEP 692 kwargs)."""

    instruction: str | None
    model: str | None
    tokens_input: int | None
    tokens_output: int | None
    usd: float | None
    created_by: str | None


@dataclass(frozen=True)
class VersionRow:
    """Inputs for one `section_versions` append (outline-space index)."""

    article_id: UUID
    section_index: int
    markdown: str
    source: str
    instruction: str | None = None
    model: str | None = None
    tokens_input: int | None = None
    tokens_output: int | None = None
    usd: float | None = None
    created_by: str | None = None


@dataclass(frozen=True)
class PersistResult:
    """Outcome of `persist_section_update`."""

    article: CanonicalArticle
    new_section_markdown: str
    version_id: UUID


async def append_version_row(repo: VersionRepoProtocol, row: VersionRow) -> UUID:
    """The ONE fan-out from `VersionRow` to the repo's 11-kwarg `append`."""
    version = await repo.append(
        article_id=row.article_id,
        section_id=make_section_id(row.article_id, row.section_index),
        section_index=row.section_index,
        markdown=row.markdown,
        source=row.source,
        instruction=row.instruction,
        model=row.model,
        tokens_input=row.tokens_input,
        tokens_output=row.tokens_output,
        usd=row.usd,
        created_by=row.created_by,
    )
    version_id: UUID = version.id  # type: ignore[attr-defined]
    return version_id


__all__ = [
    "AnchorViolationError",
    "ArticleNotFoundError",
    "ArticleRepoProtocol",
    "PersistResult",
    "SectionNotFoundError",
    "VersionMeta",
    "VersionRepoProtocol",
    "VersionRow",
    "append_version_row",
    "make_section_id",
    "md_index_for",
    "outline_index_for",
    "parse_section_id",
]
```

Replace `src/services/content/section_history.py` with (187 lines after `ruff format`; `persist_section_update` keeps every existing keyword caller working — the six optional audit columns arrive through `**meta: Unpack[VersionMeta]`, PEP 692, so the signature is 8 lines instead of 13 and the function is 18 lines AST-measured):
```python
"""Section-level edit history service (VISUAL-011 / Phase 8; L-013 index contract).

Stitches the canonical article body, the anchor validator, and the
append-only `section_versions` repository into one Service-Layer entry
point that the `/content/*` route handlers call.

Boundary invariants (mirrored from plan §11.8):
- The active state still lives on `CanonicalArticle.body_markdown` —
  this service updates that on every persist. The `section_versions`
  table is an audit sidecar; no other subsystem reads it.
- Anchor preservation is enforced here. Edits that drop a `data-spec-id`
  marker or rename a heading bound to a `before_heading` placement
  raise `AnchorViolationError`, which the route maps to HTTP 422.
- Index contract (L-013): every public `section_index` is the 0-based H2
  (outline) index. `md_index_for` converts to `split_sections` space
  exactly where the body is read / replaced; `validate_anchors` always
  receives the outline index.

Contracts (errors, protocols, `VersionRow`, index helpers) live in
`section_history_contracts`; import them from there.
"""

from __future__ import annotations

from typing import Unpack
from uuid import UUID

import structlog

from src.models.content import CanonicalArticle
from src.services.content.section_anchors import validate_anchors
from src.services.content.section_history_contracts import (
    AnchorViolationError,
    ArticleNotFoundError,
    ArticleRepoProtocol,
    PersistResult,
    SectionNotFoundError,
    VersionMeta,
    VersionRepoProtocol,
    VersionRow,
    append_version_row,
    md_index_for,
    outline_index_for,
    parse_section_id,
)
from src.services.content.section_markdown import (
    MarkdownSection,
    get_section,
    replace_section,
)

logger = structlog.get_logger()


class SectionHistoryService:
    """Single Service-Layer entry point used by `/content/*` routes."""

    def __init__(
        self,
        articles: ArticleRepoProtocol,
        versions: VersionRepoProtocol,
    ) -> None:
        self._articles = articles
        self._versions = versions

    async def get_section_markdown(
        self,
        article_id: UUID,
        section_index: int,
    ) -> tuple[CanonicalArticle, MarkdownSection]:
        """Fetch the article + the H2 section at OUTLINE index `section_index`."""
        article = await self._articles.get(article_id)
        if article is None:
            raise ArticleNotFoundError(str(article_id))
        section = None
        if section_index >= 0:
            section = get_section(article.body_markdown, md_index_for(section_index))
        if section is None:
            raise SectionNotFoundError(
                f"section {section_index} of article {article_id} not found"
            )
        return article, section

    async def persist_section_update(
        self,
        *,
        article_id: UUID,
        section_index: int,
        new_section_markdown: str,
        source: str,
        **meta: Unpack[VersionMeta],
    ) -> PersistResult:
        """Validate anchors, swap the OUTLINE section in, append a version row."""
        row = VersionRow(
            article_id=article_id,
            section_index=section_index,
            markdown=new_section_markdown,
            source=source,
            **meta,
        )
        return await self._persist_row(row)

    async def _persist_row(self, row: VersionRow) -> PersistResult:
        article, section = await self.get_section_markdown(
            row.article_id, row.section_index
        )
        _ensure_anchors(article, section, row.markdown)
        updated = await self._swap_section(article, row)
        version_id = await append_version_row(self._versions, row)
        logger.info(
            "section_persisted",
            article_id=str(row.article_id),
            section_index=row.section_index,
            source=row.source,
            version_id=str(version_id),
        )
        return PersistResult(
            article=updated, new_section_markdown=row.markdown, version_id=version_id
        )

    async def _swap_section(
        self, article: CanonicalArticle, row: VersionRow
    ) -> CanonicalArticle:
        """Replace the OUTLINE section in the body and persist it."""
        new_body = replace_section(
            article.body_markdown, md_index_for(row.section_index), row.markdown
        )
        updated = await self._articles.update_body_markdown(article.id, new_body)
        if updated is None:  # race: article deleted between fetch + update
            raise ArticleNotFoundError(str(article.id))
        return updated

    async def list_history(self, section_id: str, limit: int = 50) -> list[object]:
        article_id, _ = parse_section_id(section_id)
        return await self._versions.list_for_section(
            article_id=article_id, section_id=section_id, limit=limit
        )

    async def restore(
        self,
        *,
        section_id: str,
        version_id: UUID,
        created_by: str | None = None,
    ) -> PersistResult:
        """Restore a section to a prior version. Appends a `restore` version row."""
        article_id, section_index = parse_section_id(section_id)
        markdown = await self._version_markdown(version_id)
        return await self.persist_section_update(
            article_id=article_id,
            section_index=section_index,
            new_section_markdown=markdown,
            source="restore",
            instruction=f"restore version {version_id}",
            created_by=created_by,
        )

    async def _version_markdown(self, version_id: UUID) -> str:
        version = await self._versions.get(version_id)
        if version is None:
            raise SectionNotFoundError(f"version {version_id} not found")
        markdown = getattr(version, "markdown", None)
        if not isinstance(markdown, str):
            raise SectionNotFoundError(f"version {version_id} has no markdown payload")
        return markdown


def _ensure_anchors(
    article: CanonicalArticle, section: MarkdownSection, new_markdown: str
) -> None:
    """Run the validator with the OUTLINE index (ImagePlacement.section_index space)."""
    violations = validate_anchors(
        original_markdown=section.text,
        new_markdown=new_markdown,
        image_specs=list(article.image_specs),
        section_index=outline_index_for(section.index),
    )
    if violations:
        raise AnchorViolationError(violations)


__all__ = [
    "AnchorViolationError",
    "ArticleNotFoundError",
    "SectionHistoryService",
    "SectionNotFoundError",
]
```

`src/api/routers/content.py` — re-point the two contract names (the service module no longer re-exports them; everything else in `content.py` is untouched until Task 3):
```python
from src.services.content.section_history import (
    AnchorViolationError,
    ArticleNotFoundError,
    SectionHistoryService,
    SectionNotFoundError,
)
from src.services.content.section_history_contracts import (
    make_section_id,
    parse_section_id,
)
```

`frontend/src/lib/api/content.ts` — replace the `makeSectionId` doc comment:
```ts
/**
 * Stable section identifier used by the toolbar + drawer + popover.
 * `sectionIndex` is the 0-based H2 (outline) index — the same space the
 * backend's `make_section_id` uses since AUTHOR-004 (L-013). Never add
 * an offset for the prelude here; `SectionHistoryService` converts to
 * `split_sections` indices internally.
 */
```

- [ ] **Step 4: Run — expect pass; whole content suite green**

`COGNIFY_ANTHROPIC_API_KEY= uv run pytest tests/unit/services/content tests/unit/api/test_content_endpoints.py -q -p no:cacheprovider` → all pass (`test_md_index_is_outline_plus_one_and_inverts`, `test_append_version_row_fans_out_every_column`, `TestOutlineIndexContract` ×5, `TestOutlineIndexContractEndpoint` ×1 = **8 new**; 4 existing tests re-pointed from index 1 to 0). `wc -l src/services/content/section_history.py src/services/content/section_history_contracts.py` → **187 / 168** (measured after `ruff format`). Function lengths (AST, `def` line through end): `get_section_markdown` 17, `persist_section_update` 18, `_persist_row` 17, `_swap_section` 11, `restore` 18, `_version_markdown` 8, `_ensure_anchors` 12, `append_version_row` 17 — verify with `uv run python -c "import ast,sys;[print(f.name,f.end_lineno-f.lineno+1) for p in sys.argv[1:] for f in ast.walk(ast.parse(open(p).read())) if isinstance(f,(ast.FunctionDef,ast.AsyncFunctionDef)) and f.end_lineno-f.lineno+1>=20]" src/services/content/section_history.py src/services/content/section_history_contracts.py` → prints nothing.

- [ ] **Step 5: Lint + commit**

`uv run ruff check --fix src/ tests/ && uv run ruff format src/ tests/ && uv run mypy src/ --ignore-missing-imports`
`git add src/services/content/section_history.py src/services/content/section_history_contracts.py src/api/routers/content.py frontend/src/lib/api/content.ts tests/unit/services/content/test_section_history.py tests/unit/api/test_content_endpoints.py && git commit -m "fix(content): section_id is the 0-based outline index everywhere; md_index_for is the only conversion (L-013, AUTHOR-004)"`

---

### Task 2: `draft_one_section` + `instruction` hook + `extract_usage` (no behaviour change for the graph)

**Files:**
- Create: `src/agents/content/section_prompt.py`, `src/utils/llm_usage.py`
- Modify: `src/agents/content/section_drafter.py`
- Test: `tests/unit/agents/content/test_section_prompt.py` (new), `tests/unit/utils/test_llm_usage.py` (new)
- Regression: `tests/unit/agents/content/test_section_drafter.py`, `tests/unit/agents/content/test_prompt_updates.py` (imports `_SYSTEM_PROMPT` from `section_drafter` — keep the re-export), `tests/unit/agents/content/test_pipeline.py`

**Interfaces:**
```python
# src/utils/llm_usage.py
def extract_usage(response: object) -> dict[str, int | None]     # {"input": …, "output": …}; promoted verbatim from section_rewriter._extract_usage

# src/agents/content/section_prompt.py
SYSTEM_PROMPT: str
def build_system_prompt(section: OutlineSection, ctx: DraftingContext) -> str
def build_user_prompt(section: OutlineSection, chunks: list[ChunkResult], prior_drafts: list[SectionDraft]) -> str
def build_messages(section: OutlineSection, chunks: list[ChunkResult], ctx: DraftingContext) -> list[BaseMessage]

# src/agents/content/section_drafter.py
@dataclass(frozen=True)
class DraftingContext:            # existing fields unchanged + new trailing field
    instruction: str | None = None
@dataclass(frozen=True)
class OneSectionDraft: body_markdown: str; word_count: int; tokens_input: int | None; tokens_output: int | None
async def draft_section(section, queries, ctx) -> SectionDraft          # unchanged behaviour
async def draft_one_section(section, queries, ctx) -> OneSectionDraft   # graph-free; one LLM call
_SYSTEM_PROMPT = SYSTEM_PROMPT    # re-export for test_prompt_updates.py
```

- [ ] **Step 1: Write the failing tests**

`tests/unit/utils/test_llm_usage.py`:
```python
"""extract_usage — promoted from section_rewriter so drafter + rewriter share it."""

from langchain_core.messages import AIMessage

from src.utils.llm_usage import extract_usage


def test_reads_usage_metadata() -> None:
    msg = AIMessage(
        content="x",
        usage_metadata={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
    )
    assert extract_usage(msg) == {"input": 10, "output": 5}


def test_falls_back_to_response_metadata_usage() -> None:
    msg = AIMessage(content="x", response_metadata={"usage": {"prompt_tokens": 7, "completion_tokens": 3}})
    assert extract_usage(msg) == {"input": 7, "output": 3}


def test_unknown_shape_yields_nones() -> None:
    assert extract_usage(object()) == {"input": None, "output": None}
```

`tests/unit/agents/content/test_section_prompt.py`:
```python
"""AUTHOR-004 Task 2 — prompt assembly split + instruction slot + draft_one_section."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from src.agents.content.section_drafter import (
    _SYSTEM_PROMPT,
    DraftingContext,
    OneSectionDraft,
    draft_one_section,
    draft_section,
)
from src.agents.content.section_prompt import (
    SYSTEM_PROMPT,
    build_messages,
    build_system_prompt,
    build_user_prompt,
)
from src.models.content_pipeline import OutlineSection, SectionDraft, SectionQueries


def _section(index: int = 0) -> OutlineSection:
    return OutlineSection(
        index=index,
        title=f"Section {index}",
        description="What this section covers",
        key_points=["point a", "point b"],
        target_word_count=300,
        relevant_facets=[0],
    )


def _ctx(instruction: str | None = None, reply: AIMessage | None = None) -> DraftingContext:
    llm = AsyncMock()
    llm.ainvoke = AsyncMock(return_value=reply or AIMessage(content="Drafted body."))
    return DraftingContext(
        retriever=None,
        topic_id="topic-1",
        llm=llm,
        prior_drafts=[],
        target_audience="CTOs",
        instruction=instruction,
    )


class TestSystemPrompt:
    def test_reexport_is_identical(self) -> None:
        assert _SYSTEM_PROMPT == SYSTEM_PROMPT
        assert "{target_word_count}" in SYSTEM_PROMPT

    def test_builds_audience_and_word_target(self) -> None:
        system = build_system_prompt(_section(), _ctx())
        assert "approximately 300 words" in system
        assert "Write for this audience: CTOs." in system
        assert "Editor instruction" not in system

    def test_instruction_is_appended_when_present(self) -> None:
        system = build_system_prompt(_section(), _ctx(instruction="Lead with the metric"))
        assert system.rstrip().endswith("Editor instruction for this section: Lead with the metric")

    def test_blank_instruction_is_ignored(self) -> None:
        assert "Editor instruction" not in build_system_prompt(_section(), _ctx(instruction="   "))


class TestUserPrompt:
    def test_prior_sections_use_first_sentence(self) -> None:
        prior = SectionDraft(
            section_index=0,
            title="Intro",
            body_markdown="First sentence here. Second sentence.",
            word_count=5,
            citations_used=[],
        )
        user = build_user_prompt(_section(1), [], [prior])
        assert "### Prior Sections" in user
        assert "- Intro: First sentence here." in user
        assert "### Research Context" not in user


class TestBuildMessages:
    def test_returns_system_then_human(self) -> None:
        messages = build_messages(_section(), [], _ctx(instruction="shorter"))
        assert isinstance(messages[0], SystemMessage)
        assert isinstance(messages[1], HumanMessage)
        assert "shorter" in str(messages[0].content)


class TestDraftOneSection:
    @pytest.mark.asyncio
    async def test_returns_body_word_count_and_no_usage_when_absent(self) -> None:
        ctx = _ctx(reply=AIMessage(content="New prose [1] here."))
        out = await draft_one_section(_section(), SectionQueries(section_index=0, queries=[]), ctx)
        assert isinstance(out, OneSectionDraft)
        assert out.body_markdown == "New prose [1] here."
        assert out.word_count == 4
        assert out.tokens_input is None and out.tokens_output is None
        ctx.llm.ainvoke.assert_awaited_once()  # exactly one LLM call (L-007)

    @pytest.mark.asyncio
    async def test_returns_token_usage_when_present(self) -> None:
        reply = AIMessage(
            content="Prose.",
            usage_metadata={"input_tokens": 120, "output_tokens": 40, "total_tokens": 160},
        )
        out = await draft_one_section(_section(), SectionQueries(section_index=0, queries=[]), _ctx(reply=reply))
        assert (out.tokens_input, out.tokens_output) == (120, 40)

    @pytest.mark.asyncio
    async def test_instruction_reaches_the_llm(self) -> None:
        ctx = _ctx(instruction="Use a worked example")
        await draft_one_section(_section(), SectionQueries(section_index=0, queries=[]), ctx)
        sent = ctx.llm.ainvoke.await_args.args[0]
        assert "Use a worked example" in str(sent[0].content)

    @pytest.mark.asyncio
    async def test_draft_section_still_returns_section_draft(self) -> None:
        ctx = _ctx(reply=AIMessage(content="Body text."))
        draft = await draft_section(_section(2), SectionQueries(section_index=2, queries=[]), ctx)
        assert draft.section_index == 2
        assert draft.body_markdown == "Body text."
```

- [ ] **Step 2: Run — expect failure**

`COGNIFY_ANTHROPIC_API_KEY= uv run pytest tests/unit/utils/test_llm_usage.py tests/unit/agents/content/test_section_prompt.py -q -p no:cacheprovider` → `ModuleNotFoundError: src.utils.llm_usage` / `src.agents.content.section_prompt`.

- [ ] **Step 3: Implement**

Create `src/utils/llm_usage.py`:
```python
"""Token-usage extraction from LangChain chat responses.

Promoted from `section_rewriter._extract_usage` (VISUAL-011) so the
section drafter, the rewriter and the regenerate service share one
implementation. Returns ``{"input": int | None, "output": int | None}``.
"""

from __future__ import annotations


def extract_usage(response: object) -> dict[str, int | None]:
    """Pull token counts off whatever Claude / FakeLLM returned."""
    metadata = getattr(response, "usage_metadata", None) or {}
    if isinstance(metadata, dict) and metadata:
        return {
            "input": metadata.get("input_tokens"),
            "output": metadata.get("output_tokens"),
        }
    response_metadata = getattr(response, "response_metadata", None) or {}
    usage = response_metadata.get("usage") if isinstance(response_metadata, dict) else None
    if isinstance(usage, dict):
        return {
            "input": usage.get("input_tokens") or usage.get("prompt_tokens"),
            "output": usage.get("output_tokens") or usage.get("completion_tokens"),
        }
    return {"input": None, "output": None}


__all__ = ["extract_usage"]
```
(The only change from the original is `and metadata` — an empty `usage_metadata` dict now falls through to `response_metadata` instead of returning `{None, None}` early; `section_rewriter` switches to this function in Task 3.)

Create `src/agents/content/section_prompt.py`:
```python
"""Prompt assembly for single-section drafting (split out of section_drafter).

Pure functions — no I/O, no graph imports. `DraftingContext` is imported
under TYPE_CHECKING only to avoid a circular import with section_drafter.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from src.models.content_pipeline import OutlineSection, SectionDraft
from src.models.research import ChunkResult

if TYPE_CHECKING:
    from src.agents.content.section_drafter import DraftingContext

SYSTEM_PROMPT = (
    "You are an expert long-form writer. Draft a section of an article "
    "using the provided research context. Every factual claim must include "
    "an inline citation like [1], [2] referencing the numbered sources. "
    "Write in a clear, authoritative tone. Target approximately "
    "{target_word_count} words. "
    "Do not use em-dashes or en-dashes. Use periods or commas instead. "
    "Avoid words like delve, leverage, innovative, transformative, unprecedented. "
    "Skip transitions like moreover, furthermore, additionally. "
    "Vary sentence length and structure. "
    "Write in a natural voice as a knowledgeable human, not an AI assistant."
)


def build_system_prompt(section: OutlineSection, ctx: DraftingContext) -> str:
    """System prompt = base + session params + optional editor instruction."""
    system = SYSTEM_PROMPT.format(target_word_count=section.target_word_count)
    if ctx.target_audience:
        system += f"\nWrite for this audience: {ctx.target_audience}."
    if ctx.content_tone:
        system += f"\nTone: {ctx.content_tone}."
    if ctx.preferred_angle:
        system += f"\nEditorial angle: {ctx.preferred_angle}."
    if ctx.keywords:
        system += (
            f"\nEnsure these key topics are referenced naturally: "
            f"{', '.join(ctx.keywords)}."
        )
    instruction = (ctx.instruction or "").strip()
    if instruction:
        system += f"\nEditor instruction for this section: {instruction}"
    return system


def build_user_prompt(
    section: OutlineSection,
    chunks: list[ChunkResult],
    prior_drafts: list[SectionDraft],
) -> str:
    """Assemble user prompt with section info, RAG context, and prior summary."""
    parts = [
        f"## Section: {section.title}\n{section.description}",
        f"Key points: {', '.join(section.key_points)}",
        f"Target: ~{section.target_word_count} words\n",
    ]
    if chunks:
        parts.append("### Research Context")
        for i, c in enumerate(chunks, 1):
            source = f'[{i}] Source: "{c.source_title}" ({c.source_url})'
            parts.append(f"{source}\n{c.text}\n")
    if prior_drafts:
        parts.append("### Prior Sections")
        for d in prior_drafts:
            first = d.body_markdown.split(".")[0] + "."
            parts.append(f"- {d.title}: {first}")
    return "\n".join(parts)


def build_messages(
    section: OutlineSection,
    chunks: list[ChunkResult],
    ctx: DraftingContext,
) -> list[BaseMessage]:
    """System + human message pair for one section draft."""
    return [
        SystemMessage(content=build_system_prompt(section, ctx)),
        HumanMessage(content=build_user_prompt(section, chunks, ctx.prior_drafts)),
    ]


__all__ = ["SYSTEM_PROMPT", "build_messages", "build_system_prompt", "build_user_prompt"]
```

Edit `src/agents/content/section_drafter.py`:

1. Replace everything from `import re` down to (and including) the `_CITATION_PATTERN` line with:
```python
import re
from dataclasses import dataclass

import structlog
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage

from src.agents.content.section_prompt import SYSTEM_PROMPT, build_messages
from src.models.content_pipeline import (
    CitationRef,
    OutlineSection,
    SectionDraft,
    SectionQueries,
)
from src.models.research import ChunkResult
from src.services.milvus_retriever import MilvusRetriever
from src.utils.llm_usage import extract_usage

logger = structlog.get_logger()

# Re-exported so existing prompt-regression tests keep importing from here.
_SYSTEM_PROMPT = SYSTEM_PROMPT

_CITATION_PATTERN = re.compile(r"\[(\d+)\]")
```
2. Add the trailing field to `DraftingContext` (after `keywords`):
```python
    instruction: str | None = None
```
3. Insert after `DraftingContext`:
```python
@dataclass(frozen=True)
class OneSectionDraft:
    """Graph-free single-section result (AUTHOR-004 regenerate path)."""

    body_markdown: str
    word_count: int
    tokens_input: int | None
    tokens_output: int | None
```
4. Replace `draft_section` (whole function) and delete `_call_llm` + `_build_user_prompt`; insert instead:
```python
async def draft_section(
    section: OutlineSection,
    queries: SectionQueries,
    ctx: DraftingContext,
) -> SectionDraft:
    """Draft one section using RAG context and LLM (pipeline entry point)."""
    draft, _ = await _draft(section, queries, ctx)
    return draft


async def draft_one_section(
    section: OutlineSection,
    queries: SectionQueries,
    ctx: DraftingContext,
) -> OneSectionDraft:
    """Graph-free single-section draft with token usage (AUTHOR-004).

    Exactly one LLM call; retrieval is skipped when `ctx.retriever` is None.
    """
    draft, response = await _draft(section, queries, ctx)
    usage = extract_usage(response)
    return OneSectionDraft(
        body_markdown=draft.body_markdown,
        word_count=draft.word_count,
        tokens_input=usage.get("input"),
        tokens_output=usage.get("output"),
    )


async def _draft(
    section: OutlineSection,
    queries: SectionQueries,
    ctx: DraftingContext,
) -> tuple[SectionDraft, BaseMessage]:
    """Retrieve, call the LLM once, build the SectionDraft (+ raw response)."""
    logger.info("section_draft_started", section_index=section.index, title=section.title)
    chunks = await _retrieve_chunks(queries, ctx)
    response = await ctx.llm.ainvoke(build_messages(section, chunks, ctx))
    text = str(response.content)
    citations = extract_citations(text, chunks)
    word_count = len(text.split())
    _log_word_count(section, word_count, len(citations))
    draft = SectionDraft(
        section_index=section.index,
        title=section.title,
        body_markdown=text,
        word_count=word_count,
        citations_used=citations,
    )
    return draft, response
```
5. In `_retrieve_chunks`, move the `section_chunks_retrieved` log to the end of the function (it used to live in `draft_section`):
```python
    ranked = sorted(seen.values(), key=lambda c: c.score, reverse=True)[:5]
    logger.info(
        "section_chunks_retrieved",
        section_index=queries.section_index,
        chunk_count=len(ranked),
        unique_sources=len({c.source_url for c in ranked}),
    )
    return ranked
```
6. Add at the bottom: `__all__ = ["DraftingContext", "OneSectionDraft", "draft_one_section", "draft_section", "extract_citations"]`.

- [ ] **Step 4: Run — expect pass, and the regression set stays green**

`COGNIFY_ANTHROPIC_API_KEY= uv run pytest tests/unit/utils/test_llm_usage.py tests/unit/agents/content/test_section_prompt.py tests/unit/agents/content/test_section_drafter.py tests/unit/agents/content/test_prompt_updates.py tests/unit/agents/content/test_pipeline.py -q -p no:cacheprovider` → all pass (**13 new**: 3 usage + 10 prompt/drafter). `wc -l src/agents/content/section_drafter.py src/agents/content/section_prompt.py src/utils/llm_usage.py` → all < 200 (≈ 170 / 90 / 35).

- [ ] **Step 5: Lint + commit**

`uv run ruff check --fix src/ tests/ && uv run ruff format src/ tests/ && uv run mypy src/ --ignore-missing-imports`
`git add src/agents/content/section_prompt.py src/agents/content/section_drafter.py src/utils/llm_usage.py tests/unit/agents/content/test_section_prompt.py tests/unit/utils/test_llm_usage.py && git commit -m "refactor(content): extract section prompt assembly + draft_one_section with instruction slot and token usage (AUTHOR-004)"`

---

### Task 3: Promote shared helpers (reuse, not copy) + `content_shared.py` + `ContentService.deps` + tracked LLM for rewrite

**Files:**
- Create: `src/api/routers/content_shared.py`
- Modify: `src/services/content/section_rewriter.py` (`strip_fences`, `model_label`, import `extract_usage`), `src/agents/content/article_assembler.py` (`strip_leading_heading`), `src/services/content/section_anchors.py` (`find_spec_ids`), `src/api/routers/content.py` (use shared helpers; Literal; `_get_content_llm(request)`), `src/services/content/__init__.py` (`deps` property)
- Test: `tests/unit/api/test_content_shared.py` (new); append classes to `tests/unit/services/content/test_section_rewriter.py`, `tests/unit/services/content/test_section_anchors.py`, `tests/unit/agents/content/test_article_assembler.py`, `tests/unit/api/test_content_endpoints.py`, `tests/unit/services/test_content_service.py`

**Interfaces:**
```python
# section_rewriter.py
def strip_fences(text: str) -> str                       # was _strip_fences
def model_label(llm: object) -> str                      # .model / .model_name, then .inner.*, else "unknown"
# article_assembler.py
def strip_leading_heading(body: str) -> str              # was _strip_leading_heading
# section_anchors.py
def find_spec_ids(markdown: str) -> list[str]            # _SPEC_ID_RE.findall
# content_shared.py
class WordDiffEntry(BaseModel); class AnchorViolationEntry(BaseModel)     # moved from content.py (content.py re-imports them)
def anchor_violation_http(exc: AnchorViolationError) -> HTTPException     # 422 {"error":"anchor_violation","violations":[…]}
def get_history_service(request: Request) -> SectionHistoryService        # was content._get_history_service
# services/content/__init__.py
class ContentService:
    @property
    def deps(self) -> ContentDeps
# content.py
def _get_content_llm(request: Request) -> BaseChatModel   # prefers request.app.state.content_service.deps.llm
def _build_anthropic_llm(settings: Settings) -> ChatAnthropic   # the old body
```

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/services/content/test_section_rewriter.py`:
```python
class TestPromotedHelpers:
    def test_strip_fences_removes_markdown_fence(self) -> None:
        from src.services.content.section_rewriter import strip_fences

        assert strip_fences("```markdown\nbody\n```") == "body"
        assert strip_fences("plain") == "plain"

    def test_model_label_reads_model_then_model_name_then_inner(self) -> None:
        from types import SimpleNamespace

        from src.services.content.section_rewriter import model_label

        assert model_label(SimpleNamespace(model="claude-a")) == "claude-a"
        assert model_label(SimpleNamespace(model_name="claude-b")) == "claude-b"
        tracked = SimpleNamespace(inner=SimpleNamespace(model="claude-inner"))
        assert model_label(tracked) == "claude-inner"
        assert model_label(object()) == "unknown"
```

Append to `tests/unit/services/content/test_section_anchors.py`:
```python
class TestFindSpecIds:
    def test_returns_ids_in_document_order(self) -> None:
        from src.services.content.section_anchors import find_spec_ids

        md = '<figure data-spec-id="b"></figure>\n\ntext\n\n<img data-spec-id="a"/>'
        assert find_spec_ids(md) == ["b", "a"]
        assert find_spec_ids("no anchors") == []
```

Append to `tests/unit/agents/content/test_article_assembler.py`:
```python
class TestStripLeadingHeading:
    def test_drops_duplicated_heading_line_only(self) -> None:
        from src.agents.content.article_assembler import strip_leading_heading

        assert strip_leading_heading("## Title\n\nBody.") == "Body."
        assert strip_leading_heading("Body only.") == "Body only."
```

Create `tests/unit/api/test_content_shared.py`:
```python
"""Shared /content route helpers (AUTHOR-004 Task 3)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from src.api.routers.content_shared import anchor_violation_http, get_history_service
from src.services.content.section_anchors import AnchorViolation
from src.services.content.section_history import AnchorViolationError


def test_anchor_violation_http_shape_matches_section_update_contract() -> None:
    exc = AnchorViolationError(
        [AnchorViolation(kind="spec_id", value="s1", spec_id="s1", message="dropped")]
    )
    http = anchor_violation_http(exc)
    assert http.status_code == 422
    assert http.detail == {
        "error": "anchor_violation",
        "violations": [
            {"kind": "spec_id", "value": "s1", "spec_id": "s1", "message": "dropped"}
        ],
    }


def test_get_history_service_503_when_unconfigured() -> None:
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))
    with pytest.raises(HTTPException) as ei:
        get_history_service(request)  # type: ignore[arg-type]
    assert ei.value.status_code == 503
```

Append to `tests/unit/services/test_content_service.py`:
```python
class TestDepsProperty:
    def test_deps_exposes_injected_content_deps(self) -> None:
        from langchain_core.language_models.fake_chat_models import FakeListChatModel

        from src.services.content import ContentDeps, ContentRepositories, ContentService
        from src.services.content_repositories import (
            InMemoryArticleDraftRepository,
            InMemoryArticleRepository,
        )

        llm = FakeListChatModel(responses=["x"])
        deps = ContentDeps(llm=llm)
        repos = ContentRepositories(
            drafts=InMemoryArticleDraftRepository(),
            research=None,  # type: ignore[arg-type]
            articles=InMemoryArticleRepository(),
        )
        assert ContentService(repos, deps).deps is deps
```

Append to `tests/unit/api/test_content_endpoints.py`:
```python
class TestContentLlmSource:
    """_get_content_llm prefers the pipeline's (tracked) deps; falls back to ChatAnthropic."""

    async def test_rewrite_uses_content_service_deps_llm(
        self,
        content_app: FastAPI,
        content_client: httpx.AsyncClient,
        content_settings: Settings,
        section_id: str,
    ) -> None:
        from src.services.content import ContentDeps, ContentRepositories, ContentService
        from src.services.content_repositories import (
            InMemoryArticleDraftRepository,
            InMemoryArticleRepository,
        )

        repos = ContentRepositories(
            drafts=InMemoryArticleDraftRepository(),
            research=None,  # type: ignore[arg-type]
            articles=InMemoryArticleRepository(),
        )
        content_app.state.content_service = ContentService(
            repos, ContentDeps(llm=FakeListChatModel(responses=["Tracked reply."]))
        )
        with patch("src.api.routers.content._build_anthropic_llm") as build:
            resp = await content_client.post(
                "/api/v1/content/section-rewrite",
                json={"section_id": section_id, "instruction": "Tighten.", "current_markdown": "Old."},
                headers=_editor_headers(content_settings),
            )
        assert resp.status_code == 200, resp.text
        assert resp.json()["markdown_fragment"] == "Tracked reply."
        build.assert_not_called()

    async def test_rewrite_falls_back_to_anthropic_builder(
        self,
        content_client: httpx.AsyncClient,
        content_settings: Settings,
        section_id: str,
    ) -> None:
        fake = FakeListChatModel(responses=["Fallback reply."])
        with patch("src.api.routers.content._build_anthropic_llm", return_value=fake) as build:
            resp = await content_client.post(
                "/api/v1/content/section-rewrite",
                json={"section_id": section_id, "instruction": "Tighten.", "current_markdown": "Old."},
                headers=_editor_headers(content_settings),
            )
        assert resp.status_code == 200, resp.text
        assert resp.json()["markdown_fragment"] == "Fallback reply."
        build.assert_called_once()
```

- [ ] **Step 2: Run — expect failure**

`COGNIFY_ANTHROPIC_API_KEY= uv run pytest tests/unit/api/test_content_shared.py tests/unit/services/content/test_section_rewriter.py tests/unit/services/content/test_section_anchors.py tests/unit/agents/content/test_article_assembler.py tests/unit/api/test_content_endpoints.py tests/unit/services/test_content_service.py -q -p no:cacheprovider` → ImportErrors (`content_shared`, `strip_fences`, `model_label`, `find_spec_ids`, `strip_leading_heading`), `AttributeError: deps`, `_build_anthropic_llm` not found.

- [ ] **Step 3: Implement**

`src/services/content/section_rewriter.py`:
1. Add import `from src.utils.llm_usage import extract_usage`; delete the local `_extract_usage` function; in `rewrite_section_prose` change `usage = _extract_usage(response)` → `usage = extract_usage(response)`.
2. Rename `_strip_fences` → `strip_fences` (definition + the call `fragment = _strip_fences(raw)` → `fragment = strip_fences(raw)`).
3. Replace the inline `model_name = (getattr(llm, "model", None) or …)` expression with `model_name = model_label(llm)` and add:
```python
def model_label(llm: object) -> str:
    """Best-effort model name for version rows / responses (TrackedChatModel wraps `.inner`)."""
    for target in (llm, getattr(llm, "inner", None)):
        for attr in ("model", "model_name"):
            value = getattr(target, attr, None)
            if isinstance(value, str) and value:
                return value
    return "unknown"
```
4. `__all__` += `"model_label", "strip_fences"`.

`src/agents/content/article_assembler.py`: rename `_strip_leading_heading` → `strip_leading_heading` (definition + the call inside `_compile_body`); append `__all__ = ["assemble_canonical_article", "strip_leading_heading"]`.

`src/services/content/section_anchors.py`: add after `_SPEC_ID_RE`:
```python
def find_spec_ids(markdown: str) -> list[str]:
    """All `data-spec-id` values in document order (duplicates preserved)."""
    return _SPEC_ID_RE.findall(markdown)
```
In `_check_spec_ids` use `set(find_spec_ids(original))` / `set(find_spec_ids(new))`. `__all__` += `"find_spec_ids"`.

`src/services/content/__init__.py` — inside `ContentService`, directly after `__init__`:
```python
    @property
    def deps(self) -> ContentDeps:
        """Pipeline LLM / retriever / settings — shared with ad-hoc prose routes (AUTHOR-004)."""
        return self._deps
```

Create `src/api/routers/content_shared.py`:
```python
"""Helpers shared by the /content routers (content.py + content_regenerate.py).

Lifted out of `content.py` (AUTHOR-004) so the regenerate router can emit a
byte-identical 422 anchor-violation payload and resolve the same
`SectionHistoryService` without importing the 500-line module.
"""

from __future__ import annotations

from typing import Literal

from fastapi import HTTPException, Request
from fastapi import status as http_status
from pydantic import BaseModel

from src.services.content.section_history import (
    AnchorViolationError,
    SectionHistoryService,
)
from src.services.content.word_diff import WordDiffOp


class WordDiffEntry(BaseModel):
    """Wire-format mirror of `WordDiffOp` so OpenAPI knows the shape."""

    kind: Literal["equal", "insert", "delete", "replace"]
    before: str
    after: str

    @classmethod
    def from_op(cls, op: WordDiffOp) -> WordDiffEntry:
        return cls(kind=op.kind, before=op.before, after=op.after)


class AnchorViolationEntry(BaseModel):
    kind: Literal["spec_id", "heading_text"]
    value: str
    spec_id: str | None = None
    message: str


def anchor_violation_http(exc: AnchorViolationError) -> HTTPException:
    """The ONE 422 shape for every anchor violation (section-update, restore, regenerate)."""
    return HTTPException(
        status_code=http_status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail={
            "error": "anchor_violation",
            "violations": [
                AnchorViolationEntry(
                    kind=v.kind, value=v.value, spec_id=v.spec_id, message=v.message
                ).model_dump()
                for v in exc.violations
            ],
        },
    )


def get_history_service(request: Request) -> SectionHistoryService:
    """Resolve (and memoise) the SectionHistoryService from app.state; 503 if unconfigured."""
    svc = getattr(request.app.state, "section_history_service", None)
    if svc is None:
        article_repo = getattr(request.app.state, "article_repo", None)
        version_repo = getattr(request.app.state, "section_version_repo", None)
        if article_repo is None or version_repo is None:
            raise HTTPException(
                status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="section history service is not configured",
            )
        svc = SectionHistoryService(article_repo, version_repo)
        request.app.state.section_history_service = svc
    assert isinstance(svc, SectionHistoryService)
    return svc


__all__ = [
    "AnchorViolationEntry",
    "WordDiffEntry",
    "anchor_violation_http",
    "get_history_service",
]
```

`src/api/routers/content.py` (minimal, mechanical):
1. Imports: add `from langchain_core.language_models import BaseChatModel` and `from src.api.routers.content_shared import (AnchorViolationEntry, WordDiffEntry, anchor_violation_http, get_history_service)`; drop `from src.services.content.word_diff import WordDiffOp` (no longer used here).
2. Delete the local `WordDiffEntry` and `AnchorViolationEntry` class definitions (the "Shared schemas" block) — the imports above keep every existing reference (`SectionRewriteResponse.diff`, `WordDiffEntry.from_op`, …) working.
3. In `section_update` and `section_restore`, replace each whole `except AnchorViolationError as exc: raise HTTPException(status_code=…422…, detail={…}) from exc` block with:
```python
    except AnchorViolationError as exc:
        raise anchor_violation_http(exc) from exc
```
4. Delete the local `_get_history_service` function; `sed -i 's/_get_history_service(/get_history_service(/g' src/api/routers/content.py` (5 call sites). `SectionHistoryService` is then unused in `content.py` — let `ruff check --fix` drop it from the `section_history` import (F401).
5. `SectionUpdateRequest.source`:
```python
    source: Literal["manual", "ai", "tone_preset", "restore", "regenerate"] = "manual"
```
6. Replace `_get_content_llm` with:
```python
def _get_content_llm(request: Request) -> BaseChatModel:
    """Prefer the pipeline's (tracked) LLM so rewrite + regenerate share cost tracking."""
    service = getattr(request.app.state, "content_service", None)
    llm = getattr(getattr(service, "deps", None), "llm", None)
    if llm is not None:
        return llm  # type: ignore[no-any-return]
    return _build_anthropic_llm(request.app.state.settings)


def _build_anthropic_llm(settings: Settings) -> ChatAnthropic:
    """Fallback Claude chat model for prose rewrites (no ContentService on app.state)."""
    from pydantic import SecretStr

    return ChatAnthropic(
        model_name=settings.anthropic_model,
        api_key=SecretStr(settings.anthropic_api_key),
        timeout=30.0,
        stop=None,
        max_retries=2,
    )
```
and change both call sites (`section_rewrite`, `humanize_preview`) from `llm = _get_content_llm(settings)` to `llm = _get_content_llm(request)`. (Existing tests patch `src.api.routers.content._get_content_llm` with `return_value=` — still valid.)

- [ ] **Step 4: Run — expect pass**

`COGNIFY_ANTHROPIC_API_KEY= uv run pytest tests/unit/api tests/unit/services/content tests/unit/services/test_content_service.py tests/unit/agents/content/test_article_assembler.py -q -p no:cacheprovider` → all pass (**9 new**: 2 rewriter, 1 anchors, 1 assembler, 2 shared, 1 deps, 2 llm-source). `wc -l src/api/routers/content_shared.py` < 200; `src/api/routers/content.py` ≈ 495 (down from 546).

- [ ] **Step 5: Lint + commit**

`uv run ruff check --fix src/ tests/ && uv run ruff format src/ tests/ && uv run mypy src/ --ignore-missing-imports`
`git add src/api/routers/content_shared.py src/api/routers/content.py src/services/content/section_rewriter.py src/services/content/section_anchors.py src/services/content/__init__.py src/agents/content/article_assembler.py tests/unit/api/test_content_shared.py tests/unit/api/test_content_endpoints.py tests/unit/services/content/test_section_rewriter.py tests/unit/services/content/test_section_anchors.py tests/unit/services/test_content_service.py tests/unit/agents/content/test_article_assembler.py && git commit -m "refactor(content): promote strip_fences/model_label/strip_leading_heading/find_spec_ids, shared /content route helpers, ContentService.deps + tracked LLM for rewrite (AUTHOR-004)"`

---

### Task 4: `find_by_article_id` + `SectionRegenerateService`

**Files:**
- Modify: `src/services/content_repositories.py` (`ArticleDraftRepository.find_by_article_id` Protocol + `InMemoryArticleDraftRepository`), `src/db/repositories.py` (`PgArticleDraftRepository.find_by_article_id`)
- Create: `src/services/content/section_regenerate_models.py`, `src/services/content/section_regenerate_text.py`, `src/services/content/section_regenerate.py`
- Test: `tests/unit/services/test_content_repositories_find_by_article_id.py` (new), `tests/unit/services/content/test_section_regenerate.py` (new); append one test to `tests/integration/db/test_pg_repositories.py` (runs only with the DB up — L-005)

**Why `find_by_article_id` (read ambiguity #6 first):** `article.provenance.research_session_id` is the TOPIC id for every pipeline-generated article, so the only reliable join from a `CanonicalArticle` back to its outline is `article_drafts.article_id`, which `store_article` stamps at finalization. `draft.session_id` is then the real research-session id used for `research.get(...)` and for the `llm_calls` contextvar.

**Interfaces:**
```python
# content_repositories.py
class ArticleDraftRepository(Protocol):
    ...existing...
    async def find_by_article_id(self, article_id: UUID) -> ArticleDraft | None: ...   # newest draft stamped with this article_id
# db/repositories.py — PgArticleDraftRepository.find_by_article_id: same shape as find_latest_by_session, WHERE article_id = :id ORDER BY created_at DESC LIMIT 1

# section_regenerate_models.py (value objects; no I/O)
STEP_NAME = "section_regenerate"
class DraftContextMissingError(Exception)
@dataclass(frozen=True) class RegenerateCommand: article_id: UUID; section_index: int; instruction: str | None = None; created_by: str | None = None
@dataclass(frozen=True) class RegenerateDeps: history: SectionHistoryService; versions: VersionRepoProtocol; drafts: ArticleDraftRepository; research: ResearchSessionReader; llm: BaseChatModel; retriever: MilvusRetriever | None = None
@dataclass(frozen=True) class RegenerateInputs: cmd; article; old: MarkdownSection; draft: ArticleDraft; outline_section: OutlineSection; session: ResearchSession | None
@dataclass(frozen=True) class RegenerateResult: section_id: str; section_index: int; markdown: str; diff: list[WordDiffOp]; version_id: UUID; model: str; word_count: int; tokens_input: int | None; tokens_output: int | None

# section_regenerate_text.py (I/O-free helpers)
def build_drafting_context(prep: RegenerateInputs, deps: RegenerateDeps) -> DraftingContext
def reject_non_prose(section: MarkdownSection, article_id: UUID) -> None      # References / heading-less → SectionNotFoundError
def carry_anchor_blocks(old_body: str, new_body: str) -> str                   # block-position carry (markdown_structure)
def assemble_section(old: MarkdownSection, raw_llm_text: str) -> str           # strip fences + dup heading + [N]; re-prefix old.heading; carry anchors
def prior_drafts_from_body(body_markdown: str, section_index: int) -> list[SectionDraft]   # live H2 sections BEFORE outline index, prose blocks only
def queries_for(section: OutlineSection) -> SectionQueries                    # [title, *key_points]

# section_regenerate.py
class SectionRegenerateService:
    def __init__(self, deps: RegenerateDeps) -> None
    async def regenerate(self, cmd: RegenerateCommand) -> RegenerateResult
        # raises ArticleNotFoundError, SectionNotFoundError, DraftContextMissingError, AnchorViolationError
```
`section_index` is the OUTLINE index everywhere (command, result, version row, `validate_anchors`, `make_section_id`). The service never adds 1 — `SectionHistoryService.get_section_markdown` does the conversion (Task 1).

- [ ] **Step 1: Write the failing tests**

`tests/unit/services/test_content_repositories_find_by_article_id.py`:
```python
"""ArticleDraftRepository.find_by_article_id (AUTHOR-004 Task 4)."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from src.models.content_pipeline import ArticleDraft
from src.services.content_repositories import InMemoryArticleDraftRepository


def _draft(article_id: UUID | None, created_at: datetime) -> ArticleDraft:
    return ArticleDraft(
        session_id=uuid4(), topic_id=uuid4(), article_id=article_id, created_at=created_at
    )


@pytest.mark.asyncio
async def test_find_by_article_id_returns_newest_matching_draft() -> None:
    repo = InMemoryArticleDraftRepository()
    article_id = uuid4()
    now = datetime.now(UTC)
    older = await repo.create(_draft(article_id, now - timedelta(minutes=5)))
    newer = await repo.create(_draft(article_id, now))
    await repo.create(_draft(None, now))  # unfinalised draft — never matches
    found = await repo.find_by_article_id(article_id)
    assert found is not None
    assert found.id == newer.id != older.id


@pytest.mark.asyncio
async def test_find_by_article_id_is_none_when_unknown() -> None:
    repo = InMemoryArticleDraftRepository()
    await repo.create(_draft(uuid4(), datetime.now(UTC)))
    assert await repo.find_by_article_id(uuid4()) is None
```

Append to `tests/integration/db/test_pg_repositories.py` (inside `TestPgArticleRepository`, which already seeds topic + session + article via `_make_canonical_article`; the `article_drafts.article_id` FK needs the article row first):
```python
    async def test_draft_find_by_article_id(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        topic = await _seed_topic(session_factory)
        session = await _seed_session(session_factory, topic.id)
        article = await PgArticleRepository(session_factory).create(
            _make_canonical_article(session.id)
        )
        drafts = PgArticleDraftRepository(session_factory)
        await drafts.create(
            ArticleDraft(
                session_id=session.id,
                topic_id=topic.id,
                article_id=article.id,
                status=DraftStatus.COMPLETE,
                created_at=datetime.now(UTC),
            )
        )
        found = await drafts.find_by_article_id(article.id)
        assert found is not None
        assert found.article_id == article.id
        assert found.session_id == session.id
        assert await drafts.find_by_article_id(uuid4()) is None
```

`tests/unit/services/content/test_section_regenerate.py`:
```python
"""AUTHOR-004 — SectionRegenerateService: diff, positional anchor carry, version row, cost tracking.

The harness mirrors production: `article.provenance.research_session_id` holds the
TOPIC id (graph_state stamps `state["session_id"] = topic.id`), while the
`ArticleDraft` carries the REAL research-session id and is stamped with
`article_id`. Any code path that keys on provenance fails these tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.messages import AIMessage

from src.models.content import CanonicalArticle, ContentType, Provenance, SEOMetadata
from src.models.content_pipeline import ArticleDraft, ArticleOutline, OutlineSection
from src.models.content_pipeline import ContentType as OutlineContentType
from src.models.research_db import ResearchSession
from src.models.visual import ImagePlacement, ImageSpec
from src.services.content.section_history import (
    AnchorViolationError,
    ArticleNotFoundError,
    SectionHistoryService,
    SectionNotFoundError,
)
from src.services.content.section_markdown import split_sections
from src.services.content.section_regenerate import SectionRegenerateService
from src.services.content.section_regenerate_models import (
    DraftContextMissingError,
    RegenerateCommand,
    RegenerateDeps,
)
from src.services.content.section_regenerate_text import (
    assemble_section,
    carry_anchor_blocks,
    prior_drafts_from_body,
    queries_for,
)
from src.services.content_repositories import InMemoryArticleDraftRepository
from src.utils.llm_call_repo import InMemoryLlmCallRepository
from src.utils.tracked_llm import TrackedChatModel, current_session_id, current_step_name

FIGURE = '<figure class="cog-figure" data-spec-id="spec-a"><img src="x.png" alt="a" /></figure>'
FIGURE_B = '<figure class="cog-figure" data-spec-id="spec-b"><img src="y.png" alt="b" /></figure>'

BODY = (
    "## First Section\n"
    "First section body. Second sentence.\n\n"
    f"{FIGURE}\n\n"
    "## Second Section\n"
    "Second section body [1].\n\n"
    "## References\n"
    "1. Source\n"
)


# --- fakes ------------------------------------------------------------------


@dataclass
class _Version:
    id: UUID
    kwargs: dict[str, Any]


class _FakeArticleRepo:
    def __init__(self, article: CanonicalArticle) -> None:
        self.article = article
        self.persisted_body: str | None = None

    async def get(self, article_id: UUID) -> CanonicalArticle | None:
        return self.article if self.article.id == article_id else None

    async def update_body_markdown(self, article_id: UUID, body_markdown: str) -> CanonicalArticle | None:
        self.persisted_body = body_markdown
        self.article = self.article.model_copy(update={"body_markdown": body_markdown})
        return self.article


class _FakeVersionRepo:
    def __init__(self) -> None:
        self.rows: list[_Version] = []

    async def append(self, **kwargs: Any) -> _Version:
        row = _Version(id=uuid4(), kwargs=kwargs)
        self.rows.append(row)
        return row

    async def list_for_section(self, *, article_id: UUID, section_id: str, limit: int = 50) -> list[_Version]:
        return [r for r in self.rows if r.kwargs["section_id"] == section_id][:limit]

    async def get(self, version_id: UUID) -> _Version | None:
        return next((r for r in self.rows if r.id == version_id), None)


class _FakeResearch:
    """Only answers for the REAL session id — a provenance lookup gets None."""

    def __init__(self, session: ResearchSession) -> None:
        self.session = session

    async def get(self, session_id: UUID) -> ResearchSession | None:
        return self.session if session_id == self.session.id else None


def _outline() -> ArticleOutline:
    return ArticleOutline(
        title="T",
        content_type=OutlineContentType.ARTICLE,
        sections=[
            OutlineSection(index=0, title="First Section", description="d0", key_points=["k0"], target_word_count=250, relevant_facets=[0]),
            OutlineSection(index=1, title="Second Section", description="d1", key_points=["k1", "k2"], target_word_count=250, relevant_facets=[0]),
        ],
        total_target_words=500,
        reasoning="r",
    )


def _spec(spec_id: str, heading: str, section_index: int) -> ImageSpec:
    return ImageSpec(
        id=spec_id,
        role_style="concept",
        prompt="p",
        placement=ImagePlacement(anchor="before_heading", heading_text=heading, section_index=section_index),
    )


def _article(provenance_id: UUID, specs: list[ImageSpec] | None = None, body: str = BODY) -> CanonicalArticle:
    return CanonicalArticle(
        id=uuid4(),
        title="T",
        body_markdown=body,
        summary="s",
        content_type=ContentType.ARTICLE,
        seo=SEOMetadata(title="T", description="d"),
        authors=["Cognify"],
        domain="engineering",
        generated_at=datetime.now(UTC),
        provenance=Provenance(research_session_id=provenance_id, primary_model="m", drafting_model="m", embedding_model="e", embedding_version="v1"),
        image_specs=specs or [],
    )


class _Harness:
    def __init__(
        self,
        *,
        with_draft: bool = True,
        specs: list[ImageSpec] | None = None,
        reply: AIMessage | None = None,
        body: str = BODY,
    ) -> None:
        self.session_id = uuid4()  # the REAL research session (draft.session_id)
        self.topic_id = uuid4()  # what provenance.research_session_id really holds
        self.article = _article(self.topic_id, specs, body)
        self.articles = _FakeArticleRepo(self.article)
        self.versions = _FakeVersionRepo()
        self.drafts = InMemoryArticleDraftRepository()
        self.llm: Any = AsyncMock()
        self.llm.ainvoke = AsyncMock(return_value=reply or AIMessage(content="Fresh prose [1] here."))
        self.llm.model = "claude-test"
        self.session = ResearchSession(id=self.session_id, topic_id=self.topic_id, target_audience="CTOs", content_tone="direct", started_at=datetime.now(UTC))
        self.with_draft = with_draft

    async def service(self) -> SectionRegenerateService:
        if self.with_draft:
            await self.drafts.create(
                ArticleDraft(
                    session_id=self.session_id,
                    topic_id=self.topic_id,
                    article_id=self.article.id,  # stamped by store_article in production
                    outline=_outline(),
                    created_at=datetime.now(UTC),
                )
            )
        deps = RegenerateDeps(
            history=SectionHistoryService(self.articles, self.versions),
            versions=self.versions,
            drafts=self.drafts,
            research=_FakeResearch(self.session),
            llm=self.llm,
            retriever=None,
        )
        return SectionRegenerateService(deps)


def _cmd(h: _Harness, section_index: int, **extra: Any) -> RegenerateCommand:
    return RegenerateCommand(article_id=h.article.id, section_index=section_index, **extra)


# --- text helpers ------------------------------------------------------------


class TestCarryAnchorBlocks:
    def test_figure_first_stays_first(self) -> None:
        out = carry_anchor_blocks(f"{FIGURE}\n\nA.\n\nB.", "X.\n\nY.")
        assert out == f"{FIGURE}\n\nX.\n\nY."

    def test_figure_last_stays_last(self) -> None:
        out = carry_anchor_blocks(f"A.\n\nB.\n\n{FIGURE}", "X.\n\nY.")
        assert out == f"X.\n\nY.\n\n{FIGURE}"

    def test_middle_figure_lands_at_proportional_position(self) -> None:
        # old: A, FIGURE, B  → pos 1 of 3 (rel 0.5); new has 4 blocks → slot round(0.5*4) = 2
        out = carry_anchor_blocks(f"A.\n\n{FIGURE}\n\nB.", "W.\n\nX.\n\nY.\n\nZ.")
        assert out == f"W.\n\nX.\n\n{FIGURE}\n\nY.\n\nZ."

    def test_figure_sharing_a_paragraph_with_prose_does_not_duplicate_prose(self) -> None:
        out = carry_anchor_blocks(f"Some prose.\n{FIGURE}", "New para.")
        assert out == f"{FIGURE}\n\nNew para."
        assert "Some prose." not in out

    def test_two_figures_keep_their_order(self) -> None:
        out = carry_anchor_blocks(f"{FIGURE}\n\nA.\n\n{FIGURE_B}", "X.")
        assert out == f"{FIGURE}\n\nX.\n\n{FIGURE_B}"

    def test_idempotent_when_anchor_already_present(self) -> None:
        out = carry_anchor_blocks(FIGURE, f"new.\n\n{FIGURE}")
        assert out.count("spec-a") == 1


class TestTextHelpers:
    def test_assemble_section_prefixes_heading_and_strips_noise(self) -> None:
        old = split_sections(BODY)[1]  # md index 1 == outline 0 ("First Section")
        raw = "```markdown\n## First Section\nBrand new text [1], more [2].\n```"
        out = assemble_section(old, raw)
        assert out.startswith("## First Section\n\n")
        assert "[1]" not in out and "[2]" not in out
        assert "```" not in out
        assert out.rstrip().endswith(FIGURE)  # figure was last in the old section

    def test_prior_drafts_use_live_sections_before_target(self) -> None:
        prior = prior_drafts_from_body(BODY, section_index=1)
        assert [d.title for d in prior] == ["First Section"]
        assert prior[0].section_index == 0
        assert prior[0].body_markdown.startswith("First section body.")
        assert "data-spec-id" not in prior[0].body_markdown
        assert prior_drafts_from_body(BODY, section_index=0) == []

    def test_prior_drafts_skip_a_leading_figure(self) -> None:
        body = f"## First Section\n{FIGURE}\n\nReal prose first. More.\n\n## Second Section\nx\n"
        prior = prior_drafts_from_body(body, section_index=1)
        assert prior[0].body_markdown.startswith("Real prose first.")

    def test_queries_for_uses_title_and_key_points(self) -> None:
        sq = queries_for(_outline().sections[1])
        assert sq.section_index == 1
        assert sq.queries == ["Second Section", "k1", "k2"]
```
```python
# --- service -------------------------------------------------------------------


class TestRegenerate:
    @pytest.mark.asyncio
    async def test_returns_markdown_diff_and_word_count_without_touching_body(self) -> None:
        h = _Harness()
        svc = await h.service()
        res = await svc.regenerate(_cmd(h, 1))
        assert res.markdown.startswith("## Second Section\n\n")
        assert "Fresh prose" in res.markdown and "[1]" not in res.markdown
        assert any(op.kind != "equal" for op in res.diff)
        assert res.section_index == 1 and res.section_id == f"{h.article.id}:1"
        assert res.word_count == 4  # word count of the raw draft "Fresh prose [1] here."
        assert res.model == "claude-test"
        assert h.articles.persisted_body is None  # candidate only
        h.llm.ainvoke.assert_awaited_once()  # L-007: exactly one LLM call

    @pytest.mark.asyncio
    async def test_preserves_data_spec_id_anchor_from_old_section(self) -> None:
        h = _Harness(specs=[_spec("spec-a", "First Section", 0)])
        svc = await h.service()
        res = await svc.regenerate(_cmd(h, 0))
        assert 'data-spec-id="spec-a"' in res.markdown
        assert res.markdown.startswith("## First Section")

    @pytest.mark.asyncio
    async def test_appends_candidate_version_row_with_outline_index(self) -> None:
        reply = AIMessage(content="Tight prose.", usage_metadata={"input_tokens": 90, "output_tokens": 30, "total_tokens": 120})
        h = _Harness(reply=reply)
        svc = await h.service()
        res = await svc.regenerate(_cmd(h, 1, instruction="tighter", created_by="user-1"))
        assert len(h.versions.rows) == 1
        row = h.versions.rows[0].kwargs
        assert row["source"] == "regenerate"
        assert row["instruction"] == "tighter"
        assert row["section_id"] == res.section_id == f"{h.article.id}:1"
        assert row["section_index"] == 1
        assert row["markdown"] == res.markdown
        assert row["model"] == "claude-test"
        assert (row["tokens_input"], row["tokens_output"]) == (90, 30)
        assert (res.tokens_input, res.tokens_output) == (90, 30)
        assert row["created_by"] == "user-1"
        assert row["usd"] is None
        assert res.version_id == h.versions.rows[0].id

    @pytest.mark.asyncio
    async def test_context_uses_prior_live_sections_and_session_params(self) -> None:
        h = _Harness()
        svc = await h.service()
        await svc.regenerate(_cmd(h, 1, instruction="add a stat"))
        system, human = h.llm.ainvoke.await_args.args[0]
        assert "Write for this audience: CTOs." in str(system.content)  # only reachable via draft.session_id
        assert "Tone: direct." in str(system.content)
        assert "Editor instruction for this section: add a stat" in str(system.content)
        assert "- First Section: First section body." in str(human.content)

    @pytest.mark.asyncio
    async def test_llm_call_is_tracked_under_section_regenerate_step(self) -> None:
        calls = InMemoryLlmCallRepository()
        h = _Harness()
        h.llm = TrackedChatModel(inner=FakeListChatModel(responses=["Tracked prose."]), repo=calls)
        svc = await h.service()
        res = await svc.regenerate(_cmd(h, 1))
        rows = await calls.list_by_session(h.session_id)
        assert len(rows) == 1
        assert rows[0].call_name == "section_regenerate"
        assert "Tracked prose." in res.markdown
        # contextvars are reset after the call
        assert current_session_id.get() is None
        assert current_step_name.get() == "unknown"

    @pytest.mark.asyncio
    async def test_context_is_resolved_by_article_id_not_provenance(self) -> None:
        calls = InMemoryLlmCallRepository()
        h = _Harness()
        assert h.article.provenance.research_session_id == h.topic_id != h.session_id  # production shape
        h.llm = TrackedChatModel(inner=FakeListChatModel(responses=["Prose."]), repo=calls)
        svc = await h.service()
        await svc.regenerate(_cmd(h, 1))
        rows = await calls.list_by_session(h.session_id)
        assert len(rows) == 1 and rows[0].session_id == h.session_id  # draft.session_id, FK-valid
        assert await calls.list_by_session(h.topic_id) == []  # nothing keyed on provenance

    @pytest.mark.asyncio
    async def test_missing_article_raises(self) -> None:
        h = _Harness()
        svc = await h.service()
        with pytest.raises(ArticleNotFoundError):
            await svc.regenerate(RegenerateCommand(article_id=uuid4(), section_index=0))

    @pytest.mark.asyncio
    async def test_references_and_out_of_range_raise_section_not_found(self) -> None:
        h = _Harness()
        svc = await h.service()
        with pytest.raises(SectionNotFoundError):
            await svc.regenerate(_cmd(h, 2))  # "## References"
        with pytest.raises(SectionNotFoundError):
            await svc.regenerate(_cmd(h, 9))

    @pytest.mark.asyncio
    async def test_missing_draft_outline_raises(self) -> None:
        h = _Harness(with_draft=False)
        svc = await h.service()
        with pytest.raises(DraftContextMissingError):
            await svc.regenerate(_cmd(h, 0))

    @pytest.mark.asyncio
    async def test_draft_without_article_id_is_missing_context(self) -> None:
        # An outline-only draft (never finalised) is not stamped with article_id → 409, not a wrong outline.
        h = _Harness(with_draft=False)
        await h.drafts.create(ArticleDraft(session_id=h.session_id, topic_id=h.topic_id, outline=_outline(), created_at=datetime.now(UTC)))
        svc = await h.service()
        with pytest.raises(DraftContextMissingError):
            await svc.regenerate(_cmd(h, 0))

    @pytest.mark.asyncio
    async def test_heading_anchor_violation_raises_and_records_nothing(self) -> None:
        # A before_heading spec bound to a heading the article no longer has cannot be satisfied.
        h = _Harness(specs=[_spec("spec-h", "Renamed Heading", 1)])
        svc = await h.service()
        with pytest.raises(AnchorViolationError) as exc:
            await svc.regenerate(_cmd(h, 1))
        assert exc.value.violations[0].kind == "heading_text"
        assert h.versions.rows == []

    @pytest.mark.asyncio
    async def test_spec_on_neighbouring_section_is_not_checked(self) -> None:
        # Spec bound to outline section 0 must not block regenerating section 1 (outline index, not md index).
        h = _Harness(specs=[_spec("spec-n", "Gone Heading", 0)])
        svc = await h.service()
        res = await svc.regenerate(_cmd(h, 1))
        assert res.section_index == 1
```

- [ ] **Step 2: Run — expect failure**

`COGNIFY_ANTHROPIC_API_KEY= uv run pytest tests/unit/services/test_content_repositories_find_by_article_id.py tests/unit/services/content/test_section_regenerate.py -q -p no:cacheprovider` → `AttributeError: 'InMemoryArticleDraftRepository' object has no attribute 'find_by_article_id'` and `ModuleNotFoundError: src.services.content.section_regenerate_models`.

- [ ] **Step 3: Implement**

`src/services/content_repositories.py`:
1. In `ArticleDraftRepository` (Protocol), after `find_latest_by_session`:
```python
    async def find_by_article_id(self, article_id: UUID) -> ArticleDraft | None: ...
```
2. In `InMemoryArticleDraftRepository`, after `find_latest_by_session`:
```python
    async def find_by_article_id(self, article_id: UUID) -> ArticleDraft | None:
        """Newest draft stamped with `article_id` (set by store_article at finalisation)."""
        candidates = [d for d in self._store.values() if d.article_id == article_id]
        if not candidates:
            return None
        return max(candidates, key=lambda d: d.created_at)
```

`src/db/repositories.py` — in `PgArticleDraftRepository`, directly after `find_latest_by_session` (same shape; `ArticleDraftRow.article_id` is the nullable FK to `canonical_articles.id`):
```python
    async def find_by_article_id(self, article_id: UUID) -> ArticleDraft | None:
        async with self._sf() as db:
            stmt = (
                select(ArticleDraftRow)
                .where(ArticleDraftRow.article_id == article_id)
                .order_by(ArticleDraftRow.created_at.desc())
                .limit(1)
            )
            row = (await db.execute(stmt)).scalar_one_or_none()
            return None if row is None else self._to_model(row)
```
(`src/db/repositories.py` is pre-existing over the cap — 904 → 918; no other change.)

Create `src/services/content/section_regenerate_models.py` (91 lines after `ruff format`):
```python
"""Value objects for per-section regenerate (AUTHOR-004).

Kept apart from the service so `section_regenerate.py` and
`section_regenerate_text.py` both stay under the 200-line cap. Every
`section_index` here is the OUTLINE index (0-based over H2 sections, L-013).
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from langchain_core.language_models import BaseChatModel

from src.models.content import CanonicalArticle
from src.models.content_pipeline import ArticleDraft, OutlineSection
from src.models.research_db import ResearchSession
from src.services.content.section_history import SectionHistoryService
from src.services.content.section_history_contracts import VersionRepoProtocol
from src.services.content.section_markdown import MarkdownSection
from src.services.content.word_diff import WordDiffOp
from src.services.content_repositories import (
    ArticleDraftRepository,
    ResearchSessionReader,
)
from src.services.milvus_retriever import MilvusRetriever

STEP_NAME = "section_regenerate"


class DraftContextMissingError(Exception):
    """The article has no ArticleDraft/outline to regenerate from."""


@dataclass(frozen=True)
class RegenerateCommand:
    article_id: UUID
    section_index: int  # outline space: 0-based over H2 sections
    instruction: str | None = None
    created_by: str | None = None


@dataclass(frozen=True)
class RegenerateDeps:
    history: SectionHistoryService
    versions: VersionRepoProtocol
    drafts: ArticleDraftRepository
    research: ResearchSessionReader
    llm: BaseChatModel
    retriever: MilvusRetriever | None = None


@dataclass(frozen=True)
class RegenerateInputs:
    """Everything loaded before the single LLM call.

    `draft.session_id` is the REAL research-session id (the FK `llm_calls`
    and `research_sessions` use); `article.provenance.research_session_id`
    holds the graph's `state["session_id"]`, which is the topic id — never
    key on it (see module docstring of `section_regenerate`).
    """

    cmd: RegenerateCommand
    article: CanonicalArticle
    old: MarkdownSection
    draft: ArticleDraft
    outline_section: OutlineSection
    session: ResearchSession | None


@dataclass(frozen=True)
class RegenerateResult:
    section_id: str  # `{article_id}:{outline_index}` — pass to section-update as-is
    section_index: int
    markdown: str
    diff: list[WordDiffOp]
    version_id: UUID
    model: str
    word_count: int
    tokens_input: int | None
    tokens_output: int | None


__all__ = [
    "STEP_NAME",
    "DraftContextMissingError",
    "RegenerateCommand",
    "RegenerateDeps",
    "RegenerateInputs",
    "RegenerateResult",
]
```

Create `src/services/content/section_regenerate_text.py` (161 lines after `ruff format`):
```python
"""Helpers for per-section regeneration (AUTHOR-004) — no repository I/O.

`carry_anchor_blocks` is block-aware (via `src/utils/markdown_structure`,
the same parser the humanizer uses) so figure anchors land back where
they were relative to the surrounding prose instead of being appended.
"""

from __future__ import annotations

from uuid import UUID

from src.agents.content.article_assembler import strip_leading_heading
from src.agents.content.citation_manager import strip_citation_markers
from src.agents.content.section_drafter import DraftingContext
from src.models.content_pipeline import OutlineSection, SectionDraft, SectionQueries
from src.services.content.section_anchors import find_spec_ids
from src.services.content.section_history_contracts import (
    SectionNotFoundError,
    md_index_for,
    outline_index_for,
)
from src.services.content.section_markdown import MarkdownSection, split_sections
from src.services.content.section_regenerate_models import (
    RegenerateDeps,
    RegenerateInputs,
)
from src.services.content.section_rewriter import strip_fences
from src.utils.markdown_structure import (
    MarkdownBlock,
    extract_humanizable_text,
    parse_markdown_blocks,
    reassemble,
)

_REFERENCES_HEADING = "references"


def build_drafting_context(
    prep: RegenerateInputs, deps: RegenerateDeps
) -> DraftingContext:
    """Live previous sections + session params + editor instruction."""
    session = prep.session
    return DraftingContext(
        retriever=deps.retriever,
        topic_id=str(prep.draft.topic_id),
        llm=deps.llm,
        prior_drafts=prior_drafts_from_body(
            prep.article.body_markdown, prep.cmd.section_index
        ),
        target_audience=session.target_audience if session else None,
        content_tone=session.content_tone if session else None,
        preferred_angle=session.preferred_angle if session else None,
        keywords=session.keywords if session else None,
        instruction=prep.cmd.instruction,
    )


def reject_non_prose(section: MarkdownSection, article_id: UUID) -> None:
    """The References tail (and anything heading-less) is not regenerable."""
    heading = (section.heading or "").lstrip("#").strip().lower()
    if section.heading is None or heading == _REFERENCES_HEADING:
        raise SectionNotFoundError(
            f"section {outline_index_for(section.index)} of article "
            f"{article_id} is not a prose section"
        )


def _anchor_lines(block: MarkdownBlock) -> str:
    return "\n".join(ln for ln in block.lines if find_spec_ids(ln))


def _slot(pos: int, old_total: int, new_total: int) -> int:
    """First stays first, last stays last, otherwise proportional."""
    if pos == 0:
        return 0
    if pos >= old_total - 1:
        return new_total
    return round(pos / (old_total - 1) * new_total)


def _carried_anchor_lines(old_body: str, new_body: str) -> list[tuple[int, str]]:
    """(old block position, data-spec-id lines) for anchors missing from new_body."""
    present = set(find_spec_ids(new_body))
    carried: list[tuple[int, str]] = []
    for pos, block in enumerate(parse_markdown_blocks(old_body)):
        lines = _anchor_lines(block)
        if lines and any(sid not in present for sid in find_spec_ids(lines)):
            carried.append((pos, lines))
    return carried


def carry_anchor_blocks(old_body: str, new_body: str) -> str:
    """Re-insert every data-spec-id line of `old_body` by relative block position."""
    carried = _carried_anchor_lines(old_body, new_body)
    if not carried:
        return new_body
    old_total = len(parse_markdown_blocks(old_body))
    new_blocks = parse_markdown_blocks(new_body)
    base = len(new_blocks)
    for offset, (pos, lines) in enumerate(carried):
        block = MarkdownBlock(kind="content", raw=lines, lines=lines.split("\n"))
        new_blocks.insert(_slot(pos, old_total, base) + offset, block)
    return reassemble(new_blocks)


def assemble_section(old: MarkdownSection, raw_llm_text: str) -> str:
    """Raw LLM prose → full section: original H2 + clean body + carried anchors."""
    body = strip_citation_markers(
        strip_leading_heading(strip_fences(raw_llm_text))
    ).strip()
    body = carry_anchor_blocks(old.body, body)
    return f"{old.heading or ''}\n\n{body}".strip("\n") + "\n"


def _is_markup(block: MarkdownBlock) -> bool:
    return block.raw.lstrip().startswith("<") or bool(find_spec_ids(block.raw))


def _prose_only(body: str) -> str:
    blocks = [
        b
        for b in parse_markdown_blocks(body)
        if extract_humanizable_text(b) is not None and not _is_markup(b)
    ]
    return reassemble(blocks)


def prior_drafts_from_body(
    body_markdown: str, section_index: int
) -> list[SectionDraft]:
    """Live H2 sections BEFORE outline `section_index`, prose blocks only."""
    drafts: list[SectionDraft] = []
    for section in split_sections(body_markdown)[1 : md_index_for(section_index)]:
        prose = _prose_only(section.body)
        drafts.append(
            SectionDraft(
                section_index=outline_index_for(section.index),
                title=(section.heading or "").lstrip("#").strip(),
                body_markdown=prose,
                word_count=len(prose.split()),
                citations_used=[],
            )
        )
    return drafts


def queries_for(section: OutlineSection) -> SectionQueries:
    """Cheap retrieval queries — no LLM call (L-007 stays at one call)."""
    return SectionQueries(
        section_index=section.index, queries=[section.title, *section.key_points]
    )


__all__ = [
    "assemble_section",
    "build_drafting_context",
    "carry_anchor_blocks",
    "prior_drafts_from_body",
    "queries_for",
    "reject_non_prose",
]
```

Create `src/services/content/section_regenerate.py` (177 lines after `ruff format`):
```python
"""Per-section regenerate-with-feedback (AUTHOR-004, program plan §5.5).

Service-layer entry point for `POST /content/section-regenerate`:

1. Load the article + the H2 section at OUTLINE index `cmd.section_index`
   (`SectionHistoryService` owns the split_sections conversion, L-013).
2. Resolve the outline section via `drafts.find_by_article_id(article.id)`
   — NOT via `article.provenance.research_session_id`: the graph stamps
   `state["session_id"] = topic.id`, so provenance carries the TOPIC id
   and `find_latest_by_session(provenance)` returns None for every real
   article. `draft.session_id` is the real research-session id.
3. Draft ONE section with `draft_one_section` (graph-free, one LLM call)
   under `current_session_id = draft.session_id` /
   `current_step_name = "section_regenerate"` so `TrackedChatModel`
   records it in `llm_calls` (FK → research_sessions.id).
4. Re-prefix the original heading, carry `data-spec-id` blocks by position,
   then run `validate_anchors` (outline index) against the OLD section text.
5. Append a candidate `section_versions` row (`source="regenerate"`). The
   article body is NOT modified — accept goes through `/content/section-update`.
"""

from __future__ import annotations

from uuid import UUID

import structlog

from src.agents.content.section_drafter import OneSectionDraft, draft_one_section
from src.models.content import CanonicalArticle
from src.models.content_pipeline import ArticleDraft, OutlineSection
from src.services.content.section_anchors import validate_anchors
from src.services.content.section_history import (
    AnchorViolationError,
    SectionNotFoundError,
)
from src.services.content.section_history_contracts import (
    VersionRow,
    append_version_row,
    make_section_id,
)
from src.services.content.section_regenerate_models import (
    STEP_NAME,
    DraftContextMissingError,
    RegenerateCommand,
    RegenerateDeps,
    RegenerateInputs,
    RegenerateResult,
)
from src.services.content.section_regenerate_text import (
    assemble_section,
    build_drafting_context,
    queries_for,
    reject_non_prose,
)
from src.services.content.section_rewriter import model_label
from src.services.content.word_diff import diff_words
from src.utils.tracked_llm import current_session_id, current_step_name

logger = structlog.get_logger()


class SectionRegenerateService:
    def __init__(self, deps: RegenerateDeps) -> None:
        self._deps = deps

    async def regenerate(self, cmd: RegenerateCommand) -> RegenerateResult:
        prep = await self._prepare(cmd)
        drafted = await self._draft(prep)
        new_md = assemble_section(prep.old, drafted.body_markdown)
        self._validate(prep, new_md)
        version_id = await self._record(prep, drafted, new_md)
        return RegenerateResult(
            section_id=make_section_id(cmd.article_id, cmd.section_index),
            section_index=cmd.section_index,
            markdown=new_md,
            diff=diff_words(prep.old.text, new_md),
            version_id=version_id,
            model=model_label(self._deps.llm),
            word_count=drafted.word_count,
            tokens_input=drafted.tokens_input,
            tokens_output=drafted.tokens_output,
        )

    async def _prepare(self, cmd: RegenerateCommand) -> RegenerateInputs:
        article, old = await self._deps.history.get_section_markdown(
            cmd.article_id, cmd.section_index
        )
        reject_non_prose(old, cmd.article_id)
        draft, outline_section = await self._outline_section(article, cmd.section_index)
        session = await self._deps.research.get(draft.session_id)
        return RegenerateInputs(
            cmd=cmd,
            article=article,
            old=old,
            draft=draft,
            outline_section=outline_section,
            session=session,
        )

    async def _outline_section(
        self, article: CanonicalArticle, section_index: int
    ) -> tuple[ArticleDraft, OutlineSection]:
        draft = await self._deps.drafts.find_by_article_id(article.id)
        if draft is None or draft.outline is None:
            raise DraftContextMissingError(f"no outline for article {article.id}")
        section = next(
            (s for s in draft.outline.sections if s.index == section_index), None
        )
        if section is None:
            raise SectionNotFoundError(
                f"outline has no section {section_index} for article {article.id}"
            )
        return draft, section

    async def _draft(self, prep: RegenerateInputs) -> OneSectionDraft:
        """ONE tracked LLM call — bound to the draft's research session."""
        logger.info(
            "section_regenerate_started",
            article_id=str(prep.article.id),
            section_index=prep.cmd.section_index,
            session_id=str(prep.draft.session_id),
        )
        ctx = build_drafting_context(prep, self._deps)
        session_token = current_session_id.set(prep.draft.session_id)
        step_token = current_step_name.set(STEP_NAME)
        try:
            return await draft_one_section(
                prep.outline_section, queries_for(prep.outline_section), ctx
            )
        finally:
            current_step_name.reset(step_token)
            current_session_id.reset(session_token)

    def _validate(self, prep: RegenerateInputs, new_md: str) -> None:
        violations = validate_anchors(
            original_markdown=prep.old.text,
            new_markdown=new_md,
            image_specs=list(prep.article.image_specs),
            section_index=prep.cmd.section_index,
        )
        if violations:
            logger.warning(
                "section_regenerate_anchor_violation",
                article_id=str(prep.article.id),
                count=len(violations),
            )
            raise AnchorViolationError(violations)

    async def _record(
        self, prep: RegenerateInputs, drafted: OneSectionDraft, new_md: str
    ) -> UUID:
        row = VersionRow(
            article_id=prep.cmd.article_id,
            section_index=prep.cmd.section_index,
            markdown=new_md,
            source="regenerate",
            instruction=prep.cmd.instruction,
            model=model_label(self._deps.llm),
            tokens_input=drafted.tokens_input,
            tokens_output=drafted.tokens_output,
            created_by=prep.cmd.created_by,
        )
        version_id = await append_version_row(self._deps.versions, row)
        _log_recorded(row, version_id)
        return version_id


def _log_recorded(row: VersionRow, version_id: UUID) -> None:
    logger.info(
        "section_regenerated",
        article_id=str(row.article_id),
        section_index=row.section_index,
        version_id=str(version_id),
    )


__all__ = ["SectionRegenerateService"]
```
Notes: `_validate` passes the **outline** index (`ImagePlacement.section_index` space) — the same call the accept path (`SectionHistoryService._ensure_anchors`) makes, so both calls agree (`test_spec_on_neighbouring_section_is_not_checked`). `_record` builds a `VersionRow` and goes through the shared `append_version_row` (Task 1) — the 11-kwarg repo call exists exactly once in the codebase. `section_word_count_outside_range` is emitted by `_log_word_count` inside `section_drafter._draft`; `RegenerateResult.word_count` is the raw draft's word count. `current_session_id` is set to `prep.draft.session_id` (FK-valid for `llm_calls`), never to provenance.

- [ ] **Step 4: Run — expect pass**

`COGNIFY_ANTHROPIC_API_KEY= uv run pytest tests/unit/services/test_content_repositories_find_by_article_id.py tests/unit/services/content/test_section_regenerate.py -q -p no:cacheprovider` → `24 passed` (2 repo + 6 carry + 4 helpers + 12 service). `uv run ruff format src/services/content/section_regenerate.py src/services/content/section_regenerate_models.py src/services/content/section_regenerate_text.py && wc -l src/services/content/section_regenerate.py src/services/content/section_regenerate_models.py src/services/content/section_regenerate_text.py` → **177 / 91 / 161** (these blocks are already `ruff format` output with the repo's 88-column config — the numbers are measured, not estimated; if your count differs by more than ±3 you changed the code). Function lengths (AST, `def` through end): `regenerate` 17, `_prepare` 15, `_outline_section` 14, `_draft` 18, `_validate` 14, `_record` 17, `_log_recorded` 7; text module max is `build_drafting_context` 18 / `prior_drafts_from_body` 17 — `uv run python -c "import ast,sys;[print(f.name,f.end_lineno-f.lineno+1) for p in sys.argv[1:] for f in ast.walk(ast.parse(open(p).read())) if isinstance(f,(ast.FunctionDef,ast.AsyncFunctionDef)) and f.end_lineno-f.lineno+1>=20]" src/services/content/section_regenerate.py src/services/content/section_regenerate_text.py src/services/content/section_regenerate_models.py` → prints nothing. Integration (only if the DB stack is up; clean after, L-005): `uv run pytest tests/integration/db/test_pg_repositories.py -k find_by_article_id -q -p no:cacheprovider` → `1 passed`.

- [ ] **Step 5: Lint + commit**

`uv run ruff check --fix src/ tests/ && uv run ruff format src/ tests/ && uv run mypy src/ --ignore-missing-imports`
`git add src/services/content_repositories.py src/db/repositories.py src/services/content/section_regenerate.py src/services/content/section_regenerate_models.py src/services/content/section_regenerate_text.py tests/unit/services/test_content_repositories_find_by_article_id.py tests/unit/services/content/test_section_regenerate.py tests/integration/db/test_pg_repositories.py && git commit -m "feat(content): SectionRegenerateService — context by article_id, one tracked LLM call, positional anchor carry, candidate version row (AUTHOR-004)"`

---

### Task 5: `POST /content/section-regenerate` (new router module)

**Files:**
- Create: `src/api/routers/content_regenerate.py`
- Modify: `src/api/main.py` (import + `include_router`, next to the `content_router` block)
- Test: `tests/unit/api/test_content_regenerate_endpoint.py` (new); append one class to `tests/unit/api/test_content_endpoints.py`

**Interfaces:**
```python
content_regenerate_router = APIRouter(prefix="/content")

class SectionRegenerateRequest(BaseModel):
    article_id: UUID
    section_index: int = Field(ge=0, le=500)        # outline space (0-based H2)
    instruction: str | None = Field(default=None, max_length=2000)

class SectionRegenerateResponse(BaseModel):       # == RegenerateResult fields + instruction
    section_id: str                                # `{article_id}:{section_index}` — use for /content/section-update
    section_index: int
    markdown: str
    diff: list[WordDiffEntry]
    version_id: str
    model: str
    word_count: int
    tokens_input: int | None
    tokens_output: int | None
    instruction: str | None

# status mapping (one place: _map_regenerate_error): 401/403 auth; 404 ArticleNotFoundError / SectionNotFoundError;
# 409 DraftContextMissingError; 422 AnchorViolationError → anchor_violation_http (byte-identical to section-update);
# 503 (_resolve_regenerate_state) when app.state lacks content_service(.deps.llm) / content_repos / section_version_repo; 429 at 11th call/minute.
# Fixtures mirror production: the ArticleDraft is stamped with article_id and its session_id is deliberately != provenance.research_session_id.
```

- [ ] **Step 1: Write the failing tests**

`tests/unit/api/test_content_regenerate_endpoint.py` (builds on the `content_app` pattern from `test_content_endpoints.py`: same RSA keys, CognifyError handler, plus the `RateLimitExceeded` handler exactly as `main.py` registers it):
```python
"""Contract tests for POST /api/v1/content/section-regenerate (AUTHOR-004)."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from slowapi.errors import RateLimitExceeded

from src.api.errors import CognifyError, build_error_response
from src.api.rate_limiter import limiter
from src.api.routers.content import content_router
from src.api.routers.content_regenerate import content_regenerate_router
from src.config.settings import Settings
from src.models.content import CanonicalArticle
from src.models.content_pipeline import ArticleDraft, ArticleOutline, OutlineSection
from src.models.content_pipeline import ContentType as OutlineContentType
from src.models.research_db import ResearchSession
from src.models.visual import ImagePlacement, ImageSpec
from src.services.content import ContentDeps, ContentRepositories, ContentService
from src.services.content.section_history import SectionHistoryService
from src.services.content_repositories import (
    InMemoryArticleDraftRepository,
    InMemoryArticleRepository,
)
from tests.unit.api.conftest import make_auth_header
from tests.unit.api.test_content_endpoints import (
    _PRIV,
    _PUB,
    _build_article,
    _FakeArticleRepo,
    _FakeVersionRepo,
)

URL = "/api/v1/content/section-regenerate"
UPDATE_URL = "/api/v1/content/section-update"
FIGURE = '<figure class="cog-figure" data-spec-id="spec-a"><img src="x.png" alt="a" /></figure>'
BODY = (
    "## First Section\n"
    "First section body.\n\n"
    f"{FIGURE}\n\n"
    "## Second Section\n"
    "Second section body.\n\n"
    "## References\n"
    "1. Source\n"
)


def _spec(spec_id: str, heading: str, section_index: int) -> ImageSpec:
    return ImageSpec(
        id=spec_id,
        role_style="concept",
        prompt="p",
        placement=ImagePlacement(anchor="before_heading", heading_text=heading, section_index=section_index),
    )


class _FakeResearch:
    def __init__(self, session: ResearchSession) -> None:
        self._session = session

    async def get(self, session_id: UUID) -> ResearchSession | None:
        return self._session if self._session.id == session_id else None


@pytest.fixture
def settings() -> Settings:
    return Settings(
        jwt_private_key=_PRIV,
        jwt_public_key=_PUB,
        jwt_access_token_expire_minutes=15,
        jwt_refresh_token_expire_days=7,
        anthropic_api_key="test-anthropic",
    )


@pytest.fixture
def article() -> CanonicalArticle:
    # Specs on BOTH outline sections k=0 and k+1=1 (L-013 round-trip requirement).
    base = _build_article(
        uuid4(),
        image_specs=[_spec("spec-a", "First Section", 0), _spec("spec-b", "Second Section", 1)],
    )
    return base.model_copy(update={"body_markdown": BODY})


@pytest.fixture
def version_repo() -> _FakeVersionRepo:
    return _FakeVersionRepo()


@pytest.fixture
def session_id() -> UUID:
    """The REAL research-session id — never equal to provenance (which holds the topic id)."""
    return uuid4()


async def _drafts_for(article: CanonicalArticle, session_id: UUID) -> InMemoryArticleDraftRepository:
    assert session_id != article.provenance.research_session_id
    drafts = InMemoryArticleDraftRepository()
    await drafts.create(
        ArticleDraft(
            session_id=session_id,
            topic_id=article.provenance.research_session_id,
            article_id=article.id,  # what store_article stamps at finalisation
            created_at=datetime.now(UTC),
            outline=ArticleOutline(
                title="T",
                content_type=OutlineContentType.ARTICLE,
                total_target_words=500,
                reasoning="r",
                sections=[
                    OutlineSection(index=0, title="First Section", description="d", key_points=["k"], target_word_count=250, relevant_facets=[0]),
                    OutlineSection(index=1, title="Second Section", description="d", key_points=["k"], target_word_count=250, relevant_facets=[0]),
                ],
            ),
        )
    )
    return drafts


def _install_handlers(app: FastAPI) -> None:
    @app.exception_handler(CognifyError)
    async def _err_handler(_: Any, exc: CognifyError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=build_error_response(code=exc.code, message=exc.message),
        )

    @app.exception_handler(RateLimitExceeded)
    async def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
        return JSONResponse(
            status_code=429,
            content=build_error_response(code="rate_limited", message="Rate limit exceeded"),
        )


@pytest.fixture
async def app(settings: Settings, article: CanonicalArticle, version_repo: _FakeVersionRepo, session_id: UUID) -> FastAPI:
    article_repo = _FakeArticleRepo(article)
    session = ResearchSession(
        id=session_id, topic_id=article.provenance.research_session_id, target_audience="CTOs", started_at=datetime.now(UTC)
    )
    repos = ContentRepositories(drafts=await _drafts_for(article, session_id), research=_FakeResearch(session), articles=InMemoryArticleRepository())
    app = FastAPI()
    app.state.settings = settings
    app.state.limiter = limiter
    app.state.article_repo = article_repo
    app.state.section_version_repo = version_repo
    app.state.section_history_service = SectionHistoryService(article_repo, version_repo)
    app.state.content_repos = repos
    app.state.content_service = ContentService(
        repos, ContentDeps(llm=FakeListChatModel(responses=["Regenerated prose [1]."] * 12), settings=settings)
    )
    _install_handlers(app)
    app.include_router(content_router, prefix=settings.api_v1_prefix)
    app.include_router(content_regenerate_router, prefix=settings.api_v1_prefix)
    return app


@pytest.fixture
async def client(app: FastAPI) -> AsyncGenerator[httpx.AsyncClient, None]:
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.fixture(autouse=True)
def _reset_limiter() -> None:
    limiter.reset()


def _body(article: CanonicalArticle, **extra: Any) -> dict[str, Any]:
    return {"article_id": str(article.id), "section_index": 0, **extra}


class TestAuth:
    async def test_requires_auth(self, client: httpx.AsyncClient, article: CanonicalArticle) -> None:
        res = await client.post(URL, json=_body(article))
        assert res.status_code in {401, 403}  # HTTPBearer returns 403 without a header on some FastAPI versions

    async def test_viewer_forbidden(self, client: httpx.AsyncClient, article: CanonicalArticle, settings: Settings) -> None:
        res = await client.post(URL, json=_body(article), headers=make_auth_header("viewer", settings))
        assert res.status_code == 403


class TestRegenerate:
    async def test_returns_diff_word_count_and_preserves_anchor(
        self, client: httpx.AsyncClient, article: CanonicalArticle, settings: Settings, version_repo: _FakeVersionRepo
    ) -> None:
        res = await client.post(URL, json=_body(article, instruction="tighter"), headers=make_auth_header("editor", settings))
        assert res.status_code == 200, res.text
        payload = res.json()
        assert payload["section_id"] == f"{article.id}:0"  # outline space, no arithmetic
        assert payload["section_index"] == 0
        assert payload["markdown"].startswith("## First Section")
        assert 'data-spec-id="spec-a"' in payload["markdown"]
        assert "[1]" not in payload["markdown"]
        assert any(op["kind"] != "equal" for op in payload["diff"])
        assert payload["instruction"] == "tighter"
        assert payload["word_count"] == 3  # "Regenerated prose [1]."
        assert payload["tokens_input"] is None and payload["tokens_output"] is None  # FakeListChatModel has no usage
        rows = list(version_repo._stored.values())
        assert len(rows) == 1 and rows[0].source == "regenerate" and rows[0].created_by == "user-1"
        assert rows[0].section_index == 0
        assert payload["version_id"] == str(rows[0].id)

    async def test_round_trip_regenerate_then_accept_with_specs_on_k_and_k_plus_1(
        self, client: httpx.AsyncClient, article: CanonicalArticle, settings: Settings, version_repo: _FakeVersionRepo, app: FastAPI
    ) -> None:
        headers = make_auth_header("editor", settings)
        first = await client.post(URL, json=_body(article), headers=headers)
        assert first.status_code == 200, first.text
        cand = first.json()
        accept = await client.post(
            UPDATE_URL,
            json={"section_id": cand["section_id"], "markdown": cand["markdown"], "source": "regenerate", "instruction": None},
            headers=headers,
        )
        assert accept.status_code == 200, accept.text
        body = app.state.article_repo.persisted_body
        assert "Regenerated prose" in body and "## Second Section\nSecond section body." in body
        sources = [v.source for v in version_repo._stored.values()]
        assert sources == ["regenerate", "regenerate"]  # candidate row + applied row
        # Both rows address the same outline-space section; nothing was keyed on provenance
        # (the draft's session_id != provenance in this fixture — a provenance lookup would 409).
        assert {v.section_index for v in version_repo._stored.values()} == {0}

    async def test_dropping_section_k_heading_is_422_on_both_calls(
        self, app: FastAPI, client: httpx.AsyncClient, article: CanonicalArticle, settings: Settings
    ) -> None:
        # Spec k now points at a heading the article no longer has → regenerate can't satisfy it,
        # and a manual accept that renames the heading can't either. Same payload from both routes.
        broken = article.model_copy(update={"image_specs": [_spec("spec-h", "Gone Heading", 0), _spec("spec-b", "Second Section", 1)]})
        app.state.article_repo.article = broken
        headers = make_auth_header("editor", settings)
        regen = await client.post(URL, json=_body(article), headers=headers)
        update = await client.post(
            UPDATE_URL,
            json={"section_id": f"{article.id}:0", "markdown": f"## Renamed Heading\nReplacement.\n\n{FIGURE}", "source": "manual"},
            headers=headers,
        )
        assert regen.status_code == 422, regen.text
        assert update.status_code == 422, update.text
        assert regen.json()["detail"] == update.json()["detail"]  # byte-identical shape
        detail = regen.json()["detail"]
        assert detail["error"] == "anchor_violation"
        assert [v["kind"] for v in detail["violations"]] == ["heading_text"]
        assert detail["violations"][0]["spec_id"] == "spec-h"

    async def test_unknown_article_404(self, client: httpx.AsyncClient, settings: Settings) -> None:
        res = await client.post(URL, json={"article_id": str(uuid4()), "section_index": 0}, headers=make_auth_header("editor", settings))
        assert res.status_code == 404

    async def test_references_and_out_of_range_section_404(self, client: httpx.AsyncClient, article: CanonicalArticle, settings: Settings) -> None:
        headers = make_auth_header("editor", settings)
        assert (await client.post(URL, json=_body(article, section_index=2), headers=headers)).status_code == 404
        assert (await client.post(URL, json=_body(article, section_index=9), headers=headers)).status_code == 404

    async def test_missing_outline_409(self, app: FastAPI, client: httpx.AsyncClient, article: CanonicalArticle, settings: Settings) -> None:
        app.state.content_repos = ContentRepositories(
            drafts=InMemoryArticleDraftRepository(), research=app.state.content_repos.research, articles=InMemoryArticleRepository()
        )
        res = await client.post(URL, json=_body(article), headers=make_auth_header("editor", settings))
        assert res.status_code == 409

    async def test_draft_keyed_only_by_provenance_is_409(
        self, app: FastAPI, client: httpx.AsyncClient, article: CanonicalArticle, settings: Settings
    ) -> None:
        # A draft whose session_id == provenance but with no article_id stamp is NOT usable context —
        # guards against anyone reverting to find_latest_by_session(provenance).
        drafts = InMemoryArticleDraftRepository()
        await drafts.create(
            ArticleDraft(session_id=article.provenance.research_session_id, topic_id=uuid4(), created_at=datetime.now(UTC))
        )
        app.state.content_repos = ContentRepositories(
            drafts=drafts, research=app.state.content_repos.research, articles=InMemoryArticleRepository()
        )
        res = await client.post(URL, json=_body(article), headers=make_auth_header("editor", settings))
        assert res.status_code == 409

    async def test_missing_llm_503(self, app: FastAPI, client: httpx.AsyncClient, article: CanonicalArticle, settings: Settings) -> None:
        app.state.content_service = ContentService(app.state.content_repos, ContentDeps(settings=settings))
        res = await client.post(URL, json=_body(article), headers=make_auth_header("editor", settings))
        assert res.status_code == 503

    async def test_missing_content_service_503(self, app: FastAPI, client: httpx.AsyncClient, article: CanonicalArticle, settings: Settings) -> None:
        del app.state.content_service
        res = await client.post(URL, json=_body(article), headers=make_auth_header("editor", settings))
        assert res.status_code == 503

    async def test_rate_limited_after_ten(self, client: httpx.AsyncClient, article: CanonicalArticle, settings: Settings) -> None:
        headers = make_auth_header("editor", settings)
        codes = [(await client.post(URL, json=_body(article), headers=headers)).status_code for _ in range(11)]
        assert codes[:10] == [200] * 10
        assert codes[10] == 429
```

Append to `tests/unit/api/test_content_endpoints.py`:
```python
class TestSectionUpdateSourceLiteral:
    def test_regenerate_is_an_accepted_source(self) -> None:
        from src.api.routers.content import SectionUpdateRequest

        req = SectionUpdateRequest(section_id="a:0", markdown="x", source="regenerate")
        assert req.source == "regenerate"
```

- [ ] **Step 2: Run — expect failure**

`COGNIFY_ANTHROPIC_API_KEY= uv run pytest tests/unit/api/test_content_regenerate_endpoint.py tests/unit/api/test_content_endpoints.py -q -p no:cacheprovider` → `ImportError: content_regenerate_router`. (The Literal already accepts `"regenerate"` since Task 3 — that test passes immediately; it guards the contract.)

- [ ] **Step 3: Implement**

Create `src/api/routers/content_regenerate.py` (171 lines after `ruff format`; `section_regenerate` is 12 lines — the four error arms collapse into `_map_regenerate_error`; `_resolve_regenerate_state` + `_get_regenerate_service` split the app.state lookup from construction):
```python
"""POST /content/section-regenerate (AUTHOR-004, program plan §5.5).

Lives in its own module because `content.py` is already over the
200-line cap; mounted on the same `/content` prefix. Uses the shared
helpers in `content_shared.py` so the 422 anchor-violation payload is
byte-identical to `/content/section-update`. The LLM comes from
`app.state.content_service.deps` (TrackedChatModel → Pipeline Debug).
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi import status as http_status
from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel, Field

from src.api.auth.schemas import TokenPayload
from src.api.dependencies import require_editor_or_above
from src.api.rate_limiter import limiter
from src.api.routers.content_shared import (
    WordDiffEntry,
    anchor_violation_http,
    get_history_service,
)
from src.services.content.section_history import (
    AnchorViolationError,
    ArticleNotFoundError,
    SectionNotFoundError,
)
from src.services.content.section_history_contracts import VersionRepoProtocol
from src.services.content.section_regenerate import SectionRegenerateService
from src.services.content.section_regenerate_models import (
    DraftContextMissingError,
    RegenerateCommand,
    RegenerateDeps,
    RegenerateResult,
)
from src.services.content_repositories import ContentRepositories
from src.services.milvus_retriever import MilvusRetriever

logger = structlog.get_logger()

content_regenerate_router = APIRouter(prefix="/content")

_REGENERATE_ERRORS = (
    ArticleNotFoundError,
    SectionNotFoundError,
    DraftContextMissingError,
    AnchorViolationError,
)


class SectionRegenerateRequest(BaseModel):
    article_id: UUID
    section_index: int = Field(ge=0, le=500, description="0-based H2 (outline) index")
    instruction: str | None = Field(default=None, max_length=2000)


class SectionRegenerateResponse(BaseModel):
    section_id: str
    section_index: int
    markdown: str
    diff: list[WordDiffEntry]
    version_id: str
    model: str
    word_count: int
    tokens_input: int | None = None
    tokens_output: int | None = None
    instruction: str | None = None


@dataclass(frozen=True)
class _RegenerateState:
    llm: BaseChatModel
    repos: ContentRepositories
    versions: VersionRepoProtocol
    retriever: MilvusRetriever | None


@content_regenerate_router.post(
    "/section-regenerate", response_model=SectionRegenerateResponse
)
@limiter.limit("10/minute")
async def section_regenerate(
    request: Request,
    body: SectionRegenerateRequest,
    user: TokenPayload = Depends(require_editor_or_above),
) -> SectionRegenerateResponse:
    """Redraft one section; returns candidate markdown + diff (body untouched)."""
    service = _get_regenerate_service(request)
    try:
        result = await service.regenerate(_command(body, user))
    except _REGENERATE_ERRORS as exc:
        raise _map_regenerate_error(exc) from exc
    return _to_response(body, result)


def _command(body: SectionRegenerateRequest, user: TokenPayload) -> RegenerateCommand:
    return RegenerateCommand(
        article_id=body.article_id,
        section_index=body.section_index,
        instruction=body.instruction,
        created_by=user.sub,
    )


def _map_regenerate_error(exc: Exception) -> HTTPException:
    """404 not found / 409 no draft context / 422 anchor violation (shared shape)."""
    if isinstance(exc, AnchorViolationError):
        return anchor_violation_http(exc)
    if isinstance(exc, DraftContextMissingError):
        return HTTPException(http_status.HTTP_409_CONFLICT, str(exc))
    return HTTPException(http_status.HTTP_404_NOT_FOUND, str(exc))


def _to_response(
    body: SectionRegenerateRequest, result: RegenerateResult
) -> SectionRegenerateResponse:
    return SectionRegenerateResponse(
        section_id=result.section_id,
        section_index=result.section_index,
        markdown=result.markdown,
        diff=[WordDiffEntry.from_op(op) for op in result.diff],
        version_id=str(result.version_id),
        model=result.model,
        word_count=result.word_count,
        tokens_input=result.tokens_input,
        tokens_output=result.tokens_output,
        instruction=body.instruction,
    )


def _resolve_regenerate_state(request: Request) -> _RegenerateState:
    """Read app.state; 503 when the LLM, content repos or version repo are missing."""
    state = request.app.state
    deps = getattr(getattr(state, "content_service", None), "deps", None)
    llm = getattr(deps, "llm", None)
    repos = getattr(state, "content_repos", None)
    versions = getattr(state, "section_version_repo", None)
    if llm is None or repos is None or versions is None:
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="section regenerate is not configured",
        )
    return _RegenerateState(
        llm=llm,
        repos=repos,
        versions=versions,
        retriever=getattr(deps, "retriever", None),
    )


def _get_regenerate_service(request: Request) -> SectionRegenerateService:
    state = _resolve_regenerate_state(request)
    return SectionRegenerateService(
        RegenerateDeps(
            history=get_history_service(request),
            versions=state.versions,
            drafts=state.repos.drafts,
            research=state.repos.research,
            llm=state.llm,
            retriever=state.retriever,
        )
    )


__all__ = ["content_regenerate_router"]
```

`src/api/main.py`:
- import: `from src.api.routers.content_regenerate import content_regenerate_router` (next to the `content_router` import).
- after the `content_router` `include_router(...)` block:
```python
    app.include_router(
        content_regenerate_router,
        prefix=settings.api_v1_prefix,
        tags=["content"],
    )
```
No new `app.state` attribute — `content_service` and `content_repos` are already set at all three construction sites.

- [ ] **Step 4: Run — expect pass**

`COGNIFY_ANTHROPIC_API_KEY= uv run pytest tests/unit/api/test_content_regenerate_endpoint.py tests/unit/api/test_content_endpoints.py tests/unit/api/test_main.py -q -p no:cacheprovider` → all pass (**13 new**: 2 auth + 10 regenerate + 1 Literal). Route registered: `COGNIFY_ANTHROPIC_API_KEY= uv run python -c "from src.api.main import create_app; print([r.path for r in create_app().routes if 'regenerate' in r.path])"` → `['/api/v1/content/section-regenerate']`. `wc -l src/api/routers/content_regenerate.py` → **171** (measured after `ruff format`); AST check (same one-liner as Task 4) prints nothing — `section_regenerate` 12, `_command` 7, `_map_regenerate_error` 7, `_to_response` 15, `_resolve_regenerate_state` 18, `_get_regenerate_service` 12.

- [ ] **Step 5: Lint + commit**

`uv run ruff check --fix src/ tests/ && uv run ruff format src/ tests/ && uv run mypy src/ --ignore-missing-imports`
`git add src/api/routers/content_regenerate.py src/api/main.py tests/unit/api/test_content_regenerate_endpoint.py tests/unit/api/test_content_endpoints.py && git commit -m "feat(api): POST /content/section-regenerate (editor+, 10/min) via content_service.deps; L-013 round-trip tests (AUTHOR-004)"`

---

### Task 6: Frontend types, API client, shared `extractAnchorViolations`, `useSectionRegenerate`, `InlineProseEditor` slimming

**Files:**
- Modify: `frontend/src/types/content.ts`, `frontend/src/lib/api/content.ts`, `frontend/src/components/article/InlineProseEditor.tsx` (imports the two lifted helpers; local copies deleted)
- Create: `frontend/src/lib/api/anchorViolations.ts`, `frontend/src/lib/articles/locate-paragraph.ts`, `frontend/src/hooks/use-section-regenerate.ts`
- Test: `frontend/src/lib/api/content-regenerate.test.ts`, `frontend/src/lib/articles/locate-paragraph.test.ts`, `frontend/src/hooks/use-section-regenerate.test.tsx`; regression `frontend/src/components/article/InlineProseEditor.test.tsx`

**Interfaces:**
```ts
// types/content.ts
export type SectionUpdateSource = "manual" | "ai" | "tone_preset" | "restore" | "regenerate";
export interface SectionRegenerateRequest { article_id: string; section_index: number; instruction?: string | null }
export interface SectionRegenerateResponse { section_id: string; section_index: number; markdown: string; diff: WordDiffEntry[]; version_id: string; model: string; word_count: number; tokens_input: number | null; tokens_output: number | null; instruction: string | null }
// lib/api/content.ts
export async function regenerateSection(body: SectionRegenerateRequest): Promise<SectionRegenerateResponse>  // POST /content/section-regenerate
// lib/api/anchorViolations.ts
export function extractAnchorViolations(err: unknown): AnchorViolationEntry[]   // 422 → detail.violations, else []
// lib/articles/locate-paragraph.ts
export function locateParagraph(markdown: string, cursor: number): { paragraphIndex: number; paragraphMarkdown: string }
// hooks/use-section-regenerate.ts
export interface SectionRegenerateState { busy: boolean; error: string | null; violations: AnchorViolationEntry[]; result: SectionRegenerateResponse | null }
export function useSectionRegenerate(): SectionRegenerateState & { run: (body: SectionRegenerateRequest) => Promise<void>; reset: () => void }
```

- [ ] **Step 1: Write the failing tests**

`frontend/src/lib/api/content-regenerate.test.ts`:
```ts
import { describe, expect, it, vi, beforeEach } from "vitest";
import { apiClient } from "@/lib/api/client";
import { regenerateSection } from "@/lib/api/content";
import { extractAnchorViolations } from "@/lib/api/anchorViolations";

vi.mock("@/lib/api/client", () => ({
  apiClient: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}));

const RESPONSE = {
  section_id: "a:0",
  section_index: 0,
  markdown: "## H\n\nnew",
  diff: [],
  version_id: "v1",
  model: "claude",
  word_count: 1,
  tokens_input: 10,
  tokens_output: 5,
  instruction: "tighter",
};

describe("regenerateSection", () => {
  beforeEach(() => vi.clearAllMocks());

  it("POSTs to /content/section-regenerate and returns data", async () => {
    vi.mocked(apiClient.post).mockResolvedValue({ data: RESPONSE });
    const out = await regenerateSection({ article_id: "a", section_index: 0, instruction: "tighter" });
    expect(apiClient.post).toHaveBeenCalledWith("/content/section-regenerate", {
      article_id: "a",
      section_index: 0,
      instruction: "tighter",
    });
    expect(out).toEqual(RESPONSE);
  });
});

describe("extractAnchorViolations", () => {
  it("returns violations from a 422 detail payload", () => {
    const err = { response: { status: 422, data: { detail: { violations: [{ kind: "spec_id", value: "s", spec_id: "s", message: "m" }] } } } };
    expect(extractAnchorViolations(err)).toHaveLength(1);
  });
  it("returns [] for anything else", () => {
    expect(extractAnchorViolations({ response: { status: 500 } })).toEqual([]);
    expect(extractAnchorViolations(new Error("x"))).toEqual([]);
  });
});
```

`frontend/src/lib/articles/locate-paragraph.test.ts`:
```ts
import { describe, expect, it } from "vitest";
import { locateParagraph } from "./locate-paragraph";

describe("locateParagraph", () => {
  const md = "First para.\n\nSecond para.\n\nThird.";

  it("maps a cursor inside the second paragraph", () => {
    expect(locateParagraph(md, 15)).toEqual({ paragraphIndex: 1, paragraphMarkdown: "Second para." });
  });

  it("clamps a cursor past the end to the last paragraph", () => {
    expect(locateParagraph(md, 999)).toEqual({ paragraphIndex: 2, paragraphMarkdown: "Third." });
  });
});
```

`frontend/src/hooks/use-section-regenerate.test.tsx`:
```tsx
import { describe, expect, it, vi, beforeEach } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";
import { useSectionRegenerate } from "./use-section-regenerate";
import * as api from "@/lib/api/content";

vi.mock("@/lib/api/content", () => ({ regenerateSection: vi.fn() }));

const RESPONSE = {
  section_id: "a:0",
  section_index: 0,
  markdown: "## H\n\nnew text",
  diff: [{ kind: "replace" as const, before: "old", after: "new" }],
  version_id: "v1",
  model: "claude",
  word_count: 2,
  tokens_input: null,
  tokens_output: null,
  instruction: null,
};

describe("useSectionRegenerate", () => {
  beforeEach(() => vi.mocked(api.regenerateSection).mockReset());

  it("starts idle", () => {
    const { result } = renderHook(() => useSectionRegenerate());
    expect(result.current.busy).toBe(false);
    expect(result.current.result).toBeNull();
  });

  it("stores the result after run()", async () => {
    vi.mocked(api.regenerateSection).mockResolvedValue(RESPONSE);
    const { result } = renderHook(() => useSectionRegenerate());
    await act(async () => { await result.current.run({ article_id: "a", section_index: 0 }); });
    await waitFor(() => expect(result.current.result).toEqual(RESPONSE));
    expect(result.current.busy).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it("maps a 422 into violations and a generic error otherwise", async () => {
    vi.mocked(api.regenerateSection).mockRejectedValueOnce({
      response: { status: 422, data: { detail: { violations: [{ kind: "spec_id", value: "s", spec_id: "s", message: "dropped" }] } } },
    });
    const { result } = renderHook(() => useSectionRegenerate());
    await act(async () => { await result.current.run({ article_id: "a", section_index: 0 }); });
    expect(result.current.violations).toHaveLength(1);
    expect(result.current.error).toMatch(/anchor/i);

    vi.mocked(api.regenerateSection).mockRejectedValueOnce(new Error("boom"));
    await act(async () => { await result.current.run({ article_id: "a", section_index: 0 }); });
    expect(result.current.violations).toEqual([]);
    expect(result.current.error).toBe("boom");
  });

  it("reset() clears everything", async () => {
    vi.mocked(api.regenerateSection).mockResolvedValue(RESPONSE);
    const { result } = renderHook(() => useSectionRegenerate());
    await act(async () => { await result.current.run({ article_id: "a", section_index: 0 }); });
    act(() => result.current.reset());
    expect(result.current.result).toBeNull();
    expect(result.current.error).toBeNull();
  });
});
```

- [ ] **Step 2: Run — expect failure**

`cd frontend && npx vitest run src/lib/api/content-regenerate.test.ts src/lib/articles/locate-paragraph.test.ts src/hooks/use-section-regenerate.test.tsx` → module-not-found / `regenerateSection is not a function`.

- [ ] **Step 3: Implement**

`frontend/src/types/content.ts` — replace the `SectionUpdateSource` line and append after `SectionUpdateResponse`:
```ts
export type SectionUpdateSource =
  | "manual"
  | "ai"
  | "tone_preset"
  | "restore"
  | "regenerate";

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
```

`frontend/src/lib/api/content.ts` — extend the type import with `SectionRegenerateRequest, SectionRegenerateResponse` and add before `makeSectionId`:
```ts
/** AUTHOR-004 — redraft one section; returns a candidate + diff (body untouched). */
export async function regenerateSection(
  body: SectionRegenerateRequest,
): Promise<SectionRegenerateResponse> {
  const { data } = await apiClient.post<SectionRegenerateResponse>(
    "/content/section-regenerate",
    body,
  );
  return data;
}
```

Create `frontend/src/lib/api/anchorViolations.ts`:
```ts
import type { AnchorViolationEntry } from "@/types/content";

type AxiosLike = {
  response?: {
    status?: number;
    data?: { detail?: { violations?: AnchorViolationEntry[] } };
  };
};

/**
 * Parse the backend's 422 `{"error":"anchor_violation","violations":[…]}`
 * payload (built by `content_shared.anchor_violation_http`). Single source
 * of truth for the inline editor, the regenerate hook and the popover.
 */
export function extractAnchorViolations(err: unknown): AnchorViolationEntry[] {
  const e = err as AxiosLike;
  if (e?.response?.status !== 422) return [];
  return e.response.data?.detail?.violations ?? [];
}
```

Create `frontend/src/lib/articles/locate-paragraph.ts` (verbatim move from `InlineProseEditor.tsx`):
```ts
/** Map a textarea cursor offset to the `\n\n`-separated paragraph it sits in. */
export function locateParagraph(
  markdown: string,
  cursor: number,
): { paragraphIndex: number; paragraphMarkdown: string } {
  const paragraphs = markdown.split(/\n{2,}/);
  let traversed = 0;
  for (let i = 0; i < paragraphs.length; i++) {
    const len = paragraphs[i].length + 2; // 2 for the "\n\n" separator
    if (cursor <= traversed + len) {
      return { paragraphIndex: i, paragraphMarkdown: paragraphs[i] };
    }
    traversed += len;
  }
  const last = paragraphs.length - 1;
  return {
    paragraphIndex: Math.max(0, last),
    paragraphMarkdown: paragraphs[Math.max(0, last)] ?? "",
  };
}
```

`frontend/src/components/article/InlineProseEditor.tsx`:
1. Add imports `import { extractAnchorViolations } from "@/lib/api/anchorViolations";` and `import { locateParagraph } from "@/lib/articles/locate-paragraph";`.
2. In `handleSaveError`: `const violations = extractViolations(err);` → `const violations = extractAnchorViolations(err);`.
3. Delete the module-level `locateParagraph` and `extractViolations` functions (everything after the component's closing brace).
Expected: 224 → ≈ 189 lines; `InlineProseEditor.test.tsx` unchanged and green.

Create `frontend/src/hooks/use-section-regenerate.ts`:
```ts
import { useCallback, useState } from "react";
import { extractAnchorViolations } from "@/lib/api/anchorViolations";
import { regenerateSection } from "@/lib/api/content";
import type {
  AnchorViolationEntry,
  SectionRegenerateRequest,
  SectionRegenerateResponse,
} from "@/types/content";

export interface SectionRegenerateState {
  busy: boolean;
  error: string | null;
  violations: AnchorViolationEntry[];
  result: SectionRegenerateResponse | null;
}

const IDLE: SectionRegenerateState = {
  busy: false,
  error: null,
  violations: [],
  result: null,
};

function messageFor(err: unknown, violations: AnchorViolationEntry[]): string {
  if (violations.length > 0) {
    return `Regenerated text would drop ${violations.length} image anchor(s).`;
  }
  return err instanceof Error ? err.message : "Regenerate failed";
}

/** Local (non-cached) mutation state for one regenerate round-trip. */
export function useSectionRegenerate() {
  const [state, setState] = useState<SectionRegenerateState>(IDLE);

  const run = useCallback(async (body: SectionRegenerateRequest) => {
    setState({ ...IDLE, busy: true });
    try {
      const result = await regenerateSection(body);
      setState({ ...IDLE, result });
    } catch (err) {
      const violations = extractAnchorViolations(err);
      setState({ busy: false, result: null, violations, error: messageFor(err, violations) });
    }
  }, []);

  const reset = useCallback(() => setState(IDLE), []);

  return { ...state, run, reset };
}
```

- [ ] **Step 4: Run — expect pass**

`cd frontend && npx vitest run src/lib/api/content-regenerate.test.ts src/lib/articles/locate-paragraph.test.ts src/hooks/use-section-regenerate.test.tsx src/components/article/InlineProseEditor.test.tsx` → all pass (**9 new**: 3 client/violations + 2 locate + 4 hook). `npx tsc --noEmit` clean (the widened `SectionUpdateSource` is additive). `wc -l src/components/article/InlineProseEditor.tsx` < 200.

- [ ] **Step 5: Lint + commit**

`cd frontend && npx tsc --noEmit && npx eslint src`
`git add frontend/src/types/content.ts frontend/src/lib/api/content.ts frontend/src/lib/api/anchorViolations.ts frontend/src/lib/api/content-regenerate.test.ts frontend/src/lib/articles/locate-paragraph.ts frontend/src/lib/articles/locate-paragraph.test.ts frontend/src/components/article/InlineProseEditor.tsx frontend/src/hooks/use-section-regenerate.ts frontend/src/hooks/use-section-regenerate.test.tsx && git commit -m "feat(frontend): regenerateSection client + useSectionRegenerate hook + shared extractAnchorViolations/locateParagraph (AUTHOR-004)"`

---

### Task 7: Regenerate toolbar action + `RegeneratePopover` + page wiring (with file splits)

**Files:**
- Create: `frontend/src/components/article/RegeneratePopover.tsx` (+ `.test.tsx`), `frontend/src/components/article/SectionEditingWorkbench.tsx`, `frontend/src/lib/articles/bucket-visuals.ts` (+ `.test.ts`), `frontend/src/lib/articles/split-sections.ts` (+ `.test.ts`), `frontend/src/lib/articles/studio-sections.ts` (+ `.test.ts`), `frontend/src/components/articles/article-content-parts.tsx`, `frontend/src/components/articles/article-detail-toolbar.tsx`, `frontend/src/components/articles/article-not-found.tsx`, `frontend/src/hooks/use-article-actions.ts` (+ `.test.tsx`)
- Modify: `frontend/src/components/article/SectionContextToolbar.tsx` (+ `.test.tsx`), `frontend/src/components/article/SectionHistoryDrawer.tsx`, `frontend/src/components/articles/article-content.tsx` (+ `.test.tsx`), `frontend/src/app/(dashboard)/articles/[id]/page.tsx`

**Interfaces:**
```ts
// SectionContextToolbar
export interface SectionContextToolbarProps { …existing; onRegenerate: () => void }   // testid `toolbar-regenerate-${sectionIndex}`
// article-content.tsx
export interface SectionEditingProps { …existing; onRegenerate: (sectionIndex: number, sectionMarkdown: string) => void }
// lib/articles/split-sections.ts (moved out of article-content.tsx; shared with Visual Studio)
export function splitBySections(md: string): string[]
export function hasPreamble(segments: string[]): boolean
// lib/articles/studio-sections.ts
export interface StudioSection { section_index: number; title: string; body_markdown: string }
export function studioSectionsFrom(bodyMarkdown: string): StudioSection[]   // outline space; replaces page.tsx's `segments.slice(1)`
// components/articles/article-detail-toolbar.tsx
export function ArticleDetailToolbar({ studioOpen, onOpenGallery, onOpenImport, onToggleStudio })
// components/articles/article-not-found.tsx
export function ArticleNotFound()
// lib/articles/bucket-visuals.ts
export interface BucketedVisuals { overviewDiagrams: ImageAsset[]; sectionDiagrams: Map<number, ImageAsset[]>; coverImage: ImageAsset | null; sectionImages: Map<number, ImageAsset[]> }
export function isDiagramVisual(v: ImageAsset): boolean
export function sectionIndexOf(v: ImageAsset): number | null
export function bucketVisuals(visuals: ImageAsset[]): BucketedVisuals
// components/articles/article-content-parts.tsx
export function ArticleImage({ asset }: { asset: ImageAsset })
export function DiagramList({ diagrams }: { diagrams: ImageAsset[] })
export function ReferencesList({ citations }: { citations: Citation[] })
// RegeneratePopover
export interface RegeneratePopoverProps { articleId: string; sectionIndex: number; onAccepted: (newMarkdown: string, versionId: string) => void; onCancel: () => void; className?: string }
// SectionEditingWorkbench
export interface ActiveSection { index: number; sectionId: string; markdown: string; paragraphIndex?: number; paragraphMarkdown?: string }
export type WorkbenchPanel = "humanize" | "rewrite" | "refine" | "regenerate";
export interface SectionEditingWorkbenchProps { articleId: string; section: ActiveSection; defaultPersona: string | null; initialPanel: WorkbenchPanel | null; onChange: (next: ActiveSection | null) => void; onToast: (message: string) => void; onOpenHistory: (sectionId: string) => void; onPersisted: () => void }
// hooks/use-article-actions.ts
export interface ArticleActionsDeps { id: string; refetch: () => Promise<unknown>; showToast: (message: string, ms?: number) => void }
export type InsertableVisual = { spec: ImageSpec; render: RenderResponse };
export function useArticleActions(deps: ArticleActionsDeps): { insertVisuals: (v: InsertableVisual[]) => Promise<void>; publish: (platforms: string[]) => Promise<void> }
```

- [ ] **Step 1: Write the failing tests**

`frontend/src/components/article/SectionContextToolbar.test.tsx` — replace the file:
```tsx
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { SectionContextToolbar } from "./SectionContextToolbar";

describe("SectionContextToolbar", () => {
  function setup({ visible }: { visible: boolean }) {
    const onEditText = vi.fn();
    const onEditVisual = vi.fn();
    const onRefineLayout = vi.fn();
    const onRegenerate = vi.fn();
    render(
      <SectionContextToolbar
        sectionId="abc:1"
        sectionIndex={1}
        visible={visible}
        onEditText={onEditText}
        onEditVisual={onEditVisual}
        onRefineLayout={onRefineLayout}
        onRegenerate={onRegenerate}
      />,
    );
    return { onEditText, onEditVisual, onRefineLayout, onRegenerate };
  }

  it("renders dimmed-but-present when not hovered (affordance)", () => {
    setup({ visible: false });
    const toolbar = screen.getByRole("toolbar");
    expect(toolbar).toBeInTheDocument();
    expect(toolbar.className).toMatch(/opacity-30/);
  });

  it("renders all four actions when visible", () => {
    setup({ visible: true });
    expect(screen.getByTestId("toolbar-edit-text-1")).toBeInTheDocument();
    expect(screen.getByTestId("toolbar-edit-visual-1")).toBeInTheDocument();
    expect(screen.getByTestId("toolbar-refine-layout-1")).toBeInTheDocument();
    expect(screen.getByTestId("toolbar-regenerate-1")).toBeInTheDocument();
    expect(screen.getByRole("toolbar").className).toMatch(/opacity-100/);
  });

  it("fires the right callback when each button is clicked", () => {
    const { onEditText, onEditVisual, onRefineLayout, onRegenerate } = setup({ visible: true });
    fireEvent.click(screen.getByTestId("toolbar-edit-text-1"));
    fireEvent.click(screen.getByTestId("toolbar-edit-visual-1"));
    fireEvent.click(screen.getByTestId("toolbar-refine-layout-1"));
    fireEvent.click(screen.getByTestId("toolbar-regenerate-1"));
    expect(onEditText).toHaveBeenCalledTimes(1);
    expect(onEditVisual).toHaveBeenCalledTimes(1);
    expect(onRefineLayout).toHaveBeenCalledTimes(1);
    expect(onRegenerate).toHaveBeenCalledTimes(1);
  });
});
```

`frontend/src/components/article/RegeneratePopover.test.tsx`:
```tsx
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { RegeneratePopover } from "./RegeneratePopover";
import * as api from "@/lib/api/content";

vi.mock("@/lib/api/content", () => ({
  regenerateSection: vi.fn(),
  persistSectionUpdate: vi.fn(),
}));

const RESPONSE = {
  section_id: "art-1:1",
  section_index: 1,
  markdown: "## Second\n\nbrand new prose",
  diff: [
    { kind: "equal" as const, before: "## Second ", after: "## Second " },
    { kind: "replace" as const, before: "old prose", after: "brand new prose" },
  ],
  version_id: "cand-1",
  model: "claude",
  word_count: 3,
  tokens_input: 100,
  tokens_output: 40,
  instruction: "tighter",
};

function setup() {
  const onAccepted = vi.fn();
  const onCancel = vi.fn();
  render(<RegeneratePopover articleId="art-1" sectionIndex={1} onAccepted={onAccepted} onCancel={onCancel} />);
  return { onAccepted, onCancel };
}

describe("RegeneratePopover", () => {
  beforeEach(() => {
    vi.mocked(api.regenerateSection).mockReset();
    vi.mocked(api.persistSectionUpdate).mockReset();
  });

  it("runs with an optional instruction and shows the diff + word count", async () => {
    vi.mocked(api.regenerateSection).mockResolvedValue(RESPONSE);
    setup();
    fireEvent.change(screen.getByTestId("regenerate-instruction"), { target: { value: "tighter" } });
    fireEvent.click(screen.getByTestId("run-regenerate"));
    await waitFor(() => screen.getByTestId("word-diff-view"));
    expect(api.regenerateSection).toHaveBeenCalledWith({ article_id: "art-1", section_index: 1, instruction: "tighter" });
    expect(screen.getByTestId("regenerate-meta")).toHaveTextContent("3 words");
    expect(screen.getByTestId("accept-regenerate")).toBeInTheDocument();
    expect(screen.getByTestId("reject-regenerate")).toBeInTheDocument();
  });

  it("run button is enabled with an empty instruction", () => {
    setup();
    expect(screen.getByTestId("run-regenerate")).not.toBeDisabled();
  });

  it("accept persists via section-update with source=regenerate and the returned section_id", async () => {
    vi.mocked(api.regenerateSection).mockResolvedValue(RESPONSE);
    vi.mocked(api.persistSectionUpdate).mockResolvedValue({ section_id: "art-1:1", version_id: "applied-1", persisted_markdown: RESPONSE.markdown });
    const { onAccepted } = setup();
    fireEvent.click(screen.getByTestId("run-regenerate"));
    await waitFor(() => screen.getByTestId("accept-regenerate"));
    fireEvent.click(screen.getByTestId("accept-regenerate"));
    await waitFor(() => expect(onAccepted).toHaveBeenCalledWith(RESPONSE.markdown, "applied-1"));
    expect(api.persistSectionUpdate).toHaveBeenCalledWith({
      section_id: "art-1:1",
      markdown: RESPONSE.markdown,
      source: "regenerate",
      instruction: "tighter",
    });
  });

  it("reject clears the diff and keeps the popover open", async () => {
    vi.mocked(api.regenerateSection).mockResolvedValue(RESPONSE);
    const { onCancel } = setup();
    fireEvent.click(screen.getByTestId("run-regenerate"));
    await waitFor(() => screen.getByTestId("reject-regenerate"));
    fireEvent.click(screen.getByTestId("reject-regenerate"));
    expect(screen.queryByTestId("word-diff-view")).toBeNull();
    expect(screen.getByTestId("run-regenerate")).toBeInTheDocument();
    expect(onCancel).not.toHaveBeenCalled();
  });

  it("renders anchor violations from a 422", async () => {
    vi.mocked(api.regenerateSection).mockRejectedValue({
      response: { status: 422, data: { detail: { violations: [{ kind: "spec_id", value: "spec-a", spec_id: "spec-a", message: "dropped spec-a" }] } } },
    });
    setup();
    fireEvent.click(screen.getByTestId("run-regenerate"));
    await waitFor(() => screen.getByRole("alert"));
    expect(screen.getByTestId("regenerate-violations")).toHaveTextContent("dropped spec-a");
  });
});
```

`frontend/src/lib/articles/split-sections.test.ts`:
```ts
import { describe, expect, it } from "vitest";
import { hasPreamble, splitBySections } from "./split-sections";

describe("splitBySections / hasPreamble", () => {
  it("treats a body starting with ## as having no preamble", () => {
    const segs = splitBySections("## A\ntext\n\n## B\nmore");
    expect(segs).toHaveLength(2);
    expect(hasPreamble(segs)).toBe(false);
  });

  it("detects a prelude before the first H2", () => {
    const segs = splitBySections("Intro.\n\n## A\ntext");
    expect(segs).toHaveLength(2);
    expect(hasPreamble(segs)).toBe(true);
  });
});
```

`frontend/src/lib/articles/studio-sections.test.ts`:
```ts
import { describe, expect, it } from "vitest";
import { studioSectionsFrom } from "./studio-sections";

describe("studioSectionsFrom", () => {
  it("indexes the first H2 as 0 when there is no prelude (L-013)", () => {
    const out = studioSectionsFrom("## Alpha\none\n\n## Beta\ntwo");
    expect(out.map((s) => [s.section_index, s.title])).toEqual([
      [0, "Alpha"],
      [1, "Beta"],
    ]);
    expect(out[0].body_markdown).toMatch(/^## Alpha/);
  });

  it("skips the prelude and still starts at 0", () => {
    const out = studioSectionsFrom("Intro para.\n\n## Alpha\none");
    expect(out).toEqual([{ section_index: 0, title: "Alpha", body_markdown: "## Alpha\none" }]);
  });
});
```

`frontend/src/lib/articles/bucket-visuals.test.ts`:
```ts
import { describe, expect, it } from "vitest";
import type { ImageAsset } from "@/types/articles";
import { bucketVisuals } from "./bucket-visuals";

function asset(id: string, metadata: ImageAsset["metadata"]): ImageAsset {
  return { id, url: `https://x/${id}.png`, caption: null, altText: null, metadata };
}

describe("bucketVisuals", () => {
  it("first cover candidate wins; extra heroes are ignored", () => {
    const out = bucketVisuals([
      asset("h1", { placement_anchor: "cover", role_style: "hero" }),
      asset("h2", { role_style: "hero" }),
    ]);
    expect(out.coverImage?.id).toBe("h1");
    expect(out.sectionImages.size).toBe(0);
  });

  it("buckets images by section_index (planner) or source_section (legacy)", () => {
    const out = bucketVisuals([
      asset("a", { section_index: 1, role_style: "concept" }),
      asset("b", { source_section: 1 }),
      asset("c", { section_index: 0 }),
    ]);
    expect(out.sectionImages.get(1)?.map((v) => v.id)).toEqual(["a", "b"]);
    expect(out.sectionImages.get(0)?.map((v) => v.id)).toEqual(["c"]);
  });

  it("splits mermaid diagrams into overview (-1) and per-section buckets", () => {
    const out = bucketVisuals([
      asset("d0", { diagram_type: "flowchart", mermaid_syntax: "graph TD", section_index: -1 }),
      asset("d1", { diagram_type: "flowchart", mermaid_syntax: "graph TD", source_section: 2 }),
    ]);
    expect(out.overviewDiagrams.map((d) => d.id)).toEqual(["d0"]);
    expect(out.sectionDiagrams.get(2)?.map((d) => d.id)).toEqual(["d1"]);
  });
});
```

`frontend/src/hooks/use-article-actions.test.tsx`:
```tsx
import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as api from "@/lib/api/articles";
import { useArticleActions } from "./use-article-actions";

vi.mock("@/lib/api/articles", () => ({
  attachVisualToArticle: vi.fn(),
  publishArticle: vi.fn(),
}));

const SPEC = {
  id: "spec-1",
  role_style: "concept",
  alt_text: "alt",
  rationale: "why",
  placement: { anchor: "before_heading", section_index: 0 },
} as never;

describe("useArticleActions", () => {
  const refetch = vi.fn().mockResolvedValue(undefined);
  const showToast = vi.fn();

  beforeEach(() => {
    vi.mocked(api.attachVisualToArticle).mockReset();
    vi.mocked(api.publishArticle).mockReset();
    refetch.mockClear();
    showToast.mockClear();
  });

  it("insertVisuals attaches hosted renders, counts base64-only ones as failed, refetches, toasts", async () => {
    vi.mocked(api.attachVisualToArticle).mockResolvedValue({} as never);
    const { result } = renderHook(() => useArticleActions({ id: "art-1", refetch, showToast }));
    await act(async () => {
      await result.current.insertVisuals([
        { spec: SPEC, render: { image_url: "https://cdn/x.png", provider: "p", model: "m" } as never },
        { spec: SPEC, render: { image_url: null, image_base64: "abc" } as never },
      ]);
    });
    expect(api.attachVisualToArticle).toHaveBeenCalledTimes(1);
    expect(refetch).toHaveBeenCalledTimes(1);
    expect(showToast).toHaveBeenCalledWith("1 inserted · 1 failed (no hosted URL)", 6000);
  });

  it("publish reports one line per platform", async () => {
    vi.mocked(api.publishArticle)
      .mockResolvedValueOnce({ status: "success", external_url: "https://g/1" } as never)
      .mockRejectedValueOnce(new Error("down"));
    const { result } = renderHook(() => useArticleActions({ id: "art-1", refetch, showToast }));
    await act(async () => {
      await result.current.publish(["ghost", "medium"]);
    });
    expect(showToast).toHaveBeenCalledWith("ghost: published (https://g/1) | medium: request failed", 8000);
  });
});
```

Append to `frontend/src/components/articles/article-content.test.tsx` (inside the existing `describe`; add `fireEvent` to the `@testing-library/react` import):
```tsx
  it("mounts the toolbar per section and forwards onRegenerate with the 0-based index", () => {
    const onRegenerate = vi.fn();
    render(
      <ArticleContent
        bodyMarkdown={mockMarkdown}
        citations={[]}
        visuals={[]}
        editing={{
          articleId: "art-1",
          onEditText: vi.fn(),
          onEditVisual: vi.fn(),
          onRefineLayout: vi.fn(),
          onRegenerate,
        }}
      />,
    );
    fireEvent.click(screen.getByTestId("toolbar-regenerate-0"));
    expect(onRegenerate).toHaveBeenCalledWith(0, expect.stringMatching(/^## Introduction/));
    fireEvent.click(screen.getByTestId("toolbar-regenerate-1"));
    expect(onRegenerate).toHaveBeenLastCalledWith(1, expect.stringMatching(/^## Key Findings/));
  });
```

- [ ] **Step 2: Run — expect failure**

`cd frontend && npx vitest run src/components/article/SectionContextToolbar.test.tsx src/components/article/RegeneratePopover.test.tsx src/lib/articles/bucket-visuals.test.ts src/hooks/use-article-actions.test.tsx src/components/articles/article-content.test.tsx` → toolbar: `toolbar-regenerate-1` not found; popover / bucket / split-sections / studio-sections / actions: module not found; article-content: `toolbar-regenerate-0` not found. (Run the two new lib tests too: `npx vitest run src/lib/articles`.)

- [ ] **Step 3: Implement**

**3a. Toolbar** — `SectionContextToolbar.tsx`: import `RefreshCw` (`import { ImageIcon, LayoutPanelTop, Pencil, RefreshCw } from "lucide-react";`); add `onRegenerate: () => void;` to the props interface after `onRefineLayout`, destructure it, and add a fourth button after the Refine layout one:
```tsx
      <ToolbarButton
        icon={<RefreshCw className="h-3.5 w-3.5" />}
        label="Regenerate"
        onClick={onRegenerate}
        testId={`toolbar-regenerate-${sectionIndex}`}
      />
```
Update the doc comment: "Surfaces four actions …" and add `- **Regenerate** — redraft this section from the outline with an optional instruction; diff accept / reject (AUTHOR-004).`

**3b. History label** — `SectionHistoryDrawer.tsx` `labelForSource`: add `case "regenerate": return "Regenerated";` before `default`.

**3c. `RegeneratePopover.tsx`** (new):
```tsx
"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { persistSectionUpdate } from "@/lib/api/content";
import { useSectionRegenerate } from "@/hooks/use-section-regenerate";
import { WordDiffView } from "./WordDiffView";

/**
 * Regenerate-with-feedback popover (AUTHOR-004).
 *
 * Same anatomy as `AIRewritePopover` (header/Close, instruction textarea,
 * error alert, WordDiffView, Reject/Accept vs Run footer) but the
 * instruction is OPTIONAL and Accept persists immediately through
 * `/content/section-update` with `source: "regenerate"`, using the
 * `section_id` the regenerate response returned (outline space, L-013).
 */
export interface RegeneratePopoverProps {
  articleId: string;
  sectionIndex: number;
  onAccepted: (newMarkdown: string, versionId: string) => void;
  onCancel: () => void;
  className?: string;
}

const BUTTON_PRIMARY =
  "inline-flex items-center justify-center rounded-md bg-primary px-3 py-2 text-xs font-medium text-white hover:bg-primary/90 disabled:opacity-60";
const BUTTON_SECONDARY =
  "inline-flex items-center justify-center rounded-md bg-neutral-100 px-3 py-2 text-xs font-medium text-neutral-700 hover:bg-neutral-200";

export function RegeneratePopover({
  articleId,
  sectionIndex,
  onAccepted,
  onCancel,
  className,
}: RegeneratePopoverProps) {
  const [instruction, setInstruction] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const regen = useSectionRegenerate();

  async function handleRun() {
    setSaveError(null);
    await regen.run({
      article_id: articleId,
      section_index: sectionIndex,
      instruction: instruction.trim() || null,
    });
  }

  async function handleAccept() {
    if (!regen.result) return;
    setSaving(true);
    setSaveError(null);
    try {
      const saved = await persistSectionUpdate({
        section_id: regen.result.section_id,
        markdown: regen.result.markdown,
        source: "regenerate",
        instruction: regen.result.instruction ?? undefined,
      });
      onAccepted(saved.persisted_markdown, saved.version_id);
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  const error = saveError ?? regen.error;

  return (
    <section
      role="dialog"
      aria-label="Regenerate section popover"
      data-testid="regenerate-popover"
      className={cn(
        "z-30 flex w-[460px] flex-col gap-3 rounded-lg border border-neutral-200 bg-white p-4 shadow-lg",
        className,
      )}
    >
      <header className="flex items-center justify-between gap-3">
        <h3 className="font-heading text-sm font-semibold text-neutral-900">
          Regenerate section
        </h3>
        <button
          type="button"
          onClick={onCancel}
          className="text-xs font-medium text-neutral-500 hover:text-neutral-700"
        >
          Close
        </button>
      </header>

      <label className="flex flex-col gap-1">
        <span className="text-xs font-medium text-neutral-700">
          Instruction (optional)
        </span>
        <textarea
          value={instruction}
          onChange={(e) => setInstruction(e.target.value)}
          placeholder="e.g. open with a concrete incident, keep it under 250 words"
          rows={3}
          data-testid="regenerate-instruction"
          className="rounded-md border border-neutral-200 px-3 py-2 text-sm text-neutral-900 focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/30"
        />
      </label>

      {error ? (
        <p role="alert" className="text-xs text-error">
          {error}
        </p>
      ) : null}
      {regen.violations.length > 0 ? (
        <ul
          data-testid="regenerate-violations"
          className="list-disc space-y-1 rounded-md border border-error/40 bg-error-light p-3 pl-6 text-xs text-error"
        >
          {regen.violations.map((v) => (
            <li key={`${v.kind}-${v.value}`}>{v.message}</li>
          ))}
        </ul>
      ) : null}

      {regen.result ? (
        <>
          <p data-testid="regenerate-meta" className="text-xs text-neutral-500">
            {regen.result.word_count} words · {regen.result.model}
          </p>
          <WordDiffView ops={regen.result.diff} ariaLabel="Regenerate diff" />
        </>
      ) : null}

      <footer className="flex items-center justify-end gap-2 border-t border-neutral-100 pt-3">
        {regen.result ? (
          <>
            <button type="button" onClick={regen.reset} data-testid="reject-regenerate" className={BUTTON_SECONDARY}>
              Reject
            </button>
            <button type="button" onClick={handleAccept} disabled={saving} data-testid="accept-regenerate" className={BUTTON_PRIMARY}>
              {saving ? "Saving…" : "Accept"}
            </button>
          </>
        ) : (
          <button type="button" onClick={handleRun} disabled={regen.busy} data-testid="run-regenerate" className={BUTTON_PRIMARY}>
            {regen.busy ? "Regenerating…" : "Regenerate"}
          </button>
        )}
      </footer>
    </section>
  );
}
```

**3d. `frontend/src/lib/articles/bucket-visuals.ts`** (new — verbatim logic moved out of the `useMemo`, minus `segments`):
```ts
import type { ImageAsset } from "@/types/articles";

export interface BucketedVisuals {
  overviewDiagrams: ImageAsset[];
  sectionDiagrams: Map<number, ImageAsset[]>;
  coverImage: ImageAsset | null;
  sectionImages: Map<number, ImageAsset[]>;
}

export function isDiagramVisual(v: ImageAsset): boolean {
  return Boolean(v.metadata?.diagram_type && v.metadata?.mermaid_syntax);
}

/**
 * Section index for any visual: the planner stamps `section_index`,
 * legacy charts/diagrams use `source_section`. Read both.
 */
export function sectionIndexOf(v: ImageAsset): number | null {
  const meta = v.metadata ?? {};
  const raw = meta.section_index ?? meta.source_section;
  if (raw === undefined || raw === null) return null;
  const n = typeof raw === "number" ? raw : Number.parseInt(String(raw), 10);
  return Number.isFinite(n) ? n : null;
}

function push(map: Map<number, ImageAsset[]>, idx: number, asset: ImageAsset): void {
  const bucket = map.get(idx) ?? [];
  bucket.push(asset);
  map.set(idx, bucket);
}

/**
 * Bucket non-diagram images:
 *   * placement_anchor === "cover"  → article cover (rendered once at top)
 *   * else use section_index (new planner) OR source_section (legacy)
 *   * sections < 0 fall back to the cover slot
 * Only the FIRST cover-candidate wins — multiple heroes are not stacked.
 */
export function bucketVisuals(visuals: ImageAsset[]): BucketedVisuals {
  const diagrams = visuals.filter(isDiagramVisual);
  const images = visuals.filter((v) => !isDiagramVisual(v));
  const sectionDiagrams = new Map<number, ImageAsset[]>();
  for (const d of diagrams) {
    const idx = sectionIndexOf(d);
    if (idx !== null && idx >= 0) push(sectionDiagrams, idx, d);
  }
  let coverImage: ImageAsset | null = null;
  const sectionImages = new Map<number, ImageAsset[]>();
  for (const img of images) {
    const anchor = img.metadata?.placement_anchor;
    const role = img.metadata?.role_style;
    const idx = sectionIndexOf(img);
    const isCoverCandidate =
      anchor === "cover" || (anchor == null && idx == null && role === "hero");
    if (isCoverCandidate) {
      if (coverImage == null) coverImage = img; // first cover wins; ignore extra heroes
      continue;
    }
    if (idx !== null && idx >= 0) push(sectionImages, idx, img);
    else if (coverImage == null) coverImage = img; // unanchored non-hero — last-resort cover
  }
  return {
    overviewDiagrams: diagrams.filter((d) => sectionIndexOf(d) === -1),
    sectionDiagrams,
    coverImage,
    sectionImages,
  };
}
```

**3e. `frontend/src/components/articles/article-content-parts.tsx`** (new — verbatim moves):
```tsx
import type { Citation, ImageAsset } from "@/types/articles";
import { MermaidDiagram } from "./mermaid-diagram";

/**
 * Renders a non-diagram visual (chart, photo, illustration) inline.
 * Uses native <img> rather than next/image so MinIO/external URLs work
 * without a Next image-loader allowlist. The asset URL has already been
 * absolutified by the backend (see _to_image_response).
 */
export function ArticleImage({ asset }: { asset: ImageAsset }) {
  if (!asset.url) return null;
  return (
    <figure className="my-6">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={asset.url}
        alt={asset.altText ?? asset.caption ?? "Article visual"}
        className="w-full rounded-lg border border-neutral-200 shadow-sm"
        loading="lazy"
      />
      {asset.caption ? (
        <figcaption className="mt-2 text-center text-sm italic text-neutral-500">
          {asset.caption}
        </figcaption>
      ) : null}
    </figure>
  );
}

export function DiagramList({ diagrams }: { diagrams: ImageAsset[] }) {
  return (
    <>
      {diagrams.map((d) => (
        <MermaidDiagram
          key={d.id}
          syntax={d.metadata?.mermaid_syntax ?? ""}
          caption={d.caption}
          altText={d.altText}
          fallbackUrl={d.url}
        />
      ))}
    </>
  );
}

export function ReferencesList({ citations }: { citations: Citation[] }) {
  if (citations.length === 0) return null;
  return (
    <div className="mt-8 border-t border-neutral-200 pt-6" id="sources">
      <h3 className="font-heading text-base font-semibold text-neutral-900">
        References ({citations.length})
      </h3>
      <ol className="mt-3 space-y-2">
        {citations.map((citation) => (
          <li key={citation.index} id={`cite-${citation.index}`} className="text-sm scroll-mt-4">
            <span className="font-medium text-neutral-400">[{citation.index}]</span>{" "}
            <a
              href={citation.url}
              target="_blank"
              rel="noopener noreferrer"
              className="font-medium text-primary hover:underline"
            >
              {citation.title}
            </a>
            {citation.authors.length > 0 && (
              <span className="text-neutral-500"> — {citation.authors.join(", ")}</span>
            )}
          </li>
        ))}
      </ol>
    </div>
  );
}
```

**3f. `frontend/src/components/articles/article-content.tsx`** — replace the whole file:
```tsx
import { Fragment, useMemo, useState } from "react";
import Markdown from "react-markdown";
import rehypeRaw from "rehype-raw";
import type { Citation, ImageAsset } from "@/types/articles";
import { SectionContextToolbar } from "@/components/article/SectionContextToolbar";
import { bucketVisuals } from "@/lib/articles/bucket-visuals";
import { hasPreamble, splitBySections } from "@/lib/articles/split-sections";
import { ArticleImage, DiagramList, ReferencesList } from "./article-content-parts";

export interface SectionEditingProps {
  /** Article id for building stable section identifiers. */
  articleId: string;
  onEditText: (sectionIndex: number, sectionMarkdown: string) => void;
  onEditVisual: (sectionIndex: number) => void;
  onRefineLayout: (sectionIndex: number, sectionMarkdown: string) => void;
  /** AUTHOR-004 — redraft the section from the outline (0-based H2 index). */
  onRegenerate: (sectionIndex: number, sectionMarkdown: string) => void;
}

interface ArticleContentProps {
  bodyMarkdown: string;
  citations: Citation[];
  visuals: ImageAsset[];
  /** Optional per-section editing scaffolding (VISUAL-011 / Phase 8). */
  editing?: SectionEditingProps;
}

function stripReferencesSection(md: string): string {
  return md.split(/\n##\s+References\b/)[0].trimEnd();
}

// `sectionIdx` is the 0-based H2 (outline) index — the same space as
// section_drafts, ImagePlacement.section_index and the backend section_id
// (L-013); the preamble (if any) gets sectionIdx -1. `splitBySections` /
// `hasPreamble` live in lib/articles/split-sections.ts (shared with Visual Studio).

const PROSE_CLASS =
  "prose prose-neutral max-w-none prose-headings:font-heading prose-h2:mt-8 prose-h2:border-b prose-h2:border-neutral-200 prose-h2:pb-2 prose-h3:mt-6 prose-p:leading-7 prose-li:leading-7 prose-a:text-primary prose-a:no-underline hover:prose-a:underline";

export function ArticleContent({ bodyMarkdown, citations, visuals, editing }: ArticleContentProps) {
  const cleanMarkdown = useMemo(() => stripReferencesSection(bodyMarkdown), [bodyMarkdown]);
  const [hoveredSection, setHoveredSection] = useState<number | null>(null);
  const buckets = useMemo(() => bucketVisuals(visuals), [visuals]);
  const segments = useMemo(() => splitBySections(cleanMarkdown), [cleanMarkdown]);
  const sectionIdxOffset = hasPreamble(segments) ? 1 : 0;

  return (
    <div>
      {buckets.coverImage ? (
        <div className="mb-8">
          <ArticleImage asset={buckets.coverImage} />
        </div>
      ) : null}
      {buckets.overviewDiagrams.length > 0 ? (
        <div className="mb-8">
          <DiagramList diagrams={buckets.overviewDiagrams} />
        </div>
      ) : null}

      <div className={PROSE_CLASS}>
        {segments.map((segment, i) => {
          const sectionIdx = i - sectionIdxOffset;
          const showToolbar = editing !== undefined && sectionIdx >= 0;
          const isHovered = hoveredSection === sectionIdx;
          return (
            <Fragment key={`seg-${i}`}>
              <div
                className={
                  showToolbar
                    ? `relative -ml-3 rounded-md border-l-2 px-3 py-1 transition-colors ${
                        isHovered
                          ? "border-primary/60 bg-primary-light/30"
                          : "border-neutral-100 hover:border-neutral-300"
                      }`
                    : "relative"
                }
                data-section-index={sectionIdx}
                onMouseEnter={showToolbar ? () => setHoveredSection(sectionIdx) : undefined}
                onMouseLeave={
                  showToolbar
                    ? () => setHoveredSection((cur) => (cur === sectionIdx ? null : cur))
                    : undefined
                }
              >
                {showToolbar && editing ? (
                  <SectionContextToolbar
                    sectionId={`${editing.articleId}:${sectionIdx}`}
                    sectionIndex={sectionIdx}
                    visible={isHovered}
                    onEditText={() => editing.onEditText(sectionIdx, segment)}
                    onEditVisual={() => editing.onEditVisual(sectionIdx)}
                    onRefineLayout={() => editing.onRefineLayout(sectionIdx, segment)}
                    onRegenerate={() => editing.onRegenerate(sectionIdx, segment)}
                  />
                ) : null}
                <Markdown rehypePlugins={[rehypeRaw]}>{segment}</Markdown>
              </div>
              {sectionIdx >= 0 ? (
                <>
                  <DiagramList diagrams={buckets.sectionDiagrams.get(sectionIdx) ?? []} />
                  {(buckets.sectionImages.get(sectionIdx) ?? []).map((img) => (
                    <ArticleImage key={img.id} asset={img} />
                  ))}
                </>
              ) : null}
            </Fragment>
          );
        })}
      </div>

      <ReferencesList citations={citations} />
    </div>
  );
}
```
Expected ≈ 120 lines. Existing `article-content.test.tsx` assertions (cover, diagrams, references, toolbars) stay green — only the module boundaries moved.

**3f-bis. New lib + component files the page and the article column share:**

`frontend/src/lib/articles/split-sections.ts` (new, ≈ 17 lines — verbatim move):
```ts
/**
 * Shared H2 splitter for the article column and Visual Studio (L-013).
 *
 * `splitBySections` uses a lookahead, so when the markdown starts directly
 * with `## Heading` (the common case) segments[0] IS the first section, not
 * a preamble. Callers derive the 0-based H2 (outline) index as
 * `i - (hasPreamble(segments) ? 1 : 0)` — the same space as section_drafts,
 * ImagePlacement.section_index and the backend section_id.
 */
export function splitBySections(md: string): string[] {
  return md.split(/\n(?=##\s)/);
}

export function hasPreamble(segments: string[]): boolean {
  return !(segments[0]?.trimStart().startsWith("##") ?? false);
}
```

`frontend/src/lib/articles/studio-sections.ts` (new, ≈ 25 lines):
```ts
import { hasPreamble, splitBySections } from "./split-sections";

export interface StudioSection {
  section_index: number;
  title: string;
  body_markdown: string;
}

/**
 * Outline-space sections for `VisualStudio`. Replaces the page's old
 * `segments.slice(1)` which assumed a prelude and dropped the first section
 * of every no-prelude article (shifting `ImagePlacement.section_index` by one).
 */
export function studioSectionsFrom(bodyMarkdown: string): StudioSection[] {
  const segments = splitBySections(bodyMarkdown);
  const offset = hasPreamble(segments) ? 1 : 0;
  return segments.slice(offset).map((segment, i) => {
    const titleMatch = segment.match(/^##\s+(.+)/);
    return {
      section_index: i,
      title: titleMatch ? titleMatch[1].trim() : `Section ${i + 1}`,
      body_markdown: segment,
    };
  });
}
```

`frontend/src/components/articles/article-detail-toolbar.tsx` (new, ≈ 36 lines — verbatim move of the button row):
```tsx
export interface ArticleDetailToolbarProps {
  studioOpen: boolean;
  onOpenGallery: () => void;
  onOpenImport: () => void;
  onToggleStudio: () => void;
}

const SECONDARY_BUTTON =
  "rounded-md bg-neutral-100 px-3 py-1.5 text-xs font-medium text-neutral-700 hover:bg-neutral-200";

/** Saved visuals / Import image / Visual Studio toggle row above the article column. */
export function ArticleDetailToolbar({
  studioOpen,
  onOpenGallery,
  onOpenImport,
  onToggleStudio,
}: ArticleDetailToolbarProps) {
  return (
    <div className="mb-4 flex items-center justify-end gap-2">
      <button type="button" onClick={onOpenGallery} className={SECONDARY_BUTTON}>
        Saved visuals
      </button>
      <button type="button" onClick={onOpenImport} className={SECONDARY_BUTTON}>
        Import image
      </button>
      <button
        type="button"
        onClick={onToggleStudio}
        aria-pressed={studioOpen}
        className="rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-white hover:bg-primary/90"
      >
        {studioOpen ? "Hide Visual Studio" : "Open Visual Studio"}
      </button>
    </div>
  );
}
```

`frontend/src/components/articles/article-not-found.tsx` (new, ≈ 14 lines — verbatim move of `NotFound`):
```tsx
import Link from "next/link";
import { FileText } from "lucide-react";

export function ArticleNotFound() {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <FileText className="mb-4 h-12 w-12 text-neutral-300" />
      <h3 className="font-heading text-lg font-semibold text-neutral-700">Article not found</h3>
      <Link href="/articles" className="mt-4 text-sm font-medium text-primary hover:underline">
        &larr; Back to Articles
      </Link>
    </div>
  );
}
```

**3g. `frontend/src/components/article/SectionEditingWorkbench.tsx`** (new — the action row + editor + panels moved out of `page.tsx`, plus the Regenerate panel):
```tsx
"use client";

import { useState } from "react";
import { History, LayoutPanelTop, RefreshCw, Wand2 } from "lucide-react";
import { AIRewritePopover } from "./AIRewritePopover";
import { HumanizationDiffPanel } from "./HumanizationDiffPanel";
import { InlineProseEditor } from "./InlineProseEditor";
import { RegeneratePopover } from "./RegeneratePopover";
import { SectionHtmlRefinePanel } from "@/components/visuals/SectionHtmlRefinePanel";

export interface ActiveSection {
  /** 0-based H2 (outline) index — same space as the backend section_id (L-013). */
  index: number;
  sectionId: string;
  markdown: string;
  paragraphIndex?: number;
  paragraphMarkdown?: string;
}

export type WorkbenchPanel = "humanize" | "rewrite" | "refine" | "regenerate";

export interface SectionEditingWorkbenchProps {
  articleId: string;
  section: ActiveSection;
  defaultPersona: string | null;
  initialPanel: WorkbenchPanel | null;
  onChange: (next: ActiveSection | null) => void;
  onToast: (message: string) => void;
  onOpenHistory: (sectionId: string) => void;
  /** Called after any persisted write so the page can `refetch()`. */
  onPersisted: () => void;
}

const PILL =
  "inline-flex items-center gap-1 rounded-md bg-neutral-100 px-3 py-1.5 text-xs font-medium text-neutral-700 hover:bg-neutral-200";
const PRIMARY =
  "rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-white hover:bg-primary/90";

export function SectionEditingWorkbench({
  articleId,
  section,
  defaultPersona,
  initialPanel,
  onChange,
  onToast,
  onOpenHistory,
  onPersisted,
}: SectionEditingWorkbenchProps) {
  const [panel, setPanel] = useState<WorkbenchPanel | null>(initialPanel);
  const toggle = (p: WorkbenchPanel) => setPanel((cur) => (cur === p ? null : p));
  const stage = (md: string, msg: string) => {
    onChange({ ...section, markdown: md });
    setPanel(null);
    onToast(msg);
  };
  const close = () => {
    onChange(null);
    setPanel(null);
  };
  const persisted = (msg: string) => {
    onToast(msg);
    onPersisted();
    close();
  };

  return (
    <div className="mt-4 flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-end gap-2">
        <button type="button" onClick={() => toggle("humanize")} aria-pressed={panel === "humanize"} data-testid="open-humanize-panel" className={PILL}>
          <Wand2 className="h-3.5 w-3.5" />
          {panel === "humanize" ? "Hide humanizer" : "Humanize"}
        </button>
        <button type="button" onClick={() => toggle("rewrite")} aria-pressed={panel === "rewrite"} className={PRIMARY}>
          {panel === "rewrite" ? "Hide AI rewrite" : "Rewrite with AI"}
        </button>
        <button type="button" onClick={() => toggle("regenerate")} aria-pressed={panel === "regenerate"} data-testid="open-regenerate-panel" className={PILL}>
          <RefreshCw className="h-3.5 w-3.5" />
          {panel === "regenerate" ? "Hide regenerate" : "Regenerate"}
        </button>
        <button type="button" onClick={() => toggle("refine")} aria-pressed={panel === "refine"} className={PILL}>
          <LayoutPanelTop className="h-3.5 w-3.5" />
          {panel === "refine" ? "Hide refine" : "Refine layout"}
        </button>
        <button type="button" onClick={() => onOpenHistory(section.sectionId)} className={PILL}>
          <History className="h-3.5 w-3.5" /> History
        </button>
      </div>

      <InlineProseEditor
        key={section.sectionId}
        sectionId={section.sectionId}
        initialMarkdown={section.markdown}
        onCancel={close}
        onPersisted={(_md, vid) => persisted(`Section saved (version ${vid.slice(0, 8)})`)}
        onParagraphFocus={(paragraphIndex, paragraphMarkdown) =>
          onChange({ ...section, paragraphIndex, paragraphMarkdown })
        }
      />

      {panel === "humanize" ? (
        <HumanizationDiffPanel
          sectionId={section.sectionId}
          currentMarkdown={section.markdown}
          onAccept={(md) => stage(md, "Humanizer suggestion staged — review then save.")}
          onCancel={() => setPanel(null)}
        />
      ) : null}
      {panel === "rewrite" ? (
        <AIRewritePopover
          sectionId={section.sectionId}
          scope={section.paragraphIndex !== undefined ? "paragraph" : "section"}
          paragraphIndex={section.paragraphIndex}
          currentMarkdown={section.paragraphMarkdown ?? section.markdown}
          audiencePersona={defaultPersona}
          onAccept={(md, instr) => stage(md, `Rewrite ready — review then save (${instr.slice(0, 40)})`)}
          onCancel={() => setPanel(null)}
        />
      ) : null}
      {panel === "regenerate" ? (
        <RegeneratePopover
          articleId={articleId}
          sectionIndex={section.index}
          onAccepted={(_md, vid) => persisted(`Section regenerated (version ${vid.slice(0, 8)})`)}
          onCancel={() => setPanel(null)}
        />
      ) : null}
      {panel === "refine" ? (
        <SectionHtmlRefinePanel
          sectionId={section.sectionId}
          initialHtml={section.markdown}
          onApply={(md) => stage(md, "Refine result staged — review then save.")}
          onCancel={() => setPanel(null)}
        />
      ) : null}
    </div>
  );
}
```
Expected ≈ 165 lines.

**3h. `frontend/src/hooks/use-article-actions.ts`** (new — `handleInsertVisuals` + `handlePublish` moved out of `page.tsx`):
```ts
import { useCallback } from "react";
import { attachVisualToArticle, publishArticle } from "@/lib/api/articles";
import type { ImageSpec, RenderResponse } from "@/types/visuals";

export interface ArticleActionsDeps {
  id: string;
  refetch: () => Promise<unknown>;
  showToast: (message: string, ms?: number) => void;
}

export type InsertableVisual = { spec: ImageSpec; render: RenderResponse };

/** Side-effecting article actions lifted out of the detail page (AUTHOR-004 split). */
export function useArticleActions({ id, refetch, showToast }: ArticleActionsDeps) {
  const insertVisuals = useCallback(
    async (visuals: InsertableVisual[]) => {
      let attached = 0;
      let failed = 0;
      for (const v of visuals) {
        const url = v.render.image_url;
        // Only hosted URLs (MinIO/CDN) can be persisted. Base64 fallback
        // cannot be re-served from the article endpoint without first
        // uploading to object storage — count it as failed instead of
        // writing an unusable data: URL to the DB.
        if (!url) {
          failed += 1;
          continue;
        }
        try {
          await attachVisualToArticle(id, {
            url,
            alt_text: v.spec.alt_text,
            caption: v.spec.rationale ?? null,
            metadata: {
              spec_id: v.spec.id,
              provider: v.render.provider,
              model: v.render.model,
              section_index: v.spec.placement.section_index,
              role_style: v.spec.role_style,
            },
          });
          attached += 1;
        } catch {
          failed += 1;
        }
      }
      await refetch();
      const parts: string[] = [];
      if (attached > 0) parts.push(`${attached} inserted`);
      if (failed > 0) parts.push(`${failed} failed (no hosted URL)`);
      showToast(parts.join(" · ") || "Nothing to insert", 6000);
    },
    [id, refetch, showToast],
  );

  const publish = useCallback(
    async (platforms: string[]) => {
      const results: string[] = [];
      for (const platform of platforms) {
        try {
          const res = await publishArticle(id, platform);
          if (res.status === "success") {
            results.push(`${platform}: published${res.external_url ? ` (${res.external_url})` : ""}`);
          } else {
            results.push(`${platform}: ${res.error_message ?? "failed"}`);
          }
        } catch {
          results.push(`${platform}: request failed`);
        }
      }
      showToast(results.join(" | "), 8000);
    },
    [id, showToast],
  );

  return { insertVisuals, publish };
}
```

**3i. `frontend/src/app/(dashboard)/articles/[id]/page.tsx`** — replace the whole file (182 lines as written — count the block; there is no prettier in this repo, so what is written is what ships):
```tsx
"use client";

import { useCallback, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { Header } from "@/components/layout/header";
import {
  SectionEditingWorkbench,
  type ActiveSection,
  type WorkbenchPanel,
} from "@/components/article/SectionEditingWorkbench";
import { SectionHistoryDrawer } from "@/components/article/SectionHistoryDrawer";
import { ArticleContent } from "@/components/articles/article-content";
import { ArticleDetailToolbar } from "@/components/articles/article-detail-toolbar";
import { ArticleNotFound } from "@/components/articles/article-not-found";
import { ArticleSidebar } from "@/components/articles/article-sidebar";
import { PublishModal } from "@/components/articles/publish-modal";
import { ImageImportModal } from "@/components/visuals/ImageImportModal";
import { SavedAssetGallery } from "@/components/visuals/SavedAssetGallery";
import { VisualStudio } from "@/components/visuals/VisualStudio";
import { useArticle } from "@/hooks/use-article";
import { useArticleActions } from "@/hooks/use-article-actions";
import { useDefaultPersona } from "@/hooks/use-default-persona";
import { makeSectionId } from "@/lib/api/content";
import { studioSectionsFrom } from "@/lib/articles/studio-sections";

export default function ArticleDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { article, refetch } = useArticle(id);
  const [publishOpen, setPublishOpen] = useState(false);
  const [studioOpen, setStudioOpen] = useState(false);
  const [galleryOpen, setGalleryOpen] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const defaultPersona = useDefaultPersona();
  const [activeSection, setActiveSection] = useState<ActiveSection | null>(null);
  const [initialPanel, setInitialPanel] = useState<WorkbenchPanel | null>(null);
  const [historySectionId, setHistorySectionId] = useState<string | null>(null);
  const [focusVisualSection, setFocusVisualSection] = useState<number | null>(null);

  const showToast = useCallback((message: string, ms = 4000) => {
    setToast(message);
    setTimeout(() => setToast(null), ms);
  }, []);
  const { insertVisuals, publish } = useArticleActions({ id, refetch, showToast });
  const studioSections = useMemo(
    () => (article ? studioSectionsFrom(article.bodyMarkdown) : []),
    [article],
  );

  if (!article) return <ArticleNotFound />;

  const openSection = (sectionIndex: number, markdown: string, panel: WorkbenchPanel | null) => {
    setActiveSection({ index: sectionIndex, sectionId: makeSectionId(id, sectionIndex), markdown });
    setInitialPanel(panel);
  };

  return (
    <div className="space-y-6">
      <Link href="/articles" className="inline-flex items-center gap-1 text-sm text-neutral-500 hover:text-neutral-700">
        <ArrowLeft className="h-4 w-4" /> Back to Articles
      </Link>

      <Header title={article.title} subtitle={article.subtitle ?? ""}>
        <div className="flex items-center gap-2">
          {article.aiGenerated && (
            <span className="rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-medium text-amber-700">
              AI Generated
            </span>
          )}
          <span className="rounded-full bg-neutral-100 px-2.5 py-0.5 text-xs font-medium text-neutral-600">
            {article.contentType}
          </span>
        </div>
      </Header>

      <div className="flex gap-8">
        <div className="min-w-0 flex-[2]">
          <ArticleDetailToolbar
            studioOpen={studioOpen}
            onOpenGallery={() => setGalleryOpen(true)}
            onOpenImport={() => setImportOpen(true)}
            onToggleStudio={() => setStudioOpen((v) => !v)}
          />
          <ArticleContent
            bodyMarkdown={article.bodyMarkdown}
            citations={article.citations}
            visuals={article.visuals}
            editing={{
              articleId: id,
              onEditText: (i, md) => openSection(i, md, null),
              onEditVisual: (i) => {
                setStudioOpen(true);
                setFocusVisualSection(i);
              },
              onRefineLayout: (i, md) => openSection(i, md, "refine"),
              onRegenerate: (i, md) => openSection(i, md, "regenerate"),
            }}
          />
          {activeSection ? (
            <SectionEditingWorkbench
              key={`${activeSection.sectionId}-${initialPanel ?? "none"}`}
              articleId={id}
              section={activeSection}
              defaultPersona={defaultPersona}
              initialPanel={initialPanel}
              onChange={setActiveSection}
              onToast={showToast}
              onOpenHistory={setHistorySectionId}
              onPersisted={() => {
                void refetch();
              }}
            />
          ) : null}
        </div>
        {studioOpen ? (
          <div className="w-[560px] shrink-0">
            <VisualStudio
              article={{
                topic: {
                  title: article.title,
                  description: article.subtitle ?? article.summary,
                  domain: article.domain,
                },
                summary: article.summary,
                sections: studioSections,
              }}
              audiencePersona={defaultPersona}
              focusSectionIndex={focusVisualSection}
              onInsertIntoArticle={(visuals) => {
                void insertVisuals(visuals);
              }}
              onClose={() => {
                setStudioOpen(false);
                setFocusVisualSection(null);
              }}
            />
          </div>
        ) : (
          <div className="w-80 shrink-0">
            <ArticleSidebar article={article} onPublish={() => setPublishOpen(true)} />
          </div>
        )}
      </div>

      {historySectionId ? (
        <div className="fixed bottom-6 left-6 z-50">
          <SectionHistoryDrawer
            sectionId={historySectionId}
            open
            onClose={() => setHistorySectionId(null)}
            onRestored={(newMd, vid) => {
              setActiveSection((prev) =>
                prev && prev.sectionId === historySectionId ? { ...prev, markdown: newMd } : prev,
              );
              setHistorySectionId(null);
              showToast(`Restored to version ${vid.slice(0, 8)}`);
            }}
          />
        </div>
      ) : null}

      <PublishModal
        open={publishOpen}
        onClose={() => setPublishOpen(false)}
        onPublish={(platforms) => {
          setPublishOpen(false);
          void publish(platforms);
        }}
      />
      <SavedAssetGallery open={galleryOpen} onClose={() => setGalleryOpen(false)} />
      <ImageImportModal open={importOpen} onClose={() => setImportOpen(false)} onImported={() => setImportOpen(false)} />

      {toast && (
        <div role="status" className="fixed bottom-6 right-6 z-50 rounded-lg bg-neutral-900 px-4 py-3 text-sm text-white shadow-lg">
          {toast}
        </div>
      )}
    </div>
  );
}
```
Expected **182** lines. Behaviour preserved: `onEditText` opens the editor with no panel; `onRefineLayout` auto-opens the refine panel; `onRegenerate` auto-opens the new popover; the workbench's `key` remounts it when the section or the requested initial panel changes; `PublishModal.onPublish` still closes the modal first (it used to be the first line of `handlePublish`). If `PublishModal`'s `onPublish` prop type is `(platforms: string[]) => Promise<void>`, wrap as `async (platforms) => { setPublishOpen(false); await publish(platforms); }`.

- [ ] **Step 4: Run — expect pass + full frontend suite green**

`cd frontend && npx vitest run src/components/article src/components/articles src/lib/articles src/hooks` → all pass (**15 new** this task: popover 5, bucket 3, split-sections 2, studio-sections 2, actions 2, article-content +1; the toolbar file is rewritten with the same 3 cases). Then `npx vitest run` → 502 + 24 new (Tasks 6–7: 9 + 15) ≈ 526 passed, 0 failures — **record the actual number**. `wc -l "src/app/(dashboard)/articles/[id]/page.tsx" src/components/articles/article-content.tsx src/components/articles/article-content-parts.tsx src/components/articles/article-detail-toolbar.tsx src/components/articles/article-not-found.tsx src/lib/articles/bucket-visuals.ts src/lib/articles/split-sections.ts src/lib/articles/studio-sections.ts src/components/article/SectionEditingWorkbench.tsx src/components/article/RegeneratePopover.tsx src/components/article/InlineProseEditor.tsx src/hooks/use-article-actions.ts src/components/article/SectionContextToolbar.tsx src/components/article/SectionHistoryDrawer.tsx` → every one < 200 (182 / ≈ 120 / ≈ 75 / ≈ 36 / ≈ 14 / ≈ 70 / ≈ 17 / ≈ 25 / ≈ 165 / ≈ 165 / ≈ 189 / ≈ 75 / ≈ 105 / ≈ 189 — `page.tsx` is counted from the block above, the rest are estimates within ±5). `npm run build` succeeds.

- [ ] **Step 5: Lint + commit**

`cd frontend && npx tsc --noEmit && npx eslint src`
`git add frontend/src && git commit -m "feat(frontend): Regenerate toolbar action + RegeneratePopover (diff accept/reject); split page/article-content/workbench under 200 lines (AUTHOR-004)"`

---

### Task 8: Docs (L-013), boundary checks, full verification

**Files:**
- Modify: `project-management/PROGRESS.md`, `project-management/BACKLOG.md`, `CLAUDE.md`, `docs/LEARNINGS.md`, `frontend/DESIGN.md`, `docs/superpowers/plans/2026-08-19-epic-11-supervised-authoring-plan.md` (§9 AC tick), `docs/architecture/adrs/ADR-006-supervised-pipeline-events-and-outline-gate.md` (implementation note)
- Test: `tests/unit/test_boundaries_regenerate.py` (new, tiny)

- [ ] **Step 1: Boundary guard test (fails if someone imports the graph or publishing)**

`tests/unit/test_boundaries_regenerate.py`:
```python
"""AUTHOR-004 boundary guards: regenerate path is graph-free and publishing-free."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGEN_FILES = [
    ROOT / "src/agents/content/section_prompt.py",
    ROOT / "src/services/content/section_history_contracts.py",
    ROOT / "src/services/content/section_regenerate.py",
    ROOT / "src/services/content/section_regenerate_models.py",
    ROOT / "src/services/content/section_regenerate_text.py",
    ROOT / "src/api/routers/content_shared.py",
    ROOT / "src/api/routers/content_regenerate.py",
]


def test_regenerate_modules_do_not_import_langgraph_or_nodes() -> None:
    for path in REGEN_FILES:
        text = path.read_text(encoding="utf-8")
        assert "langgraph" not in text, path
        assert "agents.content.nodes" not in text, path
        assert "agents.content.pipeline" not in text, path


def test_regenerate_modules_do_not_import_publishing() -> None:
    for path in REGEN_FILES:
        assert "services.publishing" not in path.read_text(encoding="utf-8"), path
```
Run: `COGNIFY_ANTHROPIC_API_KEY= uv run pytest tests/unit/test_boundaries_regenerate.py -q -p no:cacheprovider` → `2 passed`.

- [x] **Step 2: Full suites** *(actual: 1632 backend / 532 frontend, 0 failures)*

`COGNIFY_ANTHROPIC_API_KEY= uv run pytest tests/unit/ -q -p no:cacheprovider` → 1557 (baseline on `develop` after AUTHOR-003) + 69 new (Tasks 1–5: 8 + 13 + 9 + 24 + 13, + 2 boundary) ≈ 1626 passed, 0 failed — **record the actual number from the run** in PROGRESS/CLAUDE.md (the 1 Pg integration test is not in this count). `cd frontend && npx vitest run` → 502 + 24 new ≈ 526 passed — **record the actual number**. `uv run ruff check src/ tests/ && uv run ruff format --check src/ tests/ && uv run mypy src/ --ignore-missing-imports` clean; `cd frontend && npx tsc --noEmit && npx eslint src && npm run build` clean. Line caps: `wc -l` on every file in the File map — every new file and every split file < 200; the five pre-existing over-cap files (`content.py`, `section_rewriter.py`, `main.py`, `services/content/__init__.py`, `db/repositories.py`) must not have grown except by the documented deltas. Function-length gate across everything new: `uv run python -c "import ast,sys;[print(p,f.name,f.end_lineno-f.lineno+1) for p in sys.argv[1:] for f in ast.walk(ast.parse(open(p).read())) if isinstance(f,(ast.FunctionDef,ast.AsyncFunctionDef)) and f.end_lineno-f.lineno+1>=20]" src/services/content/section_history.py src/services/content/section_history_contracts.py src/services/content/section_regenerate.py src/services/content/section_regenerate_models.py src/services/content/section_regenerate_text.py src/api/routers/content_shared.py src/api/routers/content_regenerate.py src/agents/content/section_prompt.py src/utils/llm_usage.py` → prints nothing. L-001 grep (`grep -rn "model_dump()" src/ | grep -v "mode="`) unchanged.

- [ ] **Step 3: Docs**

- `docs/LEARNINGS.md` — append (L-012 is already taken by briefs; this is **L-013**):
  ```markdown
  ---

  ## L-013: Two section-index spaces — outline (0-based H2) is the contract

  **Issue** (found in AUTHOR-004): `section_markdown.split_sections` ALWAYS returns the prelude as index 0 (empty string when the body starts with `## `), so the first H2 is markdown index 1. Everything else — `ArticleOutline.sections[].index`, `SectionDraft.section_index`, `ImagePlacement.section_index`, the frontend `sectionIdx` / `makeSectionId` — is 0-based over H2 sections. Until AUTHOR-004 the `/content/*` routes passed `{id}:{sectionIdx}` straight into `split_sections`, so every edit / AI rewrite / history / restore addressed the section *before* the one the user clicked, and `validate_anchors._check_headings` compared a markdown index against spec indices in outline space.

  **Rule**: the public `section_id` is `{article_id}:{outline_index}`. `src/services/content/section_history_contracts.md_index_for()` / `outline_index_for()` are the ONLY conversion; only `SectionHistoryService` (and the regenerate text helpers) call them, exactly where the body is read (`get_section`) or replaced (`replace_section`). `validate_anchors(section_index=…)` always receives the outline index. Never add `+1`/`-1` anywhere else (routers, services, frontend). On the frontend, derive indices only through `lib/articles/split-sections.ts` (`splitBySections` + `hasPreamble`) — `page.tsx`'s old `segments.slice(1)` assumed a prelude and shifted Visual Studio's `section_index` by one for every no-prelude article.

  **Grep check**:
  ```bash
  grep -rn "md_index_for\|outline_index_for\|section_index + 1\|section_index - 1\|sectionIdx + 1\|segments.slice(1)" src/ frontend/src | grep -v "section_history\|section_regenerate_text\|split-sections\|studio-sections"
  ```
  Any hit outside those modules is a bug.

  **Data already in the DB (pre-fix rows, no migration needed):** the frontend always sent outline-space ids, so `section_versions.section_id` / `section_index` are already correct and restore now lands on the intended H2. But rows with `source IN ('ai','tone_preset','humanize')` created before the fix through section-rewrite with `current_markdown=None` were generated from the PREVIOUS section's text, so restoring one writes section k-1's prose under section k's heading (only caught by the validator when a `before_heading` spec is bound); and bodies saved pre-fix had `replace_section(md k)` overwrite section k-1 with section k's edit, so duplicated-H2 bodies may exist. Audit: `SELECT id, section_id, source, created_at FROM section_versions WHERE source <> 'manual' AND created_at < '<deploy-date>';` and `SELECT id FROM canonical_articles WHERE body_markdown ~ '(## [^\n]+)\n[\s\S]*\1\n';`. `labelForSource` is intentionally NOT given a '(pre-L-013)' suffix — the drawer has no deploy date to compare against.

  **Related, NOT fixed here:** `CanonicalArticle.provenance.research_session_id` is the TOPIC id (`graph_state.build_initial_state` sets `state["session_id"] = topic.id`; `seo_node` copies it into provenance). Never key a lookup on it — AUTHOR-004 resolves context through `ArticleDraftRepository.find_by_article_id` + `draft.session_id`. AUTHOR-001's `articles.find_by_session` (`src/api/routers/session_events.py:72`) depends on the current value, so the source fix is a separate ticket. Regression tests: `tests/unit/services/content/test_section_history.py::TestOutlineIndexContract`, `tests/unit/api/test_content_regenerate_endpoint.py::TestRegenerate::test_round_trip_regenerate_then_accept_with_specs_on_k_and_k_plus_1` and `::test_dropping_section_k_heading_is_422_on_both_calls`.
  ```
- `CLAUDE.md`: Engineering Learnings list += `- **L-013**: Section ids are `{article_id}:{outline_index}` (0-based H2); `md_index_for()` in `section_history_contracts.py` is the only conversion to `split_sections` space — never add ±1 elsewhere`. Current Status: add AUTHOR-004 to the Epic 11 **Done** list ("per-section regenerate-with-feedback: `POST /content/section-regenerate` (one tracked LLM call, `llm_calls.call_name=section_regenerate`), candidate version row `source=regenerate`, accept via section-update; fixed the section-id off-by-one (L-013)"); refresh the test counts with the numbers recorded in Step 2; set **Next action** to AUTHOR-005 / INFRA-007.
- `project-management/PROGRESS.md` Epic 11 row: `AUTHOR-004 | Per-section regenerate | Done (branch feature/AUTHOR-004-section-regenerate, PR #__) | [plan](../docs/superpowers/plans/2026-08-21-author-004-section-regenerate.md) | program plan §5.5; review §6 #4` and add to the row's description: "**grew 3 → 5 SP**: the L-013 section-id fix (every existing edit/rewrite/history flow addressed the wrong section) was done at the root as Task 1". Resume note: next AUTHOR-005 (the `llm_calls` row `call_name="section_regenerate"` with `session_id = draft.session_id` — the REAL research-session id — is ready for the usage endpoint). **Follow-up tickets to open:** (1) `Provenance.research_session_id` is the topic id at the source (`graph_state.py:36` → `seo_node.py:69`); AUTHOR-001's `articles.find_by_session` (`session_events.py:72`) relies on the current value, so fixing it means touching both — separate ticket, referenced from L-013; (2) pre-L-013 `section_versions` rows / duplicated-H2 bodies — run the two audit queries from L-013 on the production DB once after deploy and record the result; (3) humanize pass on regenerated prose (AUTHOR-009); (4) `section_rewriter.py` / `content.py` / `db/repositories.py` still over 200 lines (INFRA-008). Add the test-count line.
- `project-management/BACKLOG.md` Epic 11 table: AUTHOR-004 `— **DONE** (`feature/AUTHOR-004-section-regenerate`, 2026-08-2_)`, **SP 3 → 5** (note "+2 SP: L-013 section-id contract fix, in scope"); summary row Done 5 / remaining SP −3 (the +2 is absorbed into the done column); velocity line += 5 SP.
- `frontend/DESIGN.md` → "Per-Section Context Toolbar" section: "three actions" → "four actions", add `- **Regenerate** (`RefreshCw`) — opens the `RegeneratePopover` (same anatomy as the AI rewrite popover; instruction optional; Accept persists through `/content/section-update` with `source="regenerate"`)`; in "Boundary invariants for prose editing → Section identifiers" add "`sectionIndex` is the 0-based H2 (outline) index — the backend uses the same space (L-013); never offset for the prelude."
- Program plan §9 Phase A AC: tick `- [x] Regenerate on a section returns a diff, preserves all data-spec-id anchors, appends a section_versions row with source=regenerate. *(AUTHOR-004; service + endpoint tests; accept adds a second, applied row via section-update; anchors carried by block position; L-013 section-id fix included)*`.
- ADR-006 "Implementation notes" addendum (3–5 lines): per-section regenerate is a graph-free re-entry via `draft_one_section`; no pipeline events are emitted (no AgentStep exists for an ad-hoc regenerate); cost IS captured — the service binds `current_session_id` / `current_step_name="section_regenerate"` so `TrackedChatModel` writes one `llm_calls` row per regenerate; v1 returns un-humanized prose by design (one LLM call; AUTHOR-009 owns per-pass humanize).

- [ ] **Step 4: Live smoke**

`docker compose up --build -d` (verify the frontend image timestamp advanced — cached Next builds silently ship stale code; use `--no-cache` for the frontend if the chunk hash did not change) → open an article → hover the **second** section → **Edit text** → the editor shows the second section's markdown (L-013 fix visible) → Cancel → hover a section → **Regenerate** → optional instruction → diff + "N words · model" meta shows → Accept → article re-renders with the new section, figure anchors intact, neighbouring sections untouched → History drawer on that section shows "Regenerated" twice (candidate + applied). Reject → nothing changes. `/pipeline-debug` for the article's session shows one `section_regenerate` LLM call. If the stack's Anthropic key is invalid, record the smoke as deferred in PROGRESS (same as AUTHOR-002 did).

- [x] **Step 5: Commit + hand off**

`git add project-management CLAUDE.md docs frontend/DESIGN.md tests/unit/test_boundaries_regenerate.py && git commit -m "docs(AUTHOR-004): progress/backlog (+2 SP), L-013 section-index contract, ADR-006 impl note, DESIGN toolbar, boundary guard"`
Then hand over to `superpowers:finishing-a-development-branch` (PR off `develop`, never stacked; PR body mentions the L-013 contract change so reviewers check any out-of-tree `section_id` consumers). Azure Boards: set the AUTHOR-004 work item to Closed (L-008: User Story → `Closed`) and bump its story points to 5.

---

## Self-review

**Spec coverage (program plan §5.5 / §6 / §7 / §9 AC):**
- `POST /content/section-regenerate` body `{article_id, section_index, instruction: str | None}` → Task 5 ✔ (`section_index` is the outline index; ambiguity #1 / L-013).
- "Loads the draft's outline + previous sections' markdown as context" → Task 4 `_outline_section` (`drafts.find_by_article_id(article.id)` → `draft.session_id`; provenance is the topic id and is never used) + `prior_drafts_from_body` (live sections, prose blocks only) ✔, tested by `test_context_uses_prior_live_sections_and_session_params`, `test_context_is_resolved_by_article_id_not_provenance`, `test_draft_without_article_id_is_missing_context`, the endpoint's `test_draft_keyed_only_by_provenance_is_409` and `test_prior_drafts_skip_a_leading_figure`.
- "runs `make_draft_node`'s per-section function for one section (extract `draft_one_section` … importable without the graph)" → Task 2 ✔ (signature `(section, queries, ctx) -> OneSectionDraft`, ambiguity #2; boundary guard in Task 8).
- "runs the anchor validator against the old section to preserve data-spec-ids" → Task 4 `carry_anchor_blocks` (positional, via `markdown_structure`) + `_validate` with the OUTLINE index ✔; endpoint round-trip with specs on k and k+1 ✔; 422 byte-identical to section-update asserted by `detail == detail` ✔.
- "writes a `section_versions` row with `source="regenerate"`" → Task 4 `_record` → shared `append_version_row` (with tokens) ✔ (+ Task 3 Literal so the accept path also records `regenerate`; ambiguities #3/#7).
- "returns `{markdown, diff}` using the existing `word_diff`" → Task 4 `diff_words` + Task 5 `WordDiffEntry.from_op` ✔; plus `word_count`, `tokens_input/output` (decisions B/E). Rate-limit 10/minute → Task 5 + 429 test ✔. Cost tracking → Task 4 `_draft` contextvars bound to `draft.session_id` (FK-valid) + `test_llm_call_is_tracked_under_section_regenerate_step` + `test_context_is_resolved_by_article_id_not_provenance` ✔ (decision B).
- §6 frontend: toolbar **Regenerate** (Task 7), instruction popover reusing AIRewritePopover layout + WordDiffView accept/reject (Task 7 `RegeneratePopover`), on accept calls existing section-update (Task 7, `persistSectionUpdate(source:"regenerate")`) ✔.
- §7 `test_section_regenerate.py` (anchor preservation) → Task 4 ✔. §9 AC ticked in Task 8 ✔.
- Decisions applied: A (Task 1 + L-013 + +2 SP), B (Task 4 `_draft`, `extract_usage` promoted in Task 2), C (Task 3 promotions, `content_shared.py`, `VersionRepoProtocol`, `extractAnchorViolations` shared in Task 6), D (Task 4 `carry_anchor_blocks` + `_prose_only`), E (ambiguity #8, `word_count` end-to-end, AUTHOR-009 follow-up in Task 8), F (Task 5 fixture + all listed cases), G (Task 3 `ContentService.deps` + `_get_content_llm(request)` + 2 tests; router reads `content_service.deps`; no new `app.state` attribute), H (Task 7 full code for every split file — `page.tsx` 182 counted, plus `split-sections` / `studio-sections` / `article-detail-toolbar` / `article-not-found`), I (Task 4: value objects in `section_regenerate_models.py`; `regenerate` 17 / `_prepare` 15 / `_outline_section` 14 / `_draft` 18 / `_validate` 14 / `_record` 17 lines AST-measured; files 177 / 91 / 161 after `ruff format`), J (counts per task: 8 / 13 / 9 / 24 / 13 / 9 / 15 / 2; Task 8 says "record the actual number").
- Out of scope, flagged: humanize pass on regenerated prose (AUTHOR-009); `section_rewriter.py` / `content.py` / `main.py` / `services/content/__init__.py` / `db/repositories.py` over 200 lines (INFRA-008); `Provenance.research_session_id` IS the topic id at the source (definite, verified) — this ticket routes around it via `find_by_article_id` and opens a follow-up (L-013 + PROGRESS); pre-L-013 rows audited by SQL, not migrated.

**Placeholder scan:** every Step 3 contains the code (Task 7 §3a/3b are one-line edits quoted in full; §3c–3i are complete files); no TBD/TODO. Test helpers referenced by path (`tests/unit/api/test_content_endpoints.py::_PRIV/_PUB/_FakeArticleRepo/_FakeVersionRepo/_build_article`, `tests/unit/api/conftest.py::make_auth_header`, `src/utils/llm_call_repo.InMemoryLlmCallRepository`). Every Python block in Tasks 1, 4 and 5 is already `ruff format` output with the repo config (line-length 88) and its file/function counts are measured, so there is no "if it goes over, move X" fallback left. The only conditional instruction is Task 7 §3i (`PublishModal.onPublish` is `(platforms: string[]) => void` in the repo today, so the sync form is what ships; the async wrapper is spelled out in case that type changes).

**Type consistency across tasks:** `section_id = make_section_id(article_id, outline_index)` (Task 1) is what `SectionHistoryService`, `SectionRegenerateService` (Task 4 `RegenerateResult.section_id`), `SectionRegenerateResponse.section_id` (Task 5), TS `SectionRegenerateResponse.section_id` (Task 6), `persistSectionUpdate({section_id})` (Task 7) and `makeSectionId` (frontend, unchanged) all produce/consume — outline space end-to-end, no arithmetic anywhere but `md_index_for`. `RegenerateResult` fields (`section_id, section_index, markdown, diff, version_id, model, word_count, tokens_input, tokens_output`) == `SectionRegenerateResponse` (+ `instruction`) == TS `SectionRegenerateResponse`. `source: "regenerate"` appears in the Python Literal (Task 3), the TS union (Task 6), the popover's accept call and the drawer label (Task 7), and both version-row assertions (Tasks 4/5). `validate_anchors(section_index=outline)` is called from exactly two places (`SectionHistoryService._ensure_anchors`, `SectionRegenerateService._validate`) with the same index. `DraftingContext.instruction: str | None` (Task 2) is set by `build_drafting_context` (Task 4). `OneSectionDraft.tokens_*` (Task 2) → version row + `RegenerateResult` (Task 4) → response (Task 5) → TS (Task 6). `WordDiffEntry {kind,before,after}` is the same shape on both sides. `VersionRepoProtocol.append` (Task 1) mirrors `PgSectionVersionRepository.append` / the `_FakeVersionRepo.append(**kwargs)` fakes, and is called from exactly one place (`append_version_row`), used by both `SectionHistoryService._persist_row` and `SectionRegenerateService._record`. `persist_section_update`'s six optional columns are typed by `VersionMeta` (PEP 692 `**meta`), so `content.py`'s existing keyword call compiles unchanged. `RegenerateInputs.draft.session_id` is the only session id the regenerate path ever uses (contextvar, `research.get`); `ArticleDraftRepository.find_by_article_id` exists on the Protocol, the in-memory repo and `PgArticleDraftRepository`.
