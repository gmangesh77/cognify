"""OutlineGateService — outline-first review gate for the content pipeline.

Lets an editor review and adjust the LLM-generated outline before
section drafting runs, using `ContentGraphDeps.stop_after_outline` to
end the graph right after `generate_queries` (Task 1, AUTHOR-002).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

import structlog

from src.agents.content.pipeline import build_content_graph
from src.api.errors import NotFoundError
from src.models.content import CanonicalArticle
from src.models.content_pipeline import ArticleDraft, ArticleOutline, DraftStatus
from src.services.content.graph_state import build_initial_state
from src.services.content.persist import PersistContext, persist_pipeline_result

if TYPE_CHECKING:
    from src.models.research_db import ResearchSession
    from src.services.content import ContentService

logger = structlog.get_logger()


class OutlineGateService:
    """Outline-only pipeline runs plus the outline review/approval workflow."""

    def __init__(self, content: ContentService) -> None:
        self._content = content

    async def generate_outline_only(self, session_id: UUID) -> ArticleDraft:
        """Run the pipeline up to (and including) outline generation."""
        session, state = await self._prepare_run(session_id)
        result = await self._run_graph(session_id, state, stop_after_outline=True)
        outline = self._require_outline(result)
        return await self._create_outline_draft(session, outline)

    async def get_outline(self, session_id: UUID) -> ArticleDraft:
        """Return the latest ArticleDraft for a session."""
        draft = await self._content._repos.drafts.find_latest_by_session(session_id)
        if draft is None:
            raise NotFoundError(f"No draft found for session {session_id}")
        return draft

    async def update_outline(
        self, session_id: UUID, outline: ArticleOutline
    ) -> ArticleDraft:
        """Validate an editor-supplied outline and persist it."""
        validated = validate_outline(outline)
        draft = await self.get_outline(session_id)
        updated = draft.model_copy(update={"outline": validated})
        return await self._content._repos.drafts.update(updated)

    async def regenerate_outline(
        self, session_id: UUID, instruction: str | None
    ) -> ArticleDraft:
        """Re-run outline generation with editorial `instruction`."""
        session, state = await self._prepare_run(session_id)
        state["outline_instruction"] = instruction
        result = await self._run_graph(session_id, state, stop_after_outline=True)
        outline = self._require_outline(result)
        return await self._replace_latest_outline(session, outline)

    async def generate_from_outline(self, session_id: UUID) -> CanonicalArticle:
        """Resume the full pipeline from an already-approved outline."""
        draft = await self.get_outline(session_id)
        session, state = await self._prepare_run(session_id)
        state["outline"] = draft.outline
        state["status"] = "outline_complete"
        result = await self._run_graph(session_id, state, stop_after_outline=False)
        ctx = PersistContext(
            repos=self._content._repos, settings=self._content._deps.settings
        )
        return await persist_pipeline_result(ctx, session, result)

    async def _prepare_run(
        self, session_id: UUID
    ) -> tuple[ResearchSession, dict[str, object]]:
        session = await self._content._load_session(session_id)
        findings = self._content._reconstruct_findings(session)
        topic = self._content._build_topic_input(session)
        state = build_initial_state(session, topic, findings)
        return session, state

    async def _run_graph(
        self,
        session_id: UUID,
        state: dict[str, object],
        *,
        stop_after_outline: bool,
    ) -> dict[str, object]:
        deps = self._content._graph_deps(
            session_id, stop_after_outline=stop_after_outline
        )
        graph = build_content_graph(
            self._content._require_llm(),
            self._content._deps.retriever,
            self._content._deps.settings,
            deps=deps,
        )
        result: dict[str, object] = await graph.ainvoke(state)
        return result

    @staticmethod
    def _require_outline(result: dict[str, object]) -> ArticleOutline:
        outline = result.get("outline")
        if outline is None:
            raise ValueError(result.get("error") or "Outline generation failed")
        if not isinstance(outline, ArticleOutline):
            outline = ArticleOutline.model_validate(outline)
        return outline

    async def _create_outline_draft(
        self, session: ResearchSession, outline: ArticleOutline
    ) -> ArticleDraft:
        draft = ArticleDraft(
            session_id=session.id,
            topic_id=session.topic_id,
            outline=outline,
            status=DraftStatus.OUTLINE_COMPLETE,
            created_at=datetime.now(UTC),
        )
        created = await self._content._repos.drafts.create(draft)
        logger.info(
            "outline_only_draft_created",
            draft_id=str(created.id),
            session_id=str(session.id),
        )
        return created

    async def _replace_latest_outline(
        self, session: ResearchSession, outline: ArticleOutline
    ) -> ArticleDraft:
        latest = await self._content._repos.drafts.find_latest_by_session(session.id)
        if latest is None:
            return await self._create_outline_draft(session, outline)
        updated = latest.model_copy(update={"outline": outline})
        return await self._content._repos.drafts.update(updated)


def validate_outline(outline: ArticleOutline) -> ArticleOutline:
    """Validate editor-supplied outline shape; renumber section indices.

    Raises `ValueError` (message = "; ".join of all violations found) if
    the outline itself has an empty title, has no sections, has a section
    with an empty title, or has duplicate section titles (case-insensitive,
    whitespace-stripped).
    """
    messages = _outline_validation_messages(outline)
    if messages:
        raise ValueError("; ".join(messages))
    return _renumber_sections(outline)


def _outline_validation_messages(outline: ArticleOutline) -> list[str]:
    messages: list[str] = []
    if not outline.title.strip():
        messages.append("Outline title must not be empty")
    if not outline.sections:
        messages.append("Outline must have at least one section")
        return messages
    seen: set[str] = set()
    for i, section in enumerate(outline.sections):
        title = section.title.strip()
        if not title:
            messages.append(f"Section {i} has an empty title")
            continue
        key = title.lower()
        if key in seen:
            messages.append(f"Duplicate section title: {section.title!r}")
        seen.add(key)
    return messages


def _renumber_sections(outline: ArticleOutline) -> ArticleOutline:
    """Renumber indices and recompute the total from section budgets.

    AUTHOR-008: editors add/delete sections without touching
    `total_target_words`, and the validate node's expansion floor derives
    from it — so the save path is the single place it is recomputed.
    """
    renumbered = [
        s.model_copy(update={"index": i}) for i, s in enumerate(outline.sections)
    ]
    total = sum(s.target_word_count for s in renumbered)
    return outline.model_copy(
        update={"sections": renumbered, "total_target_words": total}
    )
