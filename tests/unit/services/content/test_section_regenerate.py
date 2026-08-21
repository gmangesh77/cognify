"""AUTHOR-004 — SectionRegenerateService: diff, anchor carry, version row, cost.

The harness mirrors production: `article.provenance.research_session_id` holds
the TOPIC id (graph_state stamps `state["session_id"] = topic.id`), while the
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
from src.utils.tracked_llm import (
    TrackedChatModel,
    current_session_id,
    current_step_name,
)

FIGURE = (
    '<figure class="cog-figure" data-spec-id="spec-a">'
    '<img src="x.png" alt="a" /></figure>'
)
FIGURE_B = (
    '<figure class="cog-figure" data-spec-id="spec-b">'
    '<img src="y.png" alt="b" /></figure>'
)

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

    async def update_body_markdown(
        self, article_id: UUID, body_markdown: str
    ) -> CanonicalArticle | None:
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

    async def list_for_section(
        self, *, article_id: UUID, section_id: str, limit: int = 50
    ) -> list[_Version]:
        return [r for r in self.rows if r.kwargs["section_id"] == section_id][:limit]

    async def get(self, version_id: UUID) -> _Version | None:
        return next((r for r in self.rows if r.id == version_id), None)


class _FakeResearch:
    """Only answers for the REAL session id — a provenance lookup gets None."""

    def __init__(self, session: ResearchSession) -> None:
        self.session = session

    async def get(self, session_id: UUID) -> ResearchSession | None:
        return self.session if session_id == self.session.id else None


def _section(index: int, title: str, key_points: list[str]) -> OutlineSection:
    return OutlineSection(
        index=index,
        title=title,
        description=f"d{index}",
        key_points=key_points,
        target_word_count=250,
        relevant_facets=[0],
    )


def _outline() -> ArticleOutline:
    return ArticleOutline(
        title="T",
        content_type=OutlineContentType.ARTICLE,
        sections=[
            _section(0, "First Section", ["k0"]),
            _section(1, "Second Section", ["k1", "k2"]),
        ],
        total_target_words=500,
        reasoning="r",
    )


def _spec(spec_id: str, heading: str, section_index: int) -> ImageSpec:
    return ImageSpec(
        id=spec_id,
        role_style="concept",
        prompt="p",
        placement=ImagePlacement(
            anchor="before_heading", heading_text=heading, section_index=section_index
        ),
    )


def _article(
    provenance_id: UUID, specs: list[ImageSpec] | None = None, body: str = BODY
) -> CanonicalArticle:
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
        provenance=Provenance(
            research_session_id=provenance_id,
            primary_model="m",
            drafting_model="m",
            embedding_model="e",
            embedding_version="v1",
        ),
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
        self.llm.ainvoke = AsyncMock(
            return_value=reply or AIMessage(content="Fresh prose [1] here.")
        )
        self.llm.model = "claude-test"
        self.session = ResearchSession(
            id=self.session_id,
            topic_id=self.topic_id,
            target_audience="CTOs",
            content_tone="direct",
            started_at=datetime.now(UTC),
        )
        self.with_draft = with_draft

    async def service(self) -> SectionRegenerateService:
        if self.with_draft:
            await self.drafts.create(
                ArticleDraft(
                    session_id=self.session_id,
                    topic_id=self.topic_id,
                    article_id=self.article.id,  # stamped by store_article in prod
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
    return RegenerateCommand(
        article_id=h.article.id, section_index=section_index, **extra
    )


# --- text helpers ------------------------------------------------------------


class TestCarryAnchorBlocks:
    def test_figure_first_stays_first(self) -> None:
        out = carry_anchor_blocks(f"{FIGURE}\n\nA.\n\nB.", "X.\n\nY.")
        assert out == f"{FIGURE}\n\nX.\n\nY."

    def test_figure_last_stays_last(self) -> None:
        out = carry_anchor_blocks(f"A.\n\nB.\n\n{FIGURE}", "X.\n\nY.")
        assert out == f"X.\n\nY.\n\n{FIGURE}"

    def test_middle_figure_lands_at_proportional_position(self) -> None:
        # old: A, FIGURE, B -> pos 1 of 3 (rel 0.5); new has 4 blocks -> slot 2
        out = carry_anchor_blocks(f"A.\n\n{FIGURE}\n\nB.", "W.\n\nX.\n\nY.\n\nZ.")
        assert out == f"W.\n\nX.\n\n{FIGURE}\n\nY.\n\nZ."

    def test_figure_sharing_a_paragraph_with_prose_does_not_duplicate_prose(
        self,
    ) -> None:
        out = carry_anchor_blocks(f"Some prose.\n{FIGURE}", "New para.")
        assert out == f"{FIGURE}\n\nNew para."
        assert "Some prose." not in out

    def test_two_figures_keep_their_order(self) -> None:
        out = carry_anchor_blocks(f"{FIGURE}\n\nA.\n\n{FIGURE_B}", "X.")
        assert out == f"{FIGURE}\n\nX.\n\n{FIGURE_B}"

    def test_block_with_two_figures_carries_only_the_missing_one(self) -> None:
        # Both figures share one block; the LLM reproduced spec-a only.
        out = carry_anchor_blocks(f"{FIGURE}\n{FIGURE_B}", f"new.\n\n{FIGURE}")
        assert out.count("spec-a") == 1
        assert out.count("spec-b") == 1

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
        body = (
            f"## First Section\n{FIGURE}\n\nReal prose first. More.\n\n"
            "## Second Section\nx\n"
        )
        prior = prior_drafts_from_body(body, section_index=1)
        assert prior[0].body_markdown.startswith("Real prose first.")

    def test_queries_for_uses_title_and_key_points(self) -> None:
        sq = queries_for(_outline().sections[1])
        assert sq.section_index == 1
        assert sq.queries == ["Second Section", "k1", "k2"]


# --- service -------------------------------------------------------------------


class TestRegenerate:
    @pytest.mark.asyncio
    async def test_returns_markdown_diff_and_word_count_without_touching_body(
        self,
    ) -> None:
        h = _Harness()
        svc = await h.service()
        res = await svc.regenerate(_cmd(h, 1))
        assert res.markdown.startswith("## Second Section\n\n")
        assert "Fresh prose" in res.markdown and "[1]" not in res.markdown
        assert any(op.kind != "equal" for op in res.diff)
        assert res.section_index == 1 and res.section_id == f"{h.article.id}:1"
        assert res.word_count == 4  # word count of the raw "Fresh prose [1] here."
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
        reply = AIMessage(
            content="Tight prose.",
            usage_metadata={
                "input_tokens": 90,
                "output_tokens": 30,
                "total_tokens": 120,
            },
        )
        h = _Harness(reply=reply)
        svc = await h.service()
        res = await svc.regenerate(
            _cmd(h, 1, instruction="tighter", created_by="user-1")
        )
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
    async def test_context_uses_prior_live_sections_and_session_params(
        self,
    ) -> None:
        h = _Harness()
        svc = await h.service()
        await svc.regenerate(_cmd(h, 1, instruction="add a stat"))
        system, human = h.llm.ainvoke.await_args.args[0]
        # audience/tone are only reachable via draft.session_id
        assert "Write for this audience: CTOs." in str(system.content)
        assert "Tone: direct." in str(system.content)
        assert "### Editor instruction\nadd a stat" in str(human.content)
        assert "- First Section: First section body." in str(human.content)

    @pytest.mark.asyncio
    async def test_llm_call_is_tracked_under_section_regenerate_step(self) -> None:
        calls = InMemoryLlmCallRepository()
        h = _Harness()
        h.llm = TrackedChatModel(
            inner=FakeListChatModel(responses=["Tracked prose."]), repo=calls
        )
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
        # production shape: provenance holds the topic id, not the session id
        assert h.article.provenance.research_session_id == h.topic_id != h.session_id
        h.llm = TrackedChatModel(
            inner=FakeListChatModel(responses=["Prose."]), repo=calls
        )
        svc = await h.service()
        await svc.regenerate(_cmd(h, 1))
        rows = await calls.list_by_session(h.session_id)
        assert len(rows) == 1 and rows[0].session_id == h.session_id  # FK-valid
        assert await calls.list_by_session(h.topic_id) == []  # nothing on provenance

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
        # An outline-only draft (never finalised) has no article_id -> 409.
        h = _Harness(with_draft=False)
        await h.drafts.create(
            ArticleDraft(
                session_id=h.session_id,
                topic_id=h.topic_id,
                outline=_outline(),
                created_at=datetime.now(UTC),
            )
        )
        svc = await h.service()
        with pytest.raises(DraftContextMissingError):
            await svc.regenerate(_cmd(h, 0))

    @pytest.mark.asyncio
    async def test_heading_anchor_violation_raises_and_records_nothing(self) -> None:
        # A before_heading spec bound to a heading the article no longer has.
        h = _Harness(specs=[_spec("spec-h", "Renamed Heading", 1)])
        svc = await h.service()
        with pytest.raises(AnchorViolationError) as exc:
            await svc.regenerate(_cmd(h, 1))
        assert exc.value.violations[0].kind == "heading_text"
        assert h.versions.rows == []

    @pytest.mark.asyncio
    async def test_spec_on_neighbouring_section_is_not_checked(self) -> None:
        # Spec bound to outline section 0 must not block regenerating section 1.
        h = _Harness(specs=[_spec("spec-n", "Gone Heading", 0)])
        svc = await h.service()
        res = await svc.regenerate(_cmd(h, 1))
        assert res.section_index == 1
