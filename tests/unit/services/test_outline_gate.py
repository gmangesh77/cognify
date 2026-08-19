"""Tests for OutlineGateService.

AUTHOR-002 (Task 3) — outline-only pipeline runs, outline validation /
update / regeneration, and generate-from-approved-outline.
"""

import json
from typing import Any
from uuid import uuid4

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.messages import BaseMessage
from pydantic import Field

from src.api.errors import NotFoundError
from src.models.content import CanonicalArticle
from src.models.content_pipeline import ArticleDraft, ArticleOutline, DraftStatus
from src.services.content import (
    ContentRepositories,
    ContentService,
    InMemoryArticleDraftRepository,
    InMemoryArticleRepository,
)
from src.services.content.outline_gate import OutlineGateService, validate_outline
from src.services.content_repositories import ContentDeps
from src.services.research import InMemoryResearchSessionRepository
from tests.unit.services.test_content_service import (
    _four_section_outline_json,
    _four_section_queries_json,
    _long_draft_text,
    _make_complete_session,
    _make_retriever_mock,
    _outline_json,
)


class _RecordingLLM(FakeListChatModel):
    """FakeListChatModel that records the messages passed to every call."""

    recorded_messages: list[list[BaseMessage]] = Field(default_factory=list)

    def _call(self, *args: Any, **kwargs: Any) -> str:  # noqa: ANN401
        if args:
            self.recorded_messages.append(args[0])
        return super()._call(*args, **kwargs)


async def _make_outline_gate(
    responses: list[str],
) -> tuple[OutlineGateService, ContentService, "object", Any]:
    session = _make_complete_session()
    session_repo = InMemoryResearchSessionRepository()
    await session_repo.create(session)
    llm = _RecordingLLM(responses=responses * 3)
    repos = ContentRepositories(
        drafts=InMemoryArticleDraftRepository(),
        research=session_repo,
        articles=InMemoryArticleRepository(),
    )
    deps = ContentDeps(llm=llm, retriever=_make_retriever_mock())
    content = ContentService(repos, deps)
    gate = OutlineGateService(content)
    return gate, content, session, llm


def _outline_only_responses() -> list[str]:
    """outline + queries — the pipeline stops right after queries."""
    queries_json = json.dumps([{"section_index": 0, "queries": ["q1"]}])
    return [_outline_json(), queries_json]


def _full_pipeline_responses() -> list[str]:
    draft_text = _long_draft_text()
    seo_json = json.dumps(
        {
            "title": "Test SEO Title for the Article",
            "description": (
                "A test description that is long enough to pass "
                "validation for the SEO metadata."
            ),
            "keywords": ["test", "seo", "ai"],
        }
    )
    discoverability_json = json.dumps(
        {
            "summary": "Test summary of the article content.",
            "key_claims": ["Key claim one [1]", "Key claim two [1]"],
        }
    )
    chart_json = json.dumps({"charts": []})
    diagram_json = json.dumps({"diagrams": []})
    return [
        _four_section_queries_json(),
        draft_text,
        draft_text,
        draft_text,
        draft_text,
        draft_text,  # redraft (validation)
        seo_json,
        discoverability_json,
        chart_json,
        diagram_json,
        "pad",
        "pad",
    ]


class TestGenerateOutlineOnly:
    async def test_stores_draft_with_outline_only(self) -> None:
        gate, _content, session, _llm = await _make_outline_gate(
            _outline_only_responses()
        )
        draft = await gate.generate_outline_only(session.id)
        assert isinstance(draft, ArticleDraft)
        assert draft.outline is not None
        assert draft.status == DraftStatus.OUTLINE_COMPLETE
        assert draft.section_drafts == []
        assert draft.session_id == session.id

    async def test_rejects_unknown_session(self) -> None:
        gate, _content, _session, _llm = await _make_outline_gate(
            _outline_only_responses()
        )
        with pytest.raises(NotFoundError):
            await gate.generate_outline_only(uuid4())


class TestGetOutline:
    async def test_returns_latest_draft(self) -> None:
        gate, _content, session, _llm = await _make_outline_gate(
            _outline_only_responses()
        )
        created = await gate.generate_outline_only(session.id)
        fetched = await gate.get_outline(session.id)
        assert fetched.id == created.id

    async def test_raises_when_no_draft(self) -> None:
        gate, _content, session, _llm = await _make_outline_gate(
            _outline_only_responses()
        )
        with pytest.raises(NotFoundError):
            await gate.get_outline(session.id)


def _outline_with_sections(sections: list[dict[str, object]]) -> ArticleOutline:
    return ArticleOutline.model_validate(
        {
            "title": "T",
            "content_type": "article",
            "sections": sections,
            "total_target_words": 1000,
            "reasoning": "r",
        }
    )


def _section(index: int, title: str) -> dict[str, object]:
    return {
        "index": index,
        "title": title,
        "description": "d",
        "key_points": ["p"],
        "target_word_count": 300,
        "relevant_facets": [0],
    }


class TestValidateOutline:
    def test_rejects_empty_sections(self) -> None:
        outline = _outline_with_sections([])
        with pytest.raises(ValueError, match="at least one section"):
            validate_outline(outline)

    def test_rejects_duplicate_titles_case_insensitive(self) -> None:
        outline = _outline_with_sections([_section(0, "Intro"), _section(1, "intro ")])
        with pytest.raises(ValueError, match="Duplicate"):
            validate_outline(outline)

    def test_rejects_empty_title(self) -> None:
        outline = _outline_with_sections([_section(0, "  ")])
        with pytest.raises(ValueError, match="empty title"):
            validate_outline(outline)

    def test_rejects_empty_outline_title(self) -> None:
        outline = _outline_with_sections([_section(0, "Intro")]).model_copy(
            update={"title": "   "}
        )
        with pytest.raises(ValueError, match="Outline title must not be empty"):
            validate_outline(outline)

    def test_renumbers_indices(self) -> None:
        outline = _outline_with_sections([_section(5, "First"), _section(9, "Second")])
        validated = validate_outline(outline)
        assert [s.index for s in validated.sections] == [0, 1]
        assert [s.title for s in validated.sections] == ["First", "Second"]


