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
