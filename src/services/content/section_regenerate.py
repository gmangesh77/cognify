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
        _log_started(prep)
        ctx = build_drafting_context(prep, self._deps)
        # draft.session_id is the FK-valid research session for llm_calls;
        # provenance.research_session_id holds the topic id (see module doc).
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


def _log_started(prep: RegenerateInputs) -> None:
    logger.info(
        "section_regenerate_started",
        article_id=str(prep.article.id),
        section_index=prep.cmd.section_index,
        session_id=str(prep.draft.session_id),
    )


def _log_recorded(row: VersionRow, version_id: UUID) -> None:
    logger.info(
        "section_regenerated",
        article_id=str(row.article_id),
        section_index=row.section_index,
        version_id=str(version_id),
    )


__all__ = ["SectionRegenerateService"]