class TestUpdateOutline:
    async def test_persists_validated_outline(self) -> None:
        gate, _content, session, _llm = await _make_outline_gate(
            _outline_only_responses()
        )
        await gate.generate_outline_only(session.id)
        new_outline = _outline_with_sections(
            [_section(3, "New Section One"), _section(7, "New Section Two")]
        )
        updated = await gate.update_outline(session.id, new_outline)
        assert [s.title for s in updated.outline.sections] == [
            "New Section One",
            "New Section Two",
        ]
        assert [s.index for s in updated.outline.sections] == [0, 1]

    async def test_rejects_invalid_outline(self) -> None:
        gate, _content, session, _llm = await _make_outline_gate(
            _outline_only_responses()
        )
        await gate.generate_outline_only(session.id)
        bad_outline = _outline_with_sections([])
        with pytest.raises(ValueError):
            await gate.update_outline(session.id, bad_outline)

    async def test_raises_when_no_existing_draft(self) -> None:
        gate, _content, session, _llm = await _make_outline_gate(
            _outline_only_responses()
        )
        outline = _outline_with_sections([_section(0, "Only")])
        with pytest.raises(NotFoundError):
            await gate.update_outline(session.id, outline)


class TestRegenerateOutline:
    async def test_replaces_outline_on_latest_draft(self) -> None:
        gate, _content, session, llm = await _make_outline_gate(
            _outline_only_responses()
        )
        first = await gate.generate_outline_only(session.id)

        regen_responses = _outline_only_responses()
        llm.responses = regen_responses * 3
        llm.i = 0

        regenerated = await gate.regenerate_outline(session.id, "make it punchier")
        assert regenerated.id == first.id
        assert regenerated.outline is not None

    async def test_instruction_reaches_the_prompt(self) -> None:
        gate, _content, session, llm = await _make_outline_gate(
            _outline_only_responses()
        )
        await gate.generate_outline_only(session.id)

        regen_responses = _outline_only_responses()
        llm.responses = regen_responses * 3
        llm.i = 0
        llm.recorded_messages = []

        await gate.regenerate_outline(session.id, "make it punchier")
        all_text = "\n".join(
            str(m.content) for call in llm.recorded_messages for m in call
        )
        assert "make it punchier" in all_text

    async def test_creates_draft_when_none_exists(self) -> None:
        gate, _content, session, _llm = await _make_outline_gate(
            _outline_only_responses()
        )
        draft = await gate.regenerate_outline(session.id, None)
        assert draft.outline is not None
        assert draft.status == DraftStatus.OUTLINE_COMPLETE


class TestGenerateFromOutline:
    async def test_produces_canonical_article_matching_outline(self) -> None:
        responses = [
            _four_section_outline_json(),
            json.dumps([{"section_index": 0, "queries": ["q"]}]),
        ]
        gate, _content, session, llm = await _make_outline_gate(responses)
        draft = await gate.generate_outline_only(session.id)
        assert draft.outline is not None

        # Swap in full-pipeline responses (queries onward — the outline
        # prompt must NOT be called again since the outline is already set).
        llm.responses = _full_pipeline_responses() * 3
        llm.i = 0
        recorded_before = len(llm.recorded_messages)

        article = await gate.generate_from_outline(session.id)
        assert isinstance(article, CanonicalArticle)
        outline_titles = [s.title for s in draft.outline.sections]
        for title in outline_titles:
            assert f"## {title}" in article.body_markdown
        # No new outline-prompt call: queries is the first LLM call, so
        # exactly len(_full_pipeline_responses "used") calls happened,
        # none of them repeating the outline generation.
        assert len(llm.recorded_messages) > recorded_before

    async def test_rejects_unknown_session(self) -> None:
        gate, _content, _session, _llm = await _make_outline_gate(
            _outline_only_responses()
        )
        with pytest.raises(NotFoundError):
            await gate.generate_from_outline(uuid4())


class TestGraphDepsWithoutStepRepo:
    """Regression (AUTHOR-002 review fix): `ContentService._graph_deps()`
    used to return None whenever `step_repo` was unset, silently
    discarding `stop_after_outline` and running the full pipeline graph
    regardless -- which would have made the outline-review gate a no-op
    for any ContentService without a step repo (e.g. the in-memory
    `main.py` fallback branch)."""

    async def test_generate_outline_only_stops_after_queries(self) -> None:
        session = _make_complete_session()
        session_repo = InMemoryResearchSessionRepository()
        await session_repo.create(session)
        queries_json = json.dumps([{"section_index": 0, "queries": ["q1"]}])
        llm = _RecordingLLM(responses=[_outline_json(), queries_json])
        repos = ContentRepositories(
            drafts=InMemoryArticleDraftRepository(),
            research=session_repo,
            articles=InMemoryArticleRepository(),
        )
        deps = ContentDeps(llm=llm, retriever=_make_retriever_mock())
        content = ContentService(repos, deps)  # no step_repo, on purpose
        gate = OutlineGateService(content)

        draft = await gate.generate_outline_only(session.id)

        # Exactly outline + queries -- no drafting/SEO/chart/diagram calls.
        assert len(llm.recorded_messages) == 2
        assert draft.status == DraftStatus.OUTLINE_COMPLETE
        assert draft.section_drafts == []
        stored_article = await repos.articles.find_by_session(session.id)
        assert stored_article is None
